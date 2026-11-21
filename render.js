// Shared spiral renderer, used by spacing.html and center.html.
// Plain global script (no modules), so pages still open via file://.

// canvas / image size in pixels (a page may set SPIRAL_N before loading this)
const N = typeof SPIRAL_N !== 'undefined' ? SPIRAL_N : 512;

// Archimedean spiral r = b * theta, with b = spacing / (2π) so that
// successive rings are `spacing` pixels apart, for r in [rStart, rEnd].
// Rendered per pixel from the distance to the nearest arms.
// In rings mode, draws concentric circles at radii n * spacing within
// [rStart, rEnd] instead (phase has no effect).
// Aspect scales the whole drawing about the center by `aspect` in x and
// 1/aspect in y, preserving area (distances are measured in unscaled
// coordinates, so line widths scale too, as if the finished image were resized).
//
// Smooth edges: brightness across a line is Φ(d + w/2) - Φ(d - w/2), where Φ
// is the Gaussian CDF (erf) whose 10%-90% rise is `softness` px, i.e. a
// sharp-edged line blurred by a Gaussian. Its spectrum falls off as a
// Gaussian, so harmonics above Nyquist (which alias) are negligible. Line ends
// get the same falloff along the arc.
// Otherwise: binary on/off pixels (aliased).

// erf, Abramowitz & Stegun 7.1.26 (|error| < 1.5e-7)
function erf(x) {
  const s = x < 0 ? -1 : 1;
  x = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * x);
  const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
  return s * y;
}

// Edge step used for line edges and line ends: 0 → 1 as x goes from - to +.
function edgeStep(p) {
  const sigma = Math.max(p.softness, 0.01) / 2.5631; // 10-90% width = 2.5631 σ
  const c = 1 / (sigma * Math.SQRT2);
  return p.smooth ? x => 0.5 * (1 + erf(x * c)) : x => (x >= 0 ? 1 : 0);
}

// Radius offset (p.offsets, optional): the curve is r(θ) = bθ + δ(θ), where
// δ is piecewise linear in θ, in units of ring spacing: 0 at the start radius,
// p.offsets[0..3] at 20%, 40%, 60%, 80% of the way (by θ) from start to end
// radius, and 0 at the end radius. Continuous in value, with kinks in slope:
// a model of a real, slightly imperfect spiral. (Rings: ring n is offset by
// δ at θ = n·spacing / b.) Returns null when all offsets are 0.
function makeOffset(p) {
  const o = p.offsets;
  if (!o || o.every(v => v === 0)) return null;
  const S = p.spacing, b = S / (2 * Math.PI);
  const t0 = Math.min(p.rStart, p.rEnd) / b, L = Math.max(p.rStart, p.rEnd) / b - t0;
  if (!(L > 0)) return null;
  const vals = [0, ...o, 0].map(v => v * S); // px at t = 0, 0.2, ..., 1
  const seg = th => { const t = (th - t0) / L; return t <= 0 || t >= 1 ? -1 : Math.min(4, Math.floor(t / 0.2)); };
  return {
    off(th) { // px
      const i = seg(th);
      if (i < 0) return 0;
      const f = ((th - t0) / L - 0.2 * i) / 0.2;
      return vals[i] + f * (vals[i + 1] - vals[i]);
    },
    slope(th) { // dδ/dθ, px per radian
      const i = seg(th);
      return i < 0 ? 0 : (vals[i + 1] - vals[i]) / (0.2 * L);
    },
  };
}

// Writes 0..1 values into `out` (Float32Array N*N), then applies p.blur.
// `center` is {x, y} in pixels (fractional allowed). p.phase is in radians.
// Optional `weight(n, ra, ang)` multiplies each arm's contribution: n is the
// arm (or ring) index, ra the arm's ideal radius bθ at this pixel's angle
// (without the radius offset, so chunks stay put in θ), ang the
// pixel's angle atan2(dy, dx) in unscaled coordinates. Used by center.html to
// keep only chunks of the curve.
function renderSpiral(p, center, out, weight) {
  const S = p.spacing;
  const b = S / (2 * Math.PI);
  const r0 = Math.min(p.rStart, p.rEnd);
  const r1 = Math.max(p.rStart, p.rEnd);
  const halfW = p.lineWidth / 2;
  const sig = edgeStep(p);
  const ofs = makeOffset(p);
  const reach = ofs ? 2 : 1; // offsets up to ±1 spacing: check two arms each side

  for (let y = 0; y < N; y++) {
    const dy = (y + 0.5 - center.y) * p.aspect;
    for (let x = 0; x < N; x++) {
      const dx = (x + 0.5 - center.x) / p.aspect;
      const r = Math.hypot(dx, dy);
      // u is fractional arm index; spiral arm n passes radius b * (phi + 2πn),
      // ring n has radius n * spacing.
      const ang = Math.atan2(dy, dx);
      const phi = p.spiral ? ang - p.phase : 0;
      const u = (r / b - phi) / (2 * Math.PI);
      const n0 = Math.round(u);
      const perp = p.spiral ? r / Math.sqrt(r * r + b * b) : 1; // radial → perpendicular distance
      let v = 0;
      for (let n = n0 - reach; n <= n0 + reach; n++) {
        let d = S * (u - n); // signed radial distance to arm n
        const ra = r - d;    // ideal radius of arm n at this angle
        if (ra < 0 || (!p.spiral && n <= 0)) continue; // no zero-radius ring
        let dp;
        if (ofs) { // offset arm: shift it, and use its local slope for the perpendicular
          const th = ra / b;
          d -= ofs.off(th);
          const sl = b + ofs.slope(th);
          dp = d * (p.spiral ? r / Math.sqrt(r * r + sl * sl) : 1);
        } else {
          dp = d * perp;
        }
        const prof = sig(dp + halfW) - sig(dp - halfW);
        if (prof < 1e-7) continue;
        // spiral: arc length (approx) from each end; rings: keep whole rings in range
        const cap = p.spiral
          ? sig((ra * ra - r0 * r0) / (2 * b)) * sig((r1 * r1 - ra * ra) / (2 * b))
          : (ra >= r0 - 1e-6 && ra <= r1 + 1e-6 ? 1 : 0);
        if (cap === 0) continue;
        v += prof * cap * (weight ? weight(n, ra, ang) : 1);
      }
      out[y * N + x] = Math.min(1, v);
    }
  }

  if (p.blur > 0) gaussianBlur(out, p.blur);
}

// Separable Gaussian blur of the N×N image in place (rows, then columns).
// Wraps around at the edges, matching the FFT's view of the image as
// periodic, so the blur multiplies the spectrum by the kernel's DFT.
const blurTmp = new Float32Array(N);
function gaussianBlur(a, sigma) {
  const R = Math.ceil(3 * sigma);
  const k = new Float32Array(2 * R + 1);
  let sum = 0;
  for (let i = -R; i <= R; i++) sum += k[i + R] = Math.exp(-(i * i) / (2 * sigma * sigma));
  for (let i = 0; i < k.length; i++) k[i] /= sum;
  const pass = (base, stride) => {
    for (let i = 0; i < N; i++) {
      let v = 0;
      for (let j = -R; j <= R; j++) v += k[j + R] * a[base + (((i + j) % N + N) % N) * stride];
      blurTmp[i] = v;
    }
    for (let i = 0; i < N; i++) a[base + i * stride] = blurTmp[i];
  };
  for (let y = 0; y < N; y++) pass(y * N, 1);
  for (let x = 0; x < N; x++) pass(x, N);
}

// Copies a 0..1 float image into an ImageData as grey.
function toImageData(src, imageData) {
  const d = imageData.data;
  for (let i = 0; i < N * N; i++) {
    const c = Math.round(src[i] * 255);
    d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = c;
    d[i * 4 + 3] = 255;
  }
}
