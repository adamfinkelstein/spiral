# spiral

Small browser experiments on images of an Archimedean spiral (or concentric
rings). Open `index.html` in a browser — no build step — and pick an
experiment.

Live version: https://adamfinkelstein.github.io/spiral/ (deployed automatically
by GitHub Actions on every push to `main`).

## Ring spacing (`spacing.html`)

- Left: the spiral, rendered per pixel on a 512×512 grid (white on black).
  Drag to move its center (Shift for finer control, arrow keys to nudge,
  double-click to recenter).
- Right: log |FFT| of that image, zero frequency at the center.
- Below: radial profile of the FFT and a harmonic-sum estimate of the ring
  spacing.
- Controls for ring spacing, start/end radius, phase, aspect, line width, edge
  softness (Gaussian-blurred edges, which suppress aliasing in the FFT) and
  blur, plus rings/spiral, smooth edges, mean subtraction, Hann window and an
  overlay of the expected 1/spacing rings.

Both canvases show only their right two-thirds, since the images are nearly
symmetric.

## Center and phase (`center.html`)

- Left: the true spiral, with the chosen chunks highlighted.
- Right: only the pixels in a few random chunks of the curve (set number and
  arc length; "New chunks" draws a new random set), as if only parts of the
  spiral were recovered. Groundwork for estimating the center and phase from
  partial data, given the ring spacing.
