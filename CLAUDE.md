# CLAUDE.md

Small static browser site of spiral experiments: `index.html` links to each
experiment page. No build step, no dependencies — open `index.html` directly
(`open index.html`). Pages are plain `<script>` tags (no ES modules) so they
work from `file://`.

## Files

- `index.html` — landing page linking to the experiments.
- `render.js` — shared by all pages: `N`, `erf`, `edgeStep`, `renderSpiral`,
  `gaussianBlur`, `toImageData`. Defines globals, so page scripts must not
  redeclare them (e.g. no `const N` in a page script).
- `spacing.html` / `spacing.js` — ring-spacing experiment: spiral (or rings)
  on the left, log-magnitude 2D FFT on the right, radial profile and
  harmonic-sum spacing estimate below. Controls and their defaults live in the
  HTML `value` / `checked` attributes.
- `explain.html` — help page for `spacing.html`, opened by its "Explain"
  button. Keep it in sync when controls change.
- `center.html` / `center.js` — center/phase experiment: true spiral on the
  left (chunks highlighted), only random chunks of the curve on the right. No
  FFT or plot.

## Key design points

- `N = 512` (in `render.js`) is the internal resolution of all canvases and the FFT size. The
  FFT is radix-2, so `N` must stay a power of two. Canvases are displayed at
  400×400 via CSS and cropped (`.crop` wrapper) to show only their right 2/3;
  the full image is still drawn and transformed.
- The spiral is not stroked with canvas paths. `renderSpiral(p, center, out,
  weight?)` computes each pixel from its distance to the nearest arms
  (r = b·θ, b = spacing / 2π), writing 0..1 floats into `out` (in
  `spacing.js`, `img`, which feeds the FFT directly). `p.phase` is in radians.
  The optional `weight(n, ra, ang)` scales each arm's contribution; the
  center page uses it to keep only chunks.
- Chunks (`center.js`): each is one uniform number from a seeded PRNG (its
  position along the whole curve), so chunks stay put while sliders move and
  "New chunks" bumps the seed. Spiral arc length uses s = r²/(2b), the same
  approximation as the end caps; rings are laid end to end, smallest first,
  and a chunk wraps around its ring. Chunk ends use the line-edge profile.
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

- Element ids are shared between HTML and the `ids` list in each page script,
  and must be unique: the left canvas is `id="spiral"`, so the rings/spiral
  checkbox is `isSpiral`.

## Checking changes

No Node on this machine. Syntax-check with JavaScriptCore:

```sh
/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc -e "checkSyntax('render.js'); checkSyntax('spacing.js'); checkSyntax('center.js'); print('ok')"
```

For logic/perf checks, `jsc` can run `render.js` + `spacing.js` with a small stub of
`document` / canvas contexts prepended, then call `renderSpiral(params(), center, img)` and
`computeFFT(params())` and print `img` / `mag`. Stubs won't catch DOM issues
(like duplicate ids). To see the real page, take a headless Chrome screenshot:

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --disable-gpu --hide-scrollbars --window-size=1000,720 \
  --screenshot=/path/to/shot.png "file://$PWD/spacing.html"
```
