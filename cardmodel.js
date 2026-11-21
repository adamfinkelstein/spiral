// Idealized card model for card.html: a procedural height map of a recording
// card, evaluated at any point in full-resolution pixels. No DOM. Needs
// mulberry32 (chunkfit.js).
//
// The card's surface is flat at height 0 (no warp, bend, scratches or dust),
// plus fine paper grain. The groove is cut by a round stylus moving along
// r(θ) = b·θ + δ(θ) (b = spacing/2π, θ = α − φ + 2πn, α the angle about the
// center; δ = slow drift over turns + a small, smooth lateral wobble), and
// moving up and down with the sound (hill-and-dale): the cut depth is
// D(s) = D0·(1 + a(s)), a(s) the sound along the groove (arc length s). The
// stylus profile is a parabola, z = −D + D0·(2u/W0)² at lateral distance u,
// so a deep cut is also wider and a shallow one narrower. Where the stylus is
// above the card (D < 0) nothing is cut: the height is min(0, stylus), so the
// groove momentarily disappears.

const CARD_TAU = 2 * Math.PI;

// Lengths in full-resolution pixels; heights in units of the nominal groove
// depth D0 = 1. Measured on sonorine_001 (presentation images 21–22):
// spacing 29.0 px; grain rms 0.52 × the groove's rms (2.6 vs 5.0), cells
// ~3 px; turns wander ±2 px between neighbours; annulus ~1600–2770 px.
// The groove's width, the sound's level and spectrum are assumed.
const CARD_PRESETS = {
  typical: {
    label: 'Typical',
    F: 5551, spacing: 29.0, spacingTol: 0.01, rIn: 1600, rOut: 2770,
    centerJitter: 40, annotErr: 12, annotRadiusErr: 0.01,
    width: 0.6, edgeFade: 60,
    audio: 0.4, audioWave: [15, 300],
    grain: 0.52, grainCell: 2.5,
    drift: 2.0, driftTurns: [0.7, 12], wobble: 0.3, wobbleWave: [200, 3000],
  },
  loud: {
    label: 'Loud (sound often cuts out)',
    F: 5551, spacing: 29.0, spacingTol: 0.01, rIn: 1600, rOut: 2770,
    centerJitter: 40, annotErr: 12, annotRadiusErr: 0.01,
    width: 0.6, edgeFade: 60,
    audio: 0.7, audioWave: [15, 300],
    grain: 0.52, grainCell: 2.5,
    drift: 2.0, driftTurns: [0.7, 12], wobble: 0.3, wobbleWave: [200, 3000],
  },
  hard: {
    label: 'Hard (more grain, drift, loud sound)',
    F: 5551, spacing: 29.0, spacingTol: 0.02, rIn: 1600, rOut: 2770,
    centerJitter: 40, annotErr: 25, annotRadiusErr: 0.02,
    width: 0.6, edgeFade: 80,
    audio: 0.6, audioWave: [15, 300],
    grain: 1.0, grainCell: 2.5,
    drift: 6.0, driftTurns: [0.5, 10], wobble: 0.6, wobbleWave: [150, 3000],
  },
  clean: {
    label: 'Clean (no grain)',
    F: 5551, spacing: 29.0, spacingTol: 0.01, rIn: 1600, rOut: 2770,
    centerJitter: 40, annotErr: 12, annotRadiusErr: 0.01,
    width: 0.6, edgeFade: 60,
    audio: 0.4, audioWave: [15, 300],
    grain: 0, grainCell: 2.5,
    drift: 2.0, driftTurns: [0.7, 12], wobble: 0.3, wobbleWave: [200, 3000],
  },
};

function makeCard(presetName, seed) {
  const P = CARD_PRESETS[presetName];
  const rnd = mulberry32(seed * 9973 + 11);
  const gauss = () => { const u = Math.max(rnd(), 1e-12), v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(CARD_TAU * v); };
  const logBetween = ([a, b]) => a * Math.pow(b / a, rnd());
  const F = P.F;
  const S = P.spacing * (1 + (2 * rnd() - 1) * P.spacingTol), b = S / CARD_TAU;
  const C = { x: F / 2 + gauss() * P.centerJitter, y: F / 2 + gauss() * P.centerJitter };
  const phi = rnd() * CARD_TAU;
  const ann = {
    x: C.x + gauss() * P.annotErr, y: C.y + gauss() * P.annotErr,
    rIn: P.rIn * (1 + gauss() * P.annotRadiusErr), rOut: P.rOut * (1 + gauss() * P.annotRadiusErr),
  };

  // slow drift δ(θ): sinusoids in θ with periods of driftTurns turns,
  // tabulated on a θ grid and scaled to rms P.drift
  const th0 = Math.max(1, (P.rIn - 6 * S) / b), th1 = (P.rOut + 6 * S) / b, DTH = 0.005;
  const nTh = Math.ceil((th1 - th0) / DTH) + 2, drift = new Float32Array(nTh);
  if (P.drift > 0) {
    const comps = Array.from({ length: 12 }, () => ({ w: 1 / logBetween(P.driftTurns), p: rnd() * CARD_TAU, a: gauss() }));
    let ss = 0;
    for (let k = 0; k < nTh; k++) { let v = 0; const th = th0 + k * DTH; for (const c of comps) v += c.a * Math.sin(c.w * th + c.p); drift[k] = v; ss += v * v; }
    const sc = P.drift / Math.sqrt(ss / nTh);
    for (let k = 0; k < nTh; k++) drift[k] *= sc;
  }
  const driftAt = th => { const x = (th - th0) / DTH, i = Math.max(0, Math.min(nTh - 2, Math.floor(x))), f = Math.min(1, Math.max(0, x - i)); return drift[i] * (1 - f) + drift[i + 1] * f; };

  // band-limited signals along the groove (arc length s ≈ bθ²/2): sums of 40
  // sinusoids with wavelengths log-uniform in `waves`, tabulated per px,
  // scaled to `rms`: the lateral wobble (px) and the sound (relative depth)
  const s0 = (b * th0 * th0) / 2, s1 = (b * th1 * th1) / 2, nS = Math.ceil(s1 - s0) + 2;
  const bandTable = (rms, waves) => {
    const t = new Float32Array(nS);
    if (!(rms > 0)) return t;
    const M = 40, re = new Float64Array(M), im = new Float64Array(M), cr = new Float64Array(M), ci = new Float64Array(M), amp = new Float64Array(M);
    for (let j = 0; j < M; j++) { const w = CARD_TAU / logBetween(waves), ph = rnd() * CARD_TAU + w * s0; amp[j] = gauss(); re[j] = Math.cos(ph); im[j] = Math.sin(ph); cr[j] = Math.cos(w); ci[j] = Math.sin(w); }
    let ss = 0;
    for (let k = 0; k < nS; k++) { // rotating phasors: sin(w·s + p) without a sin per sample
      let v = 0;
      for (let j = 0; j < M; j++) { v += amp[j] * im[j]; const r2 = re[j] * cr[j] - im[j] * ci[j]; im[j] = re[j] * ci[j] + im[j] * cr[j]; re[j] = r2; }
      if ((k & 4095) === 0) for (let j = 0; j < M; j++) { const n = Math.hypot(re[j], im[j]); re[j] /= n; im[j] /= n; }
      t[k] = v; ss += v * v;
    }
    const sc = rms / Math.sqrt(ss / nS);
    for (let k = 0; k < nS; k++) t[k] *= sc;
    return t;
  };
  const lookS = (t, th) => { const x = (b * th * th) / 2 - s0, i = Math.max(0, Math.min(nS - 2, Math.floor(x))), f = Math.min(1, Math.max(0, x - i)); return t[i] * (1 - f) + t[i + 1] * f; };
  const wobble = bandTable(P.wobble, P.wobbleWave), audio = bandTable(P.audio, P.audioWave);
  const wobbleAt = th => lookS(wobble, th), audioAt = th => lookS(audio, th);

  // depth of the cut along arm θ: D0·(1 + sound), faded in/out at the ends of
  // the recording; ≤ 0 means the stylus is above the card there
  const smooth01 = t => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
  const depthAt = th => { const r = b * th; return smooth01((r - P.rIn) / P.edgeFade) * smooth01((P.rOut - r) / P.edgeFade) * (1 + audioAt(th)); };

  // value noise (smooth, hashed) for the grain
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
  const seedG = (seed * 7 + 1) | 0;
  // the groove's rms over one spacing at the nominal depth: parabola of width
  // W0 = width·S, depth 1, mean −2W0/3S, mean square 8W0/15S
  const W0 = P.width * S, wf = P.width, grooveRms = Math.sqrt((8 * wf) / 15 - ((2 * wf) / 3) ** 2);
  let nG = 1;
  { let a = 0; for (let k = 0; k < 20000; k++) { const g = vnoise(rnd() * 4000, rnd() * 4000, 1, seedG); a += g * g; } nG = 1 / Math.sqrt(a / 20000); }
  const grainAmp = P.grain * grooveRms * nG; // grain rms = P.grain × the groove's rms

  // nearest arm and position across it for point (x, y)
  const psiAt = (x, y) => {
    const dx = x - C.x, dy = y - C.y, r = Math.hypot(dx, dy), al = Math.atan2(dy, dx) - phi;
    const n = Math.round((r / b - al) / CARD_TAU), th = al + CARD_TAU * n;
    const dev = driftAt(th) + wobbleAt(th);
    return { psi: ((r - dev) / b - al) / CARD_TAU, r, a: al + phi, th, dev };
  };
  const toIdeal = (x, y) => [x, y]; // no distortion in this model

  // height of the cut surface: min(0, stylus) over the nearest arms
  const k2 = 4 / (W0 * W0);
  const sample = (x, y, box = 0, gss = 0) => {
    const dx = x - C.x, dy = y - C.y, r = Math.hypot(dx, dy), al = Math.atan2(dy, dx) - phi;
    const n0 = Math.round((r / b - al) / CARD_TAU);
    let v = 0;
    for (let n = n0 - 1; n <= n0 + 1; n++) {
      const th = al + CARD_TAU * n;
      const u = r - b * th - driftAt(th) - wobbleAt(th); // radial distance to arm n
      if (u * u * k2 > 3) continue; // stylus far above the card here
      const z = -depthAt(th) + k2 * u * u;
      if (z < v) v = z;
    }
    if (P.grain) {
      let gr = 0;
      if (box > 0 && gss > 1) { // average over the box, as downsampling by area does
        for (let j = 0; j < gss; j++) for (let i = 0; i < gss; i++) gr += vnoise(x + ((i + 0.5) / gss - 0.5) * box, y + ((j + 0.5) / gss - 0.5) * box, P.grainCell, seedG);
        gr /= gss * gss;
      } else gr = vnoise(x, y, P.grainCell, seedG);
      v += grainAmp * gr;
    }
    return v;
  };

  // true groove offset at (x, y): radial distance (px, outward +) to the
  // nearest groove centerline, in [−S/2, S/2]
  const trueOffset = (x, y) => { const g = psiAt(x, y); return (Math.round(g.psi) - g.psi) * S; };

  return { P, F, S, b, C, phi, ann, W0, grooveRms, sample, trueOffset, psiAt, toIdeal, driftAt, wobbleAt, audioAt, depthAt, seed, preset: presetName };
}
