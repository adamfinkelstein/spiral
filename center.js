// center.html: the true spiral on the left; on the right, only the pixels in
// a few random chunks of the curve, as if only parts of it were recovered,
// split into connected components with a center/phase estimate for each.
// Rendering (renderSpiral, edgeStep, N) lives in render.js; components and
// fits (labelComponents, fitChunk, costMap) in chunkfit.js.

const truthCanvas = document.getElementById('truth');
const chunkCanvas = document.getElementById('chunks');
const tctx = truthCanvas.getContext('2d');
const cctx = chunkCanvas.getContext('2d');
const costCanvas = document.getElementById('cost');
const kctx = costCanvas.getContext('2d');

const center = { x: N / 2, y: N / 2 };
const HANDLE_R = 7;
const MAX_CHUNKS = 30; // must match the nChunks slider's max
const MAX_ROWS = 20;   // rows shown in the estimates table

const ids = ['spacing', 'rStart', 'rEnd', 'phase', 'aspect', 'lineWidth', 'softness', 'blur', 'smooth', 'nChunks', 'maxExtent', 'highlight', 'showCenter', 'spacingErr', 'noise', 'denoise', 'thresh', 'threshLo', 'minArea', 'minExtent', 'refine', 'shared', 'robust', 'cutoff', 'minInlier', 'combine', 'tau', 'showEst', 'showEll'];
const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));

function params() {
  return {
    spacing: +el.spacing.value,
    rStart: +el.rStart.value,
    rEnd: +el.rEnd.value,
    phase: (+el.phase.value * Math.PI) / 180,
    aspect: +el.aspect.value,
    lineWidth: +el.lineWidth.value,
    softness: +el.softness.value,
    blur: +el.blur.value,
    smooth: el.smooth.checked,
    spiral: true, // this page is spiral-only (render.js also does rings)
    nChunks: +el.nChunks.value,
    maxExtent: (+el.maxExtent.value * Math.PI) / 180,
    highlight: el.highlight.checked,
    showCenter: el.showCenter.checked,
    spacingErr: +el.spacingErr.value,
    noise: +el.noise.value,
    denoise: +el.denoise.value,
    thresh: +el.thresh.value,
    threshLo: +el.threshLo.value,
    shared: el.shared.checked,
    combine: el.combine.checked,
    tau: +el.tau.value,
    robust: el.robust.checked,
    cutoff: +el.cutoff.value,
    minInlier: +el.minInlier.value,
    minArea: +el.minArea.value,
    minExtent: (+el.minExtent.value * Math.PI) / 180,
    refine: el.refine.checked,
    showEst: el.showEst.checked,
    showEll: el.showEll.checked,
  };
}

// ---------- Random chunks ----------

// mulberry32 (seeded PRNG) lives in chunkfit.js.

// Each chunk is two uniform numbers in [0, 1): u, its position along the
// curve, and v, its angular extent as a fraction of the max extent. Kept
// fixed while sliders move, so the same chunks persist; raising the chunk
// count adds chunks without moving the existing ones.
let seed = 1;
let chunkU = [], chunkV = [];
function drawChunkPositions() {
  const rnd = mulberry32(seed);
  chunkU = []; chunkV = [];
  for (let k = 0; k < MAX_CHUNKS; k++) { chunkU.push(rnd()); chunkV.push(rnd()); }
}
drawChunkPositions();

// The chunks as θ intervals [lo, hi] (θ = r / b, radians). Chunk k spans
// v_k × max extent of θ; its middle is placed uniformly by arc length
// (s = bθ²/2, the same approximation as the spiral's end caps) among the
// positions that keep the whole chunk between start and end radius.
function chunkIntervals(p) {
  const b = p.spacing / (2 * Math.PI);
  const t0 = Math.min(p.rStart, p.rEnd) / b, t1 = Math.max(p.rStart, p.rEnd) / b;
  const out = [];
  for (let k = 0; k < p.nChunks; k++) {
    const ext = Math.min(chunkV[k] * p.maxExtent, t1 - t0);
    const ta = t0 + ext / 2, tb = t1 - ext / 2;
    const s = (b * ta * ta) / 2 + chunkU[k] * ((b * tb * tb) / 2 - (b * ta * ta) / 2);
    const tc = Math.sqrt((2 * s) / b);
    out.push({ lo: tc - ext / 2, hi: tc + ext / 2 });
  }
  return out;
}

// Builds weight(n, ra) for renderSpiral: 1 inside a chunk, 0 outside, with
// the same edge profile as the line edges at the chunk ends (measured in px
// along the arc, ≈ ra · Δθ).
function makeChunkWeight(p) {
  const sig = edgeStep(p);
  const b = p.spacing / (2 * Math.PI);
  const margin = 3 * Math.max(p.smooth ? p.softness : 0, 0.5); // px
  const chunks = chunkIntervals(p);
  return (n, ra) => {
    if (ra < 1e-6) return 0;
    const t = ra / b, m = margin / ra;
    let w = 0;
    for (const c of chunks) {
      if (t > c.lo - m && t < c.hi + m) w = Math.max(w, sig((t - c.lo) * ra) * sig((c.hi - t) * ra));
    }
    return w;
  };
}

// ---------- Noise ----------

// A fixed field of standard normal values (Box–Muller from the chunk seed),
// scaled by the noise slider and added to the chunk image before
// thresholding, so it stays put while other sliders move.
const noiseField = new Float32Array(N * N);
function drawNoise() {
  const rnd = mulberry32(seed * 7919 + 1);
  for (let i = 0; i < N * N; i += 2) {
    const u = Math.max(rnd(), 1e-12), v = rnd(), r = Math.sqrt(-2 * Math.log(u));
    noiseField[i] = r * Math.cos(2 * Math.PI * v);
    noiseField[i + 1] = r * Math.sin(2 * Math.PI * v);
  }
}
drawNoise();

// ---------- Drawing ----------

const full = new Float32Array(N * N);   // whole spiral
const part = new Float32Array(N * N);   // chunks only (clean)
const noisy = new Float32Array(N * N);  // chunks + noise, then denoising blur: what the estimation sees
const truthImage = tctx.createImageData(N, N);
const chunkImage = cctx.createImageData(N, N);
const HL = [255, 170, 40]; // chunk highlight colour on the left (amber)
const COST_G = 128;        // cost map grid size
const costVals = new Float32Array(COST_G * COST_G);
const costSmall = document.createElement('canvas');
costSmall.width = costSmall.height = COST_G;
const costSmallCtx = costSmall.getContext('2d');
const costSmallImage = costSmallCtx.createImageData(COST_G, COST_G);

// Distinct colour per component: golden-angle hues.
function compColor(k) {
  const h = (k * 137.508 + 200) % 360, s = 0.85, l = 0.6;
  const f = n => {
    const a = s * Math.min(l, 1 - l), kk = (n + h / 30) % 12;
    return Math.round(255 * (l - a * Math.max(-1, Math.min(kk - 3, 9 - kk, 1))));
  };
  return [f(0), f(8), f(4)];
}
const css = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

// Magma-like colour map, t in 0..1.
const MAGMA = [[0, 0, 4], [59, 15, 112], [140, 41, 129], [222, 73, 104], [254, 159, 109], [252, 253, 191]];
function magma(t) {
  t = Math.max(0, Math.min(1, t)) * (MAGMA.length - 1);
  const i = Math.min(MAGMA.length - 2, Math.floor(t)), f = t - i;
  return MAGMA[i].map((v, c) => v + (MAGMA[i + 1][c] - v) * f);
}

function drawHandle(ctx) {
  ctx.beginPath();
  ctx.arc(center.x, center.y, HANDLE_R, 0, 2 * Math.PI);
  ctx.fillStyle = 'rgba(255,40,40,0.6)';
  ctx.fill();
  ctx.strokeStyle = '#f33';
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function drawCross(ctx, x, y, color = 'rgba(255,60,60,0.95)', a = 9) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x - a, y); ctx.lineTo(x + a, y);
  ctx.moveTo(x, y - a); ctx.lineTo(x, y + a);
  ctx.stroke();
}

function drawDot(ctx, x, y, color, r = 4.5, filled = true, sel = false) {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, 2 * Math.PI);
  if (filled) { ctx.fillStyle = color; ctx.fill(); }
  ctx.lineWidth = sel ? 2.5 : 1.5;
  ctx.strokeStyle = filled ? (sel ? '#fff' : '#000') : color;
  ctx.stroke();
}

function drawStart(ctx, q, i) { // shared start: hollow (1) or filled (2) white square
  const a = 5;
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = '#fff';
  if (i === 1) { ctx.fillStyle = 'rgba(255,255,255,0.85)'; ctx.fillRect(q.x - a, q.y - a, 2 * a, 2 * a); }
  ctx.strokeRect(q.x - a, q.y - a, 2 * a, 2 * a);
}

function drawCombined(ctx, c, ell) { // combined estimate: yellow ring + ellipse
  if (ell) drawEllipse(ctx, c, 'rgba(255,212,0,0.95)', 2);
  ctx.beginPath();
  ctx.arc(c.x, c.y, 8, 0, 2 * Math.PI);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = '#ffd400';
  ctx.stroke();
}

function drawEllipse(ctx, f, color, width) { // 2σ ellipse from the 2×2 covariance
  if (!f.cov) return;
  const [[a, b], [, d]] = f.cov;
  const tr = (a + d) / 2, det = Math.sqrt(Math.max(0, ((a - d) / 2) ** 2 + b * b));
  const l1 = tr + det, l2 = Math.max(0, tr - det);
  if (!(l1 > 0) || !Number.isFinite(l1)) return;
  const ang = Math.atan2(l1 - a, b) || (a >= d ? 0 : Math.PI / 2);
  const r1 = Math.min(4 * N, 2 * Math.sqrt(l1)), r2 = Math.min(4 * N, 2 * Math.sqrt(l2));
  ctx.beginPath();
  ctx.ellipse(f.x, f.y, Math.max(r1, 0.5), Math.max(r2, 0.5), ang, 0, 2 * Math.PI);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.stroke();
}

// Selection: remembered as a point, so it follows the chunk as things move.
let selPoint = null;
function pickComponent(label, comps) {
  if (!comps.length) return -1;
  if (!selPoint) return 0;
  const sx = Math.floor(selPoint.x), sy = Math.floor(selPoint.y);
  let best = -1, bd = Infinity;
  for (let dy = -12; dy <= 12; dy++) {
    for (let dx = -12; dx <= 12; dx++) {
      const x = sx + dx, y = sy + dy;
      if (x < 0 || y < 0 || x >= N || y >= N) continue;
      const l = label[y * N + x], dd = dx * dx + dy * dy;
      if (l >= 0 && dd < bd) { bd = dd; best = l; }
    }
  }
  return best >= 0 ? best : 0;
}

const fmt = (v, d = 2) => (v == null || !Number.isFinite(v) ? '–' : v.toFixed(d));
const deg = r => (r * 180) / Math.PI;
let lastComps = [];
let costTimer = 0;
let lastStarts = [];
let lastCombo = null;

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
    for (const id of ['spacing', 'rStart', 'rEnd', 'phase', 'aspect', 'lineWidth', 'softness', 'blur', 'nChunks', 'maxExtent', 'spacingErr', 'noise', 'denoise', 'thresh', 'threshLo', 'minArea', 'minExtent', 'cutoff', 'minInlier', 'tau']) {
      el[id].nextElementSibling.textContent = el[id].value;
    }
    document.getElementById('centerOut').textContent = `(${center.x.toFixed(1)}, ${center.y.toFixed(1)})`;
    document.getElementById('seedOut').textContent = `set #${seed}`;
    el.softness.disabled = !p.smooth;
    el.showEll.disabled = !p.showEst;

    renderSpiral(p, center, full);
    renderSpiral(p, center, part, makeChunkWeight(p));

    // Left: whole spiral in white, chunk pixels tinted amber.
    const d = truthImage.data;
    for (let i = 0; i < N * N; i++) {
      const f = full[i], c = p.highlight ? part[i] : 0;
      const grey = (f - c) * 255;
      d[i * 4] = Math.round(grey + c * HL[0]);
      d[i * 4 + 1] = Math.round(grey + c * HL[1]);
      d[i * 4 + 2] = Math.round(grey + c * HL[2]);
      d[i * 4 + 3] = 255;
    }
    tctx.putImageData(truthImage, 0, 0);
    drawHandle(tctx);

    // Components and fits. The fits (and cost map) use the assumed spacing:
    // the true one scaled by the spacing-error slider.
    const pFit = { ...p, spacing: p.spacing * (1 + p.spacingErr / 100) };
    document.getElementById('assumedOut').textContent = pFit.spacing.toFixed(3);
    for (let i = 0; i < N * N; i++) noisy[i] = part[i] + p.noise * noiseField[i];
    if (p.denoise > 0) gaussianBlur(noisy, p.denoise);
    const { label, comps } = labelComponents(noisy, p.thresh, p.threshLo, p.minArea);
    // Fits keep only chunks whose estimated angular extent reaches Min extent
    // (short chunks only fix the center's direction, not its distance) and
    // enough of whose pixels lie on the fitted spiral.
    const fitOpts = { refine: p.refine, shared: p.shared, robust: p.robust, cutoff: p.cutoff, minExtent: p.minExtent, minInlier: p.minInlier };
    const { fits, starts } = fitComponents(noisy, comps, pFit, fitOpts);
    lastStarts = starts;
    const colors = comps.map((_, k) => compColor(k));
    const st = document.getElementById('startOut');
    st.textContent = starts.length
      ? `Shared start 1: (${starts[0].x.toFixed(1)}, ${starts[0].y.toFixed(1)}) from ${starts[0].n} circle fits, ${Math.hypot(starts[0].x - center.x, starts[0].y - center.y).toFixed(2)} px from truth; ` +
        `start 2: (${starts[1].x.toFixed(1)}, ${starts[1].y.toFixed(1)})` + (starts[1].n ? ` from ${starts[1].n} spiral fits` : ' (no kept fits; reused start 1)') +
        `, ${Math.hypot(starts[1].x - center.x, starts[1].y - center.y).toFixed(2)} px from truth.`
      : (p.shared && p.refine ? 'Shared start: no circle fit reaches Min extent; each chunk starts from its own circle fit.' : 'Each chunk starts from its own circle fit.');
    // Combine the kept chunks into one spiral (RANSAC over chunks).
    const combo = p.combine ? combineChunks(noisy, comps, fits, pFit, { cutoff: p.cutoff, tau: p.tau }) : null;
    lastCombo = combo;
    const co = document.getElementById('comboOut');
    co.innerHTML = !p.combine ? '' : !combo ? 'Combined: no kept chunks.'
      : `<b style="color:#ffd400">Combined</b>: (${combo.x.toFixed(2)}, ${combo.y.toFixed(2)}), ` +
        `${Math.hypot(combo.x - center.x, combo.y - center.y).toFixed(2)} px from truth; phase ${deg(combo.phase).toFixed(1)}° ` +
        `(error ${deg(wrapPi(combo.phase - p.phase)).toFixed(1)}°); ${combo.nIn} of ${combo.nKept} kept chunks agree ` +
        `(${combo.nHyp} hypotheses).`;
    const sel = pickComponent(label, comps);
    lastComps = comps;

    // Right: the (denoised) noisy chunk image, each component in its colour (scaled by
    // grey level); pixels not in any kept component stay grey.
    const cd = chunkImage.data;
    for (let i = 0; i < N * N; i++) {
      const v = Math.min(1, Math.max(0, noisy[i])), l = label[i];
      // kept chunks that disagree with the combined spiral are drawn dimmed
      const c = l < 0 || !fits[l].kept ? [110, 110, 110] : combo && !combo.inlier.get(l) ? colors[l].map(v => v * 0.4) : colors[l];
      cd[i * 4] = Math.round(v * c[0]);
      cd[i * 4 + 1] = Math.round(v * c[1]);
      cd[i * 4 + 2] = Math.round(v * c[2]);
      cd[i * 4 + 3] = 255;
    }
    cctx.putImageData(chunkImage, 0, 0);
    if (p.showEst) {
      fits.forEach((f, k) => {
        if (!f.kept) return;
        const col = colors[k];
        cctx.beginPath(); // chunk → its center estimate
        cctx.moveTo(f.mean.x, f.mean.y); cctx.lineTo(f.x, f.y);
        cctx.strokeStyle = css(col, 0.35); cctx.lineWidth = 1; cctx.stroke();
        if (p.showEll) drawEllipse(cctx, f, css(col, 0.9), k === sel ? 2 : 1);
      });
      fits.forEach((f, k) => { if (f.kept) drawDot(cctx, f.x, f.y, css(colors[k]), 4.5, !combo || combo.inlier.get(k), k === sel); });
    }
    if (p.showEst) lastStarts.forEach((q, i) => drawStart(cctx, q, i));
    if (combo) drawCombined(cctx, combo, p.showEll);
    if (p.showCenter) drawCross(cctx, center.x, center.y);

    drawTable(p, fits, colors, sel, combo);
    // The cost map is the slowest part: draw it just after this frame, and
    // skip it if another render is already queued (e.g. while dragging).
    clearTimeout(costTimer);
    costTimer = setTimeout(() => { if (!pending) drawCost(pFit, comps, fits, colors, sel, fitOpts); }, 0);
  });
}

function drawCost(p, comps, fits, colors, sel, fitOpts) {
  kctx.fillStyle = '#000';
  kctx.fillRect(0, 0, N, N);
  const out = document.getElementById('costOut');
  if (sel < 0) { out.textContent = 'No components.'; return; }
  const r = costMap(noisy, comps[sel], p, COST_G, costVals, fitOpts);
  const eps = fitOpts.robust ? 0.005 : 0.02;
  const lo = Math.log(r.min + eps), hi = Math.log(r.max + eps);
  const d = costSmallImage.data;
  for (let i = 0; i < COST_G * COST_G; i++) {
    const t = 1 - (Math.log(costVals[i] + eps) - lo) / Math.max(hi - lo, 1e-9); // low cost = bright
    const c = magma(t);
    d[i * 4] = c[0]; d[i * 4 + 1] = c[1]; d[i * 4 + 2] = c[2]; d[i * 4 + 3] = 255;
  }
  costSmallCtx.putImageData(costSmallImage, 0, 0);
  kctx.imageSmoothingEnabled = true;
  kctx.drawImage(costSmall, 0, 0, N, N);

  // The chunk itself, the true center, the circle fit, the fit and the grid minimum.
  const col = colors[sel], f = fits[sel];
  kctx.fillStyle = css(col);
  for (const j of comps[sel].core) kctx.fillRect(j % N, Math.floor(j / N), 1, 1);
  drawCross(kctx, center.x, center.y);
  if (f.ok) {
    if (f.circle) drawDot(kctx, f.circle.x, f.circle.y, css(col), 4.5, false);
    if (p.showEll) drawEllipse(kctx, f, css(col, 0.9), 1.5);
    drawDot(kctx, f.x, f.y, css(col), 4.5, true, true);
  }
  lastStarts.forEach((q, i) => drawStart(kctx, q, i));
  if (lastCombo) drawCombined(kctx, lastCombo, p.showEll);
  drawCross(kctx, r.at.x, r.at.y, '#fff', 5);
  out.textContent = fitOpts.robust
    ? `Grid ${COST_G}×${COST_G}; robust loss ${r.min.toFixed(3)} to ${r.max.toFixed(3)}.`
    : `Grid ${COST_G}×${COST_G}; RMS ${r.min.toFixed(2)} to ${r.max.toFixed(2)} px.`;
}

function drawTable(p, fits, colors, sel, combo) {
  // Components are numbered by size (labelComponents), so this is largest
  // first; at most MAX_ROWS (keeping the selected one).
  let order = fits.map((f, k) => k);
  const hidden = Math.max(0, order.length - MAX_ROWS);
  if (hidden) order = order.slice(0, MAX_ROWS - (order.indexOf(sel) >= MAX_ROWS ? 1 : 0)).concat(order.indexOf(sel) >= MAX_ROWS ? [sel] : []);
  const rows = order.map(k => {
    const f = fits[k];
    const sw = `<span class="sw" style="background:${css(colors[k])}"></span> ${k + 1}`;
    if (!f.ok) return `<tr data-k="${k}"${k === sel ? ' class="sel"' : ''}><td>${sw}</td><td>${f.nCore}</td><td colspan="8" style="text-align:left">${f.reason}</td></tr>`;
    const t = f.truth(center.x, center.y, p.phase, p.spacing);
    const err = Math.hypot(f.x - center.x, f.y - center.y);
    const ph = `${fmt(deg(f.phase), 1)} <span class="d">${fmt(deg(wrapPi(f.phase - p.phase)), 1)}</span>`;
    return `<tr data-k="${k}" class="${k === sel ? 'sel' : ''}${f.kept ? '' : ' drop'}"><td>${sw}</td><td>${f.nCore}</td><td>${fmt(100 * f.inlierFrac, 0)}</td><td>${fmt(f.meanR, 0)}</td>` +
      `<td>${fmt(deg(f.thetaMax - f.thetaMin), 0)} <span class="d">${fmt(deg(f.thetaMax - f.thetaMin - (t.thetaMax - t.thetaMin)), 0)}</span></td>` +
      `<td>${fmt(err, 2)}</td><td>${ph}</td>` +
      `<td>${fmt(f.thetaMin)} <span class="d">${fmt(f.thetaMin - t.thetaMin)}</span></td>` +
      `<td>${fmt(f.thetaMax)} <span class="d">${fmt(f.thetaMax - t.thetaMax)}</span></td>` +
      `<td>${combo && combo.delta.has(k) ? `${fmt(combo.delta.get(k), 3)} ${combo.inlier.get(k) ? '✓' : '<span style="color:#f66">✗</span>'}` : '–'}</td></tr>`;
  });
  document.getElementById('fits').innerHTML =
    '<tr><th>#</th><th>px</th><th>inl%</th><th>r</th><th>extent°</th><th>center err</th><th>phase°</th><th>θ min</th><th>θ max</th><th>agree Δ</th></tr>' + rows.join('') +
    (hidden ? `<tr class="more"><td colspan="10">… ${hidden} smaller component${hidden > 1 ? 's' : ''} not shown</td></tr>` : '');
}

// ---------- Interaction ----------

function canvasPos(e, canvas = truthCanvas) {
  const r = canvas.getBoundingClientRect();
  return { x: ((e.clientX - r.left) * N) / r.width, y: ((e.clientY - r.top) * N) / r.height };
}

let drag = null;
truthCanvas.addEventListener('pointerdown', e => {
  const m = canvasPos(e);
  drag = { mx: m.x, my: m.y, cx: center.x, cy: center.y }; // relative drag, no jump
  truthCanvas.setPointerCapture(e.pointerId);
});
truthCanvas.addEventListener('pointermove', e => {
  if (!drag) return;
  const m = canvasPos(e);
  const fine = e.shiftKey ? 0.1 : 1;
  center.x = Math.max(0, Math.min(N, drag.cx + (m.x - drag.mx) * fine));
  center.y = Math.max(0, Math.min(N, drag.cy + (m.y - drag.my) * fine));
  render();
});
truthCanvas.addEventListener('pointerup', () => { drag = null; });
truthCanvas.addEventListener('pointercancel', () => { drag = null; });

// Click a component (right pane or cost map) or a table row to select it.
for (const cv of [chunkCanvas, costCanvas]) {
  cv.addEventListener('click', e => { selPoint = canvasPos(e, cv); render(); });
}
document.getElementById('fits').addEventListener('click', e => {
  const tr = e.target.closest('tr[data-k]');
  if (!tr) return;
  const c = lastComps[+tr.dataset.k];
  if (!c) return;
  const j = c.core[Math.floor(c.core.length / 2)];
  selPoint = { x: (j % N) + 0.5, y: Math.floor(j / N) + 0.5 };
  render();
});

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

truthCanvas.addEventListener('dblclick', () => { center.x = center.y = N / 2; render(); });

document.getElementById('reseed').addEventListener('click', () => {
  seed++;
  drawChunkPositions();
  drawNoise();
  selPoint = null;
  render();
});

// Reset every control to the value/checked state written in center.html, and
// recenter (the chunk set is kept).
document.getElementById('defaults').addEventListener('click', () => {
  for (const id of ids) {
    if (el[id].type === 'checkbox') el[id].checked = el[id].defaultChecked;
    else el[id].value = el[id].defaultValue;
  }
  center.x = center.y = N / 2;
  render();
});

for (const id of ids) el[id].addEventListener('input', render);
render();
