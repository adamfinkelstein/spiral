// Ring-spacing estimate from the 2D FFT (shared by spacing.html and card.html):
// FFT, radial profile, harmonic-sum score with the coarse-to-fine advanced
// search, and turn weighting. No DOM; uses N from render.js (the image size,
// a power of two). Load after render.js.

// ---------- FFT ----------

const LOG2N = Math.log2(N);
const rev = new Uint32Array(N);
for (let i = 0; i < N; i++) {
  let r = 0;
  for (let b = 0; b < LOG2N; b++) r |= ((i >> b) & 1) << (LOG2N - 1 - b);
  rev[i] = r;
}
const cosT = new Float64Array(N / 2);
const sinT = new Float64Array(N / 2);
for (let i = 0; i < N / 2; i++) {
  cosT[i] = Math.cos((2 * Math.PI * i) / N);
  sinT[i] = -Math.sin((2 * Math.PI * i) / N);
}

// In-place iterative radix-2 FFT on length-N arrays.
function fft1d(re, im) {
  for (let i = 0; i < N; i++) {
    const j = rev[i];
    if (j > i) {
      let t = re[i]; re[i] = re[j]; re[j] = t;
      t = im[i]; im[i] = im[j]; im[j] = t;
    }
  }
  for (let size = 2; size <= N; size <<= 1) {
    const half = size >> 1;
    const step = N / size;
    for (let start = 0; start < N; start += size) {
      for (let k = 0; k < half; k++) {
        const wr = cosT[k * step], wi = sinT[k * step];
        const a = start + k, b = a + half;
        const tr = re[b] * wr - im[b] * wi;
        const ti = re[b] * wi + im[b] * wr;
        re[b] = re[a] - tr; im[b] = im[a] - ti;
        re[a] += tr; im[a] += ti;
      }
    }
  }
}

const RE = new Float64Array(N * N);
const IM = new Float64Array(N * N);
const rowRe = new Float64Array(N), rowIm = new Float64Array(N);
const hann = new Float64Array(N);
for (let i = 0; i < N; i++) hann[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (N - 1));

function fft2d() {
  for (let y = 0; y < N; y++) {
    const o = y * N;
    for (let x = 0; x < N; x++) { rowRe[x] = RE[o + x]; rowIm[x] = IM[o + x]; }
    fft1d(rowRe, rowIm);
    for (let x = 0; x < N; x++) { RE[o + x] = rowRe[x]; IM[o + x] = rowIm[x]; }
  }
  for (let x = 0; x < N; x++) {
    for (let y = 0; y < N; y++) { rowRe[y] = RE[y * N + x]; rowIm[y] = IM[y * N + x]; }
    fft1d(rowRe, rowIm);
    for (let y = 0; y < N; y++) { RE[y * N + x] = rowRe[y]; IM[y * N + x] = rowIm[y]; }
  }
}

const mag = new Float64Array(N * N);

// Radial profile: every FFT pixel is assigned to the bin round(r), r being its
// distance from DC; the profile is the mean normalized log magnitude per bin.
// Bins past N/2 only cover the corners, so they hold fewer pixels.
const NBINS = Math.round(Math.SQRT2 * N / 2) + 1; // corner pixel is the farthest
const binOf = new Uint16Array(N * N);
const binCount = new Uint32Array(NBINS);
for (let y = 0; y < N; y++) {
  for (let x = 0; x < N; x++) {
    const b = Math.round(Math.hypot(x - N / 2, y - N / 2));
    binOf[y * N + x] = b;
    binCount[b]++;
  }
}
const profile = new Float64Array(NBINS);

// Mean subtraction and Hann window (optional), 2D FFT, log magnitude
// (fftshifted into mag, DC at (N/2, N/2)) and the radial profile (mean of
// mag / max per round(radius) bin). Returns max (largest value off DC).
function computeSpectrum(src, removeDC = true, useWindow = true) {
  let mean = 0;
  for (let i = 0; i < N * N; i++) {
    RE[i] = src[i];
    IM[i] = 0;
    mean += RE[i];
  }
  mean /= N * N;
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const i = y * N + x;
      let v = RE[i];
      if (removeDC) v -= mean;
      if (useWindow) v *= hann[x] * hann[y];
      RE[i] = v;
    }
  }

  fft2d();

  // log magnitude, fftshifted so DC lands at (N/2, N/2)
  let max = 0;
  const h = N / 2;
  for (let y = 0; y < N; y++) {
    const sy = (y + h) % N;
    for (let x = 0; x < N; x++) {
      const sx = (x + h) % N;
      const i = y * N + x;
      const m = Math.log1p(Math.hypot(RE[i], IM[i]));
      mag[sy * N + sx] = m;
      if (i !== 0 && m > max) max = m;
    }
  }
  const scale = max > 0 ? 1 / max : 0;
  profile.fill(0);
  for (let i = 0; i < N * N; i++) profile[binOf[i]] += mag[i] * scale;
  for (let b = 0; b < NBINS; b++) profile[b] /= binCount[b];
  return max;
}

// ---------- Harmonic sum ----------

// Rings with spacing s put peaks in the profile at k * rho1, rho1 = N / s.
// For each candidate fundamental rho1, add up over harmonics k = 1..K of
//   profile(k rho1) - (profile((k - 1/2) rho1) + profile((k + 1/2) rho1)) / 2,
// i.e. peak height above the troughs halfway to its neighbours. Subtracting
// the troughs removes the slowly varying background and keeps rho1 / 2 and
// 2 rho1 from scoring as high as the true rho1. The sum is divided by
// sqrt(K): a plain average lets a multiple of rho1 that hits one or two strong
// harmonics win, while a plain sum lets tiny rho1 win by piling up many small
// ripples (tested over spirals/rings, widths 2-8, spacings 3-60). The profile
// is first smoothed with a Gaussian of H_BLUR bins, which removes fringe
// ripple and speckle (mostly hurting the trough samples) and cut the rms error
// for rings about 3x; much wider (3 bins) merges the peaks of large spacings.
// Only radii up to N/2 are
// used (beyond that the bins only cover the FFT's corners).
const H_RMAX = N / 2;
const H_MIN = N / 64, H_MAX = H_RMAX / 1.5, H_STEP = 0.05; // spacing 64 .. ~3 px
const H_COUNT = Math.floor((H_MAX - H_MIN) / H_STEP) + 1;
const hScore = new Float64Array(H_COUNT);
const hRho = i => H_MIN + i * H_STEP;
let hBest = { rho: NaN, spacing: NaN };
const H_BLUR = 1.5;
const smoothProfile = new Float64Array(NBINS);

function profileAt(r) { // linear interpolation between bins of the smoothed profile
  const i = Math.floor(r), f = r - i;
  return smoothProfile[i] * (1 - f) + smoothProfile[i + 1] * f;
}

// Coarse to fine, for spirals whose local spacing varies (radius offsets):
// a spread of spacings within ±v turns each harmonic k into a band of
// relative width ±v around k·rho1, so higher harmonics blur more and their
// troughs vanish once k·v approaches 1/4. A stage with v > 0 smooths the
// profile with a Gaussian of σ = v/2 in log radius (the same relative width
// for every harmonic), uses only harmonics k <= 1/(4v), and finds the best
// rho1; the next stage halves v and searches only within ±v (of the previous
// stage) around that answer. vMin is the expected spacing variation (device
// tolerance): stages run from max(0.3, 3·vMin) down to vMin, and the answer
// is the vMin stage's. Refining further locks onto one region's spacing
// instead of the average when the spacing really varies (tested). vMin = 0:
// stages down to ~0.02, then the plain sharp score above (full precision for
// a perfect spiral). hScore (plotted) is always the final stage's score.
const LOG_DU = 0.004; // log-radius grid step
const LOG_M = Math.ceil(Math.log(NBINS - 2) / LOG_DU) + 1;
const logRaw = new Float64Array(LOG_M), logSm = new Float64Array(LOG_M);
const stageScore = new Float64Array(H_COUNT);
let hStages = [];
let hWin = null; // advanced mode: { lo, hi } rho range searched, and whether the answer hit its edge

function smoothedLog(v) { // returns ρ → profile smoothed by σ = v/2 in log ρ
  for (let j = 0; j < LOG_M; j++) logRaw[j] = profileAt(Math.min(NBINS - 2, Math.exp(j * LOG_DU)));
  const sg = v / 2 / LOG_DU, R = Math.ceil(3 * sg);
  for (let j = 0; j < LOG_M; j++) {
    let acc = 0, w = 0;
    for (let d = -R; d <= R; d++) {
      const g = Math.exp(-(d * d) / (2 * sg * sg));
      acc += g * logRaw[Math.min(LOG_M - 1, Math.max(0, j + d))];
      w += g;
    }
    logSm[j] = acc / w;
  }
  return r => {
    const x = Math.log(Math.max(1, r)) / LOG_DU, i = Math.min(LOG_M - 2, Math.floor(x)), f = x - i;
    return logSm[i] * (1 - f) + logSm[i + 1] * f;
  };
}

// Harmonic score at sample i with profile function P, using at most kMax harmonics.
function scoreAt(i, P, kMax) {
  const rho = hRho(i);
  let sum = 0, K = 0;
  for (let k = 1; k <= kMax && (k + 0.5) * rho <= H_RMAX; k++, K++) {
    sum += P(k * rho) - 0.5 * (P((k - 0.5) * rho) + P((k + 0.5) * rho));
  }
  return K ? sum / Math.sqrt(K) : -Infinity;
}

// Best sample of `sc` within [lo, hi], refined parabolically; returns rho.
function bestRho(sc, lo, hi) {
  let bi = lo;
  for (let i = lo; i <= hi; i++) if (sc[i] > sc[bi]) bi = i;
  let rho = hRho(bi);
  if (bi > lo && bi < hi) {
    const a = sc[bi - 1], b = sc[bi], c = sc[bi + 1], den = a - 2 * b + c;
    if (den < 0) rho += (0.5 * (a - c) / den) * H_STEP;
  }
  return rho;
}
const rhoIndex = rho => Math.max(0, Math.min(H_COUNT - 1, Math.round((rho - H_MIN) / H_STEP)));

// opts: { advanced, vMin, target }. Advanced (default on the page): search
// only spacings within ×0.5–2 of the target spacing (the device's nominal
// spacing; here the true one), coarse to fine down to vMin, and flag an
// answer on the edge of that range as unreliable. Otherwise: the original
// single sharp stage over the whole range.
function computeHarmonicScore(opts = {}) {
  const advanced = !!opts.advanced, vMin = advanced ? opts.vMin || 0 : 0;
  const R = Math.ceil(3 * H_BLUR);
  for (let i = 0; i < NBINS; i++) { // Gaussian blur, clamped at the ends
    let v = 0, w = 0;
    for (let j = -R; j <= R; j++) {
      const g = Math.exp(-(j * j) / (2 * H_BLUR * H_BLUR));
      v += g * profile[Math.min(NBINS - 1, Math.max(0, i + j))];
      w += g;
    }
    smoothProfile[i] = v / w;
  }

  hStages = [];
  let lo = 0, hi = H_COUNT - 1;
  hWin = null;
  if (advanced) {
    lo = rhoIndex(N / (2 * opts.target)); hi = rhoIndex(N / (0.5 * opts.target));
    hWin = { lo: hRho(lo), hi: hRho(hi), edge: false };
  }
  const vs = [];
  if (advanced) for (let v = Math.max(0.3, 3 * vMin); v > Math.max(vMin, 0.02) * 1.0001; v /= 2) vs.push(v);
  vs.push(vMin); // final stage (0 = sharp)
  for (const v of vs) {
    const P = v > 0 ? smoothedLog(v) : profileAt, kMax = v > 0 ? Math.max(1, Math.floor(1 / (4 * v))) : Infinity;
    const sc = v === vMin ? hScore : stageScore;
    if (v === vMin) for (let i = 0; i < H_COUNT; i++) hScore[i] = scoreAt(i, P, kMax); // full curve, for the plot
    else for (let i = lo; i <= hi; i++) stageScore[i] = scoreAt(i, P, kMax);
    const rho = bestRho(sc, lo, hi);
    hStages.push({ v, spacing: N / rho });
    hBest = { rho, spacing: N / rho };
    lo = Math.max(lo, rhoIndex(rho / (1 + v))); hi = Math.min(hi, rhoIndex(rho * (1 + v)));
  }
  if (hWin) hWin.edge = hBest.rho <= hWin.lo + 2 * H_STEP || hBest.rho >= hWin.hi - 2 * H_STEP;
  if (!advanced) hStages = [];
}

// ---------- Even weight per turn ----------

// The FFT weights each turn by its length (∝ r), so outer turns dominate the
// radial profile. Multiplying the image by 1/r about the spiral's center
// makes every turn count equally (the θ-average of the spacing). The weight
// is capped at r = 2·spacing near the center (no rings there, and 1/r would
// blow up the noise) and scaled so it averages 1 over the image.
const imgW = new Float32Array(N * N);
function evenWeight(src, c, spacing, ex = 1) { // weight 1/r^ex (ex 1: equal turns; 0.5: halfway)
  const r0 = Math.max(2 * spacing, 4);
  let sum = 0;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const w = Math.max(Math.hypot(x + 0.5 - c.x, y + 0.5 - c.y), r0) ** -ex;
    imgW[y * N + x] = w; sum += w;
  }
  const k = (N * N) / sum;
  for (let i = 0; i < N * N; i++) imgW[i] = src[i] * imgW[i] * k;
  return imgW;
}

