// Connected components of the chunk image and per-component spiral fits, for
// center.html. Pure functions (no DOM); depends only on N from render.js.
//
// Spiral model (matches render.js): arm n passes radius r = b (α − φ + 2πn),
// b = spacing / 2π, where α is the angle about the center and φ the phase.
// θ = α − φ + 2πn = r / b is the spiral parameter along the curve.
// Image values may be noisy (outside 0..1); weights are clamped to 0..1.

const TAU = 2 * Math.PI;
const MAX_FIT_PIXELS = 20000; // skip huge components (e.g. noise that percolates)
const wrapPi = a => a - TAU * Math.round(a / TAU); // into [−π, π]

// Small seeded PRNG (mulberry32), so a chunk set is reproducible from its seed.
function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- Connected components ----------

// Hysteresis thresholding (as in Canny): 8-connected components seeded by
// pixels with img > hi and extended through pixels with img > lo; components
// with fewer than minArea such pixels are dropped. Each kept component is then
// grown by up to `grow` px (8-neighbour BFS) into unlabelled pixels with
// edgeLo < img <= lo, so the soft edges of the line take part in the fit.
// Returns { label: Int32Array (−1 = none), comps: [{ core, pix }] }, largest
// (most core pixels) first, where core holds the pixels above lo and pix
// core + grown pixels (core first).
function labelComponents(img, hi, lo, minArea, grow = 2, edgeLo = 0.02) {
  lo = Math.min(lo, hi);
  const label = new Int32Array(N * N).fill(-1);
  const stack = new Int32Array(N * N);
  const found = [];
  for (let i = 0; i < N * N; i++) {
    if (img[i] <= hi || label[i] !== -1) continue;
    const id = found.length, core = [];
    let sp = 0;
    stack[sp++] = i; label[i] = id;
    while (sp) {
      const j = stack[--sp];
      core.push(j);
      const x = j % N, y = (j - x) / N;
      for (let dy = -1; dy <= 1; dy++) {
        const ny = y + dy;
        if (ny < 0 || ny >= N) continue;
        for (let dx = -1; dx <= 1; dx++) {
          const nx = x + dx;
          if (nx < 0 || nx >= N) continue;
          const k = ny * N + nx;
          if (label[k] === -1 && img[k] > lo) { label[k] = id; stack[sp++] = k; }
        }
      }
    }
    found.push(core);
  }
  label.fill(-1);
  // Numbered by size: component 0 has the most core pixels.
  const comps = found.filter(c => c.length >= minArea).sort((a, b) => b.length - a.length).map(core => ({ core, pix: core.slice() }));
  comps.forEach((c, id) => { for (const j of c.core) label[j] = id; });

  let frontier = comps.flatMap(c => c.core);
  for (let g = 0; g < grow; g++) {
    const next = [];
    for (const j of frontier) {
      const id = label[j], x = j % N, y = (j - x) / N;
      for (let dy = -1; dy <= 1; dy++) {
        const ny = y + dy;
        if (ny < 0 || ny >= N) continue;
        for (let dx = -1; dx <= 1; dx++) {
          const nx = x + dx;
          if (nx < 0 || nx >= N) continue;
          const k = ny * N + nx;
          // only soft-edge pixels: pixels above lo not in this component
          // belong to dropped components (e.g. noise specks), not the edge
          if (label[k] === -1 && img[k] > edgeLo && img[k] <= lo) { label[k] = id; comps[id].pix.push(k); next.push(k); }
        }
      }
    }
    frontier = next;
  }
  return { label, comps };
}

// ---------- Small linear algebra / Levenberg–Marquardt ----------

function solve(A, b) { // Gaussian elimination with partial pivoting; A is n×n array of arrays
  const n = b.length, M = A.map((r, i) => [...r, b[i]]);
  for (let c = 0; c < n; c++) {
    let piv = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[piv][c])) piv = r;
    if (Math.abs(M[piv][c]) < 1e-300) return null;
    [M[c], M[piv]] = [M[piv], M[c]];
    for (let r = c + 1; r < n; r++) {
      const f = M[r][c] / M[c][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  const x = new Array(n);
  for (let r = n - 1; r >= 0; r--) {
    let s = M[r][n];
    for (let k = r + 1; k < n; k++) s -= M[r][k] * x[k];
    x[r] = s / M[r][r];
  }
  return x;
}

function sumSq(e) { let s = 0; for (const v of e) s += v * v; return s; }

function jacobian(resid, p, e0) { // central differences; returns columns
  return p.map((v, i) => {
    const h = 1e-5 * Math.max(1, Math.abs(v));
    const a = p.slice(), b = p.slice();
    a[i] += h; b[i] -= h;
    const ea = resid(a), eb = resid(b);
    const col = new Float64Array(e0.length);
    for (let k = 0; k < col.length; k++) col[k] = (ea[k] - eb[k]) / (2 * h);
    return col;
  });
}

function normalEq(J, e) {
  const n = J.length;
  const A = J.map(ci => J.map(cj => { let s = 0; for (let k = 0; k < ci.length; k++) s += ci[k] * cj[k]; return s; }));
  const g = J.map(ci => { let s = 0; for (let k = 0; k < ci.length; k++) s += ci[k] * e[k]; return s; });
  return { A, g, n };
}

// Minimizes sumSq(resid(p)). Returns { p, e, cost, A } with A = JᵀJ at the end.
function lm(p0, resid, maxIter = 60) {
  let p = p0.slice(), e = resid(p), cost = sumSq(e), lambda = 1e-3;
  for (let it = 0; it < maxIter; it++) {
    const { A, g } = normalEq(jacobian(resid, p, e), e);
    let accepted = false;
    for (let t = 0; t < 12 && !accepted; t++) {
      const Ad = A.map((r, i) => r.map((v, j) => (i === j ? v * (1 + lambda) + 1e-12 : v)));
      const dp = solve(Ad, g.map(v => -v));
      if (dp && dp.every(Number.isFinite)) {
        const pn = p.map((v, i) => v + dp[i]), en = resid(pn), cn = sumSq(en);
        if (cn < cost) {
          const rel = (cost - cn) / Math.max(cost, 1e-300);
          p = pn; e = en; cost = cn; lambda = Math.max(lambda / 10, 1e-12); accepted = true;
          if (rel < 1e-10) it = maxIter; // converged
          continue;
        }
      }
      lambda *= 10;
    }
    if (!accepted) break;
  }
  return { p, e, cost, A: normalEq(jacobian(resid, p, e), e).A };
}

// ---------- Robust loss ----------

// Tukey biweight with cutoff c: ρ(e) rises like e²/2 near 0 and is constant
// (c²/6) for |e| >= c, so far pixels add a fixed penalty but no pull. Moving
// the curve away from the pixels therefore makes the loss maximal, not zero.
// tukeyW is the IRLS weight ψ(e)/e; lossNorm is ρ / ρmax, in 0..1.
const tukeyW = (e, c) => { const t = e / c; return t * t < 1 ? (1 - t * t) ** 2 : 0; };
const lossNorm = (e, c) => { const t = e / c; return t * t < 1 ? 1 - (1 - t * t) ** 3 : 1; };

// ---------- Per-component fit ----------

// Fits one component. p: params() from center.js (uses p.spacing).
// opts: { thresh, refine }. Returns an object with the circle fit (init),
// the final center, phase, θ range, rms residual and an approximate 2×2
// covariance of the center (pixels treated as independent samples).
function fitChunk(img, comp, p, opts) {
  const m = comp.pix.length;
  if (m > MAX_FIT_PIXELS) return { n: m, nCore: comp.core.length, ok: false, reason: 'too large (noise?)' };
  const X = new Float64Array(m), Y = new Float64Array(m), W = new Float64Array(m), SW = new Float64Array(m);
  const core = new Uint8Array(m);
  let sw = 0, mx = 0, my = 0;
  for (let k = 0; k < m; k++) {
    const j = comp.pix[k], x = j % N;
    X[k] = x + 0.5; Y[k] = (j - x) / N + 0.5; W[k] = Math.min(1, Math.max(0, img[j])); SW[k] = Math.sqrt(W[k]);
    core[k] = k < comp.core.length ? 1 : 0; // pix lists the core pixels first
    sw += W[k]; mx += W[k] * X[k]; my += W[k] * Y[k];
  }
  mx /= sw; my /= sw;

  // 1. Weighted algebraic (Kåsa) circle fit, in coordinates centred on the
  //    weighted mean: minimize Σ w (u² + v² + D u + E v + F)².
  const A3 = [[0, 0, 0], [0, 0, 0], [0, 0, 0]], b3 = [0, 0, 0];
  for (let k = 0; k < m; k++) {
    const u = X[k] - mx, v = Y[k] - my, z = u * u + v * v, row = [u, v, 1];
    for (let i = 0; i < 3; i++) {
      for (let j = 0; j < 3; j++) A3[i][j] += W[k] * row[i] * row[j];
      b3[i] -= W[k] * row[i] * z;
    }
  }
  const DEF = solve(A3, b3);
  let kasa = null;
  if (DEF) {
    const cx = mx - DEF[0] / 2, cy = my - DEF[1] / 2, R2 = (DEF[0] * DEF[0] + DEF[1] * DEF[1]) / 4 - DEF[2];
    if (R2 > 0 && Number.isFinite(cx + cy)) kasa = { x: cx, y: cy, R: Math.sqrt(R2) };
  }
  const out = { n: m, nCore: core.reduce((a, v) => a + v, 0), mean: { x: mx, y: my }, ok: false };
  if (!kasa || kasa.R > 20 * N) { out.reason = 'too straight'; return out; }

  // 2. Geometric circle fit (weighted distance to the circle), from Kåsa.
  const circ = lm([kasa.x, kasa.y, kasa.R], q => {
    const e = new Float64Array(m);
    for (let k = 0; k < m; k++) e[k] = SW[k] * (Math.hypot(X[k] - q[0], Y[k] - q[1]) - q[2]);
    return e;
  });
  const S = p.spacing, b = S / TAU;

  // 2b. Correct the circle center for the spiral: at a point at angle α, the
  //     spiral's center of curvature lies ≈ b sideways from the spiral center,
  //     along (−sin α, cos α) (exactly b(r²+b²)/(r²+2b²); radially only ≈ b²/r).
  //     So subtract b × the weighted mean of (−sin α, cos α) over the core
  //     pixels, with α about the circle center. One pass suffices (a second
  //     moves it ~0.01 px); this cuts the circle center's error ~10× without
  //     noise, and removes the sideways bias when all chunks are on one side.
  let tx = 0, ty = 0, tw = 0;
  for (let k = 0; k < m; k++) {
    if (!core[k]) continue;
    const a = Math.atan2(Y[k] - circ.p[1], X[k] - circ.p[0]);
    tx -= W[k] * Math.sin(a); ty += W[k] * Math.cos(a); tw += W[k];
  }
  out.circleRaw = { x: circ.p[0], y: circ.p[1], R: circ.p[2] };
  out.circle = tw > 0
    ? { x: circ.p[0] - (b * tx) / tw, y: circ.p[1] - (b * ty) / tw, R: circ.p[2] }
    : out.circleRaw;
  // Angles are measured relative to a fixed reference direction (towards the
  // chunk from the circle centre), so a chunk never straddles the ±π cut.
  const ref = Math.atan2(my - out.circle.y, mx - out.circle.x);
  const angle = (k, cx, cy) => ref + wrapPi(Math.atan2(Y[k] - cy, X[k] - cx) - ref);
  const phaseAt = (cx, cy) => { // weighted circular mean of α − r/b
    let s = 0, c = 0;
    for (let k = 0; k < m; k++) {
      const a = Math.atan2(Y[k] - cy, X[k] - cx) - Math.hypot(X[k] - cx, Y[k] - cy) / b;
      s += W[k] * Math.sin(a); c += W[k] * Math.cos(a);
    }
    return Math.atan2(s, c);
  };
  const armIndex = new Float64Array(m);
  const setArms = (cx, cy, ph) => {
    let changed = false;
    for (let k = 0; k < m; k++) {
      const r = Math.hypot(X[k] - cx, Y[k] - cy);
      const n = Math.round((r / b - (angle(k, cx, cy) - ph)) / TAU);
      if (n !== armIndex[k]) { armIndex[k] = n; changed = true; }
    }
    return changed;
  };

  // Robust loss: Tukey cutoff (px) and per-pixel IRLS weights U (1 = plain
  // least squares). Inliers are pixels within half the cutoff of their arm.
  const cut = Math.max(opts.cutoff * S, 1e-6);
  const U = new Float64Array(m).fill(1);
  const perpResid = (k, q) => {
    const r = Math.hypot(X[k] - q[0], Y[k] - q[1]);
    return (r - b * (angle(k, q[0], q[1]) - q[2] + TAU * armIndex[k])) * r / Math.sqrt(r * r + b * b);
  };
  const resid = q => { // q = [cx, cy, φ]; weighted perpendicular distance to the pixel's arm
    const e = new Float64Array(m);
    for (let k = 0; k < m; k++) e[k] = SW[k] * Math.sqrt(U[k]) * perpResid(k, q);
    return e;
  };
  const setWeights = q => {
    for (let k = 0; k < m; k++) U[k] = opts.robust ? tukeyW(perpResid(k, q), cut) : 1;
  };

  // Start from opts.start if given (shared start), else this chunk's circle fit.
  let cx = opts.start ? opts.start.x : out.circle.x, cy = opts.start ? opts.start.y : out.circle.y;
  let ph = phaseAt(cx, cy), fit = null;
  setArms(cx, cy, ph);
  if (opts.refine) {
    // 3. Refine the spiral model by iteratively reweighted least squares: each
    //    round assigns every pixel to its nearest arm, sets its Tukey weight,
    //    and runs LM with those held fixed, until the center stops moving.
    for (let round = 0; round < 12; round++) {
      setWeights([cx, cy, ph]);
      fit = lm([cx, cy, ph], resid, 20);
      const moved = Math.hypot(fit.p[0] - cx, fit.p[1] - cy);
      [cx, cy, ph] = fit.p;
      const changed = setArms(cx, cy, ph);
      if (!changed && moved < 1e-3) break;
    }
  }
  setWeights([cx, cy, ph]);
  fit = { e: resid([cx, cy, ph]) };
  fit.A = normalEq(jacobian(resid, [cx, cy, ph], fit.e), fit.e).A;

  // Robust loss (0 = every pixel on its arm, 1 = all outliers), weighted
  // inlier fraction, and inlier mask.
  const inl = new Uint8Array(m);
  let loss = 0, inW = 0, swu = 0;
  for (let k = 0; k < m; k++) {
    const e = perpResid(k, [cx, cy, ph]);
    loss += W[k] * lossNorm(e, cut);
    if (Math.abs(e) < cut / 2) { inl[k] = 1; inW += W[k]; }
    swu += W[k] * U[k];
  }

  // Approximate covariance s² (JᵀJ)⁻¹ with s² = Σ w u e² / (Σ w u − #params).
  const s2 = sumSq(fit.e) / Math.max(swu - 3, 1);
  const inv = [0, 1].map(i => solve(fit.A, fit.A.map((_, j) => (i === j ? 1 : 0))));
  const cov = inv[0] && inv[1] ? [[inv[0][0] * s2, inv[1][0] * s2], [inv[0][1] * s2, inv[1][1] * s2]] : null;

  // θ range over the core pixels that are inliers.
  let tMin = Infinity, tMax = -Infinity;
  for (let k = 0; k < m; k++) {
    if (!core[k] || !inl[k]) continue;
    const t = angle(k, cx, cy) - ph + TAU * armIndex[k];
    if (t < tMin) tMin = t;
    if (t > tMax) tMax = t;
  }

  Object.assign(out, {
    ok: Number.isFinite(tMin), reason: Number.isFinite(tMin) ? undefined : 'no inliers',
    x: cx, y: cy, cov,
    phase: ((ph % TAU) + TAU) % TAU,
    thetaMin: tMin, thetaMax: tMax,
    rms: Math.sqrt(sumSq(fit.e) / Math.max(swu, 1e-9)),
    loss: loss / sw, inlierFrac: inW / sw,
    meanR: Math.hypot(mx - cx, my - cy),
  });
  // Ground truth for the same pixels (core inliers), from the true centre,
  // phase and spacing.
  out.truth = (tx, ty, tph, tS) => {
    const b = tS / TAU;
    const tref = Math.atan2(my - ty, mx - tx);
    let a0 = Infinity, a1 = -Infinity;
    for (let k = 0; k < m; k++) {
      if (!core[k] || !inl[k]) continue;
      const a = tref + wrapPi(Math.atan2(Y[k] - ty, X[k] - tx) - tref);
      const r = Math.hypot(X[k] - tx, Y[k] - ty);
      const t = a - tph + TAU * Math.round((r / b - (a - tph)) / TAU);
      if (t < a0) a0 = t;
      if (t > a1) a1 = t;
    }
    return { thetaMin: a0, thetaMax: a1 };
  };
  return out;
}

// ---------- All components ----------

const median = a => { const s = a.slice().sort((x, y) => x - y), n = s.length; return n % 2 ? s[n >> 1] : (s[n / 2 - 1] + s[n / 2]) / 2; };
const medianPoint = fs => (fs.length ? { x: median(fs.map(f => f.x)), y: median(fs.map(f => f.y)), n: fs.length } : null);

// Fits every component and marks f.kept (extent >= opts.minExtent, inlier
// fraction >= opts.minInlier, and center at least one spacing from the chunk). With opts.shared, the spiral fits start from a
// shared center instead of each chunk's own circle fit:
//   1. circle fit per component; those with extent >= minExtent (measured
//      about the circle's center) vote: start1 = median x, median y.
//   2. fit every component's spiral from start1; start2 = median of the
//      centers of the kept fits.
//   3. fit every component again from start2: these are the results.
// Falls back to per-chunk starts when nothing qualifies. Returns
// { fits, starts: [start1, start2] }.
function fitComponents(img, comps, p, opts) {
  // (A fit whose center is within one spacing of its own pixels has collapsed
  // onto a speck, e.g. a tiny fragment; its 'extent' about that center means nothing.)
  const keep = f => f.ok && f.thetaMax - f.thetaMin >= opts.minExtent && f.inlierFrac >= opts.minInlier && f.meanR >= p.spacing;
  const run = start => comps.map(c => {
    const f = fitChunk(img, c, p, { ...opts, start });
    f.kept = keep(f);
    return f;
  });
  if (!opts.shared || !opts.refine) return { fits: run(null), starts: [] };
  const circles = comps.map(c => fitChunk(img, c, p, { ...opts, refine: false }));
  const start1 = medianPoint(circles.filter(f => f.ok && f.thetaMax - f.thetaMin >= opts.minExtent));
  if (!start1) return { fits: run(null), starts: [] };
  const fits1 = run(start1);
  const start2 = medianPoint(fits1.filter(f => f.kept)) || start1;
  return { fits: run(start2), starts: [start1, start2] };
}

// ---------- Combining chunks (RANSAC over chunks) ----------

// Pixel arrays of one component (core pixels first), subsampled to at most
// maxPix pixels if given.
function chunkData(img, comp, maxPix) {
  let idx = comp.pix;
  if (maxPix && idx.length > maxPix) { const st = Math.ceil(idx.length / maxPix); idx = idx.filter((_, i) => i % st === 0); }
  const m = idx.length, X = new Float64Array(m), Y = new Float64Array(m), W = new Float64Array(m);
  let sw = 0, mx = 0, my = 0;
  idx.forEach((j, k) => {
    const x = j % N;
    X[k] = x + 0.5; Y[k] = (j - x) / N + 0.5; W[k] = Math.min(1, Math.max(0, img[j]));
    sw += W[k]; mx += W[k] * X[k]; my += W[k] * Y[k];
  });
  return { m, X, Y, W, sw, mx: mx / sw, my: my / sw };
}

// Normalized Tukey loss (0..1) of a chunk's pixels for a fixed spiral (center,
// phase), each pixel on its nearest arm.
function evalLoss(d, cx, cy, ph, S, cut) {
  const b = S / TAU;
  let acc = 0;
  for (let k = 0; k < d.m; k++) {
    const r = Math.hypot(d.X[k] - cx, d.Y[k] - cy);
    let e = r - b * (Math.atan2(d.Y[k] - cy, d.X[k] - cx) - ph);
    e = (e - S * Math.round(e / S)) * r / Math.sqrt(r * r + b * b);
    acc += d.W[k] * lossNorm(e, cut);
  }
  return acc / d.sw;
}

// Weighted circular mean of α − r/b over several chunks: the best phase for a
// given center.
function phaseFor(ds, cx, cy, b) {
  let s = 0, c = 0;
  for (const d of ds) for (let k = 0; k < d.m; k++) {
    const a = Math.atan2(d.Y[k] - cy, d.X[k] - cx) - Math.hypot(d.X[k] - cx, d.Y[k] - cy) / b;
    s += d.W[k] * Math.sin(a); c += d.W[k] * Math.cos(a);
  }
  return Math.atan2(s, c);
}

// One spiral (center + phase, spacing S) fitted to the pixels of several
// chunks at once, by the same IRLS as fitChunk: each round assigns every pixel
// to its nearest arm and sets its Tukey weight, then LM. Angles are measured
// relative to a per-chunk reference direction, so no chunk straddles ±π.
function fitJoint(ds, start, S, cut, rounds = 8, iters = 20) {
  const b = S / TAU;
  let m = 0;
  for (const d of ds) m += d.m;
  const X = new Float64Array(m), Y = new Float64Array(m), SW = new Float64Array(m), W = new Float64Array(m);
  const REF = new Float64Array(m), ARM = new Float64Array(m), U = new Float64Array(m).fill(1);
  let o = 0, sw = 0;
  for (const d of ds) {
    const ref = Math.atan2(d.my - start.y, d.mx - start.x);
    for (let k = 0; k < d.m; k++, o++) {
      X[o] = d.X[k]; Y[o] = d.Y[k]; W[o] = d.W[k]; SW[o] = Math.sqrt(d.W[k]); REF[o] = ref; sw += d.W[k];
    }
  }
  const ang = (k, cx, cy) => REF[k] + wrapPi(Math.atan2(Y[k] - cy, X[k] - cx) - REF[k]);
  const perp = (k, q) => {
    const r = Math.hypot(X[k] - q[0], Y[k] - q[1]);
    return (r - b * (ang(k, q[0], q[1]) - q[2] + TAU * ARM[k])) * r / Math.sqrt(r * r + b * b);
  };
  const resid = q => { const e = new Float64Array(m); for (let k = 0; k < m; k++) e[k] = SW[k] * Math.sqrt(U[k]) * perp(k, q); return e; };
  const assign = q => {
    for (let k = 0; k < m; k++) {
      const r = Math.hypot(X[k] - q[0], Y[k] - q[1]);
      ARM[k] = Math.round((r / b - (ang(k, q[0], q[1]) - q[2])) / TAU);
      U[k] = 1;
      U[k] = tukeyW(perp(k, q), cut);
    }
  };
  let q = [start.x, start.y, start.ph];
  for (let round = 0; round < rounds; round++) {
    assign(q);
    const f = lm(q, resid, iters);
    const moved = Math.hypot(f.p[0] - q[0], f.p[1] - q[1]);
    q = f.p;
    if (moved < 1e-3) break;
  }
  assign(q);
  const e = resid(q), A = normalEq(jacobian(resid, q, e), e).A;
  let swu = 0;
  for (let k = 0; k < m; k++) swu += W[k] * U[k];
  const s2 = sumSq(e) / Math.max(swu - 3, 1);
  const inv = [0, 1].map(i => solve(A, A.map((_, j) => (i === j ? 1 : 0))));
  const cov = inv[0] && inv[1] ? [[inv[0][0] * s2, inv[1][0] * s2], [inv[0][1] * s2, inv[1][1] * s2]] : null;
  return { x: q[0], y: q[1], ph: q[2], cov };
}

// Combines the kept chunk fits into one spiral, robust to chunks that don't
// belong (RANSAC / MSAC over chunks):
//  - hypotheses: each kept chunk's own fit, and a joint fit of every pair of
//    kept chunks (all pairs up to 20 chunks, else 190 sampled pairs), started
//    from the first chunk's own fit; on subsampled pixels for speed;
//  - agreement of chunk k with a hypothesis: Δk = its loss under the
//    hypothesis (center and phase fixed) minus its loss under its own fit. A
//    genuine chunk whose own fit slid along its flat valley still fits the
//    true spiral almost as well, so Δk stays small; a spurious one doesn't;
//  - score: Σ nk · min(Δk, τ) (nk = its pixel count); lowest wins;
//  - refinement: joint fit over all inlier chunks (Δk < τ), recompute Δ,
//    repeat until the inlier set stops changing.
// opts: { cutoff, tau }. Returns null if no chunk is kept, else
// { x, y, phase, cov, inlier: Map comp → bool, delta: Map comp → Δ, nHyp, nIn, nKept }.
function combineChunks(img, comps, fits, p, opts) {
  const S = p.spacing, b = S / TAU, cut = Math.max(opts.cutoff * S, 1e-6), tau = opts.tau;
  const ks = fits.map((_, k) => k).filter(k => fits[k].kept);
  if (!ks.length) return null;
  const sub = ks.map(k => chunkData(img, comps[k], 300));
  const own = ks.map((k, i) => evalLoss(sub[i], fits[k].x, fits[k].y, fits[k].phase, S, cut));
  const nk = ks.map(k => comps[k].core.length);
  const deltas = h => sub.map((d, i) => Math.max(0, evalLoss(d, h.x, h.y, h.ph, S, cut) - own[i]));
  const score = D => D.reduce((s, v, i) => s + nk[i] * Math.min(v, tau), 0);

  const hyps = ks.map(k => ({ x: fits[k].x, y: fits[k].y, ph: fits[k].phase }));
  let pairs = [];
  for (let i = 0; i < ks.length; i++) for (let j = i + 1; j < ks.length; j++) pairs.push([i, j]);
  if (pairs.length > 190) { // deterministic sample
    const rnd = mulberry32(ks.length * 7919 + 17);
    for (let i = pairs.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [pairs[i], pairs[j]] = [pairs[j], pairs[i]]; }
    pairs = pairs.slice(0, 190);
  }
  for (const [i, j] of pairs) {
    const f = fits[ks[i]];
    hyps.push(fitJoint([sub[i], sub[j]], { x: f.x, y: f.y, ph: f.phase }, S, cut, 3, 8));
  }
  let best = null, bestD = null, bestS = Infinity;
  for (const h of hyps) {
    const D = deltas(h), s = score(D);
    if (s < bestS) { bestS = s; best = h; bestD = D; }
  }

  // Refine on the inliers (full pixels, capped for speed) until the set is stable.
  let inl = bestD.map(v => v < tau), h = best;
  for (let it = 0; it < 6; it++) {
    const ds = ks.map((k, i) => (inl[i] ? chunkData(img, comps[k], 1500) : null)).filter(Boolean);
    if (!ds.length) break;
    h = fitJoint(ds, { x: h.x, y: h.y, ph: h.ph }, S, cut);
    const D = deltas(h), next = D.map(v => v < tau);
    bestD = D;
    if (next.every((v, i) => v === inl[i])) break;
    inl = next;
  }
  const inlier = new Map(), delta = new Map();
  ks.forEach((k, i) => { inlier.set(k, bestD[i] < tau); delta.set(k, bestD[i]); });
  return {
    x: h.x, y: h.y, phase: ((h.ph % TAU) + TAU) % TAU, cov: h.cov ?? null,
    inlier, delta, nHyp: hyps.length, nIn: [...inlier.values()].filter(Boolean).length, nKept: ks.length,
  };
}

// ---------- Cost landscape ----------

// For each candidate centre on a G×G grid covering the image: the fit's loss
// for this component if the center were there, with each pixel on its
// nearest arm and the phase solved (weighted circular mean, then once more
// with Tukey weights). opts: { robust, cutoff }. With robust, the value is the
// normalized Tukey loss (0..1); otherwise the RMS distance (px). Writes into
// out (Float32Array G*G), returns { min, max, at }.
function costMap(img, comp, p, G, out, opts) {
  let idx = comp.core.length >= 3 ? comp.core : comp.pix;
  const stride = Math.ceil(idx.length / 150); // the landscape barely changes with fewer pixels
  idx = idx.filter((_, i) => i % stride === 0);
  const m = idx.length;
  const X = new Float64Array(m), Y = new Float64Array(m), W = new Float64Array(m);
  let sw = 0;
  idx.forEach((j, k) => { const x = j % N; X[k] = x + 0.5; Y[k] = (j - x) / N + 0.5; W[k] = Math.min(1, Math.max(0, img[j])); sw += W[k]; });
  const S = p.spacing, b = S / TAU, cut = Math.max(opts.cutoff * S, 1e-6);
  const R = new Float64Array(m), Al = new Float64Array(m), E = new Float64Array(m);
  const errs = ph => {
    for (let k = 0; k < m; k++) {
      const r = R[k];
      let e = r - b * (Al[k] - ph);
      E[k] = (e - S * Math.round(e / S)) * r / Math.sqrt(r * r + b * b);
    }
  };
  let min = Infinity, max = -Infinity, at = null;
  for (let gy = 0; gy < G; gy++) {
    const cy = ((gy + 0.5) * N) / G;
    for (let gx = 0; gx < G; gx++) {
      const cx = ((gx + 0.5) * N) / G;
      let s = 0, c = 0;
      for (let k = 0; k < m; k++) {
        R[k] = Math.hypot(X[k] - cx, Y[k] - cy);
        Al[k] = Math.atan2(Y[k] - cy, X[k] - cx);
        const a = Al[k] - R[k] / b; s += W[k] * Math.sin(a); c += W[k] * Math.cos(a);
      }
      let ph = Math.atan2(s, c);
      errs(ph);
      if (opts.robust) { // re-solve the phase with Tukey weights
        s = 0; c = 0;
        for (let k = 0; k < m; k++) {
          const w = W[k] * tukeyW(E[k], cut), a = Al[k] - R[k] / b;
          s += w * Math.sin(a); c += w * Math.cos(a);
        }
        if (s !== 0 || c !== 0) { ph = Math.atan2(s, c); errs(ph); }
      }
      let acc = 0;
      for (let k = 0; k < m; k++) acc += W[k] * (opts.robust ? lossNorm(E[k], cut) : E[k] * E[k]);
      const v = opts.robust ? acc / sw : Math.sqrt(acc / sw);
      out[gy * G + gx] = v;
      if (v < min) { min = v; at = { x: cx, y: cy }; }
      if (v > max) max = v;
    }
  }
  return { min, max, at };
}
