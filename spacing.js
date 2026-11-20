
const spiralCanvas = document.getElementById('spiral');
const fftCanvas = document.getElementById('fft');
const sctx = spiralCanvas.getContext('2d');
const fctx = fftCanvas.getContext('2d');

// Offscreen canvas holds the pure spiral (no handle overlay) used as FFT input.
const off = document.createElement('canvas');
off.width = off.height = N;
const octx = off.getContext('2d', { willReadFrequently: true });

const center = { x: N / 2, y: N / 2 };
const HANDLE_R = 7;

const ids = ['spacing', 'rStart', 'rEnd', 'phase', 'aspect', 'off20', 'off40', 'off60', 'off80', 'lineWidth', 'softness', 'blur', 'noise', 'gain', 'advanced', 'hVar', 'gradVote', 'gvPerBin', 'gvFloor', 'gvTang', 'gvShow', 'evenW', 'isSpiral', 'smooth', 'removeDC', 'window', 'showRing'];
const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));

function params() {
  return {
    spacing: +el.spacing.value,
    rStart: +el.rStart.value,
    rEnd: +el.rEnd.value,
    phase: (+el.phase.value * Math.PI) / 180,
    aspect: +el.aspect.value,
    offsets: [+el.off20.value, +el.off40.value, +el.off60.value, +el.off80.value],
    lineWidth: +el.lineWidth.value,
    softness: +el.softness.value,
    blur: +el.blur.value,
    noise: +el.noise.value,
    smooth: el.smooth.checked,
    spiral: el.isSpiral.checked,
    gain: +el.gain.value,
    advanced: el.advanced.checked,
    hVar: +el.hVar.value / 100,
    gradVote: el.gradVote.checked,
    gvPerBin: +el.gvPerBin.value,
    gvFloor: +el.gvFloor.value / 100,
    gvShow: el.gvShow.checked,
    evenW: +el.evenW.value, // weight exponent: 0 none, 0.5 1/√r, 1 1/r
    gvTang: +el.gvTang.value,
    removeDC: el.removeDC.checked,
    window: el.window.checked,
    showRing: el.showRing.checked,
  };
}

// ---------- Spiral ----------

// Rendering (renderSpiral, gaussianBlur, N) lives in render.js.
const img = new Float32Array(N * N);
const spiralImage = octx.createImageData(N, N);

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
const fftImage = fctx.createImageData(N, N);

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

function computeFFT(p, src = img) {
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
      if (p.removeDC) v -= mean;
      if (p.window) v *= hann[x] * hann[y];
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

  const d = fftImage.data;
  const scale = max > 0 ? 1 / max : 0;

  profile.fill(0);
  for (let i = 0; i < N * N; i++) profile[binOf[i]] += mag[i] * scale;
  for (let b = 0; b < NBINS; b++) profile[b] /= binCount[b];

  for (let i = 0; i < N * N; i++) {
    const v = Math.min(1, Math.pow(mag[i] * scale, 1 / p.gain));
    const c = Math.round(v * 255);
    d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = c;
    d[i * 4 + 3] = 255;
  }
  fctx.putImageData(fftImage, 0, 0);

  if (p.showRing) {
    // Rings spaced `spacing` px apart → radial frequency N/spacing (in FFT bins).
    fctx.strokeStyle = 'rgba(255,60,60,0.8)';
    fctx.lineWidth = 1;
    for (let k = 1; k * N / p.spacing < N * 0.71; k++) {
      fctx.beginPath();
      fctx.arc(h, h, (k * N) / p.spacing, 0, 2 * Math.PI);
      fctx.stroke();
    }
  }
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

// ---------- Radial profile plot ----------

const plotCanvas = document.getElementById('profile');
const PURPLE = '#b78cff';
const pctx = plotCanvas.getContext('2d');

function drawProfile(p) {
  // Match the canvas's backing store to its CSS size for crisp lines.
  const dpr = window.devicePixelRatio || 1;
  const W = plotCanvas.clientWidth, H = plotCanvas.clientHeight;
  if (plotCanvas.width !== Math.round(W * dpr) || plotCanvas.height !== Math.round(H * dpr)) {
    plotCanvas.width = Math.round(W * dpr);
    plotCanvas.height = Math.round(H * dpr);
  }
  const ctx = pctx;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);

  const L = 40, R = 10, T = 24, B = 30; // margins (top holds the spacing axis)
  const pw = W - L - R, ph = H - T - B;
  const rMax = NBINS - 1;
  const X = r => L + (r / rMax) * pw;
  const Y = v => T + (1 - v) * ph;

  // Past N/2 the bins only include the corners of the FFT image.
  ctx.fillStyle = '#1a1a1a';
  ctx.fillRect(X(N / 2), T, X(rMax) - X(N / 2), ph);

  ctx.font = '11px system-ui, sans-serif';
  ctx.strokeStyle = '#333';
  ctx.fillStyle = '#888';
  ctx.lineWidth = 1;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (let r = 0; r <= rMax; r += 50) {
    ctx.beginPath(); ctx.moveTo(X(r), T); ctx.lineTo(X(r), T + ph); ctx.stroke();
    ctx.fillText(r, X(r), T + ph + 4);
  }
  ctx.fillText('radius (FFT bins)', L + pw / 2, T + ph + 16);
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (let v = 0; v <= 1; v += 0.25) {
    ctx.beginPath(); ctx.moveTo(L, Y(v)); ctx.lineTo(L + pw, Y(v)); ctx.stroke();
    ctx.fillText(v.toFixed(2), L - 4, Y(v));
  }

  if (p.showRing) {
    ctx.strokeStyle = 'rgba(255,60,60,0.8)';
    ctx.setLineDash([4, 3]);
    for (let k = 1; (k * N) / p.spacing <= rMax; k++) {
      const x = X((k * N) / p.spacing);
      ctx.beginPath(); ctx.moveTo(x, T); ctx.lineTo(x, T + ph); ctx.stroke();
    }
    ctx.setLineDash([]);
  }

  // Purple bar: estimated spacing on its own 0..SP_MAX px scale (top axis),
  // drawn behind the curves.
  const SP_MAX = 64;
  const SX = sp => L + (sp / SP_MAX) * pw;
  ctx.fillStyle = 'rgba(160,90,255,0.55)';
  if (isFinite(hBest.spacing)) ctx.fillRect(L, T + 2, SX(Math.min(SP_MAX, hBest.spacing)) - L, 12);
  ctx.fillStyle = PURPLE;
  ctx.strokeStyle = PURPLE;
  ctx.lineWidth = 1;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'bottom';
  for (let sp = 0; sp <= SP_MAX; sp += 8) {
    ctx.beginPath(); ctx.moveTo(SX(sp), T - 3); ctx.lineTo(SX(sp), T); ctx.stroke();
    if (sp === SP_MAX) { ctx.textAlign = 'right'; ctx.fillText(`${sp} px`, SX(sp), T - 4); }
    else ctx.fillText(sp, SX(sp), T - 4);
  }

  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let r = 0; r <= rMax; r++) {
    const x = X(r), y = Y(Math.min(1, profile[r]));
    if (r === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Harmonic score vs. fundamental radius, scaled to fill the plot height.
  let lo = Infinity, hi = -Infinity;
  for (const v of hScore) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
  const sy = v => Y(hi > lo ? (v - lo) / (hi - lo) : 0);
  ctx.strokeStyle = '#ff4040';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < H_COUNT; i++) {
    const x = X(hRho(i)), y = sy(hScore[i]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  if (hWin) { // advanced search range (×0.5–2 of the target spacing)
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = 'rgba(255,64,64,0.5)';
    ctx.lineWidth = 1;
    for (const r of [hWin.lo, hWin.hi]) { ctx.beginPath(); ctx.moveTo(X(r), T); ctx.lineTo(X(r), T + ph); ctx.stroke(); }
    ctx.restore();
  }
  ctx.fillStyle = '#ff4040';
  ctx.beginPath();
  ctx.arc(X(hBest.rho), sy(hi), 3, 0, 2 * Math.PI);
  ctx.fill();
  ctx.font = '12px system-ui, sans-serif';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'top';
  // red "radius → " followed by the purple spacing, right-aligned together
  const spText = `spacing ${hBest.spacing.toFixed(2)} px`;
  const right = L + pw - 6, ty = T + 18;
  ctx.fillText(`harmonic sum peak: radius ${hBest.rho.toFixed(2)} → `, right - ctx.measureText(spText).width, ty);
  ctx.fillStyle = PURPLE;
  ctx.fillText(spText, right, ty);
  ctx.fillStyle = '#ddd';
  ctx.fillText('mean log |FFT|', L + pw - 6, T + 34);
  if (hStages.length) { // coarse-to-fine path
    ctx.fillStyle = '#999';
    ctx.fillText('coarse to fine: ' + hStages.map(s => s.spacing.toFixed(2)).join(' → ') + ' px', L + pw - 6, T + 50);
  }
  if (hWin && hWin.edge) {
    ctx.fillStyle = '#ffb020';
    ctx.fillText('⚠ at the edge of the ×0.5–2 search range: unreliable', L + pw - 6, T + 66);
  }
}

// ---------- Rendering ----------

// ---------- Noise ----------

// A fixed field of standard normal values (Box–Muller, seeded mulberry32), so
// the noise stays put while sliders move; scaled by Noise sigma (in units of
// full white) and added to the rendered image, before the FFT and the
// gradient-vote center.
const noiseField = new Float32Array(N * N);
{
  let a = 12345;
  const rnd = () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  for (let i = 0; i < N * N; i += 2) {
    const u = Math.max(rnd(), 1e-12), v = rnd(), r = Math.sqrt(-2 * Math.log(u));
    noiseField[i] = r * Math.cos(2 * Math.PI * v);
    noiseField[i + 1] = r * Math.sin(2 * Math.PI * v);
  }
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

// ---------- Gradient-line center (rough spiral center from the image) ----------

// Each pixel on a ring's edge has a gradient pointing across the ring, so the
// line through it along the gradient passes (nearly) through the center.
// On a spiral that line misses the center by about b = spacing/2π sideways:
// it passes through center + b·(−sin α, cos α), α the pixel's angle about the
// center (the same offset as the circle-fit correction on the center page);
// `lineShift` undoes that, for a given center, when the curve is a spiral.

// Small seeded PRNG (mulberry32).
function rng32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Blur along circles about c (tangentially), with a Gaussian of σ px (capped
// at r/4 near the center), sampled bilinearly along the tangent: averages
// noise along the rings without smearing across them.
function tangentialBlur(src, dst, c, sigma) {
  const K = Math.ceil(2 * sigma), wts = [];
  for (let k = -K; k <= K; k++) wts.push(Math.exp(-(k * k) / (2 * sigma * sigma)));
  const at = (x, y) => {
    x = Math.min(N - 1.001, Math.max(0, x - 0.5)); y = Math.min(N - 1.001, Math.max(0, y - 0.5));
    const i = Math.floor(x), j = Math.floor(y), fx = x - i, fy = y - j, o = j * N + i;
    return (src[o] * (1 - fx) + src[o + 1] * fx) * (1 - fy) + (src[o + N] * (1 - fx) + src[o + N + 1] * fx) * fy;
  };
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const px = x + 0.5, py = y + 0.5, dx = px - c.x, dy = py - c.y, r = Math.hypot(dx, dy);
    if (r < 1) { dst[y * N + x] = src[y * N + x]; continue; }
    const s = Math.min(1, r / (4 * sigma)), tx = (-dy / r) * s, ty = (dx / r) * s; // step shrinks near the center
    let acc = 0, w = 0;
    for (let k = -K; k <= K; k++) { acc += wts[k + K] * at(px + k * tx, py + k * ty); w += wts[k + K]; }
    dst[y * N + x] = acc / w;
  }
}

// Lines from gradients (Sobel on an already blurred image). Lines are
// undirected, so their orientation (mod 180°) falls in one of GL_BINS bins.
// Keep, in each bin, the `perBin` strongest pixels above a global floor (the
// `floorQ` quantile of all gradient magnitudes): every orientation gets an
// equal say, while orientations with no real edges (missing parts of the
// spiral) stay nearly empty instead of filling with noise. Weight =
// magnitude − floor. Returns arrays plus per-bin lists of line indices.
const GL_BINS = 64;
const glTmp = new Float32Array(N * N), glTmp2 = new Float32Array(N * N);
function gradientLines(src, perBin, floorQ) {
  const a = src;
  const mag = new Float32Array(N * N), GX = new Float32Array(N * N), GY = new Float32Array(N * N);
  let mMax = 0;
  for (let y = 1; y < N - 1; y++) for (let x = 1; x < N - 1; x++) {
    const i = y * N + x;
    const gx = (a[i - N + 1] + 2 * a[i + 1] + a[i + N + 1]) - (a[i - N - 1] + 2 * a[i - 1] + a[i + N - 1]);
    const gy = (a[i + N - 1] + 2 * a[i + N] + a[i + N + 1]) - (a[i - N - 1] + 2 * a[i - N] + a[i - N + 1]);
    GX[i] = gx; GY[i] = gy; mag[i] = Math.hypot(gx, gy);
    if (mag[i] > mMax) mMax = mag[i];
  }
  if (!(mMax > 0)) return null;
  // global floor: the floorQ quantile of the magnitudes (histogram)
  const H = 2048, hist = new Uint32Array(H);
  for (let i = 0; i < N * N; i++) hist[Math.min(H - 1, Math.floor((mag[i] / mMax) * H))]++;
  let acc = 0, tb = 0;
  while (tb < H - 1 && acc + hist[tb] < floorQ * N * N) acc += hist[tb++];
  const T = (tb / H) * mMax;
  const cand = Array.from({ length: GL_BINS }, () => []);
  for (let i = 0; i < N * N; i++) {
    if (mag[i] <= T) continue;
    let o = Math.atan2(GY[i], GX[i]);
    if (o < 0) o += Math.PI;
    cand[Math.min(GL_BINS - 1, Math.floor((o / Math.PI) * GL_BINS))].push(i);
  }
  const X = [], Y = [], W = [], UX = [], UY = [], BIN = [], bins = [];
  for (let bi = 0; bi < GL_BINS; bi++) {
    const c = cand[bi];
    if (c.length > perBin) { c.sort((p, q) => mag[q] - mag[p]); c.length = perBin; }
    const list = [];
    for (const i of c) {
      const x = i % N;
      list.push(X.length);
      X.push(x + 0.5); Y.push((i - x) / N + 0.5); W.push(mag[i] - T); UX.push(GX[i] / mag[i]); UY.push(GY[i] / mag[i]); BIN.push(bi);
    }
    bins.push(list);
  }
  return { X, Y, W, UX, UY, BIN, bins, n: X.length, T };
}

// Signed distance from point c to line k after the spiral correction about c.
// Spiral correction of a line through (px, py), about center c: shift by
// b·(sin α, −cos α) with (cos α, sin α) = (p − c)/|p − c| (no trig needed).
function shiftAbout(px, py, c, b) {
  const dx = px - c.x, dy = py - c.y, r = Math.hypot(dx, dy) || 1;
  return [px + (b * dy) / r, py - (b * dx) / r];
}

function lineDist(L, k, c, b) {
  let px = L.X[k], py = L.Y[k];
  if (b > 0) [px, py] = shiftAbout(px, py, c, b);
  return -L.UY[k] * (c.x - px) + L.UX[k] * (c.y - py);
}

// Weighted least-squares intersection of the lines with inl[k] set, each
// corrected about `ref`.
function intersectLines(L, inl, ref, b) {
  let a11 = 0, a12 = 0, a22 = 0, b1 = 0, b2 = 0, n = 0;
  for (let k = 0; k < L.n; k++) {
    if (!inl[k]) continue;
    let px = L.X[k], py = L.Y[k];
    if (b > 0) [px, py] = shiftAbout(px, py, ref, b);
    const nx = -L.UY[k], ny = L.UX[k], w = L.W[k], c = nx * px + ny * py;
    a11 += w * nx * nx; a12 += w * nx * ny; a22 += w * ny * ny; b1 += w * nx * c; b2 += w * ny * c; n++;
  }
  const det = a11 * a22 - a12 * a12;
  if (n < 3 || !(Math.abs(det) > 1e-12)) return null;
  return { x: (a22 * b1 - a12 * b2) / det, y: (a11 * b2 - a12 * b1) / det };
}

// RANSAC over pairs of lines (MSAC score): the first line is drawn with
// probability ∝ its weight; its partner from an orientation bin drawn with
// probability ∝ (lines in bin) · sin²(angle between the bins), then uniformly
// within that bin, so well-conditioned, near-perpendicular pairs are favoured
// (an intersection's error grows like 1/sin of the angle). A candidate center
// is the pair's intersection (spiral-corrected about it, twice); its cost is Σ w·min(d², ε²) over a fixed random subset of nSub lines
// (d = corrected distance, ε = 2 px). The best candidate is refined by the
// weighted intersection of its inliers (d < ε), recomputing inliers and
// corrections three times.
function ransacCenter(L, b, iters = 600, nSub = 1500, eps = 2) {
  const rnd = rng32(987654321);
  const sub = [];
  for (let i = 0; i < Math.min(nSub, L.n); i++) sub.push(Math.floor(rnd() * L.n));
  const cost = c => { let s = 0; for (const k of sub) { const d = lineDist(L, k, c, b); s += L.W[k] * Math.min(d * d, eps * eps); } return s; };
  const pair = (i, j, ref) => { // intersection of lines i, j (corrected about ref)
    let pix = L.X[i], piy = L.Y[i], pjx = L.X[j], pjy = L.Y[j];
    if (ref && b > 0) { [pix, piy] = shiftAbout(pix, piy, ref, b); [pjx, pjy] = shiftAbout(pjx, pjy, ref, b); }
    const den = L.UX[i] * L.UY[j] - L.UY[i] * L.UX[j];
    const s = ((pjx - pix) * L.UY[j] - (pjy - piy) * L.UX[j]) / den;
    return { x: pix + s * L.UX[i], y: piy + s * L.UY[i] };
  };
  const cumW = new Float64Array(L.n);
  for (let k = 0, s = 0; k < L.n; k++) cumW[k] = s += L.W[k];
  const drawCum = (cum, len) => { // index drawn ∝ increments of cum
    const t = rnd() * cum[len - 1];
    let lo = 0, hi = len - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (cum[m] < t) lo = m + 1; else hi = m; }
    return lo;
  };
  const sin2 = Array.from({ length: GL_BINS }, (_, d) => Math.sin((d * Math.PI) / GL_BINS) ** 2);
  const binCum = new Float64Array(GL_BINS);
  let best = null, bestC = Infinity, tries = 0;
  for (let it = 0; it < iters && tries < 20 * iters; tries++) {
    const i = drawCum(cumW, L.n), bi = L.BIN[i];
    for (let d = 0, s = 0; d < GL_BINS; d++) binCum[d] = s += L.bins[d].length * sin2[Math.abs(d - bi)];
    if (!(binCum[GL_BINS - 1] > 0)) continue;
    const list = L.bins[drawCum(binCum, GL_BINS)];
    const j = list[Math.floor(rnd() * list.length)];
    if (Math.abs(L.UX[i] * L.UY[j] - L.UY[i] * L.UX[j]) < 0.1) continue; // essentially parallel
    let c = pair(i, j, null);
    for (let r = 0; r < 2; r++) c = pair(i, j, c);
    if (!(c.x > -N / 2 && c.x < 1.5 * N && c.y > -N / 2 && c.y < 1.5 * N)) continue;
    it++;
    const v = cost(c);
    if (v < bestC) { bestC = v; best = c; }
  }
  if (!best) return null;
  let c = best, inl = new Uint8Array(L.n);
  for (let r = 0; r < 3; r++) {
    for (let k = 0; k < L.n; k++) inl[k] = Math.abs(lineDist(L, k, c, b)) < eps ? 1 : 0;
    c = intersectLines(L, inl, c, b) || c;
  }
  for (let k = 0; k < L.n; k++) inl[k] = Math.abs(lineDist(L, k, c, b)) < eps ? 1 : 0;
  let nIn = 0;
  for (const v of inl) nIn += v;
  return { c, inl, nIn };
}

// Center from gradient lines, with the tangential-blur loop: start from the
// plain (σ 1) image, then repeatedly blur along circles about the current
// center (σ = tang px), recompute the lines and the RANSAC center, until it
// moves < 1 px (at most 3 rounds; later rounds use 150 candidates and
// 1000 scoring lines, since they start close). Returns { c, L, inl, nIn, rounds }.
function gradientCenter(src, spacing, perBin, floorQ, spiral = true, tang = 0) {
  const b = spiral ? spacing / (2 * Math.PI) : 0;
  glTmp.set(src);
  gaussianBlur(glTmp, 1);
  let L = gradientLines(glTmp, perBin, floorQ);
  if (!L) return null;
  let r = ransacCenter(L, b, 600, 1500), rounds = 0;
  if (!r) return null;
  const path = [r.c];
  while (tang > 0 && rounds < 3) { // more rounds only chase noise
    tangentialBlur(glTmp, glTmp2, r.c, tang);
    const L2 = gradientLines(glTmp2, perBin, floorQ);
    const r2 = L2 && ransacCenter(L2, b, 150, 1000); // already close: fewer candidates
    if (!r2) break;
    rounds++;
    const moved = Math.hypot(r2.c.x - r.c.x, r2.c.y - r.c.y);
    L = L2; r = r2; path.push(r.c);
    if (moved < 1) break; // ~1 px is plenty for weighting turns by 1/r
  }
  // the image the final lines came from: last round's tangential blur, or the σ 1 blur
  return { c: r.c, L, inl: r.inl, nIn: r.nIn, rounds, path, img: rounds > 0 ? glTmp2 : glTmp };
}

const glCanvas = document.createElement('canvas');
glCanvas.width = glCanvas.height = N;
const glCtx = glCanvas.getContext('2d');
const glImage = glCtx.createImageData(N, N);
let gvResult = null;

function drawGradientVotes(ctx, r) { // inlier pixels in green
  const d = glImage.data;
  d.fill(0);
  for (let k = 0; k < r.L.n; k++) {
    if (!r.inl[k]) continue;
    const i = Math.floor(r.L.Y[k]) * N + Math.floor(r.L.X[k]);
    d[i * 4] = 40; d[i * 4 + 1] = 255; d[i * 4 + 2] = 120; d[i * 4 + 3] = 170;
  }
  glCtx.putImageData(glImage, 0, 0);
  ctx.drawImage(glCanvas, 0, 0);
}

function drawGradientMarkers(ctx, r) { // path of the tangential-blur rounds, final center (+)
  ctx.lineWidth = 2;
  ctx.strokeStyle = 'rgba(80,255,140,0.6)';
  for (const q of r.path.slice(0, -1)) { ctx.beginPath(); ctx.arc(q.x, q.y, 4, 0, 2 * Math.PI); ctx.stroke(); }
  const a = 9, c = r.c;
  ctx.strokeStyle = '#7fff9f';
  ctx.beginPath(); ctx.moveTo(c.x - a, c.y); ctx.lineTo(c.x + a, c.y); ctx.moveTo(c.x, c.y - a); ctx.lineTo(c.x, c.y + a); ctx.stroke();
}

// Blue plus through the canvas center (overlay only; not part of FFT input).
function drawCrosshair(ctx) {
  ctx.strokeStyle = 'rgb(60,130,255)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(N / 2, 0); ctx.lineTo(N / 2, N);
  ctx.moveTo(0, N / 2); ctx.lineTo(N, N / 2);
  ctx.stroke();
}

let pending = false;
function render() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => {
    pending = false;
    // Line width can't usefully exceed the ring spacing: its slider runs from
    // 0 to the current spacing (the browser clamps the value if needed).
    el.lineWidth.max = el.spacing.value;
    const p = params();
    for (const id of ['spacing', 'rStart', 'rEnd', 'phase', 'aspect', 'off20', 'off40', 'off60', 'off80', 'lineWidth', 'softness', 'blur', 'noise', 'gain', 'hVar', 'gvPerBin', 'gvFloor', 'gvTang']) {
      el[id].nextElementSibling.textContent = el[id].value;
    }
    document.getElementById('centerOut').textContent =
      `(${center.x.toFixed(1)}, ${center.y.toFixed(1)})`;

    el.softness.disabled = !p.smooth;
    el.phase.disabled = !p.spiral;
    el.hVar.disabled = !p.advanced;
    el.gvPerBin.disabled = !p.gradVote && !p.evenW;
    el.gvFloor.disabled = !p.gradVote && !p.evenW;
    el.gvShow.disabled = !p.gradVote;
    el.gvTang.disabled = !p.gradVote && !p.evenW;
    renderSpiral(p, center, img);
    if (p.noise > 0) for (let i = 0; i < N * N; i++) img[i] += p.noise * noiseField[i];
    // (even weighting needs the center too, even when it isn't shown)
    const gvRun = p.gradVote || p.evenW ? gradientCenter(img, p.spacing, p.gvPerBin, p.gvFloor, p.spiral, p.gvTang) : null;
    gvResult = p.gradVote ? gvRun : null;
    // Left pane: the image (FFT input), or with "Show blurred image" the
    // blurred image the gradient lines were computed from.
    toImageData(gvResult && p.gvShow ? gvResult.img : img, spiralImage); // (ImageData clamps to 0..255)
    octx.putImageData(spiralImage, 0, 0);
    sctx.drawImage(off, 0, 0);
    if (gvResult) drawGradientVotes(sctx, gvResult);
    document.getElementById('gvOut').textContent = !p.gradVote ? '' : !gvResult ? 'Gradient-vote center: no gradients.'
      : `Gradient-line center (green +): (${gvResult.c.x.toFixed(2)}, ${gvResult.c.y.toFixed(2)}), ` +
        `${Math.hypot(gvResult.c.x - center.x, gvResult.c.y - center.y).toFixed(2)} px from the true center; ` +
        `${gvResult.nIn} of ${gvResult.L.n} lines are inliers (green pixels); ${gvResult.rounds} tangential-blur round${gvResult.rounds === 1 ? '' : 's'} ` +
        `(earlier estimates: green circles).`;
    drawCrosshair(sctx);
    sctx.beginPath();
    sctx.arc(center.x, center.y, HANDLE_R, 0, 2 * Math.PI);
    sctx.fillStyle = 'rgba(255,40,40,0.6)';
    sctx.fill();
    sctx.strokeStyle = '#f33';
    sctx.lineWidth = 1.5;
    sctx.stroke();
    if (gvResult) drawGradientMarkers(sctx, gvResult);

    computeFFT(p, p.evenW && gvRun ? evenWeight(img, gvRun.c, p.spacing, p.evenW) : img);
    drawCrosshair(fctx);
    computeHarmonicScore({ advanced: p.advanced, vMin: p.hVar, target: p.spacing });
    drawProfile(p);
  });
}

// ---------- Interaction ----------

function canvasPos(e) {
  const r = spiralCanvas.getBoundingClientRect();
  return { x: ((e.clientX - r.left) * N) / r.width, y: ((e.clientY - r.top) * N) / r.height };
}

let drag = null;
spiralCanvas.addEventListener('pointerdown', e => {
  const m = canvasPos(e);
  // Drag is relative to where you clicked (no jump), so you can grab
  // anywhere in the image and nudge the center.
  drag = { mx: m.x, my: m.y, cx: center.x, cy: center.y };
  spiralCanvas.setPointerCapture(e.pointerId);
});
spiralCanvas.addEventListener('pointermove', e => {
  if (!drag) return;
  const m = canvasPos(e);
  const fine = e.shiftKey ? 0.1 : 1;
  center.x = Math.max(0, Math.min(N, drag.cx + (m.x - drag.mx) * fine));
  center.y = Math.max(0, Math.min(N, drag.cy + (m.y - drag.my) * fine));
  render();
});
spiralCanvas.addEventListener('pointerup', () => { drag = null; });
spiralCanvas.addEventListener('pointercancel', () => { drag = null; });

window.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' && e.target.type === 'range') return;
  const s = e.shiftKey ? 0.1 : 1;
  const moves = { ArrowLeft: [-s, 0], ArrowRight: [s, 0], ArrowUp: [0, -s], ArrowDown: [0, s] };
  const mv = moves[e.key];
  if (!mv) return;
  e.preventDefault();
  center.x += mv[0];
  center.y += mv[1];
  render();
});

spiralCanvas.addEventListener('dblclick', () => { center.x = center.y = N / 2; render(); });

// Reset every control to the value/checked state written in spacing.html, and
// recenter.
document.getElementById('defaults').addEventListener('click', () => {
  for (const id of ids) {
    if (el[id].type === 'checkbox') el[id].checked = el[id].defaultChecked;
    else if (el[id].tagName === 'SELECT') for (const o of el[id].options) o.selected = o.defaultSelected;
    else el[id].value = el[id].defaultValue;
  }
  center.x = center.y = N / 2;
  render();
});

for (const id of ids) el[id].addEventListener('input', render);
window.addEventListener('resize', render);
render();
