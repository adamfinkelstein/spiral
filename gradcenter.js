// Gradient-line center: a rough spiral center from image gradients, shared
// by spacing.html and center.html. No DOM; uses N and gaussianBlur from
// render.js. Load after render.js.

// Each pixel on a ring's edge has a gradient pointing across the ring, so the
// line through it along the gradient passes (nearly) through the center.
// On a spiral that line misses the center by about b = spacing/2π sideways:
// it passes through center + b·(−sin α, cos α), α the pixel's angle about the
// center (the same offset as the circle-fit correction on the center page);
// `shiftAbout` undoes that, for a given center, when the curve is a spiral.

// Small seeded PRNG (mulberry32).
function rng32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Blur along circles about c (tangentially), with a Gaussian of σ px (capped
// at r/4 near the center), sampled bilinearly along the circle (tangent plus
// a second-order inward term, so curved rings aren't shifted inward): averages
// noise along the rings without smearing across them.
function tangentialBlur(src, dst, c, sigma) {
  const K = Math.ceil(2 * sigma), wts = [];
  for (let k = -K; k <= K; k++) wts.push(Math.exp(-(k * k) / (2 * sigma * sigma)));
  const at = (x, y) => {
    x = Math.min(N - 1.001, Math.max(0, x - 0.5)); y = Math.min(N - 1.001, Math.max(0, y - 0.5));
    const i = Math.floor(x), j = Math.floor(y), fx = x - i, fy = y - j, o = j * N + i;
    return (src[o] * (1 - fx) + src[o + 1] * fx) * (1 - fy) + (src[o + N] * (1 - fx) + src[o + N + 1] * fx) * fy;
  };
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const px = x + 0.5, py = y + 0.5, dx = px - c.x, dy = py - c.y, r = Math.hypot(dx, dy);
    if (r < 1) { dst[y * N + x] = src[y * N + x]; continue; }
    const s = Math.min(1, r / (4 * sigma)), tx = (-dy / r) * s, ty = (dx / r) * s; // step shrinks near the center
    const cx = -dx / (2 * r * r), cy = -dy / (2 * r * r); // curvature: follow the circle, not the tangent line
    let acc = 0, w = 0;
    for (let k = -K; k <= K; k++) {
      const u2 = (k * s) * (k * s); // (arc length)²: the circle bends inward by u²/(2r)
      acc += wts[k + K] * at(px + k * tx + u2 * cx, py + k * ty + u2 * cy); w += wts[k + K];
    }
    dst[y * N + x] = acc / w;
  }
}

// Lines from gradients (Sobel on an already blurred image). Lines are
// undirected, so their orientation (mod 180°) falls in one of GL_BINS bins.
// Keep, in each bin, the `perBin` strongest pixels above a global floor (the
// `floorQ` quantile of all gradient magnitudes): every orientation gets an
// equal say, while orientations with no real edges (missing parts of the
// spiral) stay nearly empty instead of filling with noise. Weight =
// magnitude − floor. Returns arrays plus per-bin lists of line indices.
const GL_BINS = 64;
const glTmp = new Float32Array(N * N), glTmp2 = new Float32Array(N * N);
function gradientLines(src, perBin, floorQ) {
  const a = src;
  const mag = new Float32Array(N * N), GX = new Float32Array(N * N), GY = new Float32Array(N * N);
  let mMax = 0;
  for (let y = 1; y < N - 1; y++) for (let x = 1; x < N - 1; x++) {
    const i = y * N + x;
    const gx = (a[i - N + 1] + 2 * a[i + 1] + a[i + N + 1]) - (a[i - N - 1] + 2 * a[i - 1] + a[i + N - 1]);
    const gy = (a[i + N - 1] + 2 * a[i + N] + a[i + N + 1]) - (a[i - N - 1] + 2 * a[i - N] + a[i - N + 1]);
    GX[i] = gx; GY[i] = gy; mag[i] = Math.hypot(gx, gy);
    if (mag[i] > mMax) mMax = mag[i];
  }
  if (!(mMax > 0)) return null;
  // global floor: the floorQ quantile of the magnitudes (histogram)
  const H = 2048, hist = new Uint32Array(H);
  for (let i = 0; i < N * N; i++) hist[Math.min(H - 1, Math.floor((mag[i] / mMax) * H))]++;
  let acc = 0, tb = 0;
  while (tb < H - 1 && acc + hist[tb] < floorQ * N * N) acc += hist[tb++];
  const T = (tb / H) * mMax;
  const cand = Array.from({ length: GL_BINS }, () => []);
  for (let i = 0; i < N * N; i++) {
    if (mag[i] <= T) continue;
    let o = Math.atan2(GY[i], GX[i]);
    if (o < 0) o += Math.PI;
    cand[Math.min(GL_BINS - 1, Math.floor((o / Math.PI) * GL_BINS))].push(i);
  }
  const X = [], Y = [], W = [], UX = [], UY = [], BIN = [], bins = [];
  for (let bi = 0; bi < GL_BINS; bi++) {
    const c = cand[bi];
    if (c.length > perBin) { c.sort((p, q) => mag[q] - mag[p]); c.length = perBin; }
    const list = [];
    for (const i of c) {
      const x = i % N;
      list.push(X.length);
      X.push(x + 0.5); Y.push((i - x) / N + 0.5); W.push(mag[i] - T); UX.push(GX[i] / mag[i]); UY.push(GY[i] / mag[i]); BIN.push(bi);
    }
    bins.push(list);
  }
  return { X, Y, W, UX, UY, BIN, bins, n: X.length, T };
}

// Signed distance from point c to line k after the spiral correction about c.
// Spiral correction of a line through (px, py), about center c: shift by
// b·(sin α, −cos α) with (cos α, sin α) = (p − c)/|p − c| (no trig needed).
function shiftAbout(px, py, c, b) {
  const dx = px - c.x, dy = py - c.y, r = Math.hypot(dx, dy) || 1;
  return [px + (b * dy) / r, py - (b * dx) / r];
}

function lineDist(L, k, c, b) {
  let px = L.X[k], py = L.Y[k];
  if (b > 0) [px, py] = shiftAbout(px, py, c, b);
  return -L.UY[k] * (c.x - px) + L.UX[k] * (c.y - py);
}

// Weighted least-squares intersection of the lines with inl[k] set, each
// corrected about `ref`.
function intersectLines(L, inl, ref, b) {
  let a11 = 0, a12 = 0, a22 = 0, b1 = 0, b2 = 0, n = 0;
  for (let k = 0; k < L.n; k++) {
    if (!inl[k]) continue;
    let px = L.X[k], py = L.Y[k];
    if (b > 0) [px, py] = shiftAbout(px, py, ref, b);
    const nx = -L.UY[k], ny = L.UX[k], w = L.W[k], c = nx * px + ny * py;
    a11 += w * nx * nx; a12 += w * nx * ny; a22 += w * ny * ny; b1 += w * nx * c; b2 += w * ny * c; n++;
  }
  const det = a11 * a22 - a12 * a12;
  if (n < 3 || !(Math.abs(det) > 1e-12)) return null;
  return { x: (a22 * b1 - a12 * b2) / det, y: (a11 * b2 - a12 * b1) / det };
}

// RANSAC over pairs of lines (MSAC score): the first line is drawn with
// probability ∝ its weight; its partner from an orientation bin drawn with
// probability ∝ (lines in bin) · sin²(angle between the bins), then uniformly
// within that bin, so well-conditioned, near-perpendicular pairs are favoured
// (an intersection's error grows like 1/sin of the angle). A candidate center
// is the pair's intersection (spiral-corrected about it, twice); its cost is Σ w·min(d², ε²) over a fixed random subset of nSub lines
// (d = corrected distance, ε = 2 px). The best candidate is refined by the
// weighted intersection of its inliers (d < ε), recomputing inliers and
// corrections three times.
function ransacCenter(L, b, iters = 600, nSub = 1500, eps = 2) {
  const rnd = rng32(987654321);
  const sub = [];
  for (let i = 0; i < Math.min(nSub, L.n); i++) sub.push(Math.floor(rnd() * L.n));
  const cost = c => { let s = 0; for (const k of sub) { const d = lineDist(L, k, c, b); s += L.W[k] * Math.min(d * d, eps * eps); } return s; };
  const pair = (i, j, ref) => { // intersection of lines i, j (corrected about ref)
    let pix = L.X[i], piy = L.Y[i], pjx = L.X[j], pjy = L.Y[j];
    if (ref && b > 0) { [pix, piy] = shiftAbout(pix, piy, ref, b); [pjx, pjy] = shiftAbout(pjx, pjy, ref, b); }
    const den = L.UX[i] * L.UY[j] - L.UY[i] * L.UX[j];
    const s = ((pjx - pix) * L.UY[j] - (pjy - piy) * L.UX[j]) / den;
    return { x: pix + s * L.UX[i], y: piy + s * L.UY[i] };
  };
  const cumW = new Float64Array(L.n);
  for (let k = 0, s = 0; k < L.n; k++) cumW[k] = s += L.W[k];
  const drawCum = (cum, len) => { // index drawn ∝ increments of cum
    const t = rnd() * cum[len - 1];
    let lo = 0, hi = len - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (cum[m] < t) lo = m + 1; else hi = m; }
    return lo;
  };
  const sin2 = Array.from({ length: GL_BINS }, (_, d) => Math.sin((d * Math.PI) / GL_BINS) ** 2);
  const binCum = new Float64Array(GL_BINS);
  let best = null, bestC = Infinity, tries = 0;
  for (let it = 0; it < iters && tries < 20 * iters; tries++) {
    const i = drawCum(cumW, L.n), bi = L.BIN[i];
    for (let d = 0, s = 0; d < GL_BINS; d++) binCum[d] = s += L.bins[d].length * sin2[Math.abs(d - bi)];
    if (!(binCum[GL_BINS - 1] > 0)) continue;
    const list = L.bins[drawCum(binCum, GL_BINS)];
    const j = list[Math.floor(rnd() * list.length)];
    if (Math.abs(L.UX[i] * L.UY[j] - L.UY[i] * L.UX[j]) < 0.1) continue; // essentially parallel
    let c = pair(i, j, null);
    for (let r = 0; r < 2; r++) c = pair(i, j, c);
    if (!(c.x > -N / 2 && c.x < 1.5 * N && c.y > -N / 2 && c.y < 1.5 * N)) continue;
    it++;
    const v = cost(c);
    if (v < bestC) { bestC = v; best = c; }
  }
  if (!best) return null;
  let c = best, inl = new Uint8Array(L.n);
  for (let r = 0; r < 3; r++) {
    for (let k = 0; k < L.n; k++) inl[k] = Math.abs(lineDist(L, k, c, b)) < eps ? 1 : 0;
    c = intersectLines(L, inl, c, b) || c;
  }
  for (let k = 0; k < L.n; k++) inl[k] = Math.abs(lineDist(L, k, c, b)) < eps ? 1 : 0;
  let nIn = 0;
  for (const v of inl) nIn += v;
  return { c, inl, nIn };
}

// Center from gradient lines, with the tangential-blur loop: start from the
// plain (σ 1) image, then repeatedly blur along circles about the current
// center (σ = tang px), recompute the lines and the RANSAC center, until it
// moves < 1 px (at most 3 rounds; later rounds use 150 candidates and
// 1000 scoring lines, since they start close). With `start` (e.g. a
// hand-marked center) the first pass is already tangentially blurred about
// it, with the full RANSAC (it may be well off). Returns { c, L, inl, nIn,
// rounds, path, img }.
function gradientCenter(src, spacing, perBin, floorQ, spiral = true, tang = 0, eps = 2, start = null) { // eps: RANSAC inlier distance, px
  const b = spiral ? spacing / (2 * Math.PI) : 0;
  glTmp.set(src);
  gaussianBlur(glTmp, 1);
  const first = start && tang > 0;
  if (first) tangentialBlur(glTmp, glTmp2, start, tang);
  let L = gradientLines(first ? glTmp2 : glTmp, perBin, floorQ);
  if (!L) return null;
  let r = ransacCenter(L, b, 600, 1500, eps), rounds = first ? 1 : 0;
  if (!r) return null;
  const path = first ? [start, r.c] : [r.c];
  while (tang > 0 && rounds < 3) { // more rounds only chase noise
    tangentialBlur(glTmp, glTmp2, r.c, tang);
    const L2 = gradientLines(glTmp2, perBin, floorQ);
    const r2 = L2 && ransacCenter(L2, b, 150, 1000, eps); // already close: fewer candidates
    if (!r2) break;
    rounds++;
    const moved = Math.hypot(r2.c.x - r.c.x, r2.c.y - r.c.y);
    L = L2; r = r2; path.push(r.c);
    if (moved < 1) break; // ~1 px is plenty for weighting turns by 1/r
  }
  // the image the final lines came from: last round's tangential blur, or the σ 1 blur
  return { c: r.c, L, inl: r.inl, nIn: r.nIn, rounds, path, img: rounds > 0 ? glTmp2 : glTmp };
}

