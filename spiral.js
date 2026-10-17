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

const ids = ['spacing', 'rStart', 'rEnd', 'rotation', 'lineWidth', 'softness', 'gain', 'isSpiral', 'smooth', 'removeDC', 'window', 'showRing'];
const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));

function params() {
  return {
    spacing: +el.spacing.value,
    rStart: +el.rStart.value,
    rEnd: +el.rEnd.value,
    rotation: (+el.rotation.value * Math.PI) / 180,
    lineWidth: +el.lineWidth.value,
    softness: +el.softness.value,
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
    const dy = y + 0.5 - center.y;
    for (let x = 0; x < N; x++) {
      const dx = x + 0.5 - center.x;
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

  const d = spiralImage.data;
  for (let i = 0; i < N * N; i++) {
    const c = Math.round(img[i] * 255);
    d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = c;
    d[i * 4 + 3] = 255;
  }
  octx.putImageData(spiralImage, 0, 0);
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
    for (const id of ['spacing', 'rStart', 'rEnd', 'rotation', 'lineWidth', 'softness', 'gain']) {
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

for (const id of ids) el[id].addEventListener('input', render);
render();
