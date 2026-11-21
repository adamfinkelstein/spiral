// Pipeline for card.html: a low-resolution stage (spacing from the FFT, center
// from gradient lines, phase) and a full-resolution stage (groove following
// along an unrolled strip). No DOM. Needs render.js (N, gaussianBlur),
// fftspacing.js, gradcenter.js and a card from cardmodel.js.
// Coordinates: full-resolution pixels; low-res pixel i covers full-res
// [i·k, (i+1)·k), k = F / N, so a low-res point p maps to p·k.

const tick = () => new Promise(r => setTimeout(r, 0));
const wrapPI = a => a - CARD_TAU * Math.round(a / CARD_TAU);

// Low-res image: the full-res depth averaged over each low-res pixel (k×k
// full-res px): ss×ss samples per pixel, each averaging the grain over its
// own (k/ss)² share on a 3×3 grid (so 6×6 grain samples per pixel at ss 2),
// as downsampling the depth map by area would.
async function renderLowRes(card, out, ss, progress) {
  const k = card.F / N;
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      let v = 0;
      for (let j = 0; j < ss; j++) for (let i = 0; i < ss; i++) v += card.sample((x + (i + 0.5) / ss) * k, (y + (j + 0.5) / ss) * k, k / ss, 3);
      out[y * N + x] = v / (ss * ss);
    }
    if ((y & 63) === 63) { progress && progress((y + 1) / N); await tick(); }
  }
}

// 1-D Gaussian smoothing (clamped at the ends) of a Float64Array.
function smooth1d(a, sigma) {
  const n = a.length, K = Math.ceil(3 * sigma), w = [], out = new Float64Array(n);
  for (let j = -K; j <= K; j++) w.push(Math.exp(-(j * j) / (2 * sigma * sigma)));
  for (let i = 0; i < n; i++) {
    let s = 0, ws = 0;
    for (let j = -K; j <= K; j++) { const q = i + j; if (q < 0 || q >= n) continue; s += w[j + K] * a[q]; ws += w[j + K]; }
    out[i] = s / ws;
  }
  return out;
}

// ---------- Low-res stage ----------

// img: low-res depth (N×N). nominal: the machine's spacing (full-res px).
// ann: hand-marked center and annulus radii (full-res px).
// Returns the preprocessed image and the estimates (full-res px).
// Every length in opts is relative to the spacing (so it scales with the
// resolution) except search (full-res px).
const LOW_DEFAULTS = { weightEx: 0.5, window: 0.1, search: 60, gridStep: 0.15, gradient: false, gradTang: 0.5, gradEps: 0.4 };
function lowResStage(img, F, nominal, ann, opts = {}) {
  opts = { ...LOW_DEFAULTS, ...opts };
  const k = F / N, sNom = nominal / k, a = { x: ann.x / k, y: ann.y / k }, rIn = ann.rIn / k, rOut = ann.rOut / k;
  // the annulus from the hand marks: a soft mask (ramps over one spacing
  // inside the marked circles); inside it, minus its mean, scaled to unit rms
  const sm = t => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
  const hp = new Float32Array(N * N), m = new Float32Array(N * N);
  let s0 = 0, s1 = 0, sw = 0;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const r = Math.hypot(x + 0.5 - a.x, y + 0.5 - a.y), i = y * N + x;
    m[i] = sm((r - rIn) / sNom) * sm((rOut - r) / sNom); s0 += m[i] * img[i]; sw += m[i];
  }
  const mean = s0 / Math.max(sw, 1);
  for (let i = 0; i < N * N; i++) { hp[i] = (img[i] - mean) * m[i]; s1 += hp[i] * hp[i]; }
  const sc = 1 / Math.sqrt(s1 / Math.max(sw, 1));
  for (let i = 0; i < N * N; i++) hp[i] *= sc;

  // spacing: the peak of the FFT's radial profile within ±10% of the
  // nominal spacing (image weighted 1/√r about the marked center), refined
  // parabolically. The groove is nearly a cosine, so there are no useful
  // harmonics, and the profile has ripple of its own (from the annulus edges)
  // that throws off the harmonic sum's trough samples.
  const fftIn = Float32Array.from(opts.weightEx > 0 ? evenWeight(hp, a, sNom, opts.weightEx) : hp);
  computeSpectrum(fftIn);
  const pr = smooth1d(Float64Array.from(profile), 1);
  const iLo = Math.floor(N / ((1 + opts.window) * sNom)), iHi = Math.ceil(N / ((1 - opts.window) * sNom));
  let bi = iLo;
  for (let i = iLo; i <= iHi; i++) if (pr[i] > pr[bi]) bi = i;
  let rho = bi;
  if (bi > iLo && bi < iHi) { const p0 = pr[bi - 1], p1 = pr[bi], p2 = pr[bi + 1], den = p0 - 2 * p1 + p2; if (den < 0) rho += (0.5 * (p0 - p2)) / den; }
  const sFFT = N / rho, edge = bi === iLo || bi === iHi;
  // the machine's spacing is known to a few %: an answer far from it (or on
  // the edge of the window) means the FFT missed, so fall back to the nominal
  const fftOK = !edge && Math.abs(sFFT / sNom - 1) < 0.03, sLow = fftOK ? sFFT : sNom;

  // optional comparison: the gradient-line center, its first tangential
  // blur about the hand mark (tangential blur and RANSAC tolerance scaled
  // with the spacing; the Part 1 values 3 and 2 px
  // were 0.15–0.3 and 0.1–0.2 spacings there)
  const gc = opts.gradient ? gradientCenter(hp, sLow, 150, 0.7, true, opts.gradTang * sLow, opts.gradEps * sLow, a) : null; // first pass blurred about the hand mark

  // center, spacing and phase: spiral coherence, searched about the mark
  const sp = spiralCoherence(hp, a, sLow, opts.search / k, opts.gridStep);
  return {
    hp, mask: m, fftIn, mag: Float32Array.from(mag), profile: pr, fft: { iLo, iHi, rho }, spacing: sFFT * k, fftOK, coherence: sp.coh, grid: sp.grid,
    gc: gc && { x: gc.c.x * k, y: gc.c.y * k, img: Float32Array.from(gc.img), X: gc.L.X, Y: gc.L.Y, inl: gc.inl, nIn: gc.nIn, path: gc.path },
    geom: { x: sp.x * k, y: sp.y * k, b: sp.b * k, ph: sp.ph },
  };
}

// Spiral coherence. The depth is ≈ −cos(r/b − α + φ) about the true center,
// so Z = −Σ v·e^{−i(r/b − α)} ≈ (n/2)·e^{iφ}: |Z| peaks at the true center
// and spacing, and arg Z is the phase. A center off by e shifts each turn by
// up to e, so |Z| falls like J0(2πe/S): its main lobe is only ~0.4 spacing
// wide. Hence a grid over ±R about the mark (step 0.1 spacing, on a subset of
// pixels), then a pattern search on (x, y, b) with all sampled pixels.
// Coherence = |Z| relative to a pure cosine groove (1).
function spiralCoherence(hp, a, s, R, step = 0.15) {
  const rnd = mulberry32(12345), X = [], Y = [], V = [];
  for (let i = 0; i < N * N; i++) if (hp[i] !== 0 && rnd() < 0.05) { X.push((i % N) + 0.5); Y.push(Math.floor(i / N) + 0.5); V.push(hp[i]); }
  const n = X.length, sub = Math.max(1, Math.floor(n / 8000));
  let sumAbs = 0;
  for (const v of V) sumAbs += Math.abs(v);
  const Z = (cx, cy, b, step = 1) => {
    let zr = 0, zi = 0;
    for (let k = 0; k < n; k += step) {
      const dx = X[k] - cx, dy = Y[k] - cy, u = Math.hypot(dx, dy) / b - Math.atan2(dy, dx);
      zr -= V[k] * Math.cos(u); zi += V[k] * Math.sin(u);
    }
    return [zr, zi];
  };
  const score = (cx, cy, b, step) => Math.hypot(...Z(cx, cy, b, step));
  const b0 = s / CARD_TAU, h = step * s, G = Math.ceil(R / h);
  const grid = { G, h, v: new Float32Array((2 * G + 1) ** 2), x0: a.x, y0: a.y };
  let best = { x: a.x, y: a.y, v: -1 };
  for (let j = -G; j <= G; j++) for (let i = -G; i <= G; i++) {
    const v = score(a.x + i * h, a.y + j * h, b0, sub);
    grid.v[(j + G) * (2 * G + 1) + i + G] = v;
    if (v > best.v) best = { x: a.x + i * h, y: a.y + j * h, v };
  }
  let q = [best.x, best.y, b0], f = score(q[0], q[1], q[2]), st = [h / 2, h / 2, b0 * 0.004];
  for (let it = 0; it < 60 && st[0] > 0.005 * s; it++) {
    let moved = false;
    for (let d = 0; d < 3; d++) for (const sg of [1, -1]) {
      const t = q.slice(); t[d] += sg * st[d];
      const ft = score(t[0], t[1], t[2]);
      if (ft > f) { q = t; f = ft; moved = true; }
    }
    if (!moved) st = st.map(v => v / 2);
  }
  const [zr, zi] = Z(q[0], q[1], q[2]);
  return { x: q[0], y: q[1], b: q[2], ph: Math.atan2(zi, zr), coh: (2 * Math.hypot(zr, zi)) / sumAbs / (Math.PI / 2), grid };
}

// ---------- Full-res stage ----------

// Columns of the strip: θ along the spiral r = b·θ (α = θ + φ), from one
// spacing inside the marked inner edge to one spacing inside the outer edge,
// every `step` px of arc. turns: limit to that many turns about the middle.
function stripColumns(geom, ann, step, turns) {
  let t0 = (ann.rIn + 1.5 * CARD_TAU * geom.b) / geom.b, t1 = (ann.rOut - 1.5 * CARD_TAU * geom.b) / geom.b;
  if (turns && (t1 - t0) / CARD_TAU > turns) { const m = (t0 + t1) / 2; t0 = m - (turns * Math.PI); t1 = m + turns * Math.PI; }
  const th = [];
  for (let t = t0; t < t1; t += step / (geom.b * t)) th.push(t);
  return Float64Array.from(th);
}

// Point at radial offset d from the spiral at column θ.
const stripPoint = (geom, th, d) => {
  const a = th + geom.ph, R = geom.b * th + d;
  return [geom.x + R * Math.cos(a), geom.y + R * Math.sin(a)];
};

// One demodulation pass. For each column, sample rows d = c0 + j (j = −S..S,
// 1 px) along the radius, remove a linear trend, and correlate with
// e^{−2πi(d − c0)/S} under a cos² window of half-width hw·S. A groove at
// offset o gives depth ≈ −cos(2π(d − o)/S), so o = c0 − S·arg(−Z)/2π.
// Returns Z (re, im) per column.
async function demodPass(card, geom, TH, S, center, hw, progress) {
  const n = TH.length, J = Math.ceil(S), m = 2 * J + 1;
  const zr = new Float64Array(n), zi = new Float64Array(n), v = new Float64Array(m);
  const cw = new Float64Array(m), sw = new Float64Array(m), D = new Float64Array(m);
  let sd2 = 0;
  for (let j = 0; j < m; j++) {
    const d = j - J; D[j] = d; sd2 += d * d;
    const t = d / (2 * hw * S), w = Math.abs(t) < 0.5 ? Math.cos(Math.PI * t) ** 2 : 0;
    cw[j] = w * Math.cos((CARD_TAU * d) / S); sw[j] = w * Math.sin((CARD_TAU * d) / S);
  }
  for (let i = 0; i < n; i++) {
    const th = TH[i], a = th + geom.ph, ca = Math.cos(a), sa = Math.sin(a), R = geom.b * th + (center ? center[i] : 0);
    let s0 = 0, s1 = 0;
    for (let j = 0; j < m; j++) { const r = R + D[j]; const x = card.sample(geom.x + r * ca, geom.y + r * sa); v[j] = x; s0 += x; s1 += x * D[j]; }
    s0 /= m; s1 /= sd2;
    let re = 0, im = 0;
    for (let j = 0; j < m; j++) { const x = v[j] - s0 - s1 * D[j]; re += x * cw[j]; im -= x * sw[j]; }
    zr[i] = re; zi[i] = im;
    if ((i & 4095) === 4095) { progress && progress(i / n); await tick(); }
  }
  return { zr, zi };
}

// Unwrapped offsets from Z (smoothed along the strip by σ columns first, so
// noise can't flip the phase by π): o = c0 − S·arg(−Z)/2π, continuous.
function unwrapOffsets(Z, S, sigma, c0, unwrap = true) {
  const zr = sigma > 0 ? smooth1d(Z.zr, sigma) : Z.zr, zi = sigma > 0 ? smooth1d(Z.zi, sigma) : Z.zi;
  const n = zr.length, o = new Float64Array(n), amp = new Float64Array(n);
  let prev = 0;
  for (let i = 0; i < n; i++) {
    let ph = Math.atan2(-zi[i], -zr[i]); // arg(−Z)
    if (unwrap && i > 0) ph = prev + wrapPI(ph - prev);
    prev = ph;
    o[i] = (c0 ? c0[i] : 0) - (S * ph) / CARD_TAU;
    amp[i] = Math.hypot(zr[i], zi[i]);
  }
  return { o, amp };
}

// Robust fit o(θ) ≈ a + β·θ + c·cos α + d·sin α (α = θ + φ) by IRLS with Tukey
// weights (scale 4.7·MAD), weighted by the demodulation amplitude. Center
// error (c, d), spacing error β (b), phase error −a/b: returns the corrected
// geometry and the model per column.
function refitGeometry(geom, TH, o, amp, S, search = 1.5) {
  const n = TH.length, U = new Float64Array(n).fill(1), wrapS = x => x - S * Math.round(x / S);
  let q = [0, 0, 0, 0];
  const basis = i => { const a = TH[i] + geom.ph; return [1, TH[i] - TH[0], Math.cos(a), Math.sin(a)]; };
  const fit = i => { const f = basis(i); return q[0] + q[1] * f[1] + q[2] * f[2] + q[3] * f[3]; };
  // Start: a grid over the spacing change β (±2.5%, steps that shift the
  // outermost turn by S/4) and the center error (±search·S, steps of S/4) on
  // every 20th column, scoring the circular coherence
  // |Σ amp·e^{2πi(o − model)/S}| (the best constant comes out as its arg).
  // This copes with low-res estimates off by more than S/2 at the outer
  // turns, which plain IRLS on wrapped residuals can't.
  {
    const span = TH[n - 1] - TH[0], bs = S / (4 * Math.max(span, 1e-9)), bR = Math.ceil((0.025 * geom.b) / bs);
    const cs = S / 4, cR = Math.ceil((search * S) / cs), K = 2 * Math.PI / S;
    const idx = []; for (let i = 0; i < n; i += 20) idx.push(i);
    const T1 = idx.map(i => TH[i] - TH[0]), CA = idx.map(i => Math.cos(TH[i] + geom.ph)), SA = idx.map(i => Math.sin(TH[i] + geom.ph));
    const O = idx.map(i => o[i]), W = idx.map(i => amp[i]);
    let best = -1;
    for (let bi = -bR; bi <= bR; bi++) for (let yi = -cR; yi <= cR; yi++) for (let xi = -cR; xi <= cR; xi++) {
      const be = bi * bs, ex = xi * cs, ey = yi * cs;
      let cr = 0, ci = 0;
      for (let k = 0; k < idx.length; k++) { const a = K * (O[k] - be * T1[k] - ex * CA[k] - ey * SA[k]); cr += W[k] * Math.cos(a); ci += W[k] * Math.sin(a); }
      const v = Math.hypot(cr, ci);
      if (v > best) { best = v; q = [Math.atan2(ci, cr) / K, be, ex, ey]; }
    }
  }
  // then IRLS with offsets compared modulo S (a slip to the next turn costs
  // nothing): each round fits the model to model + wrapped residual
  for (let round = 0; round < 10; round++) {
    const A = [0, 1, 2, 3].map(() => [0, 0, 0, 0]), B = [0, 0, 0, 0], res = new Float64Array(n);
    for (let i = 0; i < n; i++) res[i] = wrapS(o[i] - fit(i));
    const mad = median(Array.from(res, Math.abs)) || 1e-6;
    for (let i = 0; i < n; i++) {
      const f = basis(i), w = amp[i] * tukeyW(res[i], Math.max(4.7 * 1.4826 * mad, 0.1 * S)), t = fit(i) + res[i];
      if (!(w > 0)) continue;
      for (let r = 0; r < 4; r++) { B[r] += w * f[r] * t; for (let c = 0; c < 4; c++) A[r][c] += w * f[r] * f[c]; }
    }
    q = solve(A, B) || q;
  }
  const model = new Float64Array(n);
  for (let i = 0; i < n; i++) model[i] = fit(i);
  // o = (b' − b)(θ − θ0) + const: b' = b + β; the constant at θ0 is b'·(φ − φ') + (b' − b)θ0
  const b2 = geom.b + q[1], ph2 = geom.ph - (q[0] - q[1] * TH[0]) / b2;
  return { geom: { x: geom.x + q[2], y: geom.y + q[3], b: b2, ph: ph2 }, model, q };
}

// Truth for a traced point at column θ, offset o (radial, about geom):
// tOff = signed distance from the point to the nearest true groove (outward
// +), and thTrue = that groove's θ (to detect slips to a neighbouring turn).
function truthAt(card, geom, th, o) {
  const [x, y] = stripPoint(geom, th, o);
  const [qx, qy] = card.toIdeal(x, y);
  const g = card.psiAt(qx, qy);
  const tOff = (Math.round(g.psi) - g.psi) * card.S;
  return { tOff, thTrue: g.a - card.phi + CARD_TAU * Math.round(g.psi) };
}

// Track locked to a reference: the reference is the fitted spiral (model)
// plus the slowly varying residual (circular mean of e^{2πi·res/S} smoothed by
// σ columns, kept within ±S/2 of the model), and each local estimate is taken
// as the groove nearest the reference. Groove identity comes from the fitted
// spiral, so noise can't make lasting slips; the cost is that grooves must
// stay within S/2 of it. (Unwrapping the slow residual instead lets it follow
// larger drift, but in weak stretches it slips a turn and never comes back.)
// Weighted by the demodulation amplitude, so weak stretches (damage) are
// bridged by the reference from both sides.
function lockTrack(oLocal, amp, model, S, sigma) {
  const n = oLocal.length, cr = new Float64Array(n), ci = new Float64Array(n), out = new Float64Array(n), ref = new Float64Array(n);
  for (let i = 0; i < n; i++) { const a = (CARD_TAU * (oLocal[i] - model[i])) / S; cr[i] = amp[i] * Math.cos(a); ci[i] = amp[i] * Math.sin(a); }
  const sr = smooth1d(cr, sigma), si = smooth1d(ci, sigma);
  for (let i = 0; i < n; i++) {
    const a = Math.atan2(si[i], sr[i]);
    ref[i] = model[i] + (S * a) / CARD_TAU;
    const d = oLocal[i] - ref[i];
    out[i] = ref[i] + d - S * Math.round(d / S);
  }
  return { o: out, ref };
}

// Audio readout (hill-and-dale: the sound is the depth of the cut). Per
// column, the land on both sides (mean over ±hb px at ±S/2) minus the traced
// bottom (mean over ±hb px): the cut depth, ≥ 0 (where the sound lifts the
// stylus out of the card it is 0 plus grain). Relative to its own average
// along the groove (σ avg columns; the nominal depth fades at the ends):
// est = depth/average − 1, the sound, which can't go below −1 (no cut).
// Then smoothed by σ `smooth` columns.
async function readoutPass(card, geom, TH, o, S, progress, hb = 2, smooth = 1, avg = 100) {
  const n = TH.length, r = new Float64Array(n), h = S / 2;
  for (let i = 0; i < n; i++) {
    const a = TH[i] + geom.ph, ca = Math.cos(a), sa = Math.sin(a), R = geom.b * TH[i] + o[i];
    const at = d => card.sample(geom.x + (R + d) * ca, geom.y + (R + d) * sa);
    let bot = 0, land = 0;
    for (let j = -hb; j <= hb; j++) { bot += at(j); land += at(j - h) + at(j + h); }
    r[i] = (land / 2 - bot) / (2 * hb + 1);
    if ((i & 8191) === 8191) { progress && progress(i / n); await tick(); }
  }
  // where the average depth is under ¼ of its median (the faded ends of the
  // recording) the ratio is meaningless: 0 there; otherwise clipped to −1..3
  const rs = smooth1d(r, avg), est = new Float64Array(n);
  const md = median(Array.from(rs.filter((_, i) => i % 17 === 0)));
  for (let i = 0; i < n; i++) est[i] = rs[i] > 0.25 * md ? Math.max(-1, Math.min(3, r[i] / rs[i] - 1)) : 0;
  return { raw: r, smooth: rs, est: smooth > 0 ? smooth1d(est, smooth) : est };
}
