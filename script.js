/* Croustille — landing page interactions */

(function () {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Window-fit measurement ─────────────────── */
  /* The hero sizes itself to whatever the window has left below the
     announcement bar and the nav. Both are measured rather than hard-coded:
     the nav's height follows the wordmark's clamp(), so it changes with the
     viewport and cannot be a constant in CSS. */
  const announce = document.querySelector('.announce');
  const navEl = document.getElementById('nav');

  const measureChrome = () => {
    const navH = navEl ? navEl.offsetHeight : 0;
    const h = (announce ? announce.offsetHeight : 0) + navH;
    document.documentElement.style.setProperty('--chrome-h', `${h}px`);
    // The card stack pins below the nav alone — the announcement bar has
    // scrolled away by then, so --chrome-h would leave a phantom gap.
    document.documentElement.style.setProperty('--nav-h', `${navH}px`);
  };
  measureChrome();
  window.addEventListener('resize', measureChrome);
  // Web fonts land after first paint and can change the nav's height.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measureChrome);

  /* ── Sticky nav state ───────────────────────── */
  const nav = document.getElementById('nav');
  const onScroll = () => nav.classList.toggle('is-stuck', window.scrollY > 20);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  /* ── Mobile menu ────────────────────────────── */
  const burger = document.getElementById('burger');
  const links = document.getElementById('navLinks');

  const setMenu = (open) => {
    burger.classList.toggle('is-open', open);
    links.classList.toggle('is-open', open);
    burger.setAttribute('aria-expanded', String(open));
    burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    document.body.style.overflow = open ? 'hidden' : '';
  };

  burger.addEventListener('click', () => setMenu(!links.classList.contains('is-open')));
  links.addEventListener('click', (e) => { if (e.target.tagName === 'A') setMenu(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setMenu(false); });

  /* ── Hero video ─────────────────────────────── */
  /* The clip is decorative: it holds on its poster frame when the visitor has
     asked for less motion, and the poster is also the permanent fallback if
     the file never arrives — the markup needs no <img> twin for that.
     Playback is tied to visibility so a hero scrolled past stops decoding,
     and browsers that defer autoplay still start the clip once it is on
     screen. Chrome refuses to preload multi-megabyte media on connections it
     rates slow (navigator.connection.effectiveType), so `preload` stays at
     "metadata" and the real fetch is triggered here, on demand. */
  const heroVideo = document.querySelector('.hero__figure video');

  if (heroVideo) {
    if (reduceMotion) {
      heroVideo.removeAttribute('autoplay');
      heroVideo.pause();
    } else if ('IntersectionObserver' in window) {
      const vidIo = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            // play() rejects when the browser declines; the poster stays up.
            const p = heroVideo.play();
            if (p && p.catch) p.catch(() => {});
          } else if (!heroVideo.paused) {
            heroVideo.pause();
          }
        });
      }, { threshold: 0.15 });
      vidIo.observe(heroVideo);
    }
  }

  /* ── Scroll reveal ──────────────────────────── */
  /* Two behaviours, one observer and one class: `.reveal` moves the block
     itself, `.stagger` cascades that block's children (delays live in CSS).
     An element can carry both. */
  const reveals = document.querySelectorAll('.reveal, .stagger');

  if (reduceMotion || !('IntersectionObserver' in window)) {
    reveals.forEach((el) => el.classList.add('is-in'));
  } else {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        // Stagger siblings so grids cascade rather than pop as one block.
        const siblings = [...entry.target.parentElement.children].filter((n) => n.classList.contains('reveal'));
        entry.target.style.transitionDelay = `${Math.max(0, siblings.indexOf(entry.target)) * 110}ms`;
        entry.target.classList.add('is-in');
        io.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

    reveals.forEach((el) => io.observe(el));
  }

  /* ── Scroll-scrubbed film ───────────────────── */
  /* Scroll supplies the target; decode completion supplies the next seek.
     Keeping only one seek in flight prevents fast scrolling from repeatedly
     cancelling frame decoding, especially on phones. */
  const reelSection = document.querySelector('.reel');
  const reelTrack = reelSection && reelSection.querySelector('.reel__track');
  const reelStage = reelSection && reelSection.querySelector('.reel__stage');
  const reelVideo = document.getElementById('reelVideo');
  const reelCaps = reelSection ? [...reelSection.querySelectorAll('.reel__cap')] : [];

  /* Where the cross-dissolve between the two supplied shots lands, as a
     fraction of the clip: clip one runs 10.006s, the dissolve is 0.8s, so
     its midpoint sits at 9.61s of the 19.24s cut. Swapping the caption on
     that exact mark means the words change *with* the picture. Re-cut the
     film and this has to be recomputed. */
  const REEL_MARKS = [0.4993];

  let reelLive = false;
  let reelTarget = 0;   // where the scroll says the film should be, 0–1
  let reelRAF = 0;
  let reelCapIndex = -1;

  const setReelCaption = (p) => {
    let i = 0;
    while (i < REEL_MARKS.length && p >= REEL_MARKS[i]) i++;
    if (i === reelCapIndex) return;
    reelCapIndex = i;
    reelCaps.forEach((el, n) => el.classList.toggle('is-on', n === i));
  };

  const paintReel = () => {
    const p = Math.min(reelVideo.currentTime / reelVideo.duration || 0, 1);
    reelSection.style.setProperty('--reel-progress', p.toFixed(4));
    setReelCaption(p);
  };

  const reelStep = () => {
    reelRAF = 0;
    if (!reelLive || reelVideo.seeking || reelVideo.readyState < 2) return;
    const duration = reelVideo.duration;
    if (!Number.isFinite(duration) || duration <= 0) return;

    // Stay inside the last decodable frame. Do not clamp to buffered.end:
    // a range-capable host can fetch any target, including a reverse seek.
    const t = Math.min(reelTarget * duration, Math.max(0, duration - 1 / 30));
    if (Math.abs(reelVideo.currentTime - t) > 0.016) {
      reelVideo.currentTime = t;
    } else {
      paintReel();
    }
  };

  const queueReel = () => {
    if (reelLive && !reelRAF) reelRAF = requestAnimationFrame(reelStep);
  };

  if (reelSection && reelVideo && !reduceMotion) {
    // A playing clip and a scrubbing scroll would fight over currentTime.
    reelVideo.pause();
    reelVideo.addEventListener('play', () => reelVideo.pause());

    const goLive = () => {
      if (reelLive || reelVideo.readyState < 2 || !Number.isFinite(reelVideo.duration)) return;
      reelLive = true;
      // Only now does the track grow to its full height and the captions
      // start stacking — see the note above .reel in styles.css.
      reelSection.classList.add('reel--live');
      setReelCaption(0);
      queueDrift();
      queueReel();
    };

    // goLive() reaches forward to queueDrift, which is declared below — so
    // even the already-has-frame-data path waits a frame rather than running
    // inside that temporal dead zone.
    if (reelVideo.readyState >= 2) requestAnimationFrame(goLive);
    reelVideo.addEventListener('loadeddata', goLive);
    reelVideo.addEventListener('canplay', goLive);
    reelVideo.addEventListener('seeked', () => {
      if (!reelLive) return;
      paintReel();
      queueReel();
    });
    // Retry the latest target when data arrives even if scrolling stopped.
    ['loadeddata', 'canplay', 'progress'].forEach((event) => {
      reelVideo.addEventListener(event, queueReel);
    });
    reelVideo.addEventListener('error', () => {
      reelLive = false;
      cancelAnimationFrame(reelRAF);
      reelRAF = 0;
      reelSection.classList.remove('reel--live');
      reelSection.style.removeProperty('--reel-progress');
      reelVideo.removeAttribute('src');
      reelVideo.load();
    });

    // The file is ~3.9 MB and sits below the fold, so it stays at
    // preload="metadata" until the film is roughly a screen and a half away
    // — otherwise it competes with the hero clip for the first paint.
    if ('IntersectionObserver' in window) {
      const nearIo = new IntersectionObserver((entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        reelVideo.preload = 'auto';
        // load() restarts the fetch and resets currentTime, so only call it
        // while there is nothing to lose.
        if (reelVideo.readyState < 2) reelVideo.load();
        nearIo.disconnect();
      }, { rootMargin: '150% 0px' });
      nearIo.observe(reelSection);
    } else {
      reelVideo.preload = 'auto';
    }
  }

  /* ── Scroll-linked drift ────────────────────── */
  /* The hero frame and the corner sketches travel at their own rate as the
     page moves, which is what keeps long scrolls feeling continuous rather
     than like a stack of static screens.

     Everything shares one rAF-batched pass, and that pass reads every
     measurement before it writes a single value — interleaving the two
     would force a layout recalculation per element, on every frame. */
  const sketchGroups = [...document.querySelectorAll('.edge-sketches')];
  const hero = document.querySelector('.hero');
  const heroFigure = document.querySelector('.hero__figure');

  const heroMedia = document.querySelector('.hero__figure video, .hero__figure img');

  /* The card stack. CSS position:sticky does the pinning and the pile-up —
     and, because it is pure geometry, the un-stacking on the way back up.
     This pass only writes --stack-p per card: how far the NEXT card has
     covered this one (0 → 1), from which CSS derives the recede-scale and
     the paper veil. Covered cards therefore sink back and dim in both
     directions, at exactly the rate the covering card moves. */
  const stackList = document.querySelector('.work__list');
  const stackCards = stackList ? [...stackList.children] : [];
  // Mirrors the (min-height: 560px) gate on the sticky rules in styles.css —
  // below it the cards never pin, so writing coverage would scale cards
  // sitting in plain flow. Change both together.
  const STACK_MIN_VH = 560;
  let stackPeek = 16;
  if (stackList) {
    const raw = parseFloat(getComputedStyle(stackList).getPropertyValue('--stack-peek'));
    if (!Number.isNaN(raw)) stackPeek = raw;
  }
  let stackWasActive = false;

  const SKETCH_TRAVEL = 42;   // px the ornaments cover across a full viewport
  const HERO_TRAVEL = 70;     // px the hero frame lags behind the page
  // The clip slides the other way inside its arch, so frame and content
  // separate as the hero leaves. Must stay under the headroom the overscan
  // leaves (scale 1.06 ≈ 20px each side at the rendered height), or the
  // travel would pull the frame's own edge into view.
  const HERO_INNER_TRAVEL = 16;

  let queued = false;

  const drift = () => {
    queued = false;
    const vh = window.innerHeight;

    // Read.
    const offsets = sketchGroups.map((group) => {
      const r = group.getBoundingClientRect();
      if (r.bottom < -240 || r.top > vh + 240) return null;   // off-screen
      // -0.5 while the block is still below the fold, +0.5 once it is above.
      // Sections taller than the viewport can push past that, so clamp —
      // otherwise a long section drifts its ornaments out of their own frame.
      const progress = (vh / 2 - (r.top + r.height / 2)) / vh;
      return Math.min(Math.max(progress, -0.75), 0.75) * SKETCH_TRAVEL;
    });
    const heroTop = hero ? hero.getBoundingClientRect().top : 0;

    // How far the film's track has travelled past the top of the window,
    // as a fraction of the distance it can travel. The stage is one screen
    // tall and sticks there, so that screen is not scroll the film gets.
    let reelNext = null;
    if (reelLive) {
      const rect = reelTrack.getBoundingClientRect();
      const travel = rect.height - reelStage.offsetHeight;
      const pinTop = parseFloat(getComputedStyle(reelStage).top) || 0;
      reelNext = travel > 0 ? Math.min(Math.max((pinTop - rect.top) / travel, 0), 1) : 0;
    }

    // Coverage per stacked card. Scale keeps each card's top edge where it
    // is (origin is at the top), so reading rect.top stays trustworthy even
    // for cards this pass has already scaled on earlier frames.
    const stackActive = stackCards.length > 1 && vh >= STACK_MIN_VH;
    let stackPs = null;
    if (stackActive) {
      const tops = stackCards.map((li) => li.getBoundingClientRect().top);
      const range = vh * 0.5;   // covering starts half a viewport out
      stackPs = tops.map((top, i) => {
        if (i === stackCards.length - 1) return 0;   // nothing ever covers the last card
        const gap = tops[i + 1] - top;               // pinned cards settle at gap == peek
        return Math.min(Math.max(1 - (gap - stackPeek) / range, 0), 1);
      });
    }

    // Write.
    offsets.forEach((px, i) => {
      if (px === null) return;
      sketchGroups[i].style.setProperty('--sketch-drift', `${px.toFixed(1)}px`);
    });
    if (heroFigure) {
      const gone = Math.min(Math.max(-heroTop / vh, 0), 1);
      heroFigure.style.setProperty('--hero-shift', `${(gone * HERO_TRAVEL).toFixed(1)}px`);
      if (heroMedia) {
        heroMedia.style.setProperty('--hero-inner', `${(-gone * HERO_INNER_TRAVEL).toFixed(1)}px`);
      }
    }
    if (stackPs) {
      stackPs.forEach((p, i) => stackCards[i].style.setProperty('--stack-p', p.toFixed(3)));
      stackWasActive = true;
    } else if (stackWasActive) {
      // The viewport shrank below the gate mid-scroll (e.g. phone rotated):
      // the cards are back in plain flow, so leftover coverage must not
      // keep them scaled down.
      stackCards.forEach((li) => li.style.removeProperty('--stack-p'));
      stackWasActive = false;
    }
    if (reelNext !== null && reelNext !== reelTarget) {
      reelTarget = reelNext;
      queueReel();
    }
  };

  const queueDrift = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(drift);
  };

  if (!reduceMotion) {
    drift();
    window.addEventListener('scroll', queueDrift, { passive: true });
    window.addEventListener('resize', queueDrift);
    if (document.fonts) document.fonts.ready.then(queueDrift);
    if ('ResizeObserver' in window && reelStage) {
      new ResizeObserver(queueDrift).observe(reelStage);
    }
  }

  /* ── Footer year ────────────────────────────── */
  const year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());
})();
