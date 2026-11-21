// Center and phase from the spiral coherence map (JS port of
// cardlab/lowres.py find_center). No DOM; uses N and fft1d from render.js /
// fftspacing.js (load after both).
//
// About the true center the image has a component cos(r/b - angle + phase)
// (bright arms; b = spacing / 2π), so
//   Z(c) = Σ_p v(p) exp(-i (|p - c|/b - angle(p - c)))
// is ≈ (n/2) e^{i phase} at c = center and small elsewhere. As a function of
// c it is a sum of plane waves of one wavelength (the spacing S), so near the
// center Z(c) ≈ a J0(2π |c - c0| / S): a bright spot ringed by fainter rings.
// Z is a correlation of the image with a "spiral wave" kernel, so one FFT
// gives it at every pixel; fitting the J0 pattern around its peak gives the
// center to a fraction of a pixel, and arg(a) the phase.
//
// Here the correlation is circular (N×N, no padding): the kernel reaches
// N/2 - 1 px, so a candidate center sees the image as periodic. The only
// peaks are at the true center (and its copies N px away), so the map near
// the peak is unaffected.

// J0, Abramowitz & Stegun 9.4.1 (|x| ≤ 3) and 9.4.3 (x > 3), |error| < 5e-8
function besselJ0(x) {
  x = Math.abs(x);
  if (x <= 3) {
    const t = (x / 3) ** 2;
    return 1 + t * (-2.2499997 + t * (1.2656208 + t * (-0.3163866 + t * (0.0444479 + t * (-0.0039444 + t * 0.00021)))));
  }
  const t = 3 / x;
  const f0 = 0.79788456 + t * (-0.00000077 + t * (-0.0055274 + t * (-0.00009512 + t * (0.00137237 + t * (-0.00072805 + t * 0.00014476)))));
  const th = x - 0.78539816 + t * (-0.04166397 + t * (-0.00003954 + t * (0.00262573 + t * (-0.00054125 + t * (-0.00029333 + t * 0.00013558)))));
  return (f0 * Math.cos(th)) / Math.sqrt(x);
}

const zRe = new Float64Array(N * N), zIm = new Float64Array(N * N);
const kRe = new Float64Array(N * N), kIm = new Float64Array(N * N);
const zAbs = new Float64Array(N * N);
const cohRowRe = new Float64Array(N), cohRowIm = new Float64Array(N);

function fft2Of(re, im, inverse = false) { // in place; inverse via conjugation, scaled 1/N²
  if (inverse) for (let i = 0; i < N * N; i++) im[i] = -im[i];
  for (let y = 0; y < N; y++) {
    const o = y * N;
    for (let x = 0; x < N; x++) { cohRowRe[x] = re[o + x]; cohRowIm[x] = im[o + x]; }
    fft1d(cohRowRe, cohRowIm);
    for (let x = 0; x < N; x++) { re[o + x] = cohRowRe[x]; im[o + x] = cohRowIm[x]; }
  }
  for (let x = 0; x < N; x++) {
    for (let y = 0; y < N; y++) { cohRowRe[y] = re[y * N + x]; cohRowIm[y] = im[y * N + x]; }
    fft1d(cohRowRe, cohRowIm);
    for (let y = 0; y < N; y++) { re[y * N + x] = cohRowRe[y]; im[y * N + x] = cohRowIm[y]; }
  }
  if (inverse) {
    const s = 1 / (N * N);
    for (let i = 0; i < N * N; i++) { re[i] *= s; im[i] = -im[i] * s; }
  }
}

// Kernel G(q) = K(-q), K(q) = exp(-i (|q|/b - angle(q))), zero beyond `reach`,
// stored with wraparound (q mod N), so that (v * G)(c) = Σ_p v(p) K(p - c).
function spiralWaveKernel(b, reach) {
  kRe.fill(0); kIm.fill(0);
  for (let qy = -reach; qy <= reach; qy++) for (let qx = -reach; qx <= reach; qx++) {
    const r = Math.hypot(qx, qy);
    if (r > reach) continue;
    const arg = -(r / b - Math.atan2(-qy, -qx)); // K at -q
    const i = ((qy + N) % N) * N + ((qx + N) % N);
    kRe[i] = Math.cos(arg); kIm[i] = Math.sin(arg);
  }
}

// Fills zRe/zIm with Z at every pixel center (x + 0.5, y + 0.5), zAbs with |Z|.
// Returns Σ|v| (for the coherence score). The image mean is subtracted.
function coherenceMap(src, spacing, reach = N / 2 - 1) {
  let mean = 0;
  for (let i = 0; i < N * N; i++) mean += src[i];
  mean /= N * N;
  let sumAbs = 0;
  for (let i = 0; i < N * N; i++) { zRe[i] = src[i] - mean; zIm[i] = 0; sumAbs += Math.abs(zRe[i]); }
  spiralWaveKernel(spacing / (2 * Math.PI), reach);
  fft2Of(zRe, zIm);
  fft2Of(kRe, kIm);
  for (let i = 0; i < N * N; i++) {
    const a = zRe[i], c = zIm[i];
    zRe[i] = a * kRe[i] - c * kIm[i];
    zIm[i] = a * kIm[i] + c * kRe[i];
  }
  fft2Of(zRe, zIm, true);
  for (let i = 0; i < N * N; i++) zAbs[i] = Math.hypot(zRe[i], zIm[i]);
  return sumAbs;
}

function mapPeak() {
  let best = 0;
  for (let i = 1; i < N * N; i++) if (zAbs[i] > zAbs[best]) best = i;
  return { x: (best % N) + 0.5, y: Math.floor(best / N) + 0.5 };
}

function mapPointsNear(c, radius) {
  const xs = [], ys = [], re = [], im = [];
  const x0 = Math.max(0, Math.floor(c.x - radius)), x1 = Math.min(N - 1, Math.ceil(c.x + radius));
  const y0 = Math.max(0, Math.floor(c.y - radius)), y1 = Math.min(N - 1, Math.ceil(c.y + radius));
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
    if (Math.hypot(x + 0.5 - c.x, y + 0.5 - c.y) > radius) continue;
    xs.push(x + 0.5); ys.push(y + 0.5); re.push(zRe[y * N + x]); im.push(zIm[y * N + x]);
  }
  return { xs, ys, re, im, n: xs.length };
}

// For a trial center: the J0 pattern, the best complex amplitude a (linear least
// squares; the pattern is real), and the misfit Σ |Z - a·J0|².
function ringFit(P, cx, cy, spacing, pat) {
  const k = (2 * Math.PI) / spacing;
  let pp = 0, pr = 0, pi = 0;
  for (let j = 0; j < P.n; j++) {
    const v = besselJ0(k * Math.hypot(P.xs[j] - cx, P.ys[j] - cy));
    pat[j] = v; pp += v * v; pr += v * P.re[j]; pi += v * P.im[j];
  }
  const ar = pr / pp, ai = pi / pp;
  let cost = 0;
  for (let j = 0; j < P.n; j++) cost += (P.re[j] - ar * pat[j]) ** 2 + (P.im[j] - ai * pat[j]) ** 2;
  return { ar, ai, cost };
}

// Levenberg–Marquardt over the center (2 parameters), residuals stacked
// real/imaginary, forward-difference Jacobian.
function fitRingPattern(P, start, spacing) {
  const n = P.n, pat = new Float64Array(n), p1 = new Float64Array(n);
  const resid = (cx, cy, out) => {
    const f = ringFit(P, cx, cy, spacing, pat);
    for (let j = 0; j < n; j++) { out[j] = P.re[j] - f.ar * pat[j]; out[n + j] = P.im[j] - f.ai * pat[j]; }
    return f;
  };
  const r0 = new Float64Array(2 * n), rx = new Float64Array(2 * n), ry = new Float64Array(2 * n);
  let cx = start.x, cy = start.y, lambda = 1e-3, f = resid(cx, cy, r0);
  const h = 1e-4 * spacing;
  for (let it = 0; it < 30; it++) {
    resid(cx + h, cy, rx); resid(cx, cy + h, ry);
    let a = 0, bb = 0, c = 0, gx = 0, gy = 0;
    for (let j = 0; j < 2 * n; j++) {
      const jx = (rx[j] - r0[j]) / h, jy = (ry[j] - r0[j]) / h;
      a += jx * jx; bb += jx * jy; c += jy * jy; gx += jx * r0[j]; gy += jy * r0[j];
    }
    let moved = false;
    for (let tries = 0; tries < 10 && !moved; tries++) {
      const A = a * (1 + lambda), C = c * (1 + lambda), det = A * C - bb * bb;
      const dx = -(C * gx - bb * gy) / det, dy = -(A * gy - bb * gx) / det;
      const g = ringFit(P, cx + dx, cy + dy, spacing, p1);
      if (g.cost < f.cost) {
        cx += dx; cy += dy; lambda = Math.max(lambda / 10, 1e-9);
        f = resid(cx, cy, r0); moved = true;
        if (Math.hypot(dx, dy) < 1e-5) return { x: cx, y: cy, ar: f.ar, ai: f.ai };
      } else lambda *= 10;
    }
    if (!moved) break;
  }
  return { x: cx, y: cy, ar: f.ar, ai: f.ai };
}

// The whole step: map, peak, J0 fit within fitRadius spacings of the peak.
// Returns center, phase (radians, same convention as renderSpiral's p.phase),
// the map peak, a coherence score (≈ 1 for a perfect sinusoidal spiral) and
// timings in ms.
function coherenceCenter(src, spacing, fitRadius = 2.5) {
  const t0 = performance.now();
  const sumAbs = coherenceMap(src, spacing);
  const t1 = performance.now();
  const peak = mapPeak();
  const P = mapPointsNear(peak, fitRadius * spacing);
  const fit = fitRingPattern(P, peak, spacing);
  const t2 = performance.now();
  return {
    c: { x: fit.x, y: fit.y },
    phase: Math.atan2(fit.ai, fit.ar),
    peak,
    coherence: (2 * Math.hypot(fit.ar, fit.ai)) / sumAbs / (Math.PI / 2),
    nFit: P.n,
    msMap: t1 - t0,
    msFit: t2 - t1,
  };
}
