#!/usr/bin/env python3
"""Croustille driver — launches the dev server and drives the page in a locally
spawned headless Chrome over CDP.

Why not the claude-in-chrome MCP tools: the user's Chrome window is normally
occluded by other windows, and an occluded Chrome reports
document.visibilityState === "hidden", in which state it PAUSES
requestAnimationFrame and refuses to load media entirely. Videos sit at
readyState 0 forever and the scroll-driven reel never advances. Every
measurement taken that way is a false negative that looks exactly like broken
code. A headless Chrome we launch ourselves considers itself visible.

Usage (paths relative to the repo root):

  python3 .claude/skills/run-croustille/driver.py up
  python3 .claude/skills/run-croustille/driver.py tour
  python3 .claude/skills/run-croustille/driver.py nav
  python3 .claude/skills/run-croustille/driver.py mobile
  python3 .claude/skills/run-croustille/driver.py frame '#reelVideo' 1.0 5.0
  python3 .claude/skills/run-croustille/driver.py mark  '#reelVideo'
  python3 .claude/skills/run-croustille/driver.py down

Every command that needs the server starts it on demand; `down` stops it.
Screenshots land in $TMPDIR/croustille-shots (absolute paths are printed).
"""

import asyncio
import base64
import json
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

try:
    import websockets
except ImportError:
    sys.exit("missing dependency: pip3 install --user websockets")

REPO = pathlib.Path(__file__).resolve().parents[3]
PORT = 8900
BASE = "http://localhost:%d/" % PORT
CDP_PORT = 9377
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PIDFILE = pathlib.Path(tempfile.gettempdir()) / "croustille-dev-server.pid"
OUTDIR = pathlib.Path(os.environ.get("CROUSTILLE_OUT",
                                     pathlib.Path(tempfile.gettempdir()) / "croustille-shots"))


# ───────────────────────────── dev server ─────────────────────────────

def listening(port):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def server_up():
    """Start serve.py unless something is already on the port.

    serve.py, not `python3 -m http.server`: the stdlib server ignores HTTP
    Range requests, and Chrome's media loader opens a video with
    `Range: bytes=0-`. It gets a plain 200 with no Accept-Ranges back and
    stalls — the video never starts and never reports an error either.
    """
    if listening(PORT):
        print("dev server already up on %d" % PORT)
        return
    proc = subprocess.Popen(
        [sys.executable, "serve.py", "--quiet"],
        cwd=str(REPO), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    for _ in range(60):
        if listening(PORT):
            PIDFILE.write_text(str(proc.pid))
            print("dev server started (pid %d) -> %s" % (proc.pid, BASE))
            return
        time.sleep(0.2)
    proc.kill()
    sys.exit("dev server failed to come up on %d" % PORT)


def server_down():
    if PIDFILE.exists():
        pid = int(PIDFILE.read_text().strip())
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            print("stopped dev server (pid %d)" % pid)
        except (ProcessLookupError, PermissionError):
            print("dev server pid %d already gone" % pid)
        PIDFILE.unlink()
    elif listening(PORT):
        print("something is on %d but this driver did not start it; leaving it alone" % PORT)
    else:
        print("dev server not running")


# ───────────────────────────── chrome + CDP ─────────────────────────────

class Chrome:
    """Headless Chrome on a throwaway profile, torn down on exit."""

    def __init__(self, width=1440, height=900, reduced_motion=False):
        self.width, self.height = width, height
        self.reduced_motion = reduced_motion
        self.profile = None
        self.proc = None

    def __enter__(self):
        if not os.path.exists(CHROME):
            sys.exit("Chrome not found at %s" % CHROME)
        self.profile = tempfile.mkdtemp(prefix="croustille-chrome-")
        argv = [
            CHROME, "--headless=new",
            "--remote-debugging-port=%d" % CDP_PORT,
            "--user-data-dir=%s" % self.profile,     # never the real profile
            "--window-size=%d,%d" % (self.width, self.height),
            "--autoplay-policy=no-user-gesture-required",  # or the hero video never starts
            "--hide-scrollbars",
            "--no-first-run", "--no-default-browser-check",
        ]
        if self.reduced_motion:
            argv.append("--force-prefers-reduced-motion")
        self.proc = subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        for _ in range(80):
            try:
                urllib.request.urlopen(
                    "http://127.0.0.1:%d/json/version" % CDP_PORT, timeout=0.5).read()
                return self
            except (urllib.error.URLError, OSError):
                time.sleep(0.25)
        self.__exit__(None, None, None)
        sys.exit("Chrome CDP endpoint never came up on %d" % CDP_PORT)

    def __exit__(self, *exc):
        if self.proc:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                pass
        if self.profile:
            # Chrome writes on the way out; a single rmtree can lose the race.
            for _ in range(5):
                shutil.rmtree(self.profile, ignore_errors=True)
                if not os.path.isdir(self.profile):
                    break
                time.sleep(0.4)
        return False

    def page_ws(self):
        targets = json.load(urllib.request.urlopen(
            "http://127.0.0.1:%d/json/list" % CDP_PORT))
        page = next(t for t in targets if t["type"] == "page")
        return page["webSocketDebuggerUrl"]


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.n = 0

    async def send(self, method, **params):
        self.n += 1
        mid = self.n
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=120))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    async def ev(self, expr):
        """Evaluate, awaiting any promise. Raises on a page-side exception."""
        r = await self.send("Runtime.evaluate", expression=expr,
                            returnByValue=True, awaitPromise=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:600])
        return r["result"].get("value")

    async def open_page(self, url=BASE, settle=4.0):
        await self.send("Page.enable")
        await self.send("Runtime.enable")
        await self.send("Log.enable")
        await self.send("Network.enable")
        await self.send("Page.navigate", url=url)
        await asyncio.sleep(settle)

    async def shot(self, path):
        r = await self.send("Page.captureScreenshot", format="png")
        pathlib.Path(path).write_bytes(base64.b64decode(r["data"]))
        return path


def outdir():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    return OUTDIR


# ───────────────────────── page-side helper snippets ─────────────────────────

# Bind a <video> and expose __seek. Works on a same-origin page ONLY: canvas
# readback of a video from another origin taints the canvas and toDataURL
# throws, so we always drive the real page and swap .src rather than loading
# the file into about:blank.
BIND_VIDEO = """(async () => {
    const v = document.querySelector(%(sel)s);
    if (!v) throw new Error('no element matching ' + %(sel)s);
    window.__v = v; v.pause();
    %(swap)s
    if (v.readyState < 2) await new Promise(r => {
        v.addEventListener('loadeddata', r, {once:true}); setTimeout(r, 12000); });
    window.__seek = async (t) => {
        v.currentTime = t;
        await new Promise(r => {
            v.addEventListener('seeked', r, {once:true}); setTimeout(r, 5000); });
        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    };
    return {w: v.videoWidth, h: v.videoHeight, dur: +(v.duration||0).toFixed(2)};
})()"""


def bind_video(sel_or_url):
    """Accept either a CSS selector or an asset URL/path.

    A URL is loaded by pointing #reelVideo at it, which keeps everything
    same-origin so canvas readback stays legal.
    """
    if sel_or_url.startswith(("http://", "https://", "assets/", "/assets/")):
        url = sel_or_url if sel_or_url.startswith("http") else BASE + sel_or_url.lstrip("/")
        return BIND_VIDEO % {"sel": json.dumps("#reelVideo"),
                             "swap": "v.src = %s; v.load();" % json.dumps(url)}
    return BIND_VIDEO % {"sel": json.dumps(sel_or_url), "swap": ""}


# Per-pixel temporal minimum. A static bright overlay (a generator watermark)
# survives the min over a moving scene because its pixels never go dark;
# real scene pixels do at some frame.
ACCUM_MIN = """(() => {
    __g.drawImage(__v, 0, 0);
    const d = __g.getImageData(0, 0, __c.width, __c.height).data;
    if (!window.__min) { window.__min = new Uint8ClampedArray(d); return 1; }
    const m = window.__min;
    for (let p = 0; p < d.length; p += 4) {
      if (d[p]   < m[p])   m[p]   = d[p];
      if (d[p+1] < m[p+1]) m[p+1] = d[p+1];
      if (d[p+2] < m[p+2]) m[p+2] = d[p+2];
    }
    return 1;
})()"""

MAKE_CANVAS = """(() => {
    const c = document.createElement('canvas');
    c.width = __v.videoWidth; c.height = __v.videoHeight;
    window.__c = c; window.__g = c.getContext('2d', {willReadFrequently:true});
    window.__min = null;
    return [c.width, c.height];
})()"""

# Top-hat: subtract a large-radius local mean from the min-image, so an overlay
# is isolated whether it sits on a bright or a dark part of the scene. Then take
# the strongest connected blob, restricted to a region (the whole-frame maximum
# is otherwise just the brightest scene highlight).
TOPHAT = """(() => {
    const W = __c.width, H = __c.height, m = window.__min;
    const lum = new Float32Array(W*H);
    for (let i = 0; i < W*H; i++) { const p = i*4;
      lum[i] = 0.2126*m[p] + 0.7152*m[p+1] + 0.0722*m[p+2]; }
    const R = 45;
    const tmp = new Float32Array(W*H), bg = new Float32Array(W*H);
    for (let y = 0; y < H; y++) {
      let s = 0, c = 0;
      for (let x = -R; x <= R; x++) if (x >= 0 && x < W) { s += lum[y*W+x]; c++; }
      for (let x = 0; x < W; x++) {
        tmp[y*W+x] = s/c;
        const o = x-R, i2 = x+R+1;
        if (o >= 0) { s -= lum[y*W+o]; c--; }
        if (i2 < W) { s += lum[y*W+i2]; c++; }
      }
    }
    for (let x = 0; x < W; x++) {
      let s = 0, c = 0;
      for (let y = -R; y <= R; y++) if (y >= 0 && y < H) { s += tmp[y*W+x]; c++; }
      for (let y = 0; y < H; y++) {
        bg[y*W+x] = s/c;
        const o = y-R, i2 = y+R+1;
        if (o >= 0) { s -= tmp[o*W+x]; c--; }
        if (i2 < H) { s += tmp[i2*W+x]; c++; }
      }
    }
    const RX = Math.floor(W*__rx), RY = Math.floor(H*__ry);
    const inR = (i) => { const x = i % W, y = (i-x)/W; return x >= RX && y >= RY; };
    const th = new Float32Array(W*H);
    let peak = 0;
    for (let y = RY; y < H; y++) for (let x = RX; x < W; x++) {
      const i = y*W+x; th[i] = lum[i]-bg[i]; if (th[i] > peak) peak = th[i]; }
    const T = 28, seen = new Uint8Array(W*H), st = [];
    let best = null;
    for (let i0 = 0; i0 < W*H; i0++) {
      if (seen[i0] || !inR(i0) || th[i0] <= T) continue;
      st.length = 0; st.push(i0); seen[i0] = 1;
      let mnx=1e9, mny=1e9, mxx=-1, mxy=-1, cnt=0, sum=0;
      while (st.length) {
        const i = st.pop(), x = i % W, y = (i-x)/W;
        cnt++; sum += th[i];
        if (x<mnx) mnx=x; if (x>mxx) mxx=x; if (y<mny) mny=y; if (y>mxy) mxy=y;
        for (const j of [x>0?i-1:-1, x<W-1?i+1:-1, y>0?i-W:-1, y<H-1?i+W:-1])
          if (j >= 0 && !seen[j] && inR(j) && th[j] > T) { seen[j]=1; st.push(j); }
      }
      const cand = {cnt, sum, box:[mnx, mny, mxx-mnx+1, mxy-mny+1]};
      if (!best || cand.sum > best.sum) best = cand;
    }
    const img = new ImageData(new Uint8ClampedArray(m), W, H);
    for (let p = 0; p < m.length; p += 4) img.data[p+3] = 255;
    const src = document.createElement('canvas');
    src.width = W; src.height = H; src.getContext('2d').putImageData(img, 0, 0);
    return { peak: Math.round(peak), blob: best && {px: best.cnt, box: best.box},
             png: src.toDataURL('image/png'), W, H };
})()"""


# ───────────────────────────── commands ─────────────────────────────

async def cmd_tour(args):
    """Scroll the whole page, screenshot each stop, report page health.

    CROUSTILLE_REDUCED_MOTION=1 exercises the prefers-reduced-motion path,
    which styles.css and script.js both branch on.
    """
    out = outdir()
    reduced = os.environ.get("CROUSTILLE_REDUCED_MOTION") == "1"
    if reduced:
        print("(prefers-reduced-motion forced on)")
    with Chrome(reduced_motion=reduced) as ch:
        async with websockets.connect(ch.page_ws(), max_size=256*1024*1024) as ws:
            c = CDP(ws)
            errors, failed = [], []
            await c.open_page()

            report = {}
            report["title"] = await c.ev("document.title")
            report["visibility"] = await c.ev("document.visibilityState")
            report["scrollHeight"] = await c.ev("document.documentElement.scrollHeight")
            report["videos"] = await c.ev("""
                Array.from(document.querySelectorAll('video')).map(v => ({
                  src: (v.currentSrc||v.src||'').split('/').pop(),
                  readyState: v.readyState, paused: v.paused,
                  w: v.videoWidth, h: v.videoHeight,
                  currentTime: +v.currentTime.toFixed(2),
                  duration: +(v.duration||0).toFixed(2),
                  error: v.error ? v.error.code : null }))""")
            report["images"] = await c.ev("""
                (() => { const i = Array.from(document.images);
                  return { total: i.length,
                    broken: i.filter(x => x.complete && x.naturalWidth === 0)
                             .map(x => x.src.split('/').pop()) }; })()""")
            report["sections"] = await c.ev("""
                Array.from(document.querySelectorAll('section, header, footer'))
                     .map(s => s.id || (s.className||'').split(' ')[0] || s.tagName.toLowerCase())""")

            shots = [await c.shot(str(out / "01-hero.png"))]
            h, vh = report["scrollHeight"] or 900, await c.ev("window.innerHeight")
            for i, frac in enumerate([0.18, 0.40, 0.62, 0.84, 1.0], start=2):
                y = int((h - vh) * frac)
                await c.ev("window.scrollTo({top:%d,behavior:'instant'}); "
                           "new Promise(r=>setTimeout(r,1400))" % y)
                shots.append(await c.shot(str(out / ("%02d-scroll-%d.png" % (i, int(frac*100))))))

            report["videos_after_scroll"] = await c.ev("""
                Array.from(document.querySelectorAll('video')).map(v => ({
                  src: (v.currentSrc||v.src||'').split('/').pop(),
                  readyState: v.readyState, paused: v.paused,
                  currentTime: +v.currentTime.toFixed(2) }))""")

            # Drain queued Log/Network events without blocking.
            try:
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.4))
                    if msg.get("method") == "Log.entryAdded":
                        e = msg["params"]["entry"]
                        if e["level"] in ("error", "warning"):
                            errors.append("[%s] %s" % (e["level"], e.get("text")))
                    elif msg.get("method") == "Network.loadingFailed":
                        failed.append(msg["params"].get("errorText"))
            except asyncio.TimeoutError:
                pass
            report["console"] = errors[:20]
            report["failedRequests"] = failed[:20]

            print(json.dumps(report, indent=2))
            print("\nscreenshots:")
            for s in shots:
                print("  " + s)


async def cmd_nav(args):
    """Click every in-page nav anchor and report where the page landed."""
    with Chrome() as ch:
        async with websockets.connect(ch.page_ws(), max_size=64*1024*1024) as ws:
            c = CDP(ws)
            await c.open_page()
            nav = await c.ev("""
                Array.from(document.querySelectorAll('nav a[href^="#"]')).map(a => ({
                  text: a.textContent.trim(), href: a.getAttribute('href'),
                  targetExists: !!document.querySelector(a.getAttribute('href')) }))""")
            rows = []
            for link in nav:
                href = link["href"]
                if not link["targetExists"]:
                    rows.append({"href": href, "error": "no such target"})
                    continue
                await c.ev("""(() => { window.scrollTo(0,0);
                    document.querySelector('nav a[href="%s"]').click(); })();
                    new Promise(r=>setTimeout(r,2200))""" % href)
                rows.append(dict(href=href, **(await c.ev("""
                    (() => { const r = document.querySelector('%s').getBoundingClientRect();
                      return { scrollY: Math.round(window.scrollY),
                               topOffset: Math.round(r.top) }; })()""" % href))))
            print(json.dumps({"links": nav, "landed": rows}, indent=2))
            offs = sorted(set(r.get("topOffset") for r in rows if "topOffset" in r))
            print("\ndistinct topOffset values: %s  (want one value = consistent "
                  "sticky-header offset)" % offs)


async def cmd_mobile(args):
    """Mobile viewport: screenshots plus a horizontal-overflow check."""
    out = outdir()
    with Chrome() as ch:
        async with websockets.connect(ch.page_ws(), max_size=64*1024*1024) as ws:
            c = CDP(ws)
            await c.send("Page.enable")
            await c.send("Runtime.enable")
            await c.send("Emulation.setDeviceMetricsOverride",
                         width=390, height=844, deviceScaleFactor=2, mobile=True)
            await c.send("Page.navigate", url=BASE)
            await asyncio.sleep(4)
            print(await c.shot(str(out / "10-mobile-hero.png")))
            print(json.dumps(await c.ev("""({
                docScrollWidth: document.documentElement.scrollWidth,
                innerWidth: window.innerWidth,
                pastRightEdge: Array.from(document.querySelectorAll('*'))
                  .filter(e => e.getBoundingClientRect().right > window.innerWidth + 2)
                  .slice(0, 8)
                  .map(e => e.tagName + '.' + (e.className||'').toString().split(' ')[0])
            })"""), indent=2))
            print("note: .announce__track is a marquee and is *meant* to overrun; "
                  "what matters is docScrollWidth === innerWidth")
            await c.ev("window.scrollTo(0,2200); new Promise(r=>setTimeout(r,1200))")
            print(await c.shot(str(out / "11-mobile-scroll.png")))


async def cmd_frame(args):
    """Real decoded frames -> PNG. Proves whether a mark is in the video or the DOM."""
    if not args:
        sys.exit("usage: frame <selector|assetUrl> [t ...]")
    sel, times = args[0], [float(t) for t in args[1:]] or [1.0]
    out = outdir()
    tag = "".join(ch if ch.isalnum() else "_" for ch in sel)[-40:]
    with Chrome() as ch:
        async with websockets.connect(ch.page_ws(), max_size=256*1024*1024) as ws:
            c = CDP(ws)
            await c.open_page(settle=3.5)
            meta = await c.ev(bind_video(sel))
            print("%s: %dx%d %ss" % (sel, meta["w"], meta["h"], meta["dur"]))
            if not meta["w"]:
                sys.exit("no decoded frame — is the dev server serving Range requests?")
            for t in times:
                await c.ev("__seek(%f)" % t)
                data = await c.ev("""(() => {
                    const c = document.createElement('canvas');
                    c.width = __v.videoWidth; c.height = __v.videoHeight;
                    c.getContext('2d').drawImage(__v, 0, 0);
                    return c.toDataURL('image/png'); })()""")
                p = out / ("frame-%s-t%s.png" % (tag, str(t).replace(".", "_")))
                p.write_bytes(base64.b64decode(data.split(",", 1)[1]))
                print("  t=%ss -> %s" % (t, p))


async def cmd_mark(args):
    """Detect a static burned-in watermark and print its exact bbox.

    Region defaults to the bottom-right corner, where generators put marks.
    Override with: mark <sel> [samples] [rx] [ry]
    """
    if not args:
        sys.exit("usage: mark <selector|assetUrl> [samples] [rx] [ry]")
    sel = args[0]
    samples = int(args[1]) if len(args) > 1 else 40
    rx = float(args[2]) if len(args) > 2 else 0.78
    ry = float(args[3]) if len(args) > 3 else 0.68
    out = outdir()
    tag = "".join(c2 if c2.isalnum() else "_" for c2 in sel)[-40:]
    with Chrome() as ch:
        async with websockets.connect(ch.page_ws(), max_size=256*1024*1024) as ws:
            c = CDP(ws)
            await c.open_page(settle=3.5)
            meta = await c.ev(bind_video(sel))
            W, H, dur = meta["w"], meta["h"], meta["dur"]
            print("%s: %dx%d %ss — sampling %d frames" % (sel, W, H, dur, samples))
            if not W:
                sys.exit("no decoded frame")
            await c.ev(MAKE_CANVAS)
            for i in range(samples):
                await c.ev("__seek(%f)" % (0.15 + (dur - 0.5) * i / max(1, samples - 1)))
                await c.ev(ACCUM_MIN)
            await c.ev("window.__rx = %f; window.__ry = %f" % (rx, ry))
            res = await c.ev(TOPHAT)
            p = out / ("min-%s.png" % tag)
            p.write_bytes(base64.b64decode(res["png"].split(",", 1)[1]))
            print("  top-hat peak in region : %d" % res["peak"])
            if res["blob"]:
                b = res["blob"]["box"]
                print("  strongest blob         : %d px  x=%d y=%d w=%d h=%d"
                      % (res["blob"]["px"], b[0], b[1], b[2], b[3]))
                print("  inset from right/bottom: %d / %d px" % (W-(b[0]+b[2]), H-(b[1]+b[3])))
                print("  ffmpeg delogo (6px margin): delogo=x=%d:y=%d:w=%d:h=%d"
                      % (max(0, b[0]-6), max(0, b[1]-6), b[2]+12, b[3]+12))
                print("  NOTE: a compact ~square blob is a watermark; a long thin one is "
                      "usually scene detail. Open the min image and look.")
            else:
                print("  no persistent bright blob above threshold — region looks clean")
            print("  temporal-min image     : %s" % p)


COMMANDS = {"tour": cmd_tour, "nav": cmd_nav, "mobile": cmd_mobile,
            "frame": cmd_frame, "mark": cmd_mark}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "up":
        server_up()
        return
    if cmd == "down":
        server_down()
        return
    if cmd not in COMMANDS:
        sys.exit("unknown command %r; try one of: up down %s"
                 % (cmd, " ".join(COMMANDS)))
    server_up()
    asyncio.run(COMMANDS[cmd](args))


if __name__ == "__main__":
    main()
