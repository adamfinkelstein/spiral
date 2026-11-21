# CLAUDE.md

Small static browser site of spiral experiments: `index.html` links to each
experiment page. No build step, no dependencies — open `index.html` directly
(`open index.html`). Pages are plain `<script>` tags (no ES modules) so they
work from `file://`. Deployed to GitHub Pages on every push to `main`.

## Files

- `index.html` — landing page linking to the three experiments.
- `render.js` — shared by all pages: `N` (512, or `SPIRAL_N` if a page sets
  it first: card.html uses 1024), `erf`, `edgeStep`, `renderSpiral`,
  `gaussianBlur`, `toImageData`. Defines globals, so page scripts must not
  redeclare them (e.g. no `const N` in a page script).
- `spacing.html` / `spacing.js` — ring-spacing experiment: spiral (or rings)
  on the left, log-magnitude 2D FFT on the right, radial profile and
  harmonic-sum spacing estimate below.
- `fftspacing.js` — the FFT and spacing estimate, no DOM: FFT tables,
  `computeSpectrum(src, removeDC, useWindow)` (fills `mag` and `profile`),
  `computeHarmonicScore`, `hBest`/`hStages`/`hWin`, `evenWeight`. Used by
  spacing.js (which keeps the drawing) and cardpipe.js.
- `explain.html` — help page for `spacing.html` controls ("Explain"
  button). Keep it in sync when its controls change.
- `procedure.html` + `procedure/*.png` — both methods step by step, in three
  parts: Part 1 (spacing page: spacing and rough center), Part 2 (center
  page: center and phase from chunks, incl. options under evaluation) and
  Part 3 (card page: realistic card, whole pipeline, results, next steps). Inputs, each step with parameters, what was
  tried, result tables, limits ("Procedure" buttons on both pages; linked
  from explain.html and index.html). Figures were rendered from the app in headless Chromium
  (canvas data → PNG, 384 px). Update it when the method or defaults change.
- `center.html` / `center.js` — center/phase experiment (spiral only, no
  rings mode: `params()` sets `spiral: true` for render.js). One left column:
  true spiral (drag to move center; chunks highlighted) → connected
  components with per-chunk estimates, shared starts and the combined
  estimate → table of estimates vs. truth (20 largest components) → fit-cost
  map for the selected chunk. Sticky, scrollable controls panel on the right.
  The page's hint paragraphs describe each control.
- `gradcenter.js` — gradient-line center (`gradientCenter`, `tangentialBlur`,
  `gradientLines`, `ransacCenter`, …), shared by both pages; no DOM, uses
  `N` and `gaussianBlur` from render.js. The tangential blur follows the
  circle (tangent plus a second-order inward term u²/(2r)), so curved rings
  aren't shifted inward.
- `chunkfit.js` — the estimation; no DOM, uses only `N` from render.js: `labelComponents`, `fitChunk`, `fitComponents`, `combineChunks`
  (with `chunkData`, `evalLoss`, `phaseFor`, `fitJoint`), `costMap`, plus
  `mulberry32`, `lm`, `solve`. Scripts load in the order render.js,
  gradcenter.js, chunkfit.js, center.js (spacing page: render.js, gradcenter.js,
  spacing.js).

Controls and their defaults live in the HTML `value` / `checked` attributes;
each page's `ids` list and `params()` read them, and "Defaults" resets to them.

- `card.html` — now a static report built in Python (see "Card report
  (Python)" below); `card/img/*.png` and `card/results.json` are generated
  and committed.
- `card_js.html` / `card.js` (UI), `cardmodel.js`, `cardpipe.js` — the
  earlier in-browser version of the card page, kept frozen (see "Card page
  (card_js.html)" below). Scripts: `var SPIRAL_N = 1024`,
  render.js, fftspacing.js, gradcenter.js, chunkfit.js, cardmodel.js,
  cardpipe.js, card.js. No sliders: presets + seed; runs ~8 s (progress in the
  status line; a newer run cancels an older one via `runId`).

## Card report (Python, cardlab/)

The third app moved to Python (Adam's preference for experiments): the
pipeline runs locally and writes card.html plus images, committed so GitHub
Pages serves them (nothing is built on GitHub).

- Setup on the Mac: `python -m venv .venv && .venv/bin/pip install -r
  requirements.txt` (`.venv/` is gitignored). Build: `.venv/bin/python
  build_card.py` (default: presets typical, loud, hard, clean × seeds 1–5,
  showcase typical:1; ~10 s per run). Summaries are cached in
  card/results.json, so only new preset:seed runs are computed; `--rerun`
  recomputes all (do that after any pipeline change). Options: `--presets`,
  `--seeds 1-5,8`, `--showcase hard:2`.
- Style (Adam's): small, readable functions; descriptive names; a few
  comments, no docstrings; factor shared code; lean on vetted libraries
  (OpenCV, scipy, scikit-image / scikit-learn, e.g. their RANSAC) and
  vectorized numpy instead of loops.
- Modules: `params.py` (CardParams dataclass, PRESETS, PARAM_NOTES with
  sources), `geometry.py` (Spiral, Mark, TAU, wrap, smoothstep,
  spiral_points), `model.py` (make_card, Card.groove_height /
  nearest_groove / sound, render → full-res float32 image ~6 s; grain is
  Gaussian-filtered white noise, unlike the JS value noise),
  `lowres.py` (cv2.INTER_AREA downsample, annulus mask, FFT spacing,
  coherence grid + scipy Nelder–Mead), `strip.py` (strip columns by equal
  arc length, cv2.remap sampling in blocks < 32767 wide, demodulation,
  refit: grid start + scipy least_squares with soft_l1 on wrapped
  residuals, lock_trace), `readout.py` (sound), `scoring.py` (truth),
  `pipeline.py` (run_pipeline, summarize), `figures.py` (matplotlib, one
  function per step figure), `report.py` (HTML).
- Sanity check against the JS version: `checks/compare_with_js.sh [preset]
  [seed]` (needs node — on the Mac via nvm in Terminal; ~2 min) dumps the
  Python pipeline's inputs and intermediates and feeds the same inputs to
  each JS function. Results (typical 1–3, loud 1, hard 1, clean 1): FFT
  spacing identical; strip demodulation identical to ~1e-8 (relative),
  except the few hundred columns whose rows leave the 5551² frame (the JS
  model was procedural beyond it; the image clamps); refit equal within
  0.002–0.09 px (hard 1: 0.7 px — different robust losses on a noisy
  card); trace within ~0.002 px rms; sound readout correlation ≥ 0.998.
  The low-res center differs by 0.1–0.4 px (gap at mid radius) because
  JS's pattern search stops early: Python's Nelder–Mead reaches a higher
  |Z| every time (the truth has slightly lower |Z| still, from drift).
  Two Python fixes came out of it: strip sampling uses
  scipy.ndimage.map_coordinates (cv2.remap rounds bilinear weights to
  1/32 px: 0.3% demodulation error), and Nelder–Mead runs over (x, y, mid
  radius) so all three parameters are in px.
- Not ported yet: the gradient-based centers (lines + RANSAC; tilt about
  the hand mark) — step e is a placeholder in the report.
- Results (Python, 5 seeds): typical — low-res center 0.03–0.22 px, trace
  0.40–0.70 px, no wrong groove, sound corr 0.89–0.92; clean 0.98–0.99;
  loud 0.94–0.96; hard trace 1.1–2.7 px, 0–1.9% wrong groove, sound
  0.75–0.81. Lower sound correlation than the JS version (0.93–0.96 for
  typical): the grain spectrum differs (white noise blurred vs value noise).

## Card page (card_js.html, frozen)

- `makeCard(preset, seed)` (cardmodel.js): procedural height `sample(x, y)`
  at any full-res point (frame 5551², ~200 ns/sample), so the low-res image
  and the strip come from the same card. Idealized on purpose (the user's
  choice): flat card at height 0, grain only — no warp, bend, slow height
  drift, dust, scratches, banding or damage (all removed; add back one at a
  time later). Groove centerline r = bθ + drift(θ) + wobble(arc length).
  Hill-and-dale sound: cut depth D = D0·(1 + a(s)), round stylus (parabola,
  width W0 = 0.6 S at D0), surface = min(0, stylus) over the 3 nearest arms,
  so where a < −1 nothing is cut (the groove disappears) and deep cuts are
  wider. Heights in units of D0; grain rms = P.grain × the groove's rms.
  `audioAt(θ)` is the sound; `depthAt(θ)` the cut depth incl. the end fade.
  `toIdeal` is the identity (kept for `truthAt`). Presets typical / loud /
  hard / clean in `CARD_PRESETS`; card.js `PARAM_INFO` lists each value's
  source. Keep both in sync.
- Low res (cardpipe.js `lowResStage`): area-averaged render (2×2 samples per
  pixel, grain averaged over 6×6 via `sample(x, y, box, gss)`); soft annulus
  mask from the hand marks, minus mean, unit rms (no high-pass, no clipping).
  Spacing: FFT radial-profile peak within ±10% of nominal (falls back to
  nominal if > 3% off or on the edge; the harmonic sum failed here, −11%).
  Center/spacing/phase: `spiralCoherence` maximizes |Σ v e^{−i(r/b−α)}| (grid
  ±60 px about the mark, step 0.15 S, then pattern search on x, y, b); phase
  = arg. The gradient-line center fails here (optional comparison only;
  `gradientCenter(..., tang, eps, start)` — eps and start are optional
  (default 2 px and none, so the other pages are unchanged); card.html
  passes 0.5 and 0.4 S and the hand mark as start, so the first pass is
  already tangentially blurred about it). It fails mainly because the
  hill-and-dale sound varies the depth along the groove: gradients get a
  big along-groove component (clean card, exact derivatives: median line
  misses the true center by ~90 low-res px with sound 0.4, 1.9 px with no
  sound).
- Full res: `stripColumns` (every 3 px of groove), `demodPass` (rows ±S,
  linear detrend, cos² window, Z per column), `unwrapOffsets` (o = −S
  arg(−Z)/2π; optional smoothing and unwrapping), `refitGeometry` (grid over
  β, ex, ey on wrapped residuals, then wrapped IRLS), `lockTrack` (reference
  = model + amplitude-weighted circular mean of the residual, within ±S/2;
  trace = nearest groove; default smoothing 48 px, reference 300 px),
  `readoutPass` (land at ±S/2 minus bottom, ±3 px each, over its 300-px
  average, minus 1; floored at −1, 0 where the average is faint), `truthAt`.
  Dropped: unwrapping-based refit and lock (slips accumulate on hard cards),
  a narrow second demodulation pass (noisier).
- Layout: one column of large step views (900 px), each with a sticky panel
  beside it holding that step's explanation, settings and numbers. Steps:
  (a) masked low-res input, (b) FFT, (c) radial profile, (d) coherence grid,
  (e) gradient-line center (if on), (f) detail, (g) all columns' offsets mod
  S with the refit model and the true geometry (red), (h) strip, (i) offset
  plot, (j) per-turn error, (k) sound readout vs truth. Settings carry
  `data-stage` (render, low, strip, refit, track, readout, draw) and re-run
  from that stage (`runFrom`); each stage clears its own output first so an
  interrupted run is redone. Low-res settings are in spacings
  (`LOW_DEFAULTS`); full-res smoothing in px (converted to columns).
- Results (5 seeds): typical — center 0.02–0.17 px, trace 0.28–0.57 px, no
  wrong groove, sound corr 0.93–0.96; loud (7.6% not cut) 0.93–0.98; hard
  (grain ×2, drift 6 px) — trace 1.05–2.6 px, 0–1.8% wrong groove, sound
  0.80–0.87; clean 0.97–0.99. Node benchmarks: concatenate the scripts with
  `const N=1024` and call the functions directly (all are DOM-free).

## Radius offsets (both pages)

`p.offsets` (sliders off20/40/60/80, −1..1 × spacing): the curve is
r(θ) = bθ + δ(θ), δ piecewise linear in θ with knots at 20/40/60/80% of the
way from start to end radius (0 at both ends): continuous, kinks in slope —
a model of a real, imperfect spiral. `makeOffset` in render.js; renderSpiral
searches two arms each side when offsets are on, and uses the arm's local
slope for the perpendicular distance. Chunks and end caps stay on the ideal θ
(`weight` and caps get the ideal radius). With all offsets 0 the image is
bit-identical to before. "Truth" on the center page is still the ideal
spiral's center and phase.

Note the local spacing changes by Δoffset over 20% of the θ range, i.e. over
0.2 × (number of turns) turns, so the same offsets distort a spiral with
fewer turns (larger spacing) much more.

Robustness (8 random offset sets, uniform in ±amp at each knot):
- Spacing estimate, spacing 10 (15 turns): ±0.1 → 0.4% median error,
  ±0.25 → 1.1%, ±0.5 → 15% (breaks), ±1 → 40%. Spacing 20 (7.5 turns): ±0.1
  → 2% median but up to 70%, ±0.25 → ~70% (wrong peak). Rings similar.
- Center page (noise 0.3): center stays good (start 2 median 0.02 → 0.19 px
  from ±0 to ±1; combined 0.04 → 0.69 px). Phase isn't well defined for an
  offset spiral (local phase shifts by 2π·δ/spacing): combined phase error
  ±0.1 → 10°, ±0.25 → 33°, ±1 → 76°. RANSAC then rejects chunks whose local
  phase differs (agreeing 52/52 → 25/51 at ±1), and the shared-phase joint
  fit ends up worse for the center than start 2.

## Spacing page: key design points

- `N = 512` is the internal resolution of all canvases and the FFT size. The
  FFT is radix-2, so `N` must stay a power of two. Canvases are displayed at
  400×400 and cropped (`.crop`) to their right 2/3; the full image is still
  drawn and transformed.
- The spiral is not stroked with canvas paths. `renderSpiral(p, center, out,
  weight?)` computes each pixel from its distance to the nearest arms
  (r = bθ, b = spacing / 2π), writing 0..1 floats into `out`. `p.phase` is in
  radians. The optional `weight(n, ra, ang)` scales each arm's contribution;
  the center page uses it to keep only chunks.
- Smooth edges use a Gaussian CDF (erf) profile; "Edge transition" is the
  10–90% width. Deliberate: hard or sigmoid edges have harmonics above Nyquist
  that alias into arcs at the FFT's edges/corners; ~2–3 px of erf transition
  removes them.
- `drawProfile` bins FFT pixels by round(distance from DC) (tables built once)
  and plots the mean of `mag / max` per bin, independent of the contrast slider.
- `computeHarmonicScore`: for each candidate fundamental radius rho, sum over
  harmonics of (peak minus the mean of the half-way troughs), divided by
  sqrt(K) (a plain average picks a higher harmonic, a plain sum picks tiny
  rho). The profile is blurred first (`H_BLUR` = 1.5 bins; ~3× lower rms error
  for rings, 3 bins breaks large spacings). Tested error ~0.2–0.65% rms.
- Overlays are drawn only on the visible canvases, never into `img`.
- Gradient-line center (checkbox, off by default; `gradientCenter`): blur
  σ 1, Sobel; lines along the gradients, binned by orientation (64 bins over
  180°); keep the strongest "Lines per orientation" (150) per bin above a
  global floor (70th percentile of magnitude), weight = magnitude − floor.
  RANSAC over pairs (`ransacCenter`): first line ∝ weight, partner bin ∝
  count · sin²(angle), uniform within the bin; each candidate is spiral-
  corrected (lines shifted by b·(−sin α, cos α) about it; not for rings) and
  scored by Σ w·min(d², 2²) over a subset of lines; the best is refined by the
  weighted intersection of its inliers (3×). Then the tangential-blur loop
  (`tangentialBlur`, σ 3 px): blur along circles about the current center
  (a gather along the local tangent, bilinear, step shrinks near the center),
  recompute lines and center, until it moves < 1 px (≤ 5 rounds; ~1 px is
  plenty for 1/r weighting). Groundwork
  for weighting every turn equally (1/r about this center) before the FFT.
  Tests (off-center spirals, 3 positions): clean 0.02–0.05 px; noise σ 0.3 /
  0.6 / 1.0: without tangential blur ~4–8 / 8.5 / 20–27 px, with it ~0.3–0.5 /
  1.8–1.9 / 3.6–4.7 px (the tangential blur is the big win; RANSAC alone ≈ the
  Hough vote it replaced). Speed (headless Chromium): first RANSAC 600
  candidates × 1500 scoring lines, later rounds 150 × 1000 (they start
  close); the spiral correction uses vector math, no trig.
  Per later round: tangential blur ~60 ms, gradients + lines ~40 ms, RANSAC
  ~12 ms (was ~210 ms at 600 × 3000); ~0.6 s total with 5 rounds (was ~1.6 s).
  Accuracy about the same (noise 0.3: median 0.6–0.8 px, was 0.3–0.5; noise
  1.0: 2.3–3.8 px, was 3.6–4.7). Under noise the loop still usually runs all
  5 rounds: the estimate keeps moving by > 0.2 px.
- "Advanced peak search" (checkbox, default on; `computeHarmonicScore({
  advanced, vMin, target })`): search only spacings within ×0.5–2 of the
  target spacing (the true spacing stands in for a device's nominal one;
  dashed lines on the plot), coarse to fine down to "Expected spacing
  variation" (default 10%), and warn when the answer is at the window's edge.
  Off: the original single sharp stage over all spacings. Benchmark
  (spiral, 10 offset sets, median/max %): spacing 20, offsets ±0.1: original
  2.1/70 → advanced 0.55/1.1; ±0.25: 70/71 → 2.5/12. Perfect spiral costs
  0.3–1%. Beyond ~±30% local variation it still fails, but within ×0.5–2;
  such failures land on strong local peaks inside the window, so the edge
  warning rarely fires and is not a reliable failure detector.
- Turn weighting (select: none / 1/√r / 1/r; `evenWeight(src, c, spacing,
  ex)`): multiply the image by max(r, 2·spacing)^−ex about the gradient-line
  center (computed even if not shown), normalized to mean 1, before the FFT
  (`computeFFT(p, src)`). Estimated vs true center gave identical results.
  Test (advanced, vMin 10%, 10 offset sets, off-center spiral; median / max
  %): 1/r makes mild offsets worse (±0.1: 0.37 → 0.87, 0.42 → 1.57) but cuts
  the worst cases; 1/√r keeps the medians about as good as none (sometimes
  better: spacing 10 ±0.25 0.80 → 0.48; noise 0.3 1.35 → 0.85) and cuts the
  worst cases most (spacing 20 ±0.25: max 11.6 → 4.0, with noise 10.9 → 3.7;
  spacing 10 ±0.5: 14.6 → 8.2, with noise 24 → 12.8). Spacing 20 ±0.5 stays
  ~16% / 35% for all. Default: 1/√r (the center costs ~0.2–0.4 s per frame).
- Tried and rejected: tangential blur (σ 3, along circles about the
  gradient-line center) on the FFT input. Test (advanced 10%, 1/√r, radii
  50–200 and 30–100, spacing 10/20, noise 0–1.5, 6 patterns): differences
  within ±0.2 percentage points either way, slightly worse with no noise.
  The FFT is already noise-tolerant (errors ≤ ~2% even at noise 1.5).
- Coarse to fine (`vMin`, "Expected spacing variation" slider): stages smooth the profile in log radius (σ = v/2), use harmonics
  k ≤ 1/(4v), halve v each stage from max(0.3, 3·vMin) and search within ±v
  of the previous answer; the final stage is at vMin (0 → the sharp score).
  In advanced mode the coarse stages always run first, even at vMin = 0,
  which removes most wrong-peak failures at no cost for a perfect spiral. With radius offsets,
  refining past the real variation locks onto one region's spacing (e.g.
  spacing 20, offsets ±0.25: 0.9% at v = 0.3 → 9.9% at v = 0), so vMin
  should match the expected variation. Benchmarks (10 offset sets, median /
  max error): spacing 20, offsets ±0.1 (local ±13%): vMin 0 → 2.1/5.8%,
  10% → 0.55/1.1%; offsets ±0.25 (±33%): 0 → 9.9/12%, 15% → 1.6/2.9%.
  Cost on a perfect spiral: up to ~1% at vMin 15% (spacing 20), ~0.0–0.5%
  otherwise. Beyond ~±33% local variation nothing works well; the FFT's
  pixel-weighted mean spacing itself then differs from the target.

## Center page: pipeline

1. **Chunks** (`center.js`): each is two seeded uniform numbers (position u,
   extent fraction v), so chunks stay put while sliders move; "New chunks"
   bumps the seed (and redraws the noise). A chunk is a θ interval of width
   v × Max extent, placed uniformly by arc length (s = bθ²/2, the same
   approximation as the end caps). Chunk ends use the line-edge profile.
2. **Noise**: a fixed Gaussian field per seed × Noise sigma, added to the
   chunk image; then **Denoise blur** (Gaussian, σ 1). Weights are clamped
   to 0..1.
3. **Components** (`labelComponents`): a single threshold (0.45) after the
   tangential blur, 8-connected (the function also supports hysteresis,
   hi > lo, used before the blur existed: high 0.5 / low 0.4); drop
   components below Min component px, number them by size (#1 = largest),
   grow 2 px into soft-edge pixels (only those ≤ the threshold).
4. **Per-chunk fit** (`fitChunk`): weighted Kåsa circle → geometric circle →
   circle-center correction (below) → IRLS: each round assigns every pixel to
   its nearest arm (pixels of one component may sit on different arms) and
   sets its Tukey weight (cutoff 0.5 × spacing), then Levenberg–Marquardt
   over center + phase with the spacing known (the assumed spacing: true ×
   (1 + Spacing error %); truth uses the true spacing). Outputs center,
   phase, θ range (core inliers), inlier fraction (within cutoff/2), loss,
   approximate covariance (shape reliable, size not).
5. **Shared start** (`fitComponents`, default on): start 1 = median x and y
   of the corrected circle centers of chunks reaching Min extent; fit all
   from it; start 2 = median of the kept fits' centers; fit all again from
   start 2. A fit is kept if extent ≥ Min extent (30°), inlier fraction ≥
   0.65, and its center is at least one spacing from its own pixels.
6. **Combine** (`combineChunks`, default on): RANSAC/MSAC over chunks.
   Hypotheses: each kept chunk's fit, plus a joint fit (`fitJoint`, one
   center + phase) of every pair of kept chunks (all pairs up to 20 chunks,
   else 190 sampled), on pixels subsampled to ≤300 per chunk. Agreement of
   chunk k: Δk = its loss with the hypothesis's center and phase fixed minus
   its loss under its own fit (pixel space, not center distance — a genuine
   chunk that slid along its flat valley still fits the truth almost as
   well). Score Σ nk · min(Δk, τ), τ = 0.04; best wins; then a joint fit over
   all agreeing chunks, repeated until the agreeing set is stable.
7. **Cost map** (`costMap`, deferred after each frame): for the selected
   chunk, loss vs. candidate center on a 128² grid, phase solved per point.

## Center page: what the experiments showed

- Chunk model (select; `combineChunks` opts.model): 'shared' (default),
  'phase' (A: shared center, each chunk its own phase), 'local' (B: also its
  own spacing, penalty (b − b0)²/(tol·b0)², "Spacing tolerance" ±10%;
  `fitLocal` = linear regression of r on the unwrapped angle for a fixed
  center; `fitJointLocal` alternates that with LM over the center). Test
  (noise 0.3, 6 sets, offsets 0/±0.25/±0.5, chunks around or one quadrant):
  A accepts all genuine chunks and beats 'shared' whenever offsets are
  present; B is worse everywhere (center 0.35–0.72 px; local spacings off
  3–13%) — the penalty is swamped by correlated pixels. Start 2 (median of
  per-chunk fits) was the best center whenever offsets are present
  (0.10–0.25 px).

- Tangential blur before components ("Tangential blur σ", default 3 px, 0 = off): the
  gradient-line center from the raw noisy image, then after the denoise blur
  a blur along circles about it. 8 chunk sets / noise level: no effect at
  noise 0.3; at 0.6 fewer bad per-chunk fits (8 → 3) and per-chunk median
  0.51 → 0.36 px; at 1.0 it cleans up segmentation hugely (components 1038 →
  127 at σ 3 → 75 at σ 5; kept fits > 5 px off 107 → 18 → 6; per-chunk
  median 46 → 1.0 → 0.8 px; start 2 4.5 → 0.35 → 0.16 px). The combined
  (RANSAC) center was already ~0.1 px and stays so; its phase got slightly
  worse (median 0.95° → 1.3° at noise 1). The gradient-line center itself is
  poor on sparse chunk images (median 6.7 / 9.4 px at noise 0.6 / 1.0), but
  the blur tolerates that far from the center.

- b = spacing / 2π. A chunk constrains the *direction* to the center well
  and the *distance* poorly (only curvature): the cost valley points at the
  center. A distance error δ gives a phase error of δ/b radians. A spacing
  error ε leaves the center alone and goes into the phase, ≈ θ·ε radians.
- Accuracy depends mostly on angular extent (σ 0.3, width 4: median distance
  error <20° ~50 px, 20–45° ~3 px, 45–90° ~0.5 px, >90° ~0.1 px). The clean
  ~0.01 px results rely on anti-aliased edges; binary pixels give ~2 px.
- Denoise blur is the big win under noise (σ 0.6: median 206 px → 0.9).
  (Before the tangential blur) hysteresis low 0.4 beat 0.3 (blurred noise
  percolates) and 0.5. With the tangential blur, a single threshold 0.4 gave
  the same results as hysteresis 0.5/0.4 at noise 0.3/0.6/1.0, and 0.4–0.5 is
  a safe range (0.3: junk merges at noise 1; 0.6: arcs break) — hence the
  single "Threshold", default 0.45. Tukey loss
  helps only slightly; cutoffs ~0.25 × spacing reject good fits.
- Per-chunk failures that remain have the same inlier fraction and loss as
  good fits (they slide along the flat valley), so per-chunk outlier tests
  can't catch them.
- Components spanning two arms fit *better* than single-arm ones (median 0.11
  vs 0.25 px): the nearest-arm assignment handles them.
- Circle-fit correction: a circle fitted to a spiral arc has its center ≈ b
  sideways, along (−sin α, cos α) for a pixel at angle α (exactly
  b(r²+b²)/(r²+2b²); radially only ≈ b²/r). Subtracting b × the weighted mean
  of that vector (one pass; a second moves it ~0.01 px) cuts circle-center
  error ~1.7 → ~0.2 px and removes the sideways bias of start 1 when all
  chunks lie on one side.
- Start 2 alone is within ~0.03–0.08 px (max 0.2) of the truth when chunks
  surround the center, even at noise 0.6.
- One-sided chunks are ill-conditioned: their valleys are nearly parallel, so
  distance errors add instead of cancelling, and under noise there is an
  unexplained mean pull of the estimate toward the chunks (0.4–2.7 px). The
  combined fit's shared phase helps: NE + SW quadrants at noise 0.6, center
  0.11 → 0.02 px and phase 3.4° → 0.9°; NE quadrant median 0.37 → 0.11 px,
  but one set in eight still ended ~20 px off.
- Genuine chunks' Δ at the combined fit: 99% ≤ 0.012, so τ = 0.04 rejects
  almost none (2 of 561 in tests). Earlier "false" rejections were tiny
  fragments whose fit collapsed onto the speck itself — hence the
  center-at-least-one-spacing-away rule.
- Keep line width + noise fringe well under spacing/2: pixels farther than
  that from their centerline are assigned to the neighbouring arm.

## Gotchas

- Line width's slider max is set to the current spacing on every render
  (both pages), so changing spacing may clamp the width.
- Element ids are shared between HTML and the `ids` list in each page
  script, and must be unique: e.g. the spacing page's canvas is
  `id="spiral"`, so its rings/spiral checkbox is `isSpiral`.
- `labelComponents` grows only into pixels at or below the low threshold;
  growing into above-threshold pixels picked up dropped noise specks between
  arms, which broke θ ranges and fits.
- The center page recomputes everything each frame (renders, components,
  three fit passes, combination); the cost map is drawn just after, and
  skipped while another render is queued (e.g. dragging).

## Checking changes

Node on the Mac is available through nvm in a Terminal bash shell (not in Claude's Cowork Linux VM, which has its own node). Syntax-check on the
Mac with JavaScriptCore:

```sh
/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc -e "checkSyntax('render.js'); checkSyntax('spacing.js'); checkSyntax('chunkfit.js'); checkSyntax('center.js'); print('ok')"
```

For logic/benchmarks, load a page in headless Chromium (e.g. Playwright) and
call the page's globals in `page.evaluate`: set `seed`, call
`drawChunkPositions()`, `drawNoise()`, `renderSpiral(p, center, part,
makeChunkWeight(p))`, build `noisy`, then `labelComponents`,
`fitComponents`, `combineChunks`, and compare with `center` / `p.phase`.
Test-only setups (e.g. masking chunks to a wedge) can be done there without
adding controls. To see a page, take a headless Chrome screenshot:

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --disable-gpu --hide-scrollbars --window-size=1150,1000 \
  --screenshot=/path/to/shot.png "file://$PWD/center.html"
```

## Handoff (Nov 2026, from a Cowork session)

State: all work is committed locally; `main` is 6 commits ahead of
origin/main (card page work 9eecd25..9406574, plus this note) — not yet pushed.

Open experiment — "gradient tilt" center for step e (JS, not
committed; work in progress saved, gitignored, in
`Claude outputs/cardpipe_tilt_wip.js`, with the node harness
`Claude outputs/tilt_test_harness.js`; run harnesses by concatenating
chunkfit.js, render.js, fftspacing.js, gradcenter.js, cardmodel.js,
cardpipe.js and the test with `const N=1024` prepended):
- Idea (Adam's): at each pixel take the gradient's component perpendicular
  to the direction to the hand-marked center H, and blur it along circles
  about H. Implemented as: P = g_t·g_r, Q = g_r² blurred tangentially;
  τ = P̃/Q̃ ≈ (−b + e_x sin α − e_y cos α)/r for a true center H + e; a
  weighted least-squares fit of r·τ gives e; repeat with H ← H + e.
  Variants in the WIP: reference direction = the spiral's normal about H
  (SPIRREF), κ correction 1 − ⟨g_t²⟩/⟨g_r²⟩ (KAPPA), radial pre-blur
  (RADB), exact FFT gradients instead of Sobel (SPECTRAL).
- Findings so far (clean card, seed 3, hand mark 12 px off, full-res px):
  with no sound it converges in one pass to 0.01–0.03 px (drift doesn't
  matter). With sound it converges in 1–2 passes but to a biased point
  (~1.9 px at sound rms 0.4; bias ∝ sound², 0.07 px at 0.1). Not from the
  mask, radial cross terms, pitch coupling or κ. Residual r·τ vs α at the
  true center shows a strong 4-fold (90°) pattern of ±7 px → Sobel's
  direction error vs orientation acting on the along-groove (sound)
  gradient, leaking ~D'²·δ(α). Next test (was running when stopped):
  SPECTRAL = 1 (exact derivatives).
- The RANSAC line method (Part 1) fails here for the same root cause: the
  sound makes along-groove gradients (clean card, exact derivatives: median
  line misses the true center by ~90 low-res px at sound 0.4, 1.9 px with
  no sound). Adam's future idea: RANSAC over N > 2 lines.

Done since: the card pipeline is ported to Python (cardlab/, card.html is
the generated report; the JS page lives on as card_js.html). Next: port the
tilt center to cardlab and redo the test with exact gradients (e.g.
spectral derivatives or scipy.ndimage.gaussian_gradient_magnitude-style
Gaussian derivatives), then the line method with skimage.measure.ransac.
