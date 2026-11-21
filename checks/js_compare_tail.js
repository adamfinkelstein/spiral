// Appended to the concatenated JS card pipeline (see compare_with_js.sh):
// feeds the Python pipeline's inputs to the JS functions, stage by stage, and
// prints how far the results differ.
const fs = require('fs');
const D = process.env.DUMP.replace(/\/?$/, '/');
const meta = JSON.parse(fs.readFileSync(D + 'meta.json'));
const f32 = n => new Float32Array(fs.readFileSync(D + n + '.bin').buffer.slice(0));
const f64 = n => { const b = fs.readFileSync(D + n + '.bin'); return new Float64Array(b.buffer, b.byteOffset, b.length / 8); };
const F = meta.F, image = f32('image');
// a "card" that samples the same full-res image bilinearly (pixel centers at i + 0.5)
const card = { F, sample(x, y) {
  x -= 0.5; y -= 0.5; const i = Math.max(0, Math.min(F - 2, Math.floor(x))), j = Math.max(0, Math.min(F - 2, Math.floor(y))), fx = x - i, fy = y - j, o = j * F + i;
  return (image[o] * (1 - fx) + image[o + 1] * fx) * (1 - fy) + (image[o + F] * (1 - fx) + image[o + F + 1] * fx) * fy;
} };
const rms = a => Math.sqrt(a.reduce((s, v) => s + v * v, 0) / a.length);
const diff = (a, b) => Float64Array.from(a, (v, i) => v - b[i]);
const corr = (a, b) => { let sa = 0, sb = 0, sab = 0, ma = 0, mb = 0; for (let i = 0; i < a.length; i++) { ma += a[i]; mb += b[i]; } ma /= a.length; mb /= b.length; for (let i = 0; i < a.length; i++) { sa += (a[i] - ma) ** 2; sb += (b[i] - mb) ** 2; sab += (a[i] - ma) * (b[i] - mb); } return sab / Math.sqrt(sa * sb); };
// rms radial gap (mod S) between two spirals over a circle at the middle radius
const gap = (g, t) => { const rm = (meta.mark.rIn + meta.mark.rOut) / 2, S = 2 * Math.PI * t.b; let s = 0;
  for (let k = 0; k < 360; k++) { const a = k / 360 * 2 * Math.PI, x = t.x + rm * Math.cos(a), y = t.y + rm * Math.sin(a);
    const e = q => { const r = Math.hypot(x - q.x, y - q.y), al = Math.atan2(y - q.y, x - q.x); const v = r - q.b * (al - q.ph); return v - S * Math.round(v / S); };
    let d = e(g) - e(t); d -= S * Math.round(d / S); s += d * d; } return Math.sqrt(s / 360); };
const geo = (g, t) => `gap at mid radius ${gap(g, t).toFixed(3)} px, ` + `center Δ ${Math.hypot(g.x - t.x, g.y - t.y).toFixed(3)} px, spacing Δ ${(100 * (g.b / t.b - 1)).toFixed(4)}%, phase Δ ${(t.b * wrapPI(g.ph - t.ph)).toFixed(3)} px`;
(async () => {
  const out = [];
  // 1. low-res stage on the same downsampled image
  const L = lowResStage(f32('low_raw'), F, meta.nominal, meta.mark, {});
  out.push(`low-res FFT spacing: JS ${L.spacing.toFixed(4)} vs Python ${meta.fft_spacing.toFixed(4)} (Δ ${(100 * (L.spacing / meta.fft_spacing - 1)).toFixed(4)}%)`);
  out.push(`low-res fit: JS vs Python: ${geo(L.geom, meta.low)}; coherence JS ${L.coherence.toFixed(3)} vs Python ${meta.coherence.toFixed(3)}`);
  out.push(`  (vs truth: JS ${geo(L.geom, meta.true)} | Python ${geo(meta.low, meta.true)})`);
  // 2. strip demodulation, same spiral and columns
  const g = meta.low, TH = f64('theta'), S = 2 * Math.PI * g.b;
  const Z = await demodPass(card, g, TH, S, null, 1);
  const zr = f64('demod_re'), zi = f64('demod_im');
  const dz = Float64Array.from(zr, (v, i) => Math.hypot(Z.zr[i] - v, Z.zi[i] - zi[i])), zm = Float64Array.from(zr, (v, i) => Math.hypot(v, zi[i]));
  // columns whose rows leave the frame: the JS model was defined beyond it, the image isn't
  const inside = Float64Array.from(TH, (th) => { const r = g.b * th + S, a = th + g.ph; return Math.abs(g.x + r * Math.cos(a) - F / 2) < F / 2 - 2 && Math.abs(g.y + r * Math.sin(a) - F / 2) < F / 2 - 2 ? 1 : 0; });
  const keep = a => Float64Array.from(a).filter((_, i) => inside[i]);
  const nOut = inside.length - inside.reduce((a, v) => a + v, 0);
  out.push(`demodulation (${nOut} columns reaching past the frame excluded): |Z_js − Z_py| rms ${(rms(keep(dz)) / rms(zm)).toExponential(2)} of |Z| rms; max ${(keep(dz).reduce((a, v) => Math.max(a, v), 0) / rms(zm)).toExponential(2)}`);
  const Ujs = unwrapOffsets(Z, S, 0, null, false), opy = f64('offsets');
  out.push(`  offsets: rms Δ ${rms(keep(diff(Ujs.o, opy).map(v => v - S * Math.round(v / S)))).toExponential(2)} px`);
  // 3. refit from the same offsets
  const R = refitGeometry(g, TH, opy, f64('confidence'), S);
  out.push(`refit: JS vs Python: ${geo(R.geom, meta.refit)}; model rms Δ ${rms(diff(R.model, f64('model'))).toFixed(3)} px`);
  out.push(`  (vs truth: JS ${geo(R.geom, meta.true)} | Python ${geo(meta.refit, meta.true)})`);
  // 4. trace from the same demodulation and model
  const Zpy = { zr, zi }, U16 = unwrapOffsets(Zpy, S, 16, null, false);
  const T = lockTrack(U16.o, U16.amp, f64('model'), S, 100).o, tpy = f64('trace');
  out.push(`trace: rms Δ ${rms(diff(T, tpy)).toExponential(2)} px, max ${diff(T, tpy).reduce((a, v) => Math.max(a, Math.abs(v)), 0).toExponential(2)} px`);
  // 5. sound readout along the same trace
  const rd = await readoutPass(card, g, TH, tpy, S, null, 3, 1, 100), spy = f64('sound');
  out.push(`sound: rms Δ ${rms(diff(rd.est, spy)).toExponential(2)} (sound rms ${rms(spy).toFixed(3)}), correlation ${corr(rd.est, spy).toFixed(6)}`);
  console.log(out.join('\n'));
})();
