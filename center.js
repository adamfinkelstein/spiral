// center.html: the true spiral on the left; on the right, only the pixels in
// a few random chunks of the curve, as if only parts of it were recovered.
// Rendering (renderSpiral, edgeStep, N) lives in render.js.

const truthCanvas = document.getElementById('truth');
const chunkCanvas = document.getElementById('chunks');
const tctx = truthCanvas.getContext('2d');
const cctx = chunkCanvas.getContext('2d');

const center = { x: N / 2, y: N / 2 };
const HANDLE_R = 7;
const MAX_CHUNKS = 30; // must match the nChunks slider's max

const ids = ['spacing', 'rStart', 'rEnd', 'phase', 'aspect', 'lineWidth', 'softness', 'blur', 'isSpiral', 'smooth', 'nChunks', 'chunkLen', 'highlight', 'showCenter'];
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
    spiral: el.isSpiral.checked,
    nChunks: +el.nChunks.value,
    chunkLen: +el.chunkLen.value,
    highlight: el.highlight.checked,
    showCenter: el.showCenter.checked,
  };
}

// ---------- Random chunks ----------

// Small seeded PRNG (mulberry32), so a chunk set is reproducible from its seed.
function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Each chunk is one uniform number u in [0, 1): its position along the whole
// curve. Kept fixed while sliders move, so the same chunks persist; raising
// the chunk count adds chunks without moving the existing ones.
let seed = 1;
let chunkU = [];
function drawChunkPositions() {
  const rnd = mulberry32(seed);
  chunkU = Array.from({ length: MAX_CHUNKS }, rnd);
}
drawChunkPositions();

// Builds weight(n, ra, ang) for renderSpiral: 1 inside a chunk, 0 outside,
// with the same edge profile as the line edges at the chunk ends.
// Positions are arc lengths along the curve, in unscaled pixels.
//  Spiral: arc length from the center is approximated by s = r^2 / (2b)
//    (exact up to a small constant for r >> b; the same approximation is used
//    for the spiral's end caps). Chunks are placed so they lie entirely
//    between start and end radius when the spiral is long enough.
//  Rings: the rings in range are laid end to end (smallest first, each starting
//    at angle 0); a chunk falls on whichever ring its position lands on and
//    wraps around that ring if needed.
function makeChunkWeight(p) {
  const sig = edgeStep(p);
  const half = p.chunkLen / 2;
  const margin = half + 3 * Math.max(p.smooth ? p.softness : 0, 0.5);
  const r0 = Math.min(p.rStart, p.rEnd);
  const r1 = Math.max(p.rStart, p.rEnd);
  const us = chunkU.slice(0, p.nChunks);
  const inChunk = ds => sig(half + ds) * sig(half - ds); // ds: offset from chunk middle

  if (p.spiral) {
    const b = p.spacing / (2 * Math.PI);
    const s0 = (r0 * r0) / (2 * b), total = (r1 * r1 - r0 * r0) / (2 * b);
    const mids = us.map(u => (total > p.chunkLen ? s0 + half + u * (total - p.chunkLen) : s0 + total / 2));
    return (n, ra) => {
      const s = (ra * ra) / (2 * b);
      let w = 0;
      for (const m of mids) {
        const ds = s - m;
        if (ds > -margin && ds < margin) w = Math.max(w, inChunk(ds));
      }
      return w;
    };
  }

  const S = p.spacing;
  const nLo = Math.max(1, Math.ceil((r0 - 1e-6) / S)), nHi = Math.floor((r1 + 1e-6) / S);
  const byRing = new Map(); // ring index -> chunk middles (arc length from angle 0)
  let total = 0;
  for (let n = nLo; n <= nHi; n++) total += 2 * Math.PI * n * S;
  for (const u of us) {
    let g = u * total;
    for (let n = nLo; n <= nHi; n++) {
      const C = 2 * Math.PI * n * S;
      if (g < C || n === nHi) {
        if (!byRing.has(n)) byRing.set(n, []);
        byRing.get(n).push(g);
        break;
      }
      g -= C;
    }
  }
  return (n, ra, ang) => {
    const mids = byRing.get(n);
    if (!mids) return 0;
    const rn = n * S, C = 2 * Math.PI * rn;
    if (p.chunkLen >= C) return 1; // chunk covers the whole ring
    const s = rn * (ang < 0 ? ang + 2 * Math.PI : ang);
    let w = 0;
    for (const m of mids) {
      let ds = s - m;
      ds -= C * Math.round(ds / C); // wrap into [-C/2, C/2]
      if (ds > -margin && ds < margin) w = Math.max(w, inChunk(ds));
    }
    return w;
  };
}

// ---------- Drawing ----------

const full = new Float32Array(N * N);   // whole spiral
const part = new Float32Array(N * N);   // chunks only
const truthImage = tctx.createImageData(N, N);
const chunkImage = cctx.createImageData(N, N);
const HL = [255, 170, 40]; // chunk highlight colour on the left (amber)

function drawHandle(ctx) {
  ctx.beginPath();
  ctx.arc(center.x, center.y, HANDLE_R, 0, 2 * Math.PI);
  ctx.fillStyle = 'rgba(255,40,40,0.6)';
  ctx.fill();
  ctx.strokeStyle = '#f33';
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function drawCross(ctx) { // true center marker on the right (overlay only)
  const a = 9;
  ctx.strokeStyle = 'rgba(255,60,60,0.9)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(center.x - a, center.y); ctx.lineTo(center.x + a, center.y);
  ctx.moveTo(center.x, center.y - a); ctx.lineTo(center.x, center.y + a);
  ctx.stroke();
}

let pending = false;
function render() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => {
    pending = false;
    const p = params();
    for (const id of ['spacing', 'rStart', 'rEnd', 'phase', 'aspect', 'lineWidth', 'softness', 'blur', 'nChunks', 'chunkLen']) {
      el[id].nextElementSibling.textContent = el[id].value;
    }
    document.getElementById('centerOut').textContent = `(${center.x.toFixed(1)}, ${center.y.toFixed(1)})`;
    document.getElementById('seedOut').textContent = `set #${seed}`;
    el.softness.disabled = !p.smooth;
    el.phase.disabled = !p.spiral;

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

    // Right: only the recovered chunk pixels.
    toImageData(part, chunkImage);
    cctx.putImageData(chunkImage, 0, 0);
    if (p.showCenter) drawCross(cctx);
  });
}

// ---------- Interaction ----------

function canvasPos(e) {
  const r = truthCanvas.getBoundingClientRect();
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
