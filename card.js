// card.html: a realistic card (cardmodel.js) through the whole pipeline
// (cardpipe.js), every step shown in one column with its settings beside it:
// low-res spacing, center and phase from a hand-marked start, then the
// full-res strip, geometry refit, groove trace and audio readout, scored
// against the card's truth.

const $ = id => document.getElementById(id);
const ctx2 = id => $(id).getContext('2d');
const cardCv = $('card'), cardCtx = ctx2('card');
const fftCtx = ctx2('fft'), profCv = $('prof'), profCtx = ctx2('prof'), cohCtx = ctx2('coh'), gradCtx = ctx2('grad');
const wrapCv = $('wrap'), wrapCtx = ctx2('wrap'), audioCv = $('audio'), audioCtx = ctx2('audio');
const detCv = $('detail'), detCtx = ctx2('detail');
const stripCv = $('strip'), stripCtx = ctx2('strip');
const plotCv = $('plot'), plotCtx = ctx2('plot');
const turnCv = $('turns'), turnCtx = ctx2('turns');
let DET = 256; // detail window, full-res px

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
  ['width', 'Groove width at nominal depth', '× spacing', 'assumed (the mask in image 22 covers ~47%); round stylus (parabola)'],
  ['edgeFade', 'Depth fade at the ends', 'px', 'assumed'],
  ['audio', 'Sound: depth modulation (rms)', '× depth', 'assumed; hill-and-dale; at −1 the stylus leaves the card'],
  ['audioWave', 'Sound wavelengths along the groove', 'px', 'assumed'],
  ['grain', 'Grain (rms)', '× groove rms', 'measured: 2.6 vs. groove 5.0 rms (image 21)'],
  ['grainCell', 'Grain cell size', 'px', 'measured ACF 0.5 at ~3–5 px'],
  ['drift', 'Groove drift from the spiral (rms)', 'px', 'phase between turns varies ±2 px (image 21)'],
  ['driftTurns', 'Drift periods', 'turns', 'assumed'],
  ['wobble', 'Lateral wobble (rms)', 'px', 'assumed; small and smooth'],
  ['wobbleWave', 'Wobble wavelengths', 'px', 'assumed'],
];

function showParams(P) {
  const fmt = v => (v === null ? 'none' : Array.isArray(v) ? v.join('–') : typeof v === 'object' ? `${v.width} rad, ×${v.groove}, ×${v.grain}` : String(v));
  $('params').innerHTML = '<tr><th>Parameter</th><th>Value</th><th style="text-align:left">Source</th></tr>' +
    PARAM_INFO.map(([k, name, unit, src]) => `<tr><td>${name}</td><td>${fmt(P[k])}${unit && P[k] !== null ? ' ' + unit : ''}</td><td class="src">${src}</td></tr>`).join('');
}

// ---------- state and pipeline ----------
// Stages, in order; a setting re-runs from its stage (data-stage in the HTML).
const STAGES = ['render', 'low', 'strip', 'refit', 'track', 'readout', 'draw'];
let card = null, img = null, low = null, strip = null, spot = null, runId = 0, times = {};
const status = s => { $('status').textContent = s; };
class Stale extends Error {}
const guard = id => { if (id !== runId) throw new Stale(); };
const num = id => +$(id).value;
const lowOpts = () => ({
  weightEx: num('weightEx'), window: num('window'),
  search: num('search'), gridStep: num('gridStep'), gradient: $('gradient').checked, gradTang: num('gradTang'), gradEps: num('gradEps'),
});

async function runFrom(stage) {
  const id = ++runId, at = STAGES.indexOf(stage), t0 = performance.now();
  const tm = async (name, f) => { const t = performance.now(); await f(); times[name] = (performance.now() - t) / 1000; guard(id); };
  try {
    // each stage clears its own output first, so an interrupted run is redone
    if (at <= 0 || !img) {
      card = makeCard($('preset').value, +$('seed').value || 1);
      img = low = strip = null; times = {}; showParams(card.P); clearSteps();
      const im = new Float32Array(N * N);
      await tm('render', () => renderLowRes(card, im, 2, f => { guard(id); status(`Rendering the low-res card… ${Math.round(100 * f)}%`); }));
      img = im; drawCard();
    }
    if (at <= 1 || !low) {
      low = strip = null;
      status('Low-res stage: spacing, center, phase…'); await tick(); guard(id);
      await tm('low', async () => { low = lowResStage(img, card.F, card.P.spacing, card.ann, lowOpts()); });
      drawCard(); drawLowSteps(); await tick(); guard(id);
    }
    if (at <= 2 || !strip) {
      strip = null;
      const g = low.geom, S = CARD_TAU * g.b, step = num('colStep');
      const TH = stripColumns(g, card.ann, step, num('turnsSel'));
      await tm('strip', async () => {
        const Z = await demodPass(card, g, TH, S, null, 1, f => { guard(id); status(`Full-res strip: ${TH.length.toLocaleString()} columns… ${Math.round(100 * f)}%`); });
        strip = { g, S, TH, Z, step, U: unwrapOffsets(Z, S, 0, null, false) };
      });
    }
    if (at <= 3 || !strip.R) await tm('refit', async () => refit());
    if (at <= 4 || !strip.o) await tm('track', async () => track());
    if (at <= 5 || !strip.audio) await tm('readout', () => readout(id));
    showResults(); drawAll();
    status(`Done in ${((performance.now() - t0) / 1000).toFixed(1)} s (` + Object.entries(times).map(([k, v]) => `${k} ${v.toFixed(1)}`).join(', ') + ').');
  } catch (e) {
    if (!(e instanceof Stale)) { status('Error: ' + e.message); throw e; }
  }
}

// geometry refit from the strip's offsets; also the true spiral (center,
// spacing, phase; no drift) as an offset from the strip's spiral, for h.
function refit() {
  const { g, S, TH, U } = strip, n = TH.length;
  strip.R = refitGeometry(g, TH, U.o, U.amp, S, num('refitR'));
  const ideal = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const [x, y] = stripPoint(g, TH[i], 0), dx = x - card.C.x, dy = y - card.C.y;
    let e = Math.hypot(dx, dy) - card.b * (Math.atan2(dy, dx) - card.phi);
    ideal[i] = -(e - card.S * Math.round(e / card.S));
  }
  strip.ideal = ideal;
  strip.o = strip.audio = null;
}

// lock the trace and score it
function track() {
  const { g, S, TH, Z, R, step } = strip, n = TH.length;
  const u = unwrapOffsets(Z, S, num('smooth') / step, null, false);
  const L = lockTrack(u.o, u.amp, R.model, S, num('lockS') / step);
  const tOff = new Float64Array(n), D = new Float64Array(n);
  for (let i = 0; i < n; i++) { const t = truthAt(card, g, TH[i], L.o[i]); tOff[i] = t.tOff; D[i] = t.thTrue - TH[i]; }
  const ds = []; for (let i = 0; i < n; i += 7) ds.push(D[i]);
  const md = median(ds), wrong = new Uint8Array(n);
  for (let i = 0; i < n; i++) wrong[i] = Math.round((D[i] - md) / CARD_TAU) !== 0 ? 1 : 0;
  const audioTrue = Float64Array.from(D, (d, i) => Math.max(-1, card.audioAt(d + TH[i]))); // the sound of the groove actually traced (−1: not cut)
  Object.assign(strip, { o: L.o, ref: L.ref, amp: u.amp, tOff, wrong, audioTrue, audio: null });
  if (!spot) { const i = Math.floor(n / 2), [x, y] = stripPoint(g, TH[i], L.o[i]); spot = { x, y }; }
}

async function readout(id) {
  const { g, S, TH, o, step } = strip;
  const rd = await readoutPass(card, g, TH, o, S, f => { guard(id); status(`Sound readout… ${Math.round(100 * f)}%`); }, num('hb'), num('audioSmooth') * 3 / step, 300 / step);
  strip.audio = rd.est;
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
  rows.push(`<tr><td colspan="4" class="src">Coherence ${f(low.coherence)} (1 = a pure cosine groove). True spacing ${f(card.S, 3)} px. Spiral vs. grooves: RMS radial distance (px, mod S) from the fitted spiral to the true grooves over the traced turns: what is left for the trace to follow (drift, wobble).</td></tr>`);
  $('est').innerHTML = rows.join('');

  const { tOff, wrong, o, TH } = strip, n = TH.length;
  let se = 0, big = 0, nw = 0;
  for (let i = 0; i < n; i++) { se += tOff[i] ** 2; if (Math.abs(tOff[i]) > card.S / 4) big++; nw += wrong[i]; }
  // audio readout vs. the true audio of the traced groove
  const { audio, audioTrue } = strip;
  let sxy = 0, sxx = 0, syy = 0, sd = 0;
  for (let i = 0; i < n; i++) { const a = audioTrue[i], b = audio[i]; sxy += a * b; sxx += a * a; syy += b * b; sd += (a - b) ** 2; }
  const turns = (TH[n - 1] - TH[0]) / CARD_TAU;
  $('trace').innerHTML = [
    `<tr><td>Columns traced</td><td>${n.toLocaleString()} (${f(turns, 1)} turns, ${(strip.step * n / 1000).toFixed(0)} k px of groove)</td></tr>`,
    `<tr><td>RMS distance to the true groove</td><td>${f(Math.sqrt(se / n))} px</td></tr>`,
    `<tr><td>Columns off by more than S/4</td><td>${f((100 * big) / n)}%</td></tr>`,
    `<tr><td>Columns on the wrong groove</td><td>${f((100 * nw) / n)}%</td></tr>`,
    `<tr><td>Sound (relative depth): true RMS</td><td>${f(Math.sqrt(sxx / n), 3)}</td></tr>`,
    `<tr><td>Groove not cut (sound ≤ −1)</td><td>${f((100 * audioTrue.reduce((a, v) => a + (v <= -1), 0)) / n)}%</td></tr>`,
    `<tr><td>Sound readout: error RMS / correlation</td><td>${f(Math.sqrt(sd / n), 3)} / ${f(sxy / Math.sqrt(sxx * syy), 3)}</td></tr>`,
  ].join('');
}

// ---------- drawing ----------

const K = () => card.F / N; // full-res px per low-res px
function stretch(a, step = 1) { // 2nd–98th percentile of a sample
  const s = []; for (let i = 0; i < a.length; i += step) s.push(a[i]);
  s.sort((x, y) => x - y);
  return [s[Math.floor(0.02 * s.length)], s[Math.floor(0.98 * s.length)]];
}

// grey image of an N×N array into a 1024² canvas, 2–98% stretch
function grey(ctx, a) {
  const [lo, hi] = stretch(a, 37), id = ctx.createImageData(N, N), sc = 255 / (hi - lo);
  for (let i = 0; i < N * N; i++) { const v = Math.max(0, Math.min(255, (a[i] - lo) * sc)); id.data[4 * i] = id.data[4 * i + 1] = id.data[4 * i + 2] = v; id.data[4 * i + 3] = 255; }
  ctx.putImageData(id, 0, 0);
}
// markers on a 1024² card view (full-res coordinates / k)
function marks(c, which = { ann: true, low: true, refit: true, spot: true }) {
  const k = K();
  const cross = (x, y, col, a = 14, w = 2) => { c.strokeStyle = col; c.lineWidth = w; c.beginPath(); c.moveTo(x / k - a, y / k); c.lineTo(x / k + a, y / k); c.moveTo(x / k, y / k - a); c.lineTo(x / k, y / k + a); c.stroke(); };
  const ring = (x, y, r, col, w = 2) => { c.strokeStyle = col; c.lineWidth = w; c.beginPath(); c.arc(x / k, y / k, r, 0, CARD_TAU); c.stroke(); };
  if (which.ann) {
    c.setLineDash([8, 8]); c.strokeStyle = 'rgba(255,255,255,0.7)'; c.lineWidth = 2;
    for (const r of [card.ann.rIn, card.ann.rOut]) { c.beginPath(); c.arc(card.ann.x / k, card.ann.y / k, r / k, 0, CARD_TAU); c.stroke(); }
    c.setLineDash([]);
    cross(card.ann.x, card.ann.y, '#fff');
  }
  if (which.gc && low && low.gc) ring(low.gc.x, low.gc.y, 10, '#f6f', 3);
  if (which.low && low) ring(low.geom.x, low.geom.y, 10, '#4cf');
  if (which.refit && strip) ring(strip.R.geom.x, strip.R.geom.y, 14, '#fd3');
  cross(card.C.x, card.C.y, '#f44', 10, 2);
  if (which.spot && spot) { c.strokeStyle = '#f44'; c.lineWidth = 2; c.strokeRect((spot.x - DET / 2) / k, (spot.y - DET / 2) / k, DET / k, DET / k); }
}

function drawCard() { // the low-res card until the low-res stage has run, then the masked input it uses
  grey(cardCtx, low ? low.hp : img);
  marks(cardCtx);
  const k = K();
  $('rawOut').textContent = `Scale ×${k.toFixed(2)}: the nominal ${card.P.spacing} px spacing is ${(card.P.spacing / k).toFixed(2)} low-res px; the annulus r ≈ ${Math.round(card.P.rIn / k)}–${Math.round(card.P.rOut / k)} px. Hand mark ${Math.hypot(card.ann.x - card.C.x, card.ann.y - card.C.y).toFixed(1)} px from the true center.`;
}

function blank(ctx, msg) {
  const c = ctx.canvas; ctx.fillStyle = '#000'; ctx.fillRect(0, 0, c.width, c.height);
  if (msg) { ctx.fillStyle = '#777'; ctx.font = `${Math.round(c.width / 32)}px system-ui`; ctx.fillText(msg, c.width / 20, c.height / 2); }
}
function clearSteps() { for (const c of [cardCtx, fftCtx, profCtx, cohCtx, gradCtx, wrapCtx, stripCtx, plotCtx, turnCtx, audioCtx, detCtx]) blank(c); }

function drawLowSteps() {
  const k = K();
  // c. log |FFT|, central half (DC at N/2), 1 bin per canvas px
  {
    const M = 512, o = N / 2 - M / 2, a = new Float32Array(M * M);
    for (let y = 0; y < M; y++) for (let x = 0; x < M; x++) a[y * M + x] = low.mag[(o + y) * N + o + x];
    const s = a.slice().sort(), lo = s[Math.floor(0.02 * s.length)], hi = s[Math.floor(0.999 * s.length)], id = fftCtx.createImageData(M, M);
    for (let i = 0; i < M * M; i++) { const v = Math.max(0, Math.min(255, ((a[i] - lo) / (hi - lo)) * 255)); id.data[4 * i] = id.data[4 * i + 1] = id.data[4 * i + 2] = v; id.data[4 * i + 3] = 255; }
    fftCtx.putImageData(id, 0, 0);
    const circ = (r, col, dash) => { fftCtx.setLineDash(dash || []); fftCtx.strokeStyle = col; fftCtx.lineWidth = 1.5; fftCtx.beginPath(); fftCtx.arc(M / 2, M / 2, r, 0, CARD_TAU); fftCtx.stroke(); fftCtx.setLineDash([]); };
    circ(low.fft.iLo, 'rgba(255,255,255,0.6)', [5, 5]); circ(low.fft.iHi, 'rgba(255,255,255,0.6)', [5, 5]);
    circ(low.fft.rho, 'rgba(70,200,255,0.9)');
  }
  // d. radial profile vs. ρ, labelled by spacing (full-res px)
  {
    const c = profCtx, W = profCv.width, H = profCv.height, r0 = 60, r1 = 400, P = low.profile;
    blank(c);
    let mn = Infinity, mx = -Infinity;
    for (let r = r0; r <= r1; r++) { mn = Math.min(mn, P[r]); mx = Math.max(mx, P[r]); }
    const xOf = r => 30 + ((r - r0) / (r1 - r0)) * (W - 50), yOf = v => H - 40 - ((v - mn) / (mx - mn)) * (H - 70);
    c.fillStyle = 'rgba(255,255,255,0.12)'; c.fillRect(xOf(low.fft.iLo), 10, xOf(low.fft.iHi) - xOf(low.fft.iLo), H - 50);
    const vline = (r, col, dash) => { c.setLineDash(dash || []); c.strokeStyle = col; c.lineWidth = 1.5; c.beginPath(); c.moveTo(xOf(r), 10); c.lineTo(xOf(r), H - 40); c.stroke(); c.setLineDash([]); };
    vline((N * k) / card.P.spacing, 'rgba(255,255,255,0.7)', [5, 5]); vline((N * k) / card.S, '#f44'); vline(low.fft.rho, '#4cf');
    c.strokeStyle = '#ddd'; c.lineWidth = 1.5; c.beginPath();
    for (let r = r0; r <= r1; r++) r === r0 ? c.moveTo(xOf(r), yOf(P[r])) : c.lineTo(xOf(r), yOf(P[r]));
    c.stroke();
    c.fillStyle = '#999'; c.font = '17px system-ui';
    for (const sp of [15, 20, 25, 29, 35, 50, 80]) { const r = (N * k) / sp; if (r < r0 || r > r1) continue; c.fillText(String(sp), xOf(r) - 7, H - 22); c.fillRect(xOf(r), H - 40, 1, 5); }
    c.fillText('spacing (full-res px) →  finer to the right', W / 2 - 110, H - 6);
    $('profOut').textContent = `Peak at ${low.spacing.toFixed(3)} px (${low.spacing >= card.S ? '+' : ''}${(100 * (low.spacing / card.S - 1)).toFixed(2)}% vs. true ${card.S.toFixed(3)}; nominal ${card.P.spacing}).${low.fftOK ? '' : ' Rejected: nominal used.'}`;
    c.fillText(`peak ${low.spacing.toFixed(2)} px${low.fftOK ? '' : ' (rejected → nominal)'}`, 40, 28);
  }
  // e. coherence grid
  {
    const { G, h, v, x0, y0 } = low.grid, n = 2 * G + 1, cell = 512 / n, c = cohCtx;
    let mx = 0; for (const q of v) mx = Math.max(mx, q);
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
      const t = v[j * n + i] / mx, r = Math.round(255 * Math.min(1, 1.6 * t)), g = Math.round(255 * Math.max(0, Math.min(1, 1.6 * t - 0.4))), b = Math.round(255 * Math.max(0, 2 * t - 1));
      c.fillStyle = `rgb(${r},${g},${b})`; c.fillRect(i * cell, j * cell, Math.ceil(cell), Math.ceil(cell));
    }
    const P = (x, y) => [((x / k - x0) / h + G + 0.5) * cell, ((y / k - y0) / h + G + 0.5) * cell];
    const cross = ([x, y], col) => { c.strokeStyle = col; c.lineWidth = 2; c.beginPath(); c.moveTo(x - 10, y); c.lineTo(x + 10, y); c.moveTo(x, y - 10); c.lineTo(x, y + 10); c.stroke(); };
    cross(P(card.ann.x, card.ann.y), '#fff'); cross(P(card.C.x, card.C.y), '#f44');
    const [gx, gy] = P(low.geom.x, low.geom.y); c.strokeStyle = '#4cf'; c.lineWidth = 2; c.beginPath(); c.arc(gx, gy, 9, 0, CARD_TAU); c.stroke();
    $("cohOut").textContent = `Grid step ${(h * k).toFixed(1)} px, ${n}² candidates. Answer ${Math.hypot(low.geom.x - card.C.x, low.geom.y - card.C.y).toFixed(2)} px from the true center; coherence ${low.coherence.toFixed(2)} (1 = a pure cosine groove)`;
  }
  drawGrad();
}

function drawGrad() {
  if (!low) return blank(gradCtx);
  if (!low.gc) { $('gradOut').textContent = ''; return blank(gradCtx, 'Off: tick “Run it” at right.'); }
  grey(gradCtx, low.gc.img);
  const { X, Y, inl } = low.gc;
  for (let pass = 0; pass < 2; pass++) for (let i = 0; i < X.length; i++) { // red first, green on top
    if (!!inl[i] !== (pass === 1)) continue;
    gradCtx.fillStyle = inl[i] ? 'rgba(60,255,100,1)' : 'rgba(255,60,60,0.55)'; gradCtx.fillRect(X[i] - (inl[i] ? 3 : 1.5), Y[i] - (inl[i] ? 3 : 1.5), inl[i] ? 6 : 3, inl[i] ? 6 : 3);
  }
  $('gradOut').textContent = `${low.gc.nIn} of ${X.length} lines agree; answer ${Math.hypot(low.gc.x - card.C.x, low.gc.y - card.C.y).toFixed(0)} px from the true center (hand mark ${Math.hypot(card.ann.x - card.C.x, card.ann.y - card.C.y).toFixed(0)} px). The lines are measured 300–500 px from the center on a ~5.4 px pattern, so tiny angle errors miss it. `;
  marks(gradCtx, { gc: true, spot: true });
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
  c.fillStyle = '#888'; c.fillText(`${((i1 - i0) * strip.step).toLocaleString()} px of groove`, W - 110, H - 4);
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

function drawWrap() {
  const c = wrapCtx, W = wrapCv.width, H = wrapCv.height, { TH, R, o, tOff, S, ideal } = strip, n = TH.length;
  blank(c);
  const wr = d => d - S * Math.round(d / S), yOf = d => H / 2 - (wr(d) / S) * (H - 30), xOf = i => (i / n) * W;
  const us = unwrapOffsets(strip.Z, S, 24 / strip.step, null, false); // smoothed along the groove by σ 24 px, for display
  let am = 0; for (let i = 0; i < n; i += 40) am = Math.max(am, us.amp[i]);
  c.strokeStyle = '#333'; c.beginPath(); c.moveTo(0, H / 2); c.lineTo(W, H / 2); c.stroke();
  // turn boundaries
  c.strokeStyle = '#222'; for (let i = 1, t = TH[0] + CARD_TAU; i < n; i++) if (TH[i] >= t) { c.beginPath(); c.moveTo(xOf(i), 0); c.lineTo(xOf(i), H); c.stroke(); t += CARD_TAU; }
  for (let i = 0; i < n; i += 40) { const t = Math.min(1, (2 * us.amp[i]) / am); c.fillStyle = `rgba(255,255,255,${0.15 + 0.85 * t})`; c.fillRect(xOf(i) - 1, yOf(us.o[i]) - 1, 2, 2); }
  for (let i = 0; i < n; i += 40) { c.fillStyle = 'rgba(60,230,100,0.8)'; c.fillRect(xOf(i), yOf(o[i] + tOff[i]), 1.5, 1.5); }
  for (let i = 0; i < n; i += 5) { c.fillStyle = 'rgba(255,60,60,0.9)'; c.fillRect(xOf(i), yOf(ideal[i]) + 1, 1, 2); }
  for (let i = 0; i < n; i += 5) { c.fillStyle = '#fd3'; c.fillRect(xOf(i), yOf(R.model[i]) - 2, 1, 2); }
  c.fillStyle = '#999'; c.font = '15px system-ui'; c.fillText('+S/2', 6, 20); c.fillText('−S/2', 6, H - 8);
  c.fillText(`${((TH[n - 1] - TH[0]) / CARD_TAU).toFixed(0)} turns →`, W - 90, H - 8);
  const G = R.geom, L = low.geom, k = Math.hypot(G.x - L.x, G.y - L.y);
  $('wrapOut').textContent = `${n.toLocaleString()} columns. The refit moved the center ${k.toFixed(2)} px from the low-res fit (the amplitude of yellow's one-turn wave) and the spacing by ${(100 * (G.b / L.b - 1)).toFixed(3)}%. True vs. low-res: center ${Math.hypot(card.C.x - L.x, card.C.y - L.y).toFixed(2)} px (red's wave), spacing ${(100 * (card.b / L.b - 1)).toFixed(3)}%.`;
}

function drawAudio() {
  const W = audioCv.width, H = audioCv.height, c = audioCtx, { audio, audioTrue, step } = strip, cols = Math.floor((W * 3) / (3 * step)), px = W / cols;
  const [i0, i1] = stripWindow(cols);
  blank(c);
  const mx = Math.max(0.3, 4 * card.P.audio), yOf = v => H / 2 - (v / mx) * (H / 2 - 12);
  c.strokeStyle = '#333'; c.lineWidth = 1; c.font = '11px system-ui'; c.fillStyle = '#888';
  for (const d of [-mx, -mx / 2, 0, mx / 2, mx]) { c.beginPath(); c.moveTo(0, yOf(d)); c.lineTo(W, yOf(d)); c.stroke(); c.fillText(`${d >= 0 ? '+' : ''}${d.toFixed(2)}`, 4, yOf(d) - 2); }
  const line = (a, col) => { c.strokeStyle = col; c.lineWidth = 1.5; c.beginPath(); for (let i = i0; i < i1; i++) { const x = (i - i0) * px + px / 2, y = yOf(Math.max(-mx, Math.min(mx, a[i]))); i === i0 ? c.moveTo(x, y) : c.lineTo(x, y); } c.stroke(); };
  line(audioTrue, 'rgba(60,230,100,0.9)'); line(audio, 'rgba(255,68,68,0.85)');
  c.fillStyle = '#888'; c.fillText(`${((i1 - i0) * strip.step).toLocaleString()} px of groove`, W - 110, H - 4);
}

function drawAll() { DET = num('detSize'); drawCard(); drawGrad(); drawDetail(); drawWrap(); drawStrip(); drawPlot(); drawTurns(); drawAudio(); }

// ---------- events ----------
for (const cv of [cardCv, $('grad')]) cv.addEventListener('click', e => {
  if (!strip || !strip.audio) return;
  const r = cv.getBoundingClientRect(), k = K();
  spot = { x: ((e.clientX - r.left) / r.width) * N * k, y: ((e.clientY - r.top) / r.height) * N * k };
  drawAll();
});
detCv.addEventListener('click', e => { // recenter on a point in the detail
  if (!strip || !strip.audio) return;
  const r = detCv.getBoundingClientRect();
  spot = { x: spot.x - DET / 2 + ((e.clientX - r.left) / r.width) * DET, y: spot.y - DET / 2 + ((e.clientY - r.top) / r.height) * DET };
  drawAll();
});
$('preset').addEventListener('change', () => { spot = null; runFrom('render'); });
$('seed').addEventListener('change', () => { spot = null; runFrom('render'); });
$('newCard').addEventListener('click', () => { $('seed').value = (+$('seed').value || 0) + 1; spot = null; runFrom('render'); });
$('run').addEventListener('click', () => runFrom('render'));
for (const el of document.querySelectorAll('[data-stage]')) el.addEventListener('change', () => {
  const st = el.dataset.stage;
  if (st === 'draw') { if (strip && strip.audio) drawAll(); return; }
  if (st === 'strip') spot = null;
  runFrom(st);
});

runFrom('render');
