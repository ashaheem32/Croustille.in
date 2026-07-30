---
name: run-croustille
description: Run, launch, serve, screenshot, or verify the Croustille bakery landing page — start the dev server, drive the page in headless Chrome, capture screenshots at any scroll position, check nav anchors and mobile layout, extract real video frames, and detect burned-in watermarks in the reel videos. Use when asked to run/start/preview/screenshot/test the site or to confirm a change works in the real page.
---

# Run Croustille

A static, dependency-free landing page: `index.html` + `styles.css` + `script.js`
+ `assets/`. No build step, no package manager, no node_modules. The interesting
behaviour is **scroll-driven and video-backed**, so eyeballing the HTML proves
nothing — you have to drive it.

Everything goes through one committed driver:

```
.claude/skills/run-croustille/driver.py
```

It starts the dev server on demand and drives the page in a **headless Chrome it
launches itself**, over CDP. All paths below are relative to the repo root.
Verified on macOS (darwin 25.5.0), Chrome 150, Python 3.9.6.

## Do not use the claude-in-chrome MCP tools for this page

This is the single most important thing here. The user's Chrome window is
normally sitting behind other windows, and an occluded Chrome reports
`document.visibilityState === "hidden"`. In that state Chrome **pauses
`requestAnimationFrame` and refuses to load media at all** — videos stall at
`readyState 0` forever, and the scroll-driven reel never advances.

`resize_window` does not raise the window, and `computer` input is delivered via
CDP without focusing it, so this cannot be worked around from the tool side.
Every measurement taken that way is a **false negative that looks exactly like
broken code**. The driver launches its own headless Chrome, which considers
itself visible.

## Prerequisites

Only one Python package beyond the stdlib:

```bash
pip3 install --user websockets     # already present here: 15.0.1
```

`python3` must be `/usr/bin/python3` (3.9.6); that's where the `websockets`
install above lands. Chrome must exist at
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.

Only the `mark`-adjacent video work needs ffmpeg (`brew install ffmpeg`,
installed here as 8.1.2). Nothing else does.

## Run (agent path)

```bash
python3 .claude/skills/run-croustille/driver.py up      # start dev server -> http://localhost:8900/
python3 .claude/skills/run-croustille/driver.py tour    # full-page screenshots + health JSON
python3 .claude/skills/run-croustille/driver.py nav     # click every nav anchor, check landings
python3 .claude/skills/run-croustille/driver.py mobile  # 390x844 + horizontal-overflow check
python3 .claude/skills/run-croustille/driver.py down    # stop the dev server
```

Every command except `down` starts the server itself, so `tour` alone is a valid
cold start. Screenshots land in `$TMPDIR/croustille-shots/` and absolute paths
are printed — **open them and look**; a blank frame means the launch failed.

Override the output directory with `CROUSTILLE_OUT=/some/dir`, and force the
reduced-motion code path with `CROUSTILLE_REDUCED_MOTION=1`.

`tour` reports title, `visibilityState` (must be `visible`), `scrollHeight`, every
`<video>`'s `readyState`/`paused`/`currentTime`/`error`, broken images, the section
list, console errors and failed requests. A healthy run looks like:

```
scrollHeight   12067
hero-video.mp4 readyState 4, playing, ~3.7s of 29.25s
film-reel.mp4  readyState 4, currentTime 19.24 after scrolling to the bottom
images         5 total, 0 broken
console        []      failedRequests  []
```

`film-reel.mp4` reaching ~19.24s only after the scroll pass is the signal that
the scroll-as-transport reel works. `nav` should print
`distinct topOffset values: [88]` — one value means every anchor clears the
sticky header consistently.

## Video work: frames and watermarks

The reel videos are the fiddly part of this project, so the driver has two
video-specific commands.

```bash
# Real decoded frames -> PNG. Accepts a CSS selector or an asset path.
python3 .claude/skills/run-croustille/driver.py frame '#reelVideo' 1.0 5.0 15.0
python3 .claude/skills/run-croustille/driver.py frame 'assets/film-reel.original.mp4' 1.0

# Detect a static burned-in watermark, with its exact bbox and a ready delogo box.
python3 .claude/skills/run-croustille/driver.py mark 'assets/film-reel.original.mp4'
python3 .claude/skills/run-croustille/driver.py mark '#reelVideo'
```

**`frame` settles "is this mark in the page or in the video?"** It paints the
video into a `<canvas>`, which copies *only* decoded video pixels — no DOM, no
CSS, no overlay. If a mark shows up in a `frame` PNG, it is in the `.mp4`.

**`mark` finds static overlays** using a per-pixel temporal minimum across 40
sampled frames: real scene pixels go dark at some frame, a persistent overlay
never does, so it survives the min. A top-hat filter then subtracts a
large-radius local mean, which isolates the overlay whether it sits on a bright
or dark part of the scene.

Read its output by **shape, not just score** — the region always contains
*something*:

| | `film-reel.original.mp4` (pre-fix) | `film-reel.mp4` (shipping) |
|---|---|---|
| peak | 67 | 50 |
| blob | **820 px, 48×48 at (1136,576)** | 183 px, 28×14 at (1020,583) |
| verdict | compact square → **watermark** | thin sliver → scene detail |

A compact, roughly square blob is a watermark. A long thin one is scene detail.
Always open the printed temporal-min PNG and look before concluding.

**Do not lower the sample count to save time — it produces false positives.**
The optional 2nd argument is the number of sampled frames (default 40). With too
few, the temporal minimum hasn't seen enough scene motion, so scene content
survives it and reads as a mark. On the *already-fixed* `#reelVideo`:

```
mark '#reelVideo'      -> peak 50, blob  183 px 28×14   (correct: clean)
mark '#reelVideo' 12   -> peak 71, blob 1376 px 86×34   (false positive)
```

40 is the floor for a ~19s clip. Raise it for longer or slower-moving footage.

## Human path

```bash
python3 serve.py            # http://localhost:8900, Ctrl-C to stop
python3 serve.py 9000       # any port
```

Then open the URL in a real, **focused, unoccluded** browser window. Useful for
judging design; useless for automated verification, per the occlusion trap above.

## Gotchas

- **`python3 -m http.server` breaks the videos, silently.** It ignores HTTP Range
  requests. Chrome's media loader opens a video with `Range: bytes=0-`, gets a
  plain `200` with no `Accept-Ranges`, and stalls — the video never starts *and
  never fires an error*. Always `serve.py`. Confirm with
  `curl -s -r 0-1023 -o /dev/null -w '%{http_code}\n' http://localhost:8900/assets/film-reel.mp4`
  → must be `206`.

- **Canvas readback needs same-origin.** Loading a video into `about:blank` and
  drawing it to a canvas taints the canvas, and `toDataURL` then throws — which
  presents as the script *hanging*, not erroring. The driver always navigates to
  the real page and swaps `video.src`, which is why `frame`/`mark` accept an
  asset path rather than an arbitrary URL.

- **Autoplay needs a flag.** Without
  `--autoplay-policy=no-user-gesture-required` the hero video stays paused in
  headless and looks broken. The driver sets it.

- **The reel never plays; scroll *is* its transport.** `film-reel.mp4` sitting at
  `paused: true` is correct. Judge it by `currentTime` after scrolling, not by
  `paused`.

- **Re-encoding the reel has two hard constraints.** It needs a keyframe every
  ~0.4s (`-g 10` at 25fps — verify with
  `ffprobe -v error -select_streams v:0 -skip_frame nokey -show_entries frame=pts_time -of csv=p=0 assets/film-reel.mp4`,
  which must print 49 evenly spaced times) or seeks stop landing instantly and
  the scrub feels laggy. And the **duration must stay 19.24s**, because
  `REEL_MARKS = [0.4993]` in `script.js` is a *fraction* of duration — a longer
  cut silently drags the caption swap off the cross-dissolve.

- **`prefers-reduced-motion` changes the page height.** `scrollHeight` drops
  12067 → 8734 with `CROUSTILLE_REDUCED_MOTION=1`, because the tall
  `.reel__track` collapses when the reel becomes a still poster. Don't treat
  that as a regression.

- **`.announce__track` overruns the viewport on purpose.** It's a marquee, so it
  always shows up in an "elements past the right edge" scan. The check that
  matters is `docScrollWidth === innerWidth`.

- **zsh does not word-split unquoted variables.** `COMMON="-crf 20 -g 10"` then
  `ffmpeg $COMMON out.mp4` passes one giant argument and ffmpeg reports
  `At least one output file must be specified`. Use an array:
  `COMMON=(-crf 20 -g 10)` … `"${COMMON[@]}"`.

- **`timeout` does not exist on macOS.** Don't reach for it in wrapper scripts;
  the driver does its own `asyncio.wait_for` timeouts.

- **Always a throwaway `--user-data-dir`.** Never the real Chrome profile. The
  driver mkdtemps one and retries the cleanup, because Chrome writes on the way
  out and a single `rmtree` can lose the race.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `missing dependency: pip3 install --user websockets` | Exactly that. Must land in the `/usr/bin/python3` user site-packages. |
| `Chrome not found at /Applications/...` | Chrome isn't installed at the standard path; edit `CHROME` in `driver.py`. |
| `Chrome CDP endpoint never came up on 9377` | A stale Chrome is holding the port: `pkill -f 'remote-debugging-port=9377'`. |
| `dev server failed to come up on 8900` | Port taken by something else. `lsof -i :8900`, or run `serve.py 9000` and edit `PORT`. |
| `no decoded frame — is the dev server serving Range requests?` | You're serving with `http.server`, not `serve.py`. See the first gotcha. |
| Script hangs with no output during a `frame`/`mark` run | Tainted canvas from a cross-origin video. Pass an `assets/...` path, not a bare file URL. |
| `videos` show `readyState: 0`, `visibility: "hidden"` | You're driving the user's occluded Chrome instead of this driver. |
| `down` says "something is on 8900 but this driver did not start it" | A server you started by hand. Stop it yourself: `pkill -f serve.py`. |
