# CLAUDE.md

Small static browser site of spiral experiments: `index.html` links to each
experiment page. No build step, no dependencies — open `index.html` directly
(`open index.html`). Pages are plain `<script>` tags (no ES modules) so they
work from `file://`. Deployed to GitHub Pages on every push to `main`.

New session? Read `notes/context.md` first: the project's story, goals,
Adam's preferences and open questions.

## Files

- `index.html` — landing page linking to the three experiments.
- `render.js` — shared by all pages: `N` (512, or `SPIRAL_N` if a page sets
  it first: card.html uses 1024), `erf`, `edgeStep`, `renderSpiral`,
  `gaussianBlur`, `toImageData`. Defines globals, so page scripts must not
  redeclare them (e.g. no `const N` in a page script).
- `spacing.html` / `spacing.js` — ring-spacing experiment: spiral (or rings)
  on the left with a simulated hand mark, log-magnitude 2D FFT on the right,
  radial profile and its smoothed peak (the spacing) below, then the
  coherence map (center and phase).
- `fftspacing.js` — the FFT and spacing estimate, no DOM: FFT tables,
  `computeSpectrum(src, removeDC, useWindow)` (fills `mag` and `profile`),
  `annulusMask`, `normalizeInMask`, `fftInput`, `profilePeak` / `peak` /
  `peakProfile` (as cardlab/lowres.py), and `evenWeight` (only for the
  frozen cardpipe.js). Used by spacing.js (which keeps the drawing) and
  cardpipe.js.
- `coherence.js` — center and phase from the spiral coherence map, a JS port
  of `cardlab/lowres.py` find_center (used by spacing.html): `fft2(re, im,
  M)` (radix-2, any power-of-two M, tables cached per M), `coherenceMap`
  (three N² FFTs, circular, kernel reach = marked outer radius + 2 spacings,
  at most N/2 − 1; fills `zRe`/`zIm`/`zAbs`),
  `mapPeak`, `mapAt` (bilinear Z), `symmetryCenter` (point symmetry of the
  map near its peak: self-convolution of the windowed zero-mean |Z| on an
  M×M crop, M = power of two ≥ 6σ, at most N; max at twice the center),
  `coherenceCenter(src, spacing, mark, windowFraction = 1 / 8, search = 1.5)`
  (σ = mark.rOuter / 8, center within 1.5σ of the peak; phase = arg Z at
  the center). No DOM. Bright arms, so Z has no minus sign (Python's
  grooves do). Same rules as cardlab's find_center.
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
  `gradientLines`, `ransacCenter`, …), used by the center page and the
  frozen card_js.html (no longer by the spacing page); no DOM, uses
  `N` and `gaussianBlur` from render.js. The tangential blur follows the
  circle (tangent plus a second-order inward term u²/(2r)), so curved rings
  aren't shifted inward.
- `chunkfit.js` — the estimation; no DOM, uses only `N` from render.js: `labelComponents`, `fitChunk`, `fitComponents`, `combineChunks`
  (with `chunkData`, `evalLoss`, `phaseFor`, `fitJoint`), `costMap`, plus
  `mulberry32`, `lm`, `solve`. Scripts load in the order render.js,
  gradcenter.js, chunkfit.js, center.js (spacing page: render.js, fftspacing.js,
  coherence.js, spacing.js).

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
- Colors (Adam's: one meaning everywhere in card.html; `figures.COLORS`, the
  report's span classes and its color key): white input (hand mark,
  nominal), cyan low-res estimates, yellow refit, orange path (trace) and
  read-out sound, green true groove and true sound, pale green true geometry
  (center, spacing, ideal spiral), magenta wrong groove (with "none on this
  card" when there is none), grey raw measurements (the wedges), violet
  annotations (detail-spot boxes, cartoon labels, the rectangle's rows and
  wedge edges). Red is not used; blue was the sector method while it ran
  beside the strip. Add a new color
  rather than reuse one with another meaning.
- Constants (Adam's, for a paper later): prefer round, justifiable values
  over fitted decimals, e.g. a peak at least 2× its background (ln 2), not
  0.65; a window from halfway to zero frequency to halfway to the second
  harmonic (0.5–1.5 × the expected radius). Find the range empirically on
  the synthetic experiments, then pick the round value inside it, check it
  still separates the cases, and record both the measured range and the
  reason in the docs.
- Full-res stage = the unrolled rectangle and its wedges (`wedges.py`,
  Nov 2026, Adam's idea; replaced the strip, which stays in `strip.py` for
  the experiments and shared helpers): columns along the low-res spiral at
  equal steps in theta (Adam: the card turns at a constant rate, so theta
  is time), 1 px of groove apart on the outermost turn (~17 k per turn; no
  turn undersampled, so bilinear needs no prefilter); readout lengths are px
  at the middle turn (`Unrolled.step`). Rows = radial offset; rows
  ±S/2 cover every pixel once. Never stored: `Unrolled.pull` samples a block
  when needed. Wedges of 1/40 turn; per column one untapered period of rows
  × e^{−2πid/S}, summed per wedge. Pass 1: rows about the spiral →
  `refit_wedges` (the strip's refit on ~1500 wedge offsets, no resampling)
  → path = model + offsets within ±S/2. Pass 2: rows centered midway between
  the lands, (groove + mean of the turns either side) / 2 (on the groove
  itself was worse; with true offsets the rule gives 0.158 vs 0.16 px
  measured). Path = wedge offsets as phasors |Z|e^{iφ}. 20 cards: path
  medians 0.15 / 0.16 / 0.81 / 0.08 px (typical / loud / hard / clean) vs
  the strip's 0.59 / 0.68 / 1.32 / 0.56, sound the same; 0.37 s vs 0.54 s.
  Why the strip was worse: its ±S cos² window takes in the neighbouring
  turns, which drift differently, and pulled the path ~10% toward the
  spiral. card.html shows only the wedges; its section 4 and procedure
  P3.6b list the alternatives tried with numbers (strip, strip with ±S/2
  or two-period windows, per-pixel sectors, re-centering on the groove,
  per-wedge tilt). Experiments: unrolled_wedges.py, strip_window.py,
  cell_coherence*.py, cell_error_breakdown.py. `Run.strip` is now just the
  rectangle's columns (a Strip with no demodulation), the frame of
  `Run.model` / `trace` / `score`.
- Modules: `params.py` (CardParams dataclass, PRESETS, PARAM_NOTES with
  sources), `geometry.py` (Spiral, Mark, TAU, wrap, smoothstep,
  spiral_points), `model.py` (make_card, Card.groove_height /
  nearest_groove / sound, render → full-res float32 image ~6 s; grain is
  Gaussian-filtered white noise, unlike the JS value noise),
  `lowres.py` (cv2.INTER_AREA downsample, annulus mask, FFT spacing,
  spiral coherence map by FFT + center of point symmetry), `wedges.py`
  (the full-res stage, above), `strip.py` (the former stage: strip columns by equal
  arc length, cv2.remap sampling in blocks < 32767 wide, demodulation,
  refit: grid start + scipy least_squares with soft_l1 on wrapped
  residuals, lock_trace), `readout.py` (sound), `scoring.py` (truth),
  `pipeline.py` (run_pipeline, summarize), `figures.py` (matplotlib, one
  function per step figure), `report.py` (HTML): step e is 16 pre-built
  256-px details (`figures.detail_columns`: evenly spaced turns at golden-
  angle steps, up to 4 replaced by the longest wrong-groove runs;
  `e_detail_00..15.png`, crops clamped to the frame). Step a draws their
  boxes; clicking one (HTML boxes over the image, small script) swaps step
  e. The detail draws trace and truth as polylines over the whole spiral,
  clipped by the axes (consecutive columns are neighbours along the
  groove), wrong-groove columns in magenta. Before step f, a cartoon
  (`figures.offsets_explainer`, `f_explain.png`, also in procedure P3.4):
  toy card with the rectangle's spiral off center, the offsets unrolled, and
  modulo S, with three columns A, B, C followed through all three.
  Steps f0 (`rectangle_turns`: 4 wedges of 5 consecutive turns, stacked so
  they tile) and f0b (`wedges_on_card`) show the rectangle. Step f is two
  panes: f1 pass 1's wedges about the low-res spiral (what the refit sees: the
  low-res center / spacing errors as a one-turn wave and a slope), f2
  (`figures.offsets_vs_truth`, `f_truth.png`) everything minus the true
  spiral: yellow = the refit's remaining error (with a ±1 px zoom below),
  green = the drift; numbers: refit error and drift rms.
- Sanity check against the JS version (covers the low-res stage and the
  former strip, not the wedges): `checks/compare_with_js.sh [preset]
  [seed]` (needs node — on the Mac via nvm in Terminal; ~2 min) dumps the
  Python pipeline's inputs and intermediates and feeds the same inputs to
  each JS function. Results (typical 1–3, loud 1, hard 1, clean 1): FFT
  spacing identical; strip demodulation identical to ~1e-8 (relative),
  except the few hundred columns whose rows leave the 5551² frame (the JS
  model was procedural beyond it; the image clamps); refit equal within
  0.002–0.09 px (hard 1: 0.7 px — different robust losses on a noisy
  card); trace within ~0.002 px rms; sound readout correlation ≥ 0.998.
  The low-res center differed by 0.1–0.4 px (gap at mid radius) because
  JS's pattern search stops early: Python's Nelder–Mead reached a higher
  |Z| every time (the truth has slightly lower |Z| still, from drift).
  Since then the Python center search is a different method (below), so
  that line of the check now compares two methods.
  Two Python fixes came out of it: strip sampling uses
  scipy.ndimage.map_coordinates (cv2.remap rounds bilinear weights to
  1/32 px: 0.3% demodulation error), and Nelder–Mead runs over (x, y, mid
  radius) so all three parameters are in px.
- Spacing error budget (Nov 2026, `experiments/spacing_budget.py`, results
  in `experiments/spacing_budget_results.md`; 6 cards, spacing forced to
  truth × (1 + error)): ±1% no change; ±2–3% the low-res center is up to
  ~10 px off (cards: 95 spacings out, so ~5× less tolerant than the page's
  spirals) and the trace degrades (1–3 px, sound 0.85), though the refit
  recovers center (0.1–0.5 px) and spacing; ±5% hard cards fail, ±10% all.
  FFT within 0.1% → 10–40× margin; a fallback to the nominal is not
  survivable, so an edge peak now fails the card (`lowres.SpacingNotFound`;
  build_card.py records {"failed": ...} and the report lists it; the page
  shows no spacing and skips the coherence center). Also a weak peak:
  prominence (height above the trough line, log magnitude) < ln 2, i.e. the
  peak less than twice its background (first 0.65; rounded for the paper)
  (`min_prominence`, `profilePeak({ minProminence })`): correct peaks ≥ 0.89
  (cards) / 1.08 (spirals), wrong ones not on the edge ≤ 0.41, no groove
  ≤ 0.21 (experiments/spacing_prominence.py). This catches a nominal far too
  large (1.7–2.5 ×), which used to give a wrong spacing silently. Idea (full-res refit on
  hold, Adam): a second strip pass only when the refit corrects a lot.
- Spacing search (Nov 2026, `experiments/spacing_window.py`, results in
  `experiments/spacing_window_results.md`): window ±50% (then of the nominal spacing; now of the expected peak radius, below)
  (`spacing_window`; ±10/20/50% identical), profile smoothing 1.5 bins, now
  1 bin (`profile_smoothing`; cards: 2 ≥ 1.5 ≥ 1 by 0.004% median, spirals:
  1 best or tied, 2 worst under noise; 0 worst on cards), and no
  fallback to the nominal (now not even for an edge peak, which fails): the old
  rule (nominal if > 3% off) turned cards cut at 25.9 / 32.2 px searched
  with the 29-px nominal into 9.5–12.9% errors (peak itself right to 0.08%).
- FFT window (tested Nov 2026, 4 presets × 10 seeds): the soft annulus mask
  is the only window — no Hann on top (it starved the outer turns: spacing
  rms error 0.071 → 0.046 % on typical/loud/clean, peak 11 → 8 bins wide;
  hard about the same, rms 0.21 vs 0.22 %, worst 0.31 → 0.48 %). The mean
  is subtracted inside the mask only (made no measurable difference, but
  keeps the frame outside exactly 0).
- Center search experiment (offline, `experiments/center_search.py`,
  results in `experiments/center_search_results.md`; 32 cards × 10 simulated
  hand marks): computing Z at every pixel with one FFT correlation (spiral-
  wave kernel) and fitting a·J0(2π|c−c0|/S) around the map's peak beat the
  current grid + Nelder–Mead — median 0.07 vs 0.17 px, no failures even for
  marks 100 px off (the grid searches only ±60 px), same ~0.5 s. The gain is
  from using all pixels (NM on all pixels matches it but takes 1.4 s). A
  sparse 0.45-spacing grid + J0 fit is fast but locks onto side rings 3–6%
  of the time. Adopted then: coherence_map (fftconvolve with
  spiral_wave_kernel, reach r_outer + 100 low-res px) → map_peak → J0 fit.
  No search window: the hand mark only places the annulus mask. The
  spacing stays the FFT's. The old grid / direct sums / Nelder–Mead and
  the J0 fit live only in experiments/center_search.py. Report step d
  shows |Z| around the answer; steps renumbered a–j.
- Symmetry center (Nov 2026, `experiments/symmetry_center.py`, results in
  `experiments/symmetry_center_results.md`; 20 cards × 3 marks × aspect
  1, ±1%, ±2%, 3%, low-res image warped by cv2): a card stretched ≥ 1%
  breaks the J0 fit at the peak (59 / 130 / 210 px off at 1 / 2 / 3%: turns
  reach ~95 spacings out, so the bright spot splits into lobes). Now
  lowres.find_center = coherence_map → `symmetry_center` (self-convolution
  of (|Z| − window mean) × Gaussian window σ = `symmetry_window` 10
  spacings about the peak, crop ±3σ, ~7 ms; max at twice the center,
  parabola) → phase = arg Z there (`map_at`, bilinear). Typical / loud /
  clean: 0.16–0.30 px median at any stretch ≤ 3% (none > 1 px); unstretched
  0.28 vs J0's 0.04 px, fine since the refit searches ±1.5 spacings and
  fits the center (Adam: no need for sub-pixel here). σ 3 handles only 1%.
  Now σ = r_outer / 8 (≈ 12 spacings; was 0.12 × r_outer), search ±1.5σ.
  Hard cards: ~0.8 px unstretched, 1 of 5 fails at 2%. The full-res refit
  has no stretch term yet (a 1% stretch moves outer turns ±28 px).
- Gradient-based centers dropped (Adam's decision, Nov 2026): the spiral
  coherence map wins on every count we tested. RANSAC on gradient lines
  (Part 1) missed by 20–200 px on these cards (JS tests): the lines are
  extrapolated 300–500 px on a ~5.4-px pattern, and the hill-and-dale sound
  gives the gradients a big along-groove component (clean card, exact
  derivatives: median line misses the true center by ~90 low-res px at
  sound 0.4 vs 1.9 px with no sound), so only 2–4% of lines agree on any
  point. The "tilt" variant (gradient component across the direction to the
  hand mark, blurred along circles, sine fit) converged but stayed ~1.9 px
  off at sound 0.4 (bias ∝ sound², likely Sobel's orientation error on the
  along-groove gradient; exact derivatives untested). Even if fixed, both
  use the same pixels less directly than Z. Not in the procedure or report;
  card_js.html (frozen) still has the line method as an option. Possible
  future idea (Adam): RANSAC over N > 2 lines.
- Sound readout window (Nov 2026, typical, 5 seeds): ±1/2/3/4 px → corr
  0.875 / 0.886 / 0.896 / 0.902; default still ±3 (±4 not adopted yet).
- Test sound (Nov 2026, Adam): a function of theta, not arc length (the
  card turns at a constant rate, so a frequency's wavelength grows with r);
  `sound_wavelengths` 15–300 px are at the mid radius.
- Card model (Nov 2026): the groove's lateral wobble (0.3 px rms, 200–3000
  px along the groove, assumed) was removed: results unchanged within the
  seed-to-seed spread (trace −0.01–0.03 px). Drift vs. the real card
  (Tomaz's images 21 / 26, groove-mask centroid per turn vs. his fitted
  spiral): 2.9 / 3.5 px rms, extremes −7.8..+4.7 px; neighbouring turns
  uncorrelated, while along a turn it changes ~1.5 px per 1200 px. The
  model's drift was 2 px rms with periods 0.7–12 turns (too slow from turn
  to turn); now 3.2 px rms (hard 5), periods 0.3–1 turn, 60 waves (corr ~0
  one turn apart, ~1.6 px median change per 0.06 turn). Effect: refit
  center 0.03–0.18 → 0.09–0.33 px, trace 0.39–0.63 → 0.54–0.83 px rms,
  sound corr ~0.01–0.02 lower on typical/loud/clean; hard cards easier.
- Tried and dropped (Nov 2026): a second strip pass along the first
  refit's spiral, refit again. Yellow's one-turn wave dropped ~0.14 →
  ~0.01 px but the center didn't improve (20 cards: median 0.175 → 0.168
  px, better on 9 of 20); drift-limited. `figures.offsets_mod_spacing`
  still takes the strip and model to show.
- Results (Python, 5 seeds, symmetry center; J0 fit before it gave
  0.01–0.16 px and the same trace and sound): typical — low-res center
  0.14–0.35 px, refit 0.09–0.33 px, trace 0.54–0.84 px, no wrong groove,
  sound corr 0.89–0.91 (drift 3.2 px from Nov 2026; before: trace
  0.39–0.63, sound 0.89–0.92);
  (results before the drift change:) clean 0.98–0.99; loud 0.94–0.96; hard center 0.3–2.0 px, trace
  1.1–2.7 px, 0–1.9% wrong groove, sound
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

- Same pipeline as cardlab's low-res stage (Nov 2026), all in fftspacing.js:
  a simulated hand mark (`handMark` in spacing.js: true center + "Hand-mark
  error" × fixed normal draws `noiseField[0..1]`, radii ±1% from
  `noiseField[2..3]`), the soft annulus mask (`annulusMask`, ramp 1
  spacing), `normalizeInMask`, 1/√r about the mark with the mask as the only
  window (`fftInput`; no Hann), and the spacing as the peak of the profile
  smoothed by 1 bin within 0.5–1.5 × the expected peak radius N /
  target, i.e. ±50% in frequency (`profilePeak({ target,
  window, blur })` → `peak` = { rho, spacing, measured, lo, hi, edge }; sub-bin
  position: the trough line (profile at 0.5 and 1.5 × the peak bin)
  subtracted from the 5 bins around the peak, vertex of a least-squares
  parabola (cardlab `peak_without_slope`; cards 0.049 → 0.023 % median,
  spirals at spacing 40 1.72 → 0.51 %, varying spacing slightly worse; a line
  through valley bottoms tried instead: deepest point ≈ the same, first dip
  fragile, stops on ripple: 3.5 vs 1.0 % at spacing 40 with noise); a
  peak on the window's edge → spacing NaN: warning, coherence skipped). The coherence map
  runs on the masked, normalized image. The plot draws the smoothed profile
  (`peakProfile`) in red only inside the window (dashed lines).
- Removed in Nov 2026 (procedure Part 1, steps 1 and 5): the harmonic-sum
  score with its coarse-to-fine "Advanced peak search" and "Expected spacing
  variation" (replaced by the profile peak so both pipelines use one method;
  on drawn spirals it was ~2–3× more accurate when the local spacing
  varies, e.g. spacing 10 ±0.25: 0.83 vs 1.62% median, and at spacing 40:
  0.22 vs 1.99%), and the gradient-line center with its controls (lines per
  orientation, strength floor, tangential blur, show blurred image): too
  unstable on realistic (simulated) card data. gradcenter.js stays for the
  center page and the frozen card_js.html. Also removed: "Subtract mean",
  "Hann window". Tests: mask beat the old no-mask + Hann + ×0.5–2 pipeline
  everywhere (perfect spacing 20: 0.83 → 0.08%); Hann on top of the mask
  hurt; ±10/20/50% windows identical; profile smoothing 0 better at spacing
  10, worse at 20. Profile peak now (8 offset sets): perfect spacing 5–20
  0.05–0.5%; spacing 40 2%; offsets ±0.1 0.9%, ±0.25 1.6–2%; fails (> 20%)
  at spacing 20 ±0.5 and with under 2 turns (as the harmonic sum did).
- Search window in frequency (both pipelines, Nov 2026): 0.5–1.5 × the
  expected peak radius, from halfway to zero frequency to halfway to the
  second harmonic; for a true spacing within ~0.67–1.33 × nominal only the
  fundamental fits. The earlier ±50% of the spacing (radii 0.67–2 ×) put the
  second harmonic on its edge. Same answers on spirals and cards (also with
  the nominal 30–40% off); chosen for the guarantee. Robust before accurate
  (Adam): the coherence center tolerates ~5% spacing error and the refit
  re-fits the spacing (±2.5%), so a method that never lands on the wrong
  peak matters more than precision; failing with 2–3 turns is acceptable.
- Coherence aligned with cardlab (Nov 2026): σ = r_outer / 8 (first 0.12 ×
  r_outer; was 3 spacings here, 10 on cards), center within 1.5σ of the
  peak, kernel reach = outer radius + 2 spacings. Page: same centers (aspect
  1.05 0.12 vs 0.10 px). Cards (experiments/symmetry_center.py, re-run with
  the current drift, 360 runs per rule): medians a little better, failures
  > 20 px 7 → 1. Only implementation differences remain (circular 512²
  FFTs here, scipy linear convolution there).
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
- Overlays are drawn only on the visible canvases, never into `img`.
- Turn weighting (select: none / 1/√r / 1/r; in `fftInput`): multiply the
  image by max(r, 2·spacing)^−ex about the hand mark, normalized to mean 1,
  before the FFT. Estimated vs true center gave identical results. Test
  (harmonic sum, before the mask; advanced, vMin 10%, 10 offset sets, off-center spiral; median / max
  %): 1/r makes mild offsets worse (±0.1: 0.37 → 0.87, 0.42 → 1.57) but cuts
  the worst cases; 1/√r keeps the medians about as good as none (sometimes
  better: spacing 10 ±0.25 0.80 → 0.48; noise 0.3 1.35 → 0.85) and cuts the
  worst cases most (spacing 20 ±0.25: max 11.6 → 4.0, with noise 10.9 → 3.7;
  spacing 10 ±0.5: 14.6 → 8.2, with noise 24 → 12.8). Spacing 20 ±0.5 stays
  ~16% / 35% for all. Default: 1/√r (the center costs ~0.2–0.4 s per frame).
- Coherence center (checkbox "Coherence center", default on; spiral only;
  `coherenceCenter` in coherence.js): the card pipeline's center search on
  the noisy image with the FFT's spacing estimate ("Spacing for Z" select:
  FFT estimate / true). Panels below the profile: |Z| (square-rooted) and a
  ±3-spacing zoom (yellow square: map peak); cyan + also on the image.
  ~46 ms per frame (node), almost all the map; crop 128² / 256² / 512² at
  spacing 5 / 10 / ≥ 20.
  Center = point symmetry of the map (Adam's idea, Nov 2026), replacing the
  J0 fit at the peak, which locks onto a side lobe once the spiral is
  stretched: aspect 0.98 / 1.03 / 1.05 → J0 fit 5 / 10 / 20 px off, symmetry
  0.03 / 0.06 / 0.09 px. Aspect 1: 0.013 vs 0.001 px (noise 0.5: equal,
  0.017). Radius offsets: 0.2 px either way. A normalized-asymmetry refine
  (window per trial center) gained ≤ 0.03 px for 26 ms: dropped; so was the
  J0 fit (Adam: sub-pixel isn't needed). Phase = arg Z at the center:
  ≤ 1.8° at aspect 1, meaningless at 1.05.
  Spacing off by 0.5–5% (J0 fit, noise 0.3): center median 0.01–0.14 px, no
  failures; phase shifts ≈ 360° × (mean radius / S) × ε (26° per 0.5% at
  spacing 10), so the FFT's 0.5% error on the default spiral gives 24°.
- Tried and rejected: tangential blur (σ 3, along circles about the
  gradient-line center) on the FFT input. Test (advanced 10%, 1/√r, radii
  50–200 and 30–100, spacing 10/20, noise 0–1.5, 6 patterns): differences
  within ±0.2 percentage points either way, slightly worse with no noise.
  The FFT is already noise-tolerant (errors ≤ ~2% even at noise 1.5).

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

State: check `git status -sb` for commits not yet pushed to GitHub.

Closed: the "gradient tilt" center experiment (JS work in progress, gitignored,
in `Claude outputs/cardpipe_tilt_wip.js` and `tilt_test_harness.js`) and the
gradient-line method are dropped in favor of the spiral coherence map; see
"Gradient-based centers dropped" above for the findings.

Done since: the card pipeline is ported to Python (cardlab/, card.html is
the generated report; the JS page lives on as card_js.html); the center
search is the FFT coherence map + its center of point symmetry (both the
spacing page and cardlab).
