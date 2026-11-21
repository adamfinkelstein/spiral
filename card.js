// card.html: a realistic card (cardmodel.js) through the whole pipeline
// (cardpipe.js): low-res spacing, center and phase from a hand-marked start,
// then the full-res strip, geometry refit and groove trace, scored against the
// card's truth.

const $ = id => document.getElementById(id);
const cardCv = $('card'), cardCtx = cardCv.getContext('2d');
const detCv = $('detail'), detCtx = detCv.getContext('2d');
const stripCv = $('strip'), stripCtx = stripCv.getContext('2d');
const plotCv = $('plot'), plotCtx = plotCv.getContext('2d');
const turnCv = $('turns'), turnCtx = turnCv.getContext('2d');
const DET = 256; // detail window, full-res px
$('detailSize').textContent = `${DET}×${DET}`;

for (const [k, v] of Object.entries(CARD_PRESETS)) {
  const o = document.createElement('option'); o.value = k; o.textContent = v.label; $('preset').appendChild(o);
}

// what each preset parameter is and where its value came from
const PARAM_INFO = [
  ['F', 'Frame size', 'px', 'scan 9600² aligned, card ~5551² after crop (image 22)'],
  ['spacing', 'Nominal groove spacing', 'px', 'measured 29.0 (image 21 patch; FFT 29.1 on sonorine_001)'],
  ['spacingTol', 'True spacing within ±', '×', 'assumed (cards 25.9–32.2 px across machines)'],
  ['rIn', 'Inner groove radius', 'px', 'image 22 (~1600)'],
  ['rOut', 'Outer groove radius', 'px', 'image 22 (~2770): ~40 turns'],
  ['centerJitter', 'Card center vs. frame center (σ)', 'px', 'assumed'],
  ['annotErr', 'Hand-mark error (σ per axis)', 'px', 'assumed'],
  ['annotRadiusErr', 'Hand-marked radii error (σ)', '×', 'assumed'],
  ['groove', 'Groove amplitude (cosine)', '', 'unit; profile near-sinusoidal, groove ≈ 47% of spacing (image 21)'],
  ['edgeFade', 'Groove fade at the ends', 'px', 'assumed'],
  ['grain', 'Fine grain (rms)', '', 'measured: 2.6 vs. groove 5.0 rms'],
  ['grainCell', 'Grain cell size', 'px', 'measured ACF 0.5 at ~3–5 px'],
  ['slow', 'Slow depth drift (rms)', '', 'measured: 10.9 vs. groove 5.0 rms'],
  ['slowCell', 'Slow drift scale', 'px', 'measured correlation ~90 px'],
  ['drift', 'Groove drift from the spiral (rms)', 'px', 'phase between turns varies ±2 px (image 21)'],
  ['driftTurns', 'Drift periods', 'turns', 'assumed'],
  ['audio', 'Audio lateral modulation (rms)', 'px', 'wobble along the arc ~1.3 px (incl. noise)'],
  ['audioWave', 'Audio wavelengths', 'px', 'assumed (smooth over ~10 px)'],
  ['aspect', 'Stretch (aspect − 1, ±)', '', 'assumed (scanner)'],
  ['warp', 'Smooth warp (rms)', 'px', 'assumed (card not flat)'],
  ['warpScale', 'Warp wavelengths', 'px', 'assumed'],
  ['banding', 'Scanner banding', '', 'assumed'],
  ['bandPeriod', 'Banding period', 'px', 'assumed'],
  ['dust', 'Dust specks', 'count', 'assumed'],
  ['dustAmp', 'Dust depth', '', 'assumed'],
  ['scratches', 'Scratches', 'count', 'assumed'],
  ['scratchAmp', 'Scratch depth', '', 'assumed'],
  ['damage', 'Damaged sector', '', 'assumed: width rad, groove ×, grain ×'],
];

function showParams(P) {
  const fmt = v => (v === null ? 'none' : Array.isArray(v) ? v.join('–') : typeof v === 'object' ? `${v.width} rad, ×${v.groove}, ×${v.grain}` : String(v));
  $('params').innerHTML = '<tr><th>Parameter</th><th>Value</th><th style="text-align:left">Source</th></tr>' +
    PARAM_INFO.map(([k, name, unit, src]) => `<tr><td>${name}</td><td>${fmt(P[k])}${unit && P[k] !== null ? ' ' + unit : ''}</td><td class="src">${src}</td></tr>`).join('');
}

// ---------- state ----------
let card = null, img = null, low = null, strip = null, spot = null, runId = 0;
const status = s => { $('status').textContent = s; };
class Stale extends Error {}
const guard = id => { if (id !== runId) throw new Stale(); };

async function run() {
  const id = ++runId;
  try {
    const t0 = performance.now();
    card = makeCard($('preset').value, +$('seed').value || 1);
    low = strip = null;
    showParams(card.P);
    img = new Float32Array(N * N);
    await renderLowRes(card, img, 2, f => { guard(id); status(`Rendering the low-res card… ${Math.round(100 * f)}%`); });
    guard(id); drawCard(); status('Low-res stage: spacing, center, phase…'); await tick(); guard(id);
    const t1 = performance.now();
    low = lowResStage(img, card.F, card.P.spacing, card.ann, { search: 60, gradient: $('gradient').checked });
    const t2 = performance.now();
    drawCard(); await tick(); guard(id);
    await runStrip(id);
    const t3 = performance.now();
    status(`Done in ${((t3 - t0) / 1000).toFixed(1)} s (low-res render ${((t1 - t0) / 1000).toFixed(1)}, low-res stage ${((t2 - t1) / 1000).toFixed(1)}, full-res stage ${((t3 - t2) / 1000).toFixed(1)}).`);
  } catch (e) {
    if (!(e instanceof Stale)) { status('Error: ' + e.message); throw e; }
  }
}

async function runStrip(id) {
  const g = low.geom, S = CARD_TAU * g.b;
  const TH = stripColumns(g, card.ann, 3, +$('turnsSel').value);
  const Z = await demodPass(card, g, TH, S, null, 1, f => { guard(id); status(`Full-res strip: ${TH.length.toLocaleString()} columns… ${Math.round(100 * f)}%`); });
  guard(id);
  const U = unwrapOffsets(Z, S, 0, null, false);
  const R = refitGeometry(g, TH, U.o, U.amp, S);
  strip = { g, S, TH, Z, R };
  track();
}

// lock the trace (fast: re-run when only the smoothing changes) and score it
function track() {
  const { g, S, TH, Z, R } = strip, n = TH.length;
  const u = unwrapOffsets(Z, S, +$('smooth').value, null, false);
  const L = lockTrack(u.o, u.amp, R.model, S, 100);
  const tOff = new Float64Array(n), D = new Float64Array(n);
  for (let i = 0; i < n; i++) { const t = truthAt(card, g, TH[i], L.o[i]); tOff[i] = t.tOff; D[i] = t.thTrue - TH[i]; }
  const ds = []; for (let i = 0; i < n; i += 7) ds.push(D[i]);
  const md = median(ds), wrong = new Uint8Array(n);
  for (let i = 0; i < n; i++) wrong[i] = Math.round((D[i] - md) / CARD_TAU) !== 0 ? 1 : 0;
  Object.assign(strip, { o: L.o, ref: L.ref, amp: u.amp, tOff, wrong });
  if (!spot) { // default spot: middle of the traced range, upper right
    const i = Math.floor(n / 2), [x, y] = stripPoint(g, TH[i], L.o[i]);
    spot = { x, y };
  }
  showResults(); drawAll();
}

// ---------- metrics ----------

// RMS distance (mod S) from a fitted spiral to the true grooves over the
// traced columns. m(i): the spiral's offset from the strip's center line
// (0 for the low-res spiral the strip was laid along, the refit's model).
function spiralErr(m) {
  const { o, tOff } = strip, S = card.S;
  let s = 0;
  for (let i = 0; i < o.length; i++) { let d = o[i] + tOff[i] - m(i); d -= S * Math.round(d / S); s += d * d; }
  return Math.sqrt(s / o.length);
}

function showResults() {
  const C = card.C, f = (v, d = 2) => v.toFixed(d), cerr = p => Math.hypot(p.x - C.x, p.y - C.y);
  const sp = s => `${f(s, 3)} <span style="color:#888">(${s >= card.S ? '+' : ''}${f(100 * (s / card.S - 1), 2)}%)</span>`;
  const rows = [];
  rows.push(`<tr><th>Stage</th><th>Center error</th><th>Spacing</th><th>Spiral vs. grooves</th></tr>`);
  rows.push(`<tr><td><span class="k" style="background:#fff"></span>Hand mark + nominal</td><td>${f(cerr(card.ann), 1)}</td><td>${sp(card.P.spacing)}</td><td>–</td></tr>`);
  rows.push(`<tr><td>Low-res FFT spacing</td><td>–</td><td>${sp(low.spacing)}${low.fftOK ? '' : ' <span style="color:#f88">rejected</span>'}</td><td>–</td></tr>`);
  if (low.gc) rows.push(`<tr><td><span class="k" style="background:#f6f"></span>Gradient-line center</td><td>${f(cerr(low.gc), 1)}</td><td>–</td><td>–</td></tr>`);
  rows.push(`<tr><td><span class="k" style="background:#4cf"></span>Low-res coherence fit</td><td>${f(cerr(low.geom))}</td><td>${sp(CARD_TAU * low.geom.b)}</td><td>${f(spiralErr(() => 0))}</td></tr>`);
  const R = strip.R.geom;
  rows.push(`<tr><td><span class="k" style="background:#fd3"></span>Full-res refit</td><td>${f(cerr(R))}</td><td>${sp(CARD_TAU * R.b)}</td><td>${f(spiralErr(i => strip.R.model[i]))}</td></tr>`);
  rows.push(`<tr><td colspan="4" class="src">Coherence ${f(low.coherence)} (1 = perfect cosine groove). True spacing ${f(card.S, 3)} px. Spiral vs. grooves: RMS radial distance (px, mod S) from the fitted spiral to the true grooves over the traced turns: what is left for the trace to follow (drift, audio, warp).</td></tr>`);
  $('est').innerHTML = rows.join('');

  const { tOff, wrong, o, TH } = strip, n = TH.length;
  let se = 0, big = 0, nw = 0;
  for (let i = 0; i < n; i++) { se += tOff[i] ** 2; if (Math.abs(tOff[i]) > card.S / 4) big++; nw += wrong[i]; }
  // audio band: both traced and true offsets minus their Gaussian smoothing
  // over σ 300 px of groove (100 columns)
  const oT = Float64Array.from(o, (v, i) => v + tOff[i]), sT = smooth1d(oT, 100), sE = smooth1d(o, 100);
  let sxy = 0, sxx = 0, syy = 0, sd = 0;
  for (let i = 0; i < n; i++) { const a = oT[i] - sT[i], b = o[i] - sE[i]; sxy += a * b; sxx += a * a; syy += b * b; sd += (a - b) ** 2; }
  const turns = (TH[n - 1] - TH[0]) / CARD_TAU;
  $('trace').innerHTML = [
    `<tr><td>Columns traced</td><td>${n.toLocaleString()} (${f(turns, 1)} turns, ${(3 * n / 1000).toFixed(0)} k px of groove)</td></tr>`,
    `<tr><td>RMS distance to the true groove</td><td>${f(Math.sqrt(se / n))} px</td></tr>`,
    `<tr><td>Columns off by more than S/4</td><td>${f((100 * big) / n)}%</td></tr>`,
    `<tr><td>Columns on the wrong groove</td><td>${f((100 * nw) / n)}%</td></tr>`,
    `<tr><td>Audio band (λ ≲ 1 k px): true RMS</td><td>${f(Math.sqrt(sxx / n))} px</td></tr>`,
    `<tr><td>Audio band: error RMS / correlation</td><td>${f(Math.sqrt(sd / n))} px / ${f(sxy / Math.sqrt(sxx * syy), 3)}</td></tr>`,
  ].join('');
}

// ---------- drawing ----------

const K = () => card.F / N; // full-res px per low-res px
function stretch(a, step = 1) { // 2nd–98th percentile of a sample
  const s = []; for (let i = 0; i < a.length; i += step) s.push(a[i]);
  s.sort((x, y) => x - y);
  return [s[Math.floor(0.02 * s.length)], s[Math.floor(0.98 * s.length)]];
}

function drawCard() { // the raw low-res depth until the low-res stage has run, then its local-contrast image
  const im = low ? low.hp : img;
  const [lo, hi] = stretch(im, 37), id = cardCtx.createImageData(N, N), sc = 255 / (hi - lo);
  for (let i = 0; i < N * N; i++) { const v = Math.max(0, Math.min(255, (im[i] - lo) * sc)); id.data[4 * i] = id.data[4 * i + 1] = id.data[4 * i + 2] = v; id.data[4 * i + 3] = 255; }
  cardCtx.putImageData(id, 0, 0);
  const k = K(), c = cardCtx;
  const cross = (x, y, col, a = 14, w = 2) => { c.strokeStyle = col; c.lineWidth = w; c.beginPath(); c.moveTo(x / k - a, y / k); c.lineTo(x / k + a, y / k); c.moveTo(x / k, y / k - a); c.lineTo(x / k, y / k + a); c.stroke(); };
  const ring = (x, y, r, col, w = 2) => { c.strokeStyle = col; c.lineWidth = w; c.beginPath(); c.arc(x / k, y / k, r, 0, CARD_TAU); c.stroke(); };
  // annotation
  c.setLineDash([8, 8]); c.strokeStyle = 'rgba(255,255,255,0.7)'; c.lineWidth = 2;
  for (const r of [card.ann.rIn, card.ann.rOut]) { c.beginPath(); c.arc(card.ann.x / k, card.ann.y / k, r / k, 0, CARD_TAU); c.stroke(); }
  c.setLineDash([]);
  cross(card.ann.x, card.ann.y, '#fff');
  if (low && low.gc) ring(low.gc.x, low.gc.y, 7, '#f6f');
  if (low) ring(low.geom.x, low.geom.y, 10, '#4cf');
  if (strip) ring(strip.R.geom.x, strip.R.geom.y, 14, '#fd3');
  cross(card.C.x, card.C.y, '#f44', 10, 2);
  if (spot) { c.strokeStyle = '#f44'; c.lineWidth = 2; c.strokeRect((spot.x - DET / 2) / k, (spot.y - DET / 2) / k, DET / k, DET / k); }
}

function drawDetail() {
  const id = detCtx.createImageData(DET, DET), x0 = spot.x - DET / 2, y0 = spot.y - DET / 2, v = new Float32Array(DET * DET);
  for (let y = 0; y < DET; y++) for (let x = 0; x < DET; x++) v[y * DET + x] = card.sample(x0 + x + 0.5, y0 + y + 0.5);
  const [lo, hi] = stretch(v, 3), sc = 255 / (hi - lo);
  for (let i = 0; i < DET * DET; i++) { const q = Math.max(0, Math.min(255, (v[i] - lo) * sc)); id.data[4 * i] = id.data[4 * i + 1] = id.data[4 * i + 2] = q; id.data[4 * i + 3] = 255; }
  const tmp = document.createElement('canvas'); tmp.width = tmp.height = DET; tmp.getContext('2d').putImageData(id, 0, 0);
  detCtx.imageSmoothingEnabled = false; detCtx.drawImage(tmp, 0, 0, 512, 512);
  // trace and truth: columns whose point falls in the window
  const s = 512 / DET, { g, TH, o, tOff } = strip;
  for (let i = 0; i < TH.length; i++) {
    const [x, y] = stripPoint(g, TH[i], o[i]);
    if (x < x0 || y < y0 || x >= x0 + DET || y >= y0 + DET) continue;
    const [tx, ty] = stripPoint(g, TH[i], o[i] + tOff[i]);
    detCtx.fillStyle = '#3e6'; detCtx.fillRect((tx - x0) * s - 1.5, (ty - y0) * s - 1.5, 3, 3);
    detCtx.fillStyle = strip.wrong[i] ? '#f0f' : '#f44'; detCtx.fillRect((x - x0) * s - 1.5, (y - y0) * s - 1.5, 3, 3);
  }
}

// columns of the strip window around the spot (nearest column to it)
function stripWindow(W) {
  const { g, TH } = strip, dx = spot.x - g.x, dy = spot.y - g.y, r = Math.hypot(dx, dy);
  const al = Math.atan2(dy, dx) - g.ph, th = al + CARD_TAU * Math.round((r / g.b - al) / CARD_TAU);
  let lo = 0, hi = TH.length - 1; // first column with TH ≥ th
  while (lo < hi) { const m = (lo + hi) >> 1; if (TH[m] < th) lo = m + 1; else hi = m; }
  const c = lo;
  const i0 = Math.max(0, Math.min(TH.length - W, c - W / 2));
  return [i0, Math.min(TH.length, i0 + W)];
}

function drawStrip() {
  const W = stripCv.width, H = stripCv.height, { g, S, TH, o, tOff, R } = strip;
  const [i0, i1] = stripWindow(W), rows = Math.round(1.6 * S), ry = H / (2 * rows + 1);
  const v = new Float32Array(W * (2 * rows + 1));
  for (let i = i0; i < i1; i++) {
    const a = TH[i] + g.ph, ca = Math.cos(a), sa = Math.sin(a), R0 = g.b * TH[i];
    let m = 0;
    for (let j = -rows; j <= rows; j++) m += v[(j + rows) * W + (i - i0)] = card.sample(g.x + (R0 + j) * ca, g.y + (R0 + j) * sa);
    m /= 2 * rows + 1; // display: remove each column's mean (the slow depth drift)
    for (let j = -rows; j <= rows; j++) v[(j + rows) * W + (i - i0)] -= m;
  }
  const [lo, hi] = stretch(v, 5), sc = 255 / (hi - lo), id = stripCtx.createImageData(W, H);
  for (let y = 0; y < H; y++) {
    const j = Math.min(2 * rows, Math.floor(y / ry)); // outward = up
    for (let x = 0; x < W; x++) {
      const q = Math.max(0, Math.min(255, (v[(2 * rows - j) * W + x] - lo) * sc)), p = 4 * (y * W + x);
      id.data[p] = id.data[p + 1] = id.data[p + 2] = q; id.data[p + 3] = 255;
    }
  }
  stripCtx.putImageData(id, 0, 0);
  const yOf = d => (rows - d + 0.5) * ry;
  const line = (f, col, w = 1.5) => {
    stripCtx.strokeStyle = col; stripCtx.lineWidth = w; stripCtx.beginPath();
    let pen = false;
    for (let i = i0; i < i1; i++) { const d = f(i); if (Math.abs(d) > rows) { pen = false; continue; } const x = i - i0 + 0.5; if (pen) stripCtx.lineTo(x, yOf(d)); else stripCtx.moveTo(x, yOf(d)); pen = true; }
    stripCtx.stroke();
  };
  line(i => R.model[i], 'rgba(255,221,51,0.8)', 1);
  line(i => R.model[i] + S, 'rgba(255,221,51,0.35)', 1); line(i => R.model[i] - S, 'rgba(255,221,51,0.35)', 1);
  line(i => o[i] + tOff[i], 'rgba(60,230,100,0.9)');
  line(i => o[i], 'rgba(255,68,68,0.9)');
}

function drawPlot() {
  const W = plotCv.width, H = plotCv.height, { o, tOff, R, S } = strip, c = plotCtx;
  const [i0, i1] = stripWindow(W);
  c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
  let mx = 2;
  for (let i = i0; i < i1; i++) mx = Math.max(mx, Math.abs(o[i] - R.model[i]), Math.abs(o[i] + tOff[i] - R.model[i]));
  mx = Math.min(Math.ceil(mx), Math.ceil(S));
  const yOf = d => H / 2 - (d / mx) * (H / 2 - 14);
  c.strokeStyle = '#333'; c.lineWidth = 1; c.font = '11px system-ui'; c.fillStyle = '#888';
  for (const d of [-mx, -mx / 2, 0, mx / 2, mx]) { c.beginPath(); c.moveTo(0, yOf(d)); c.lineTo(W, yOf(d)); c.stroke(); c.fillText(`${d >= 0 ? '+' : ''}${d.toFixed(1)} px`, 4, yOf(d) - 2); }
  const line = (f, col) => { c.strokeStyle = col; c.lineWidth = 1.5; c.beginPath(); for (let i = i0; i < i1; i++) { const x = i - i0 + 0.5; i === i0 ? c.moveTo(x, yOf(f(i))) : c.lineTo(x, yOf(f(i))); } c.stroke(); };
  line(i => o[i] + tOff[i] - R.model[i], 'rgba(60,230,100,0.9)');
  line(i => o[i] - R.model[i], 'rgba(255,68,68,0.85)');
  c.fillStyle = '#888'; c.fillText(`${((i1 - i0) * 3).toLocaleString()} px of groove`, W - 110, H - 4);
}

function drawTurns() {
  const W = turnCv.width, H = turnCv.height, { TH, tOff, wrong } = strip, c = turnCtx, n = TH.length;
  c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
  const T = [];
  for (let a = 0; a < n;) { let b = a; while (b < n && TH[b] < TH[a] + CARD_TAU) b++; let s = 0, w = 0; for (let i = a; i < b; i++) { s += tOff[i] ** 2; w += wrong[i]; } T.push({ rms: Math.sqrt(s / (b - a)), w: w / (b - a) }); a = b; }
  const top = Math.max(card.S / 4 * 1.25, ...T.map(t => t.rms)), bw = W / T.length, yOf = v => H - 14 - (v / top) * (H - 24);
  T.forEach((t, k) => {
    c.fillStyle = '#6a8'; c.fillRect(k * bw + 1, yOf(t.rms), Math.max(1, bw - 2), H - 14 - yOf(t.rms));
    if (t.w > 0) { c.fillStyle = 'rgba(255,60,60,0.8)'; const h = t.w * (H - 24); c.fillRect(k * bw + bw * 0.3, H - 14 - h, Math.max(1, bw * 0.4), h); }
  });
  c.setLineDash([3, 4]); c.strokeStyle = '#aaa'; c.beginPath(); c.moveTo(0, yOf(card.S / 4)); c.lineTo(W, yOf(card.S / 4)); c.stroke(); c.setLineDash([]);
  c.fillStyle = '#888'; c.font = '11px system-ui';
  c.fillText(`${top.toFixed(1)} px`, 4, 12); c.fillText(`S/4`, W - 30, yOf(card.S / 4) - 3); c.fillText(`${T.length} turns`, 4, H - 2);
}

function drawAll() { drawCard(); drawDetail(); drawStrip(); drawPlot(); drawTurns(); }

// ---------- events ----------
cardCv.addEventListener('click', e => {
  if (!strip) return;
  const r = cardCv.getBoundingClientRect(), k = K();
  spot = { x: ((e.clientX - r.left) / r.width) * N * k, y: ((e.clientY - r.top) / r.height) * N * k };
  drawAll();
});
detCv.addEventListener('click', e => { // recenter on a point in the detail
  if (!strip) return;
  const r = detCv.getBoundingClientRect();
  spot = { x: spot.x - DET / 2 + ((e.clientX - r.left) / r.width) * DET, y: spot.y - DET / 2 + ((e.clientY - r.top) / r.height) * DET };
  drawAll();
});
$('preset').addEventListener('change', () => { spot = null; run(); });
$('seed').addEventListener('change', () => { spot = null; run(); });
$('newCard').addEventListener('click', () => { $('seed').value = (+$('seed').value || 0) + 1; spot = null; run(); });
$('run').addEventListener('click', () => run());
$('gradient').addEventListener('change', () => run());
$('turnsSel').addEventListener('change', async () => {
  if (!low) return;
  const id = ++runId; spot = null;
  try { const t = performance.now(); await runStrip(id); status(`Full-res stage ${((performance.now() - t) / 1000).toFixed(1)} s.`); } catch (e) { if (!(e instanceof Stale)) throw e; }
});
$('smooth').addEventListener('change', () => { if (strip) track(); });

run();
