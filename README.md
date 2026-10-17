# spiral

A small browser app for exploring the 2D Fourier transform of an Archimedean
spiral (or concentric rings). Open `index.html` in a browser — no build step.

- Left: the spiral, rendered per pixel on a 512×512 grid (white on black).
  Drag to move its center (Shift for finer control, arrow keys to nudge,
  double-click to recenter).
- Right: log |FFT| of that image, zero frequency at the center.
- Controls for ring spacing, start/end radius, rotation, line width, and edge
  softness (Gaussian-blurred edges, which suppress aliasing in the FFT), plus
  rings/spiral, smooth edges, mean subtraction, Hann window and an overlay of
  the expected 1/spacing rings.

Both canvases show only their right two-thirds, since the images are nearly
symmetric.
