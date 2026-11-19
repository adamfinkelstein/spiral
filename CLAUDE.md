# CLAUDE.md

Small static browser site of spiral experiments: `index.html` links to each
experiment page. No build step, no dependencies — open `index.html` directly
(`open index.html`). Pages are plain `<script>` tags (no ES modules) so they
work from `file://`. Deployed to GitHub Pages on every push to `main`.

## Files

- `index.html` — landing page linking to the two experiments.
- `render.js` — shared by all pages: `N`, `erf`, `edgeStep`, `renderSpiral`,
  `gaussianBlur`, `toImageData`. Defines globals, so page scripts must not
  redeclare them (e.g. no `const N` in a page script).
- `spacing.html` / `spacing.js` — ring-spacing experiment: spiral (or rings)
  on the left, log-magnitude 2D FFT on the right, radial profile and
  harmonic-sum spacing estimate below.
- `explain.html` — help page for `spacing.html` ("Explain" button). Keep it
  in sync when its controls change.
- `center.html` / `center.js` — center/phase experiment (spiral only, no
  rings mode: `params()` sets `spiral: true` for render.js). One left column:
  true spiral (drag to move center; chunks highlighted) → connected
  components with per-chunk estimates, shared starts and the combined
  estimate → table of estimates vs. truth (20 largest components) → fit-cost
  map for the selected chunk. Sticky, scrollable controls panel on the right.
  The page's hint paragraphs describe each control.
- `chunkfit.js` — the estimation; no DOM, uses only `N` from render.js: `labelComponents`, `fitChunk`, `fitComponents`, `combineChunks`
  (with `chunkData`, `evalLoss`, `phaseFor`, `fitJoint`), `costMap`, plus
  `mulberry32`, `lm`, `solve`. Scripts load in the order render.js,
  chunkfit.js, center.js.

Controls and their defaults live in the HTML `value` / `checked` attributes;
each page's `ids` list and `params()` read them, and "Defaults" resets to them.

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

## Center page: pipeline

1. **Chunks** (`center.js`): each is two seeded uniform numbers (position u,
   extent fraction v), so chunks stay put while sliders move; "New chunks"
   bumps the seed (and redraws the noise). A chunk is a θ interval of width
   v × Max extent, placed uniformly by arc length (s = bθ²/2, the same
   approximation as the end caps). Chunk ends use the line-edge profile.
2. **Noise**: a fixed Gaussian field per seed × Noise sigma, added to the
   chunk image; then **Denoise blur** (Gaussian, σ 1). Weights are clamped
   to 0..1.
3. **Components** (`labelComponents`): hysteresis thresholding as in Canny
   (seeds > high 0.5, extended through 8-connected pixels > low 0.4), drop
   components below Min component px, number them by size (#1 = largest),
   grow 2 px into soft-edge pixels (only those ≤ low threshold).
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

- b = spacing / 2π. A chunk constrains the *direction* to the center well
  and the *distance* poorly (only curvature): the cost valley points at the
  center. A distance error δ gives a phase error of δ/b radians. A spacing
  error ε leaves the center alone and goes into the phase, ≈ θ·ε radians.
- Accuracy depends mostly on angular extent (σ 0.3, width 4: median distance
  error <20° ~50 px, 20–45° ~3 px, 45–90° ~0.5 px, >90° ~0.1 px). The clean
  ~0.01 px results rely on anti-aliased edges; binary pixels give ~2 px.
- Denoise blur is the big win under noise (σ 0.6: median 206 px → 0.9).
  Low threshold 0.4 beats 0.3 (blurred noise percolates) and 0.5. Tukey loss
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

No Node on the Mac; the Linux VM used by Claude has Node. Syntax-check on the
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
