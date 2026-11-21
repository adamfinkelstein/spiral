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
- Below: radial profile of the FFT and a harmonic-sum estimate of the ring
  spacing.
- Controls for ring spacing, start/end radius, phase, aspect, radius offsets
  (an imperfect spiral whose local spacing varies), line width (up to the
  spacing), edge softness (Gaussian-blurred edges, which suppress aliasing in
  the FFT), blur and noise, plus rings/spiral, smooth edges, mean
  subtraction, Hann window and an overlay of the expected 1/spacing rings.
- Advanced peak search (default): searches only ×0.5–2 of the target
  spacing, coarse to fine down to an expected spacing variation.
- Gradient-line center: estimates the spiral's center from image gradients
  (RANSAC over pairs of lines, with blur along the rings to resist noise),
  used to weight turns (default 1/√r) before the FFT so outer turns don't
  dominate.
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

The whole pipeline on a simulated recording card: flat, with paper grain
(level measured on the sonorine scans), ~40 turns at 29 px groove spacing,
and the sound cut into the groove's depth (hill-and-dale): a round stylus
moves up and down, and where it rises above the card the groove disappears.
Presets and a seed instead of sliders.

- Starts from a hand-marked center and annulus (the truth plus error); the
  low-res input is masked to that annulus.
- Low resolution (1024²): ring spacing from the FFT near the machine's
  nominal spacing, then center, spacing and phase by maximizing the spiral's
  coherence near the hand mark.
- Full resolution: an unrolled strip along that spiral, one demodulated
  column every 3 px of groove, a robust refit of the geometry, and the groove
  traced locked to the refitted spiral.
- Sound: read from the groove's depth along the trace.
- Every step is shown large in one column with its own settings beside it,
  with errors against the truth and every card parameter with its source.
