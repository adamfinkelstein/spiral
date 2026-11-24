# spiral

Small browser experiments on images of an Archimedean spiral (r = bθ, with
ring spacing 2πb). Open `index.html` in a browser — no build step, no
dependencies — and pick an experiment.

Live version: https://adamfinkelstein.github.io/spiral/ (deployed automatically
by GitHub Actions on every push to `main`).

## Ring spacing (`spacing.html`)

Estimate the ring spacing from the 2D Fourier transform.

- Left: the spiral (or concentric rings), rendered per pixel on a 512×512
  grid. Drag to move its center (Shift for finer control, arrow keys to
  nudge, double-click to recenter).
- Right: log |FFT| of that image, zero frequency at the center.
- Below: radial profile of the FFT; the spacing is its peak after smoothing
  (1 bin), searched within ±50% of the radius where the target spacing
  would put it (drawn in red),
  the same rule as the card pipeline.
- Controls for ring spacing, start/end radius, phase, aspect, radius offsets
  (an imperfect spiral whose local spacing varies), line width (up to the
  spacing), edge softness (Gaussian-blurred edges, which suppress aliasing in
  the FFT), blur and noise, plus rings/spiral, smooth edges and an overlay
  of the expected 1/spacing rings.
- A simulated hand mark (center and radii plus a small error), as on the
  cards: its soft annulus masks the image, which is weighted 1/√r about the
  marked center (so outer turns don't dominate) and transformed with the
  mask as its only window.
- Earlier versions scored spacings by a harmonic sum and found a rough
  center from gradient lines (RANSAC); both were dropped in Nov 2026 to
  match the card pipeline (see considered.html, Part 1).
- Coherence center (default on, spiral only): the card pipeline's center
  search ported to JS (`coherence.js`): the spiral coherence map |Z| by one
  FFT correlation; the center is the map's center of point symmetry near its
  peak (self-convolution on a crop, robust to a stretched spiral), the phase
  the angle of Z there; live (~50 ms), shown with a zoom below the profile.
- "Explain" opens a description of every control.

## Center and phase (`center.html`)

Given the ring spacing, estimate the spiral's center and phase from only a
few pieces ("chunks") of it.

- The true spiral, with random chunks of random angular extent highlighted;
  only the chunk pixels, plus optional noise, are given to the estimator.
- Estimation: denoising blur, then blur along the rings about a rough
  center from image gradients → thresholding → connected
  components → a robust (Tukey) fit of center and phase for each component,
  starting from a shared median estimate → a RANSAC-style combination of all
  agreeing chunks into one spiral.
- Shows each component in its own color with its center estimate and
  uncertainty ellipse, the combined estimate, a table of estimates and
  errors against the truth, and the fit-cost landscape for a selected chunk.
- Controls for the spiral (including radius offsets), the chunks (count,
  maximum extent), noise,
  spacing error, and each estimation step; the page describes each.

## An idealized card (`card.html`)

The whole pipeline on a simulated recording card, as a static report built in
Python (`cardlab/`, `build_card.py`) and committed with its images:

```sh
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python build_card.py          # presets × seeds 1–5, rebuilds card.html
```

The card is flat with paper grain (level measured on the sonorine scans),
~40 turns at 29 px groove spacing, and the sound cut into the groove's depth
(hill-and-dale); where the stylus rises above the card the groove disappears.
From a hand-marked center: spacing (FFT) and center/spacing/phase (spiral
coherence) at low resolution, then the annulus unrolled into a rectangle
along that spiral and cut into wedges (1/40 turn) at full resolution, a robust
geometry refit on the wedges, the groove's path and the sound read from the depth,
all scored against the truth over many seeds. The earlier in-browser version
is `card_js.html`.
