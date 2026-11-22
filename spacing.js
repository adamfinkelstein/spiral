
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

const ids = ['spacing', 'rStart', 'rEnd', 'phase', 'aspect', 'off20', 'off40', 'off60', 'off80', 'lineWidth', 'softness', 'blur', 'noise', 'gain', 'cohOn', 'cohSp', 'evenW', 'isSpiral', 'smooth', 'markErr', 'sWin', 'showRing'];
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
    cohOn: el.cohOn.checked,
    cohTrue: el.cohSp.value === 'true',
    evenW: +el.evenW.value, // weight exponent: 0 none, 0.5 1/√r, 1 1/r
    markErr: +el.markErr.value,
    sWin: +el.sWin.value / 100,
    showRing: el.showRing.checked,
  };
}

// ---------- Spiral ----------

// Rendering (renderSpiral, gaussianBlur, N) lives in render.js.
const img = new Float32Array(N * N);
const spiralImage = octx.createImageData(N, N);

// ---------- FFT: see fftspacing.js (FFT, radial profile, harmonic score) ----------

const fftImage = fctx.createImageData(N, N);


function computeFFT(p, src = img) {
  const max = computeSpectrum(src, false, false); // fftspacing.js: fills mag and profile (src already masked, mean removed)
  const d = fftImage.data;
  const scale = max > 0 ? 1 / max : 0;
  const h = N / 2;

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

// ---------- Harmonic sum: see fftspacing.js ----------

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
  if (isFinite(peak.spacing)) ctx.fillRect(L, T + 2, SX(Math.min(SP_MAX, peak.spacing)) - L, 12);
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

  // The smoothed profile (red), only where it is searched: within ±window of
  // the target spacing (dashed); its largest value (dot) gives the spacing.
  ctx.save();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = 'rgba(255,64,64,0.5)';
  ctx.lineWidth = 1;
  for (const r of [peak.lo, peak.hi]) { ctx.beginPath(); ctx.moveTo(X(r), T); ctx.lineTo(X(r), T + ph); ctx.stroke(); }
  ctx.restore();
  ctx.strokeStyle = '#ff4040';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let r = peak.lo; r <= peak.hi; r++) {
    const x = X(r), y = Y(Math.min(1, peakProfile[r]));
    if (r === peak.lo) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  const b0 = Math.floor(peak.rho), f = peak.rho - b0;
  const top = peakProfile[b0] * (1 - f) + peakProfile[Math.min(NBINS - 1, b0 + 1)] * f;
  ctx.fillStyle = '#ff4040';
  ctx.beginPath();
  ctx.arc(X(peak.rho), Y(Math.min(1, top)), 3.5, 0, 2 * Math.PI);
  ctx.fill();
  ctx.font = '12px system-ui, sans-serif';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'top';
  // red "radius → " followed by the purple spacing, right-aligned together
  const spText = `spacing ${peak.measured.toFixed(2)} px`;
  const right = L + pw - 6, ty = T + 18;
  ctx.fillText(`peak of the smoothed profile: radius ${peak.rho.toFixed(2)} → `, right - ctx.measureText(spText).width, ty);
  ctx.fillStyle = PURPLE;
  ctx.fillText(spText, right, ty);
  ctx.fillStyle = '#ddd';
  ctx.fillText(`white: mean log |FFT|; red: smoothed, where searched; prominence ${peak.prominence.toFixed(2)}`, right, T + 34);
  if (peak.edge || peak.weak) {
    ctx.fillStyle = '#ffb020';
    ctx.fillText(peak.edge ? '⚠ maximum on the edge of the search window: no reliable spacing (the pipeline stops)'
      : `⚠ peak less than 2× its background (prominence ${peak.prominence.toFixed(2)} < ln 2): no reliable spacing`, right, T + 50);
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

// ---------- Coherence center: see coherence.js ----------

const cohCanvas = document.getElementById('coh');
const cohCtx = cohCanvas.getContext('2d');
const cohImage = cohCtx.createImageData(N, N);
const zoomCanvas = document.getElementById('cohZoom');
const zoomCtx = zoomCanvas.getContext('2d');
const zoomImage = zoomCtx.createImageData(zoomCanvas.width, zoomCanvas.height);
const CYAN = '#3ff0ff';

function drawPlus(ctx, c, a, color, width = 2) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath(); ctx.moveTo(c.x - a, c.y); ctx.lineTo(c.x + a, c.y); ctx.moveTo(c.x, c.y - a); ctx.lineTo(c.x, c.y + a); ctx.stroke();
}

// |Z| / max, square-rooted so the faint rings show.
const zShade = (v, max) => Math.round(255 * Math.sqrt(Math.min(1, v / max)));

function drawCoherence(r, spacing) {
  const max = zAbs[Math.floor(r.peak.y) * N + Math.floor(r.peak.x)];
  const d = cohImage.data;
  for (let i = 0; i < N * N; i++) {
    d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = zShade(zAbs[i], max);
    d[i * 4 + 3] = 255;
  }
  cohCtx.putImageData(cohImage, 0, 0);
  drawPlus(cohCtx, r.c, 9, CYAN);

  // zoom: ±3 spacings about the fitted center, nearest pixel of the map
  const W = zoomCanvas.width, half = 3 * spacing, s = (2 * half) / W;
  const z = zoomImage.data;
  for (let y = 0; y < W; y++) for (let x = 0; x < W; x++) {
    const mx = Math.floor(r.c.x - half + (x + 0.5) * s), my = Math.floor(r.c.y - half + (y + 0.5) * s);
    const v = mx >= 0 && mx < N && my >= 0 && my < N ? zShade(zAbs[my * N + mx], max) : 0;
    const k = (y * W + x) * 4;
    z[k] = z[k + 1] = z[k + 2] = v; z[k + 3] = 255;
  }
  zoomCtx.putImageData(zoomImage, 0, 0);
  const toZoom = q => ({ x: (q.x - r.c.x + half) / s, y: (q.y - r.c.y + half) / s });
  const pk = toZoom(r.peak); // the map's brightest pixel
  zoomCtx.strokeStyle = '#ffd23f'; zoomCtx.lineWidth = 1.5;
  zoomCtx.strokeRect(pk.x - 5, pk.y - 5, 10, 10);
  const t = toZoom(center);
  zoomCtx.fillStyle = 'rgba(255,40,40,0.8)';
  zoomCtx.beginPath(); zoomCtx.arc(t.x, t.y, 5, 0, 2 * Math.PI); zoomCtx.fill();
  drawPlus(zoomCtx, toZoom(r.c), 12, CYAN);
}

function clearCoherence() {
  cohCtx.fillStyle = '#000'; cohCtx.fillRect(0, 0, N, N);
  zoomCtx.fillStyle = '#000'; zoomCtx.fillRect(0, 0, zoomCanvas.width, zoomCanvas.height);
}

const deg = a => (a * 180) / Math.PI;
const wrapDeg = a => deg(Math.atan2(Math.sin(a), Math.cos(a)));

function coherenceText(p, r, spacing) {
  const err = Math.hypot(r.c.x - center.x, r.c.y - center.y);
  return `Coherence center (cyan +): (${r.c.x.toFixed(2)}, ${r.c.y.toFixed(2)}), ${err.toFixed(3)} px from the true center (red); ` +
    `phase ${((deg(r.phase) + 360) % 360).toFixed(1)}° (true ${deg(p.phase).toFixed(0)}°, error ${wrapDeg(r.phase - p.phase).toFixed(1)}°). ` +
    `Spacing used: ${spacing.toFixed(2)} px (${p.cohTrue ? 'true' : 'the FFT estimate'}). Center: point symmetry of |Z| near its peak (yellow square, ` +
    `${Math.hypot(r.peak.x - r.c.x, r.peak.y - r.c.y).toFixed(1)} px away), on a ${r.crop}² crop; phase: the angle of Z there. ` +
    `Map ${r.msMap.toFixed(0)} ms, center and phase ${r.msCenter.toFixed(0)} ms.`;
}

// ---------- Simulated hand mark ----------

// Fixed random errors (from the noise field, so they stay put while sliders
// move): center off by Hand-mark error × a standard normal per axis, radii
// off by 1% × a standard normal (as on the cards).
const shown = new Float32Array(N * N);
function handMark(p) {
  return {
    x: center.x + p.markErr * noiseField[0], y: center.y + p.markErr * noiseField[1],
    rInner: Math.min(p.rStart, p.rEnd) * (1 + 0.01 * noiseField[2]),
    rOuter: Math.max(p.rStart, p.rEnd) * (1 + 0.01 * noiseField[3]),
  };
}

function drawMark(ctx, mark) { // dashed marked circles, white + at the marked center
  ctx.save();
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = 'rgba(255,255,255,0.7)';
  ctx.lineWidth = 1.2;
  for (const r of [mark.rInner, mark.rOuter]) { ctx.beginPath(); ctx.arc(mark.x, mark.y, r, 0, 2 * Math.PI); ctx.stroke(); }
  ctx.restore();
  drawPlus(ctx, mark, 8, '#fff', 2);
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
    for (const id of ['spacing', 'rStart', 'rEnd', 'phase', 'aspect', 'off20', 'off40', 'off60', 'off80', 'lineWidth', 'softness', 'blur', 'noise', 'gain', 'markErr', 'sWin']) {
      el[id].nextElementSibling.textContent = el[id].value;
    }
    document.getElementById('centerOut').textContent =
      `(${center.x.toFixed(1)}, ${center.y.toFixed(1)})`;

    el.softness.disabled = !p.smooth;
    el.phase.disabled = !p.spiral;
    renderSpiral(p, center, img);
    if (p.noise > 0) for (let i = 0; i < N * N; i++) img[i] += p.noise * noiseField[i];
    // Simulated hand annotation (as on the cards): the true center and radii
    // plus fixed random errors; its annulus is the mask (fftspacing.js).
    const mark = handMark(p);
    const mask = annulusMask(mark, p.spacing);
    const norm = normalizeInMask(img, mask);
    // Left pane: the image, dimmed outside the mask.
    for (let i = 0; i < N * N; i++) shown[i] = img[i] * (0.3 + 0.7 * mask[i]);
    toImageData(shown, spiralImage); // (ImageData clamps to 0..255)
    octx.putImageData(spiralImage, 0, 0);
    sctx.drawImage(off, 0, 0);
    drawMark(sctx, mark);
    document.getElementById('centerOut').textContent = `(${center.x.toFixed(1)}, ${center.y.toFixed(1)}); hand mark (white +, dashed circles) ` +
      `${Math.hypot(mark.x - center.x, mark.y - center.y).toFixed(1)} px off`;
    drawCrosshair(sctx);
    sctx.beginPath();
    sctx.arc(center.x, center.y, HANDLE_R, 0, 2 * Math.PI);
    sctx.fillStyle = 'rgba(255,40,40,0.6)';
    sctx.fill();
    sctx.strokeStyle = '#f33';
    sctx.lineWidth = 1.5;
    sctx.stroke();

    computeFFT(p, fftInput(norm, mask, mark, p.spacing, p.evenW)); // weighted about the mark, mask as the window
    drawCrosshair(fctx);
    profilePeak({ target: p.spacing, window: p.sWin }); // fftspacing.js, as cardlab
    drawProfile(p);

    // Coherence center, with the FFT's spacing estimate (spiral only)
    el.cohOn.disabled = !p.spiral;
    el.cohSp.disabled = !p.spiral || !p.cohOn;
    document.getElementById('cohRow').style.display = p.cohOn && p.spiral ? '' : 'none';
    const cohOut = document.getElementById('cohOut');
    if (p.cohOn && p.spiral && !p.cohTrue && !isFinite(peak.spacing)) {
      clearCoherence();
      cohOut.textContent = `Coherence center: skipped, no reliable spacing (the FFT peak is ${peak.edge ? 'on the edge of the search window' : 'too weak'}).`;
    } else if (p.cohOn && p.spiral) {
      const sp = p.cohTrue ? p.spacing : peak.spacing;
      const r = coherenceCenter(norm, sp, mark); // the masked image and the mark, as in cardlab
      drawCoherence(r, sp);
      drawPlus(sctx, r.c, 9, CYAN);
      cohOut.textContent = coherenceText(p, r, sp);
    } else {
      clearCoherence();
      cohOut.textContent = p.cohOn ? 'Coherence center: spiral only (rings have no winding).' : '';
    }
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
