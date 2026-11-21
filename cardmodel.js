// Realistic card model for card.html: a procedural depth map of a recording
// card, evaluated at any point in full-resolution pixels, with parameters
// calibrated from the sonorine scans (see CARD_PRESETS). No DOM.
// Needs mulberry32 (chunkfit.js).
//
// Geometry (ideal card coordinates): the groove is r(θ) = b·θ + δ(θ),
// b = spacing/2π, θ = α − φ + 2πn (α the angle about the true center), with
// δ = slow drift (smooth over turns) + audio (band-limited along the groove).
// The observed image is that ideal card under a slight stretch and a smooth
// warp. Depth = −A·contrast·cos(2π·ψ) (ψ integer on the groove centerline)
// + slow depth drift + paper grain + banding + dust + scratches.

const CARD_TAU = 2 * Math.PI;

// Values are full-resolution pixels unless noted; depth amplitudes are
// relative to the groove amplitude A = 1 (cosine amplitude; rms 0.71).
// Measured on sonorine_001 (presentation image 21, 700 px full-res patch):
// spacing 29.0 px; near-sinusoidal groove profile (groove ≈ 47% of the
// spacing); groove rms 5.0, fine grain rms 2.6 (correlation ~3 px across,
// ~5 px along the grooves), slow drift rms 10.9 (correlation ~90 px) in the
// "local contrast" depth; groove wander ~1.3 px along the groove (smooth at
// 10 px), ±2 px between neighbouring turns. Annulus ~1600–2770 px (image 22).
const CARD_PRESETS = {
  typical: {
    label: 'Typical (like sonorine_001)',
    F: 5551, spacing: 29.0, spacingTol: 0.01, rIn: 1600, rOut: 2770,
    centerJitter: 40, annotErr: 12, annotRadiusErr: 0.01,
    groove: 1.0, edgeFade: 60,
    grain: 0.37, grainCell: 2.5, slow: 1.54, slowCell: 90,
    drift: 2.0, driftTurns: [0.7, 12], audio: 1.0, audioWave: [15, 300],
    aspect: 0.001, warp: 3, warpScale: [1500, 4000],
    banding: 0.2, bandPeriod: 55,
    dust: 150, dustSize: [3, 14], dustAmp: 2.5,
    scratches: 12, scratchLen: [60, 400], scratchWidth: 1.5, scratchAmp: 1.5,
    damage: { at: 2.4, width: 1.1, groove: 0.45, grain: 1.8 },
  },
  hard: {
    label: 'Hard (more drift, damage and grain)',
    F: 5551, spacing: 29.0, spacingTol: 0.02, rIn: 1600, rOut: 2770,
    centerJitter: 40, annotErr: 25, annotRadiusErr: 0.02,
    groove: 1.0, edgeFade: 80,
    grain: 0.6, grainCell: 2.5, slow: 2.2, slowCell: 90,
    drift: 6.0, driftTurns: [0.5, 10], audio: 2.0, audioWave: [12, 300],
    aspect: 0.002, warp: 6, warpScale: [1200, 3500],
    banding: 0.35, bandPeriod: 55,
    dust: 400, dustSize: [3, 20], dustAmp: 3,
    scratches: 40, scratchLen: [60, 600], scratchWidth: 2, scratchAmp: 2,
    damage: { at: 2.4, width: 1.6, groove: 0.3, grain: 2.5 },
  },
  clean: {
    label: 'Clean (geometry only, for checking)',
    F: 5551, spacing: 29.0, spacingTol: 0.01, rIn: 1600, rOut: 2770,
    centerJitter: 40, annotErr: 12, annotRadiusErr: 0.01,
    groove: 1.0, edgeFade: 60,
    grain: 0, grainCell: 2.5, slow: 0, slowCell: 90,
    drift: 2.0, driftTurns: [0.7, 12], audio: 1.0, audioWave: [15, 300],
    aspect: 0, warp: 0, warpScale: [1500, 4000],
    banding: 0, bandPeriod: 55,
    dust: 0, dustSize: [3, 14], dustAmp: 0,
    scratches: 0, scratchLen: [60, 400], scratchWidth: 1.5, scratchAmp: 0,
    damage: null,
  },
};

function makeCard(presetName, seed) {
  const P = CARD_PRESETS[presetName];
  const rnd = mulberry32(seed * 9973 + 11);
  const gauss = () => { const u = Math.max(rnd(), 1e-12), v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(CARD_TAU * v); };
  const between = ([a, b]) => a + (b - a) * rnd();
  const logBetween = ([a, b]) => a * Math.pow(b / a, rnd());
  const F = P.F;
  const S = P.spacing * (1 + (2 * rnd() - 1) * P.spacingTol), b = S / CARD_TAU;
  const C = { x: F / 2 + gauss() * P.centerJitter, y: F / 2 + gauss() * P.centerJitter };
  const phi = rnd() * CARD_TAU;
  const ann = {
    x: C.x + gauss() * P.annotErr, y: C.y + gauss() * P.annotErr,
    rIn: P.rIn * (1 + gauss() * P.annotRadiusErr), rOut: P.rOut * (1 + gauss() * P.annotRadiusErr),
  };

  // slow drift δ(θ): a sum of sinusoids in θ with periods of driftTurns turns,
  // tabulated on a θ grid and scaled to rms P.drift
  const th0 = Math.max(1, (P.rIn - 6 * S) / b), th1 = (P.rOut + 6 * S) / b, DTH = 0.005;
  const nTh = Math.ceil((th1 - th0) / DTH) + 2, drift = new Float32Array(nTh);
  if (P.drift > 0) {
    const comps = Array.from({ length: 12 }, () => ({ w: CARD_TAU / (CARD_TAU * logBetween(P.driftTurns)), p: rnd() * CARD_TAU, a: gauss() }));
    let ss = 0;
    for (let k = 0; k < nTh; k++) { let v = 0; const th = th0 + k * DTH; for (const c of comps) v += c.a * Math.sin(c.w * th + c.p); drift[k] = v; ss += v * v; }
    const sc = P.drift / Math.sqrt(ss / nTh);
    for (let k = 0; k < nTh; k++) drift[k] *= sc;
  }
  const driftAt = th => { const x = (th - th0) / DTH, i = Math.max(0, Math.min(nTh - 2, Math.floor(x))), f = Math.min(1, Math.max(0, x - i)); return drift[i] * (1 - f) + drift[i + 1] * f; };

  // audio: band-limited lateral deviation along the groove (arc length s ≈ bθ²/2),
  // a sum of sinusoids with wavelengths log-uniform in audioWave, tabulated per px
  const s0 = (b * th0 * th0) / 2, s1 = (b * th1 * th1) / 2, nS = Math.ceil(s1 - s0) + 2;
  const audio = new Float32Array(nS);
  if (P.audio > 0) {
    const M = 40, re = new Float64Array(M), im = new Float64Array(M), cr = new Float64Array(M), ci = new Float64Array(M), amp = new Float64Array(M);
    for (let j = 0; j < M; j++) { const w = CARD_TAU / logBetween(P.audioWave), ph = rnd() * CARD_TAU + w * s0; amp[j] = gauss(); re[j] = Math.cos(ph); im[j] = Math.sin(ph); cr[j] = Math.cos(w); ci[j] = Math.sin(w); }
    let ss = 0;
    for (let k = 0; k < nS; k++) { // rotating phasors: sin(w·s + p) without a sin per sample
      let v = 0;
      for (let j = 0; j < M; j++) { v += amp[j] * im[j]; const r2 = re[j] * cr[j] - im[j] * ci[j]; im[j] = re[j] * ci[j] + im[j] * cr[j]; re[j] = r2; }
      if ((k & 4095) === 0) for (let j = 0; j < M; j++) { const n = Math.hypot(re[j], im[j]); re[j] /= n; im[j] /= n; }
      audio[k] = v; ss += v * v;
    }
    const sc = P.audio / Math.sqrt(ss / nS);
    for (let k = 0; k < nS; k++) audio[k] *= sc;
  }
  const audioAt = th => { const x = (b * th * th) / 2 - s0, i = Math.max(0, Math.min(nS - 2, Math.floor(x))), f = Math.min(1, Math.max(0, x - i)); return audio[i] * (1 - f) + audio[i + 1] * f; };

  // card distortion: stretch about the center (aspect) plus a smooth warp
  const aspect = 1 + (2 * rnd() - 1) * P.aspect;
  const warpModes = P.warp > 0 ? Array.from({ length: 6 }, () => {
    const wl = logBetween(P.warpScale), a = rnd() * CARD_TAU;
    return { kx: (CARD_TAU / wl) * Math.cos(a), ky: (CARD_TAU / wl) * Math.sin(a), p: rnd() * CARD_TAU, ax: gauss(), ay: gauss() };
  }) : [];
  let warpNorm = 1;
  if (warpModes.length) { let ss = 0; for (const m of warpModes) ss += (m.ax * m.ax + m.ay * m.ay) / 2; warpNorm = P.warp / Math.sqrt(ss); }
  // smooth fields (warp, slow depth drift) are tabulated on a coarse grid
  // over the frame and interpolated bilinearly
  const TG = 16, tw = Math.ceil(F / TG) + 2;
  const table = f => { const t = new Float32Array(tw * tw); for (let j = 0; j < tw; j++) for (let i = 0; i < tw; i++) t[j * tw + i] = f(i * TG, j * TG); return t; };
  const lerpT = (t, x, y) => {
    const fx = Math.min(tw - 1.001, Math.max(0, x / TG)), fy = Math.min(tw - 1.001, Math.max(0, y / TG));
    const i = fx | 0, j = fy | 0, u = fx - i, v = fy - j, o = j * tw + i;
    return (t[o] * (1 - u) + t[o + 1] * u) * (1 - v) + (t[o + tw] * (1 - u) + t[o + tw + 1] * u) * v;
  };
  const warpF = (x, y, axis) => { let q = 0; for (const m of warpModes) q += (axis ? m.ay : m.ax) * Math.sin(m.kx * x + m.ky * y + m.p) * warpNorm; return q; };
  const WX = warpModes.length ? table((x, y) => warpF(x, y, 0)) : null, WY = warpModes.length ? table((x, y) => warpF(x, y, 1)) : null;
  let QX = 0, QY = 0; // toIdealQ's result (no allocation in the hot path)
  const toIdealQ = (x, y) => { // observed → ideal card coordinates
    let qx = x, qy = y;
    if (WX) { qx += lerpT(WX, x, y); qy += lerpT(WY, x, y); }
    QX = C.x + (qx - C.x) / aspect; QY = C.y + (qy - C.y) * aspect;
  };
  const toIdeal = (x, y) => { toIdealQ(x, y); return [QX, QY]; };

  // value noise (smooth, hashed), unit rms after normalization
  const hash = (ix, iy, s) => {
    let h = (Math.imul(ix, 374761393) + Math.imul(iy, 668265263) + Math.imul(s, 1442695041)) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177); h ^= h >>> 16;
    return (h & 0xffffff) / 0x800000 - 1;
  };
  const vnoise = (x, y, cell, s) => {
    const fx = x / cell, fy = y / cell, ix = Math.floor(fx), iy = Math.floor(fy);
    let tx = fx - ix, ty = fy - iy; tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty);
    const a = hash(ix, iy, s), b2 = hash(ix + 1, iy, s), c = hash(ix, iy + 1, s), d = hash(ix + 1, iy + 1, s);
    return (a * (1 - tx) + b2 * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
  };
  const seedG = (seed * 7 + 1) | 0, seedS = (seed * 13 + 5) | 0, seedS2 = (seed * 17 + 3) | 0;
  let nG = 1, nSl = 1;
  { let a = 0, c = 0; for (let k = 0; k < 20000; k++) { const x = rnd() * 4000, y = rnd() * 4000; const g = vnoise(x, y, 1, seedG); a += g * g; const s = vnoise(x, y, 1, seedS) + 0.5 * vnoise(x, y, 0.5, seedS2); c += s * s; } nG = 1 / Math.sqrt(a / 20000); nSl = 1 / Math.sqrt(c / 20000); }
  const bandPh = rnd() * CARD_TAU;
  const SL = P.slow ? table((x, y) => P.slow * nSl * (vnoise(x, y, P.slowCell, seedS) + 0.5 * vnoise(x, y, P.slowCell / 2, seedS2))) : null;

  // dust and scratches, with a coarse grid for lookup
  const GRID = 128, gw = Math.ceil(F / GRID), grid = Array.from({ length: gw * gw }, () => []);
  const addToGrid = (obj, x0, y0, x1, y1) => {
    for (let gy = Math.max(0, Math.floor(y0 / GRID)); gy <= Math.min(gw - 1, Math.floor(y1 / GRID)); gy++)
      for (let gx = Math.max(0, Math.floor(x0 / GRID)); gx <= Math.min(gw - 1, Math.floor(x1 / GRID)); gx++) grid[gy * gw + gx].push(obj);
  };
  const randInAnnulus = () => { const r = Math.sqrt(between([(P.rIn - 200) ** 2, (P.rOut + 200) ** 2])), a = rnd() * CARD_TAU; return [C.x + r * Math.cos(a), C.y + r * Math.sin(a)]; };
  for (let k = 0; k < P.dust; k++) {
    const [x, y] = randInAnnulus(), sg = logBetween(P.dustSize) / 2, amp = P.dustAmp * (rnd() < 0.7 ? 1 : -1) * (0.5 + rnd());
    addToGrid({ t: 0, x, y, sg, amp }, x - 3 * sg, y - 3 * sg, x + 3 * sg, y + 3 * sg);
  }
  for (let k = 0; k < P.scratches; k++) {
    const [x, y] = randInAnnulus(), L = between(P.scratchLen), a = rnd() * CARD_TAU;
    const x1 = x + L * Math.cos(a), y1 = y + L * Math.sin(a), w = P.scratchWidth * (0.6 + 0.8 * rnd()), amp = P.scratchAmp * (rnd() < 0.5 ? 1 : -1);
    addToGrid({ t: 1, x, y, x1, y1, w, amp }, Math.min(x, x1) - 3 * w, Math.min(y, y1) - 3 * w, Math.max(x, x1) + 3 * w, Math.max(y, y1) + 3 * w);
  }
  const defectsAt = (x, y) => {
    const gx = Math.floor(x / GRID), gy = Math.floor(y / GRID);
    if (gx < 0 || gy < 0 || gx >= gw || gy >= gw) return 0;
    let v = 0;
    for (const o of grid[gy * gw + gx]) {
      if (o.t === 0) { const d2 = (x - o.x) ** 2 + (y - o.y) ** 2; if (d2 < 9 * o.sg * o.sg) v += o.amp * Math.exp(-d2 / (2 * o.sg * o.sg)); }
      else {
        const vx = o.x1 - o.x, vy = o.y1 - o.y, L2 = vx * vx + vy * vy;
        const t = Math.max(0, Math.min(1, ((x - o.x) * vx + (y - o.y) * vy) / L2));
        const d2 = (x - o.x - t * vx) ** 2 + (y - o.y - t * vy) ** 2;
        if (d2 < 9 * o.w * o.w) v += o.amp * Math.exp(-d2 / (2 * o.w * o.w));
      }
    }
    return v;
  };

  const smooth01 = t => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
  const dmg = P.damage;
  const damageAt = a => { // 0..1 inside the damaged sector (soft edges)
    if (!dmg) return 0;
    const d = Math.abs(((a - dmg.at + 3 * Math.PI) % CARD_TAU) - Math.PI);
    return smooth01((dmg.width / 2 - d) / 0.25);
  };

  // groove phase ψ at ideal point (qx, qy): integer on the groove centerline
  const psiAt = (qx, qy) => {
    const dx = qx - C.x, dy = qy - C.y, r = Math.hypot(dx, dy), al = Math.atan2(dy, dx) - phi;
    const n = Math.round((r / b - al) / CARD_TAU), th = al + CARD_TAU * n;
    const dev = driftAt(th) + audioAt(th);
    return { psi: ((r - dev) / b - al) / CARD_TAU, r, a: al + phi, th, dev };
  };

  const sample = (x, y) => { // depth at observed full-res point (x, y)
    toIdealQ(x, y);
    const dx = QX - C.x, dy = QY - C.y, r = Math.hypot(dx, dy), a = Math.atan2(dy, dx), al = a - phi;
    const th = al + CARD_TAU * Math.round((r / b - al) / CARD_TAU);
    const psi = ((r - driftAt(th) - audioAt(th)) / b - al) / CARD_TAU;
    const dm = dmg ? damageAt(a) : 0;
    const contrast = P.groove * smooth01((r - P.rIn) / P.edgeFade) * smooth01((P.rOut - r) / P.edgeFade) * (1 - dm * (1 - (dmg ? dmg.groove : 1)));
    let v = contrast > 0 ? -contrast * Math.cos(CARD_TAU * psi) : 0;
    if (SL) v += lerpT(SL, x, y);
    if (P.grain) v += P.grain * nG * (1 + dm * ((dmg ? dmg.grain : 1) - 1)) * vnoise(x, y, P.grainCell, seedG);
    if (P.banding) v += P.banding * Math.sin((CARD_TAU * y) / P.bandPeriod + bandPh);
    if (P.dust || P.scratches) v += defectsAt(x, y);
    return v;
  };

  // true groove offset at observed point (x, y): radial distance (px, outward
  // positive) to the nearest groove centerline, in [−S/2, S/2]
  const trueOffset = (x, y) => { const [qx, qy] = toIdeal(x, y); const g = psiAt(qx, qy); return (Math.round(g.psi) - g.psi) * S; };

  return { P, F, S, b, C, phi, ann, aspect, sample, trueOffset, psiAt, toIdeal, driftAt, audioAt, seed, preset: presetName };
}
