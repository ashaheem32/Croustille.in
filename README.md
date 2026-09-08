# Croustille — Portfolio Site

Portfolio-style site for **Croustille**, a bakery and coffee house in Lawgate,
Punjab. The bakes are presented the way a studio presents work: numbered
chapters, hairline rules, editorial type on paper.

> "Where brew meet bakes" — [@croustille.in](https://www.instagram.com/croustille.in/)

Static HTML/CSS/JS. No build step, no dependencies — open it and it runs.

## Run it

```bash
python3 serve.py        # → http://localhost:8900
```

**Use `serve.py`, not `python3 -m http.server`.** The stdlib server ignores HTTP
Range requests. Chrome opens a video with `Range: bytes=0-`, gets a plain `200`
with no `Accept-Ranges`, and stalls — the hero clip never starts and never
reports an error, so it looks like a broken file when nothing is wrong.
`serve.py` adds Range support, speaks HTTP/1.1 (keep-alive, which the media
loader needs), and is threaded so a streaming video cannot block the CSS.

Every real host — nginx, Netlify, Vercel, GitHub Pages, S3 — supports Range, so
this only affects local preview. This was not theoretical: under
`python3 -m http.server` the clip never loaded at all and reported no error;
under `serve.py` it buffers all 29.2s and reports its true 720×1280.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | All markup — one page, top to bottom |
| `styles.css` | Design tokens + all styling |
| `script.js` | Sticky nav, mobile menu, scroll reveal, scroll-linked drift, the card-deck coverage pass, the scroll-scrubbed film |
| `assets/` | The wordmark, the hero clip, the two-act film, plus five product photographs |

## Brand

The layout is an editorial portfolio: a type-first hero, oversized marquee
bands between chapters, a numbered work list, and one dark film section. The
page lives on cream; the wine is the accent rather than the ground, and the
dark grounds are saved for the film and the sign-off, so they land as
moments instead of wallpaper.

The two primary values are **sampled from the supplied wordmark artwork**, not
approximated:

| Token | Value | Source |
| --- | --- | --- |
| `--wine` | `#59090C` | The logo ground — 98.7% of the artwork's pixels |
| `--white` | `#FFFFFF` | The script itself, measured at `#FEFEFE` |

Everything else is derived to support that pair:

| Token | Value | Role |
| --- | --- | --- |
| `--wine-700` / `--wine-900` | `#47070A` / `#2E0406` | Section and footer grounds |
| `--cream` / `--cream-2` | `#FBF6EF` / `#FFFCF7` | Light section surfaces |
| `--sand` / `--sand-deep` | `#EADCC6` / `#D6BC9B` | Warm accents, on-dark small text |
| `--caramel` | `#946428` | Eyebrows, italic accents, stars |

### The wordmark

`assets/croustille-wordmark.png` is your actual logo, extracted from the artwork by
keying out the burgundy ground. It is applied as a **CSS mask**, not an `<img>`:

```css
.logo__word {
  background-color: var(--white);
  mask: url("assets/croustille-wordmark.png") center / contain no-repeat;
}
```

That means one asset serves every placement and recolours by changing
`background-color` alone — set it to `var(--wine)` to drop the mark onto a cream
surface. The word "Croustille" stays in the markup for search engines and screen
readers and is shifted out of view.

If you have the logo as vector (SVG/AI/EPS), swapping it in is worth doing — it
would render crisper on large displays. The current asset is 778×317, which is
ample for its largest on-page use (268px wide).

### Type

Three families, three jobs:

- **Fraunces** (variable) is the display voice — titles, entry names, pull
  quotes, the big italic bands. A warm, slightly wonky serif that reads
  artisanal without costuming.
- **Space Grotesk** does the talking: body copy, descriptions.
- **Space Mono** does the labelling: section indexes, eyebrows, nav links,
  captions, tags, the meta strips. The mono is what makes the page read as a
  portfolio rather than a brochure.

The script voice now comes only from the wordmark asset itself — the previous
script webfont (Mrs Saint Delafield) is no longer loaded.

All colour, radius, shadow and spacing values live as custom properties at the top
of `styles.css` — retheming means editing that one block.

## Sections

The page is an index — every chapter carries its number in the section head,
and the nav links repeat those numbers:

1. Announcement ticker (mono, ink strip) + sticky nav carrying the wordmark
2. Hero — type-first: "Where brew / meets bakes." with the clip beside it
   in an arched frame, and a specs line at the foot
3. Marquee band — oversized italic strap, pure divider
4. **01 · Selected bakes** — five numbered cards that stack into a deck as
   you scroll, each pinning below the nav while the next slides over it
5. **02 · The film** — two supplied macro films cut into one two-act
   scrub: the Berliner, then the cheesecake
6. **03 · The practice** — pull quote and the case for the slow way
7. Second marquee band
8. **04 · The menu** — two-column index with dotted leaders, oven and bar
9. **05 · Kind words** — one featured quote, two supporting
10. **06 · Visit** — dark close: "Come say hello." + address grid
11. Footer — one slim bar

(The nav skips 05 — five links plus the CTA is enough; Kind words is not a
destination anyone navigates to.)

## Edge ornaments

Three sections (hero, practice, visit) each carry four pencil-sketch drawings
at their corners, drawn from two 3×3 transparent sprite sheets in
`assets/decor/` — eighteen drawings available, two image requests. The sheets
are **WebP at 1032×1032**, not PNG. They are soft-shaded raster drawings with
~228k distinct colours, so lossless PNG was the worst possible fit: the pair
cost 2.6 MB, more than the hero video, for decoration sitting at `opacity:
.18` behind a colour filter. WebP q84 puts them at 408 KB together — an 85%
cut whose worst per-pixel difference in a rendered corner is 12/255, with
0.03% of pixels off by more than 8. 1032px is deliberate: the 3×3 grid puts
cells at 344px and `.edge-sketch` never renders wider than 172px, so that is
exactly 2× for retina and nothing is spent on invisible pixels. All the sprite
maths is percentage-based (`background-size: 300% 300%`), so the sheet
resolution is a free variable — no CSS changes when it moves. Light
sections multiply the linework into the paper; dark sections invert and screen
it so only the pencil marks glow through. The portfolio layout uses them
sparingly on purpose — against the hairline rules, four sketched corners per
section read as texture; more read as clutter.

**The drawings do not fill their sprite cells consistently.** Measured from the
sheets' alpha channel, ink footprints range from 64% to 86% of a cell (a 1.35×
spread) and centres drift up to 12%. Identical boxes therefore rendered at visibly
different sizes and different distances from the page edge. Each drawing carries a
measured `--sketch-scale` and `--sketch-nudge-x/y` that normalises its ink to a
uniform 76% footprint and recentres it.

If you replace or re-export a sprite sheet, those corrections must be recomputed —
they are specific to where the ink sits in each cell.

## Photography

All stock imagery is gone. The site now runs on supplied media, each item
used exactly once, served locally — no external image or video requests:

| Asset | Where it appears | Processing |
| --- | --- | --- |
| `hero-video.mp4` + `hero-poster.jpg` | Hero | Native 720×1280 portrait, untouched. Autoplays muted and looped; holds on the poster frame under `prefers-reduced-motion` |
| `film-reel.mp4` + `film-poster.jpg` | The film | Two supplied macro films (1280×720, 10s each) cut into one 19.2s two-act film — see [The film](#the-film-scroll-scrubbed); never plays, the scroll is its transport |
| `pistachio-croissant.jpg` | Selected bakes 01 | Cropped 5:4 by the frame |
| `san-sebastian.jpg` | Selected bakes 02 | Cropped 5:4 by the frame |
| `korean-garlic-bun.jpg` | Selected bakes 03 | Cropped 5:4 by the frame |
| `berliner.jpg` | Selected bakes 04 | Cropped 5:4 by the frame |
| `cinnamon-roll.jpg` | Selected bakes 05 | Cropped 5:4 by the frame |

All five photographs live in the work list — one entry each, 5:4 landscape
frames (16:10 when the entries stack on mobile). The sources mix portrait and
landscape, and a shared frame ratio is what makes five different shots read as
one series.

`assets/bakery-reel.mp4` + `bakery-reel-poster.jpg` are **kept but unused** —
an earlier cut of the film section, assembled from the five photographs with
ffmpeg (Ken Burns pushes, cross-dissolves). The section now runs the supplied
Berliner footage instead; delete these two if the montage cut is never coming
back.

### Sections that run without photography

The menu, the practice and the visit sections are built typographic-first —
dotted-leader lists, a pull quote, a display headline — rather than padded
with stock. Supply more photography and the menu columns or the visit close
could take an image, but neither needs one.

### The hero is a split layout, not full-bleed

The hero clip is a 720×1280 portrait — a 9:16 reel. Stretched across a full-bleed
hero it would upscale roughly 2.5× and crop away everything but the middle. The
hero is two columns instead, so the video renders under 1:1 and stays sharp. **If
you shoot wide, high-resolution hero footage (2000px+ across), the full-bleed
treatment is the better look** and is worth reverting to.

The frame carries the clip's exact 9:16 proportion, so `object-fit` crops
nothing. It previously sat at `4 / 4.5` (0.889) against the video's 0.5625,
which meant `cover` discarded 37% of every frame — that is why it read as an
unintelligible extreme close-up.

### The hero fits the window

The reel's width is **derived from the height the window has left**, not fixed:

```css
--avail-h: calc(100svh - var(--chrome-h) - var(--hero-pad-t) - var(--hero-pad-b));
width: min(100%, 360px, calc((var(--avail-h) - 2.4rem) * 9 / 16));
```

Whatever vertical room remains after the announcement bar, the nav and the
hero's own padding — minus 2.4rem for the caption line under the frame —
times 9/16, is the widest the frame may be, so a 9:16 panel plus its caption
can never be taller than the first screen. The 360px ceiling stops it
ballooning on tall windows; `100%` keeps it inside its column on narrow ones.
`.hero__inner` takes `min-height: calc(100svh - var(--chrome-h))` to fill
exactly that space.

`--chrome-h` is **measured in `script.js`**, not hard-coded: the nav's height
follows the wordmark's `clamp()`, so it changes with the viewport. It is
remeasured on resize and again on `document.fonts.ready`, since web fonts land
after first paint and can change the nav's height.

`svh` rather than `vh` so mobile browser chrome does not push the hero taller
than the screen it is trying to fit.

(The specific frame sizes quoted for the old layout no longer apply — the
derivation is the same, the constants changed with the redesign.)

The one thing that does crop the reel is the parallax overscan — `scale: 1.06`
loses about 6% at the edges. That is the price of the drift having somewhere to
travel; drop it to `scale: 1` and set `HERO_INNER_TRAVEL = 0` in `script.js` if
you would rather have the whole frame.

Two gotchas worth remembering if you touch this:

- The `<video>` carries `width`/`height` attributes to reserve space before the
  file arrives. That height is a presentational hint that **beats
  `aspect-ratio`** — `height: auto` in the CSS is what lets the aspect govern.
  Without it the frame renders 1280px tall.
- The media element runs three independent movements. `scale` is static overscan,
  `translate` is the entrance, `transform` is the scroll parallax. Animating the
  entrance on `transform` would erase the parallax the instant it settled.

### The clip is heavy, and 720p is the floor

2.73 MB over 29 seconds. It used to be 3.0 MB, carrying a 64 kbps AAC track
across the whole clip that was never heard because the element is `muted`.
That is gone — stripped with a stream copy, so the video bitstream is
byte-identical (same packet MD5), 276 KB for free:

```bash
ffmpeg -i hero-video.mp4 -an -c:v copy -movflags +faststart out.mp4
```

Chrome will not preload media this size on a connection it rates slow, so on
3G the visitor gets the poster and nothing else. `preload` stays `metadata`
and playback starts on visibility, which helps.

**Do not downscale it.** The obvious next move is a smaller frame, but
measured in-browser, the element renders 379px wide on a 1440px desktop and
228px on a 390px phone — and that phone is typically 3× DPR, which wants a
684px source. At 720px the file is already within 5% of the minimum that keeps
it sharp for the mobile audience this page is actually for. Cutting to 640px
saves 750 KB and softens the hero for the majority of visitors.

Re-encoding at the same size is also a dead end: the source is already
efficient at 780 kbps, and libx264 at CRF 26 came out *larger* than the
original. The two levers that remain, neither taken:

| Option | Size | Cost |
|---|---|---|
| current: H.264, no audio | 2.73 MB | — |
| VP9 `.webm` | 2.25 MB | second file + `<source>` fallback |
| AV1 | 2.00 MB | second file + fallback, Safari 17+ |
| trim to ~8s | ~0.8 MB | the element has `loop`; an arbitrary cut loops every 8s and can land mid-motion |

The codec options cost ~0.5–0.7 MB against doubling the hero asset count and
adding conditional delivery. The trim is the big win but it is a creative
decision about how the hero feels, not a technical one.

## The bake deck

The five Selected Bakes cards stack as the page scrolls: each card pins just
below the nav, the next slides up over it, and covered cards recede — scaled
down 4.5% and dimmed under a paper-coloured veil. Scrolling back up plays
the whole thing in reverse, card by card, because there is nothing to
rewind: `position: sticky` is pure geometry, and the recede is recomputed
from that geometry every frame.

### How it is built

- **Every `<li>` is sticky at almost the same top** — each one 16px
  (`--stack-peek`) lower than the last, so covered cards keep a sliver of
  top edge visible and the pile reads as a deck of sheets. Painting order is
  DOM order, so later cards sit on top without any z-index management.
- **`grid-auto-rows: 1fr` equalises every card to the tallest.** With mixed
  heights, a covered card's bottom edge would poke out under the card on
  top of it.
- **`.work__list::after` is the resting beat.** Sticky cards stay pinned
  only while their containing block — the ol's *content* box; padding does
  not count — still has room below them, so the hold after the fifth card
  lands has to be content. The empty pseudo-item takes an implicit 1fr row,
  which the equalisation makes a full card tall: one card-height of scroll
  with the finished deck on screen before it releases.
- **The recede is driven by `--stack-p`** (0 → 1, how far the next card has
  covered this one), written per-card by the same rAF drift pass that moves
  the hero and the sketches. CSS derives both the scale and the veil from
  it, so covered cards sink and dim in one coordinated move — in both
  scroll directions. `transform-origin` is at the card's top, which also
  means scaling never moves `rect.top`, so the pass can keep trusting its
  own measurements.

### Two things that would silently break it

- **`.section`'s `overflow: hidden` kills the pinning** — it would make the
  section the cards' nearest scroll box and sticky would never engage.
  `.work.section` overrides it to `visible`; nothing in this chapter bleeds
  (no corner sketches here), so that is safe. Add sketches to this section
  and the stack breaks — pick one.
- **The pin offset uses `--nav-h`, not `--chrome-h`.** By the time the deck
  pins, the announcement bar has scrolled away; the combined measurement
  would leave a phantom gap above every card. Both are measured in
  `script.js`.

### Gates

The stack needs the viewport to be taller than a card, or a pinned card
would hide its own bottom with no way to scroll it into view — so the
sticky rules sit behind `@media (min-height: 560px)`, mirrored by
`STACK_MIN_VH` in `script.js` (change both together; the JS also clears its
written coverage if the viewport shrinks below the gate mid-scroll). Under
`prefers-reduced-motion` the deck reverts to a plain scrolling list.

Verified in headless Chrome at 1440×900 and 390×844: rows equalise (459px /
470px), cards pin at exactly nav + 14px + 16px steps, `--stack-p` runs 0 → 1
per card as its successor arrives, the assembled deck holds through the
phantom row, and reverse-scroll samples match the forward samples exactly —
back at the top of the list, every card is unpinned with coverage 0.

## The film (scroll-scrubbed)

Between the Selected Bakes deck and The Practice, the page hands one full
screen over to the two supplied macro films, cut into a single two-act film
— and the film **does not play**. The scroll wheel is its transport: scroll
down and it runs forward, scroll up and it runs backward, stop and it stops.
`.reel__track` is 480svh tall (360svh under 700px) and supplies the scroll
distance. The stage pins below the measured navigation and fills the remaining
small viewport height, keeping mobile browser toolbar changes from stretching
the track. Portrait phones reserve the lower part for copy; short landscape
screens use compact typography and spacing.

`script.js` maps travel onto `currentTime`, with one seek in flight at a time.
Once decoding completes, the latest scroll target is applied and the caption
and meter follow the decoded position. Media readiness events retry a pending
target after buffering, even when scrolling has stopped. The tall track activates
only after frame data arrives; a media error restores the static presentation.

Run `node tests/reel.test.cjs` for the mocked media lifecycle regression checks
(loading, rapid and reverse seeks, buffering recovery, end frame, errors, and
reduced motion). These checks do not replace visual browser testing.

**The two shots are joined by a 0.8s cross-dissolve, not a cut** — hard
cuts read as glitches under a scrub, dissolves read as a camera move. The
dissolve midpoint sits at 9.61s of the 19.24s cut (fraction 0.4993), and
`REEL_MARKS` in `script.js` swaps the Act I / Act II caption exactly there,
so the words change with the picture. Re-cut the film and that number must
be recomputed.

### The sources had to be re-encoded, and this is not optional

Both supplied files (`Cinematic_macro_product_film_o.mp4` and
`…_o (1).mp4`, each 1280×720, 10s, 24fps) carried **exactly one keyframe —
at 0:00**. A scrub seeks on almost every frame, and a seek can only land on
a keyframe, so scrubbing the originals would have decoded from the start of
the file on every wheel tick. `assets/film-reel.mp4` is both pictures
joined (`xfade=transition=fade:duration=0.8`) and re-encoded in the
Higgsfield sandbox with:

```bash
ffmpeg -i src.mp4 -vf "scale=…:flags=lanczos,format=yuv420p" -an \
  -c:v libx264 -crf 24 -g 10 -keyint_min 10 -sc_threshold 0 \
  -preset slow -movflags +faststart film-reel.mp4
```

`-g 10` gives a keyframe every 0.4s — 50 across the cut — which is what
makes the scrub land instantly in both directions. Audio is stripped (the
element is muted anyway). 5.2 MB of sources in, 3.9 MB out. Swap in
different footage and the same re-encode is required; a straight copy will
stutter no matter what the JS does.

Scene detection found **no cuts inside either shot** — each is one
continuous move, which is exactly what scrubs well. The only transition in
the cut is the dissolve the captions key off.

### The generator's star had to be painted out

The supplied footage carried a **48×48 four-pointed star burned into the
picture** at (1136, 576) — 96px in from the right edge, 96px up from the
bottom — for the whole 19.24s. It is in the decoded frames, not the page, so
no amount of CSS reaches it: `.reel__video` is `object-fit: cover`, which
means the video-pixel→screen mapping changes with every viewport aspect, and
nothing overlaid stays on top of the mark. It hides against the white
cheesecake plate around 15s but never actually goes away — a per-pixel
temporal minimum across the clip shows it surviving every frame.

`assets/film-reel.mp4` is the cut above with the star interpolated away:

```bash
ffmpeg -i film-reel.original.mp4 -vf "delogo=x=1130:y=570:w=60:h=60" \
  -c:v libx264 -profile:v high -pix_fmt yuv420p -crf 23 \
  -g 10 -keyint_min 10 -sc_threshold 0 -an -movflags +faststart \
  film-reel.mp4
```

The box carries 6px of margin around the mark. **The `-g 10` group and the
19.24s duration must survive any re-encode**: dense keyframes are what make
the scrub land instantly, and `REEL_MARKS` in `script.js` is a *fraction* of
duration, so a longer or shorter cut silently drags the caption swap off the
dissolve.

Cropping the star off was the alternative and it is worse here. Removing
everything right of x=1136 takes the aspect from 1.778 to 1.575, and because
the stage is `cover`, the narrower picture is then scaled *up* to fill the
width — the subject grows, the composition tightens and the bottom of the
stack leaves frame. delogo keeps the framing pixel-for-pixel; its
interpolation only becomes visible above about 4× zoom, over a background
that is already out of focus. SSIM against the pre-removal master is 0.9918,
3.71 MB in and 3.83 MB out.

`film-reel.original.mp4` is the pre-removal master, kept locally and
`.vercelignore`d so the pass can be redone. Swap in new footage and expect
to redo it: re-measure the mark before reusing these coordinates.

Two standing gotchas, documented here because they bite silently: the reel
section must **not** carry the `.section` class (its `overflow: hidden`
would strand the sticky stage), and `body` must keep `overflow-x: clip`,
not `hidden`. The seek also clamps to the buffered end, so a slow
connection holds the last decoded frame instead of flashing black.

Verified in headless Chrome: at 0 / 15 / 30 / 50 / 70 / 85 / 100% of the
track the film sits at 0.00 / 2.88 / 5.77 / 9.62 / 13.46 / 16.35 / 19.24s
with the caption swapping Act I → Act II exactly at the 50% mark, the stage
pinned at `top: 0` throughout; scrolling back to 20% returns it to 3.85s
and Act I. Under `prefers-reduced-motion` the track collapses to one screen
and the section holds as a still poster with both acts listed.

## Before going live

**Check the details.** These were inferred from the Instagram bio and posts, so
confirm before publishing:

- Prices are not listed anywhere — the menu index's dotted-leader rows carry a
  mono note in the right column (`.menu__note`); a price would go in that same
  slot
- Opening hours (8:00 AM – 11:00 PM, daily) are placeholders
- The address reads "Lawgate, Phagwara" — the bio only says "Lawgate, Punjab · Near Shawok"
- Two of the three testimonials are written; only the featured one is adapted
  from a real post
- The menu names two items (Pain au Chocolat, Sourdough Loaf) that were
  assumed, not confirmed — the five Selected Bakes match supplied photos and
  are accurate

**Then consider adding:** a real map embed on the Visit section, `schema.org/Bakery`
structured data for local SEO, and an OG preview image.

## Motion

Every moving part draws from one of two easing curves — `--ease-soft` for
interactions (hovers, state flips) and `--ease-glide`, a longer expo-out, for
anything that travels a distance. Nothing eases in a dialect of its own.

| Layer | What moves | Driven by |
| --- | --- | --- |
| Load | Hero meta → headline lines → sub → actions → specs strip cascade in; the video frame rises beside them | CSS `animation` with hand-set delays |
| Marquee | The ticker and the two italic bands run continuously; both hold while hovered | One shared `marquee` keyframe |
| Scroll reveal | `.reveal` blocks fade up; `.reveal--left/--right` bring two-column sections in from their own side | `IntersectionObserver` toggling one class |
| Cascade | `.stagger` containers deal their own children in behind the block — the practice list, the address grid | CSS `:nth-child` `transition-delay` |
| Scroll-linked | Hero frame lags the page by up to 70px; corner sketches drift ±42px, top and bottom corners against each other | One rAF-batched pass in `script.js` |
| Card stack | The five bakes pin below the nav and pile into a deck; covered cards recede and dim, in both directions | `position: sticky` pins; the drift pass writes `--stack-p` |
| Scroll-scrubbed | The film's 19.2s mapped onto ~380vh of scroll, forwards and back; the caption swaps on the dissolve | The drift pass reads it; seek completion schedules the latest target |

The drift pass reads every measurement before writing a single value. Reading and
writing in the same loop would force a layout recalculation per element per frame,
which is the usual way a parallax effect turns into jank. It writes CSS custom
properties (`--hero-shift`, `--sketch-drift`) rather than `transform` directly, so
it composes with the transforms those elements already carry.

## Accessibility & support

Semantic landmarks, labelled controls, a skip-to-content link ahead of the
nav, and a full `prefers-reduced-motion` path: the ticker, bands, reveals,
cascades and hero video all stop, the drift pass never registers its scroll
listener, the bake deck reverts to a plain scrolling list, the film never
goes live and holds as a still poster, and smooth scrolling reverts to
instant. The marquee bands are
`aria-hidden` — everything they say already lives elsewhere on the page. The
oversized entry indexes are `aria-hidden` too; the `<ol>` carries the
numbering semantically. Layout is CSS Grid with breakpoints at
1000 / 900 / 700px.

Every text/background pair in the palette was measured against WCAG. All clear AA
or better; the tightest are `--caramel` on cream at 4.75:1 and `--muted` on cream
at 5.42:1. Focus rings use `currentColor` so they stay legible on both the light
and dark sections. If you adjust `--caramel`, re-check it — the original
`#B8813F` failed at 3.12:1 for the small uppercase eyebrow labels, which is why
it was darkened.
