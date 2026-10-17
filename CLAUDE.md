# CLAUDE.md

Small static browser app: an Archimedean spiral (or concentric rings) on the
left and the log-magnitude 2D FFT of that image on the right. No build step,
no dependencies — open `index.html` directly (`open index.html`).

## Files

- `index.html` — layout, CSS, and all controls (sliders/checkboxes; defaults
  live in their `value` / `checked` attributes).
- `spiral.js` — everything else: per-pixel spiral rendering, radix-2 FFT,
  display, and mouse/keyboard interaction.
- `explain.html` — plain-HTML help page describing each control, opened by the
  "Explain" button. Keep it in sync when controls change.

## Key design points

- `N = 512` is the internal resolution of both canvases and the FFT size. The
  FFT is radix-2, so `N` must stay a power of two. Canvases are displayed at
  400×400 via CSS and cropped (`.crop` wrapper) to show only their right 2/3;
  the full image is still drawn and transformed.
- The spiral is not stroked with canvas paths. `renderSpiral` computes each
  pixel from its distance to the nearest arms (r = b·θ, b = spacing / 2π),
  writing 0..1 floats into `img`, which feeds the FFT directly.
- Smooth edges use a Gaussian CDF (erf) profile; the "edge transition" slider
  is the 10–90% width. This is deliberate: hard or sigmoid edges have
  harmonics above Nyquist that alias into arcs at the FFT's edges/corners.
  With erf edges, ~2–3 px transition removes them. Unchecking "Smooth line
  edges" gives binary (aliased) pixels for comparison.
- The radial profile plot (`drawProfile`) bins FFT pixels by round(distance
  from DC) using tables built once (`binOf`, `binCount`) and plots the mean
  of `mag / max` per bin, i.e. independent of the contrast slider.
- `computeHarmonicScore` estimates ring spacing from the profile: for each
  candidate fundamental radius rho, sum over harmonics of (peak minus the
  mean of the half-way troughs), divided by sqrt(K). That normalization was
  chosen by testing: a plain average picks a higher harmonic, a plain sum
  picks tiny rho. The profile is blurred first (fixed `H_BLUR` = 1.5 bins;
  ~3x lower rms error for rings, 3 bins breaks large spacings). Plotted in
  red on the profile plot with x = rho.
- Overlays (red center handle, blue crosshair, 1/spacing rings) are drawn only
  on the visible canvases, never into `img`, so they don't affect the FFT.

## Gotchas

- Element ids are shared between HTML and the `ids` list in `spiral.js`, and
  must be unique: the left canvas is `id="spiral"`, so the rings/spiral
  checkbox is `isSpiral`.

## Checking changes

No Node on this machine. Syntax-check with JavaScriptCore:

```sh
/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc -e "checkSyntax('spiral.js'); print('ok')"
```

For logic/perf checks, `jsc` can run `spiral.js` with a small stub of
`document` / canvas contexts prepended, then call `renderSpiral(params())` and
`computeFFT(params())` and print `img` / `mag`. Stubs won't catch DOM issues
(like duplicate ids). To see the real page, take a headless Chrome screenshot:

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --disable-gpu --hide-scrollbars --window-size=1000,720 \
  --screenshot=/path/to/shot.png "file://$PWD/index.html"
```
