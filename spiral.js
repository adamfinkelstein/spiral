const N = 512;

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

const ids = ['spacing', 'rStart', 'rEnd', 'rotation', 'aspect', 'lineWidth', 'softness', 'blur', 'gain', 'isSpiral', 'smooth', 'removeDC', 'window', 'showRing'];
const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));

function params() {
  return {
    spacing: +el.spacing.value,
    rStart: +el.rStart.value,
    rEnd: +el.rEnd.value,
    rotation: (+el.rotation.value * Math.PI) / 180,
    aspect: +el.aspect.value,
    lineWidth: +el.lineWidth.value,
    softness: +el.softness.value,
    blur: +el.blur.value,
    smooth: el.smooth.checked,
    spiral: el.isSpiral.checked,
    gain: +el.gain.value,
    removeDC: el.removeDC.checked,
    window: el.window.checked,
    showRing: el.showRing.checked,
  };
}

// ---------- Spiral ----------

// Archimedean spiral r = b * theta, with b = spacing / (2π) so that
// successive rings are `spacing` pixels apart, for r in [rStart, rEnd].
// Rendered per pixel from the distance to the nearest arms.
// In rings mode, draws concentric circles at radii n * spacing within
// [rStart, rEnd] instead (rotation has no effect).
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
// Writes 0..1 values into `img`.
const img = new Float32Array(N * N);
const spiralImage = octx.createImageData(N, N);

// erf, Abramowitz & Stegun 7.1.26 (|error| < 1.5e-7)
function erf(x) {
  const s = x < 0 ? -1 : 1;
  x = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * x);
  const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
  return s * y;
}

function renderSpiral(p) {
  const S = p.spacing;
  const b = S / (2 * Math.PI);
  const r0 = Math.min(p.rStart, p.rEnd);
  const r1 = Math.max(p.rStart, p.rEnd);
  const halfW = p.lineWidth / 2;
  const sigma = Math.max(p.softness, 0.01) / 2.5631; // 10-90% width = 2.5631 σ
  const c = 1 / (sigma * Math.SQRT2);
  const sig = p.smooth ? x => 0.5 * (1 + erf(x * c)) : x => (x >= 0 ? 1 : 0);

  for (let y = 0; y < N; y++) {
    const dy = (y + 0.5 - center.y) * p.aspect;
    for (let x = 0; x < N; x++) {
      const dx = (x + 0.5 - center.x) / p.aspect;
      const r = Math.hypot(dx, dy);
      // u is fractional arm index; spiral arm n passes radius b * (phi + 2πn),
      // ring n has radius n * spacing.
      const phi = p.spiral ? Math.atan2(dy, dx) - p.rotation : 0;
      const u = (r / b - phi) / (2 * Math.PI);
      const n0 = Math.round(u);
      const perp = p.spiral ? r / Math.sqrt(r * r + b * b) : 1; // radial → perpendicular distance
      let v = 0;
      for (let n = n0 - 1; n <= n0 + 1; n++) {
        const d = S * (u - n); // signed radial distance to arm n
        const ra = r - d;      // radius of arm n at this angle
        if (ra < 0 || (!p.spiral && n <= 0)) continue; // no zero-radius ring
        const dp = d * perp;
        const prof = sig(dp + halfW) - sig(dp - halfW);
        if (prof < 1e-7) continue;
        // spiral: arc length (approx) from each end; rings: keep whole rings in range
        const cap = p.spiral
          ? sig((ra * ra - r0 * r0) / (2 * b)) * sig((r1 * r1 - ra * ra) / (2 * b))
          : (ra >= r0 - 1e-6 && ra <= r1 + 1e-6 ? 1 : 0);
        v += prof * cap;
      }
      img[y * N + x] = Math.min(1, v);
    }
  }

  if (p.blur > 0) gaussianBlur(img, p.blur);

  const d = spiralImage.data;
  for (let i = 0; i < N * N; i++) {
    const c = Math.round(img[i] * 255);
    d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = c;
    d[i * 4 + 3] = 255;
  }
  octx.putImageData(spiralImage, 0, 0);
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

function computeFFT(p) {
  let mean = 0;
  for (let i = 0; i < N * N; i++) {
    RE[i] = img[i];
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

function computeHarmonicScore() {
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

  let bi = 0;
  for (let i = 0; i < H_COUNT; i++) {
    const rho = hRho(i);
    let sum = 0, K = 0;
    for (let k = 1; (k + 0.5) * rho <= H_RMAX; k++, K++) {
      sum += profileAt(k * rho) - 0.5 * (profileAt((k - 0.5) * rho) + profileAt((k + 0.5) * rho));
    }
    hScore[i] = sum / Math.sqrt(K);
    if (hScore[i] > hScore[bi]) bi = i;
  }
  // parabolic refinement of the maximum between samples
  let rho = hRho(bi);
  if (bi > 0 && bi < H_COUNT - 1) {
    const a = hScore[bi - 1], b = hScore[bi], c = hScore[bi + 1];
    const den = a - 2 * b + c;
    if (den < 0) rho += (0.5 * (a - c) / den) * H_STEP;
  }
  hBest = { rho, spacing: N / rho };
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
}

// ---------- Rendering ----------

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
    const p = params();
    for (const id of ['spacing', 'rStart', 'rEnd', 'rotation', 'aspect', 'lineWidth', 'softness', 'blur', 'gain']) {
      el[id].nextElementSibling.textContent = el[id].value;
    }
    document.getElementById('centerOut').textContent =
      `(${center.x.toFixed(1)}, ${center.y.toFixed(1)})`;

    el.softness.disabled = !p.smooth;
    el.rotation.disabled = !p.spiral;
    renderSpiral(p);
    sctx.drawImage(off, 0, 0);
    drawCrosshair(sctx);
    sctx.beginPath();
    sctx.arc(center.x, center.y, HANDLE_R, 0, 2 * Math.PI);
    sctx.fillStyle = 'rgba(255,40,40,0.6)';
    sctx.fill();
    sctx.strokeStyle = '#f33';
    sctx.lineWidth = 1.5;
    sctx.stroke();

    computeFFT(p);
    drawCrosshair(fctx);
    computeHarmonicScore();
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

// Reset every control to the value/checked state written in index.html, and
// recenter.
document.getElementById('defaults').addEventListener('click', () => {
  for (const id of ids) {
    if (el[id].type === 'checkbox') el[id].checked = el[id].defaultChecked;
    else el[id].value = el[id].defaultValue;
  }
  center.x = center.y = N / 2;
  render();
});

for (const id of ids) el[id].addEventListener('input', render);
window.addEventListener('resize', render);
render();
