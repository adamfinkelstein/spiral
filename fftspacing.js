// Ring-spacing estimate from the 2D FFT (shared by spacing.html and the frozen
// card_js.html): FFT, radial profile, the hand mark's annulus mask and turn
// weighting, and the spacing as the peak of the smoothed profile (all as
// cardlab/lowres.py). No DOM; uses N from render.js (the image size, a power
// of two). Load after render.js. (The harmonic-sum score with its
// coarse-to-fine search, used until Nov 2026, is described in procedure.html.)

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


// ---------- Hand mark and annulus mask (as cardlab/lowres.py) ----------

// A hand mark: center and inner / outer radius of the groove's annulus. The
// mask is a soft annulus inside the marked circles (smoothstep over `ramp` px,
// one nominal spacing). fftInput: the image normalized inside the mask (mean
// removed, times the mask, unit rms), times the turn weight
// max(r, 2·spacing)^-ex about the mark (mean 1), minus its mean inside the
// mask, so the frame outside stays 0. The mask is the FFT's only window.
const maskArr = new Float32Array(N * N), normArr = new Float32Array(N * N), fftIn = new Float32Array(N * N);
const smoothstep = t => { t = Math.min(1, Math.max(0, t)); return t * t * (3 - 2 * t); };

function annulusMask(mark, ramp) {
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const r = Math.hypot(x + 0.5 - mark.x, y + 0.5 - mark.y);
    maskArr[y * N + x] = smoothstep((r - mark.rInner) / ramp) * smoothstep((mark.rOuter - r) / ramp);
  }
  return maskArr;
}

function normalizeInMask(src, mask) { // fills normArr
  let sm = 0, smv = 0;
  for (let i = 0; i < N * N; i++) { sm += mask[i]; smv += mask[i] * src[i]; }
  const mean = smv / sm;
  let ss = 0;
  for (let i = 0; i < N * N; i++) { normArr[i] = (src[i] - mean) * mask[i]; ss += normArr[i] * normArr[i]; }
  const k = ss > 0 ? 1 / Math.sqrt(ss / sm) : 0;
  for (let i = 0; i < N * N; i++) normArr[i] *= k;
  return normArr;
}

function fftInput(norm, mask, mark, spacing, ex) { // fills fftIn
  const r0 = 2 * spacing;
  let sw = 0;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const w = ex > 0 ? Math.max(Math.hypot(x + 0.5 - mark.x, y + 0.5 - mark.y), r0) ** -ex : 1;
    fftIn[y * N + x] = w; sw += w;
  }
  const k = (N * N) / sw;
  let sm = 0, smv = 0;
  for (let i = 0; i < N * N; i++) { fftIn[i] *= norm[i] * k; sm += mask[i]; smv += mask[i] * fftIn[i]; }
  const mean = smv / sm;
  for (let i = 0; i < N * N; i++) fftIn[i] -= mean * mask[i];
  return fftIn;
}

// ---------- Spacing: peak of the smoothed profile (as cardlab/lowres.py) ----------

// The radial profile smoothed by a Gaussian of `blur` bins; its largest value
// within ±window of the expected peak radius rho0 = N / target (target: the
// device's nominal spacing), refined by a parabola through it and its
// neighbours; spacing = N / radius. The window is set in frequency: with 0.5 it
// runs from halfway to zero frequency (0.5 rho0) to halfway to the second
// harmonic (1.5 rho0), so for any true spacing within ~0.67–1.33 × the target
// the fundamental is inside and its second harmonic outside. A peak on the
// window's edge is unreliable: the target is used instead.
const peakProfile = new Float64Array(NBINS);
let peak = { rho: NaN, spacing: NaN, lo: NaN, hi: NaN, edge: false };

function profilePeak({ target, window = 0.5, blur = 1.5 }) {
  const R = Math.ceil(3 * blur);
  for (let i = 0; i < NBINS; i++) {
    if (!(blur > 0)) { peakProfile[i] = profile[i]; continue; }
    let v = 0, w = 0;
    for (let j = -R; j <= R; j++) {
      const g = Math.exp(-(j * j) / (2 * blur * blur));
      v += g * profile[Math.min(NBINS - 1, Math.max(0, i + j))];
      w += g;
    }
    peakProfile[i] = v / w;
  }
  const rho0 = N / target;
  const lo = Math.max(1, Math.floor((1 - window) * rho0));
  const hi = Math.min(NBINS - 2, Math.ceil((1 + window) * rho0));
  let best = lo;
  for (let i = lo; i <= hi; i++) if (peakProfile[i] > peakProfile[best]) best = i;
  const edge = best === lo || best === hi;
  let rho = best;
  if (!edge) {
    const a = peakProfile[best - 1], b = peakProfile[best], c = peakProfile[best + 1], den = a - 2 * b + c;
    if (den < 0) rho += (0.5 * (a - c)) / den;
  }
  peak = { rho, spacing: edge ? target : N / rho, measured: N / rho, lo, hi, edge };
  return peak;
}
