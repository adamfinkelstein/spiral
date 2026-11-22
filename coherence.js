// Center and phase from the spiral coherence map (JS port of
// cardlab/lowres.py find_center). No DOM; uses N from render.js.
//
// About the true center the image has a component cos(r/b - angle + phase)
// (bright arms; b = spacing / 2π), so
//   Z(c) = Σ_p v(p) exp(-i (|p - c|/b - angle(p - c)))
// is ≈ (n/2) e^{i phase} at c = center and small elsewhere: every turn adds in
// step there. Z is a correlation of the image with a "spiral wave" kernel, so
// one FFT gives it at every pixel. Near the center it is a bright spot ringed
// by fainter rings, but if the spiral is stretched (aspect ≠ 1) the turns no
// longer add in step, the spot splits into lobes and the brightest pixel is
// off center. The map stays symmetric under a 180° turn about the center, so
// the center is the map's center of point symmetry near its peak
// (symmetryCenter), and the phase is arg Z there.
//
// The map's correlation is circular (N×N, no padding): the kernel reaches
// N/2 - 1 px, so a candidate center sees the image as periodic. The only
// peaks are at the true center (and its copies N px away), so the map near
// the peak is unaffected.

// ---------- FFT of any power-of-two size M (tables cached per M) ----------

const fftTables = {};
function fftTablesFor(M) {
  if (fftTables[M]) return fftTables[M];
  const bits = Math.log2(M), rev = new Uint32Array(M), cos = new Float64Array(M / 2), sin = new Float64Array(M / 2);
  for (let i = 0; i < M; i++) {
    let r = 0;
    for (let b = 0; b < bits; b++) r |= ((i >> b) & 1) << (bits - 1 - b);
    rev[i] = r;
  }
  for (let i = 0; i < M / 2; i++) { cos[i] = Math.cos((2 * Math.PI * i) / M); sin[i] = -Math.sin((2 * Math.PI * i) / M); }
  return (fftTables[M] = { rev, cos, sin, rowRe: new Float64Array(M), rowIm: new Float64Array(M) });
}

function fftLine(re, im, T, M) { // in place, iterative radix-2
  for (let i = 0; i < M; i++) {
    const j = T.rev[i];
    if (j > i) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; }
  }
  for (let size = 2; size <= M; size <<= 1) {
    const half = size >> 1, step = M / size;
    for (let start = 0; start < M; start += size) {
      for (let k = 0; k < half; k++) {
        const wr = T.cos[k * step], wi = T.sin[k * step], a = start + k, b = a + half;
        const tr = re[b] * wr - im[b] * wi, ti = re[b] * wi + im[b] * wr;
        re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti;
      }
    }
  }
}

function fft2(re, im, M, inverse = false) { // M×M in place; inverse via conjugation, scaled 1/M²
  const T = fftTablesFor(M), rRe = T.rowRe, rIm = T.rowIm;
  if (inverse) for (let i = 0; i < M * M; i++) im[i] = -im[i];
  for (let y = 0; y < M; y++) {
    const o = y * M;
    for (let x = 0; x < M; x++) { rRe[x] = re[o + x]; rIm[x] = im[o + x]; }
    fftLine(rRe, rIm, T, M);
    for (let x = 0; x < M; x++) { re[o + x] = rRe[x]; im[o + x] = rIm[x]; }
  }
  for (let x = 0; x < M; x++) {
    for (let y = 0; y < M; y++) { rRe[y] = re[y * M + x]; rIm[y] = im[y * M + x]; }
    fftLine(rRe, rIm, T, M);
    for (let y = 0; y < M; y++) { re[y * M + x] = rRe[y]; im[y * M + x] = rIm[y]; }
  }
  if (inverse) {
    const s = 1 / (M * M);
    for (let i = 0; i < M * M; i++) { re[i] *= s; im[i] = -im[i] * s; }
  }
}

// ---------- The coherence map ----------

const zRe = new Float64Array(N * N), zIm = new Float64Array(N * N);
const kRe = new Float64Array(N * N), kIm = new Float64Array(N * N);
const zAbs = new Float64Array(N * N);

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
  fft2(zRe, zIm, N);
  fft2(kRe, kIm, N);
  for (let i = 0; i < N * N; i++) {
    const a = zRe[i], c = zIm[i];
    zRe[i] = a * kRe[i] - c * kIm[i];
    zIm[i] = a * kIm[i] + c * kRe[i];
  }
  fft2(zRe, zIm, N, true);
  for (let i = 0; i < N * N; i++) zAbs[i] = Math.hypot(zRe[i], zIm[i]);
  return sumAbs;
}

function mapPeak() {
  let best = 0;
  for (let i = 1; i < N * N; i++) if (zAbs[i] > zAbs[best]) best = i;
  return { x: (best % N) + 0.5, y: Math.floor(best / N) + 0.5 };
}

function mapAt(c) { // bilinear Z at a point (pixel i's center is i + 0.5; the map wraps)
  const u = c.x - 0.5, v = c.y - 0.5, x0 = Math.floor(u), y0 = Math.floor(v), fx = u - x0, fy = v - y0;
  let re = 0, im = 0;
  for (const [dx, dy, w] of [[0, 0, (1 - fx) * (1 - fy)], [1, 0, fx * (1 - fy)], [0, 1, (1 - fx) * fy], [1, 1, fx * fy]]) {
    const i = (((y0 + dy) % N + N) % N) * N + (((x0 + dx) % N + N) % N);
    re += w * zRe[i]; im += w * zIm[i];
  }
  return { re, im };
}

// ---------- Center of point symmetry ----------

// For g = (|Z| - its window mean) × a Gaussian window (σ px) about the peak,
// the self-convolution C(s) = Σ_p g(p) g(s - p) is largest at s = 2 c0, where
// every term is g(p)². It runs on an M×M crop about the peak, M = the power of
// two ≥ 6σ (at most N): circular, but the window is ~1e-4 of its peak where
// the wrap could reach. The center is searched within `search` σ of the peak
// (s in pixel-index sums, i.e. half-pixel steps of c), then refined by a
// parabola along x and y. (Same rule as cardlab/lowres.py symmetry_center.)
function symmetryCenter(peak, sigma, search = 1.5) {
  const M = Math.min(N, 2 ** Math.ceil(Math.log2(6 * sigma)));
  const ox = Math.floor(peak.x) - M / 2, oy = Math.floor(peak.y) - M / 2; // crop origin: the peak pixel is at M/2
  const gRe = new Float64Array(M * M), gIm = new Float64Array(M * M), w = new Float64Array(M * M);
  let sw = 0, swz = 0;
  for (let y = 0; y < M; y++) for (let x = 0; x < M; x++) {
    const i = (((oy + y) % N + N) % N) * N + (((ox + x) % N + N) % N);
    const k = y * M + x;
    w[k] = Math.exp(-((x - M / 2) ** 2 + (y - M / 2) ** 2) / (2 * sigma * sigma));
    gRe[k] = zAbs[i]; sw += w[k]; swz += w[k] * zAbs[i];
  }
  const mean = swz / sw;
  for (let k = 0; k < M * M; k++) gRe[k] = w[k] * (gRe[k] - mean);
  fft2(gRe, gIm, M);
  for (let k = 0; k < M * M; k++) { const a = gRe[k], b = gIm[k]; gRe[k] = a * a - b * b; gIm[k] = 2 * a * b; }
  fft2(gRe, gIm, M, true);
  // crop sums b1 + b2 = M + d (mod M), d = 0 at the peak pixel; image sums i1 + i2 = M + d + 2·origin
  const C = (dx, dy) => gRe[((dy % M + M) % M) * M + ((dx % M + M) % M)];
  // c within `search` sigma of the peak: index-sum offsets up to 2·search·sigma
  // (and at most M/4, where the circular crop is still clean)
  const R = Math.min(M / 4, Math.ceil(2 * search * sigma));
  let bx = 0, by = 0;
  for (let dy = -R; dy < R; dy++) for (let dx = -R; dx < R; dx++) if (C(dx, dy) > C(bx, by)) { bx = dx; by = dy; }
  const parabola = (l, m, r) => { const cu = l - 2 * m + r; return cu < 0 ? (0.5 * (l - r)) / cu : 0; };
  const fx = parabola(C(bx - 1, by), C(bx, by), C(bx + 1, by)), fy = parabola(C(bx, by - 1), C(bx, by), C(bx, by + 1));
  return { x: (M + bx + fx + 2 * ox + 1) / 2, y: (M + by + fy + 2 * oy + 1) / 2, M };
}

// The whole step: map, peak, symmetry center, phase = arg Z there. Returns
// center, phase (radians, same convention as renderSpiral's p.phase), the map
// peak, a relative coherence score, the crop size and timings in ms.
// As cardlab/lowres.py find_center: kernel reach = marked outer radius + 2
// spacings (here at most N/2 − 1), symmetry window σ = 1/8 of the marked outer
// radius, the center within 1.5σ of the map's peak.
function coherenceCenter(src, spacing, mark, windowFraction = 1 / 8, search = 1.5) {
  const t0 = performance.now();
  const sumAbs = coherenceMap(src, spacing, Math.min(N / 2 - 1, Math.ceil(mark.rOuter + 2 * spacing)));
  const t1 = performance.now();
  const peak = mapPeak();
  const c = symmetryCenter(peak, windowFraction * mark.rOuter, search);
  const z = mapAt(c);
  const t2 = performance.now();
  return {
    c: { x: c.x, y: c.y },
    phase: Math.atan2(z.im, z.re),
    peak,
    coherence: (2 * Math.hypot(z.re, z.im)) / sumAbs / (Math.PI / 2),
    crop: c.M,
    msMap: t1 - t0,
    msCenter: t2 - t1,
  };
}
