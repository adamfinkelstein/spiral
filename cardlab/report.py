import json
from dataclasses import asdict
from html import escape

import numpy as np

from . import figures
from .geometry import wrap
from .params import PARAM_NOTES, PRESETS
from .scoring import ideal_offset

# Writes card.html: one column of step figures with notes beside them, a
# summary over many runs, and the card parameters.

STYLE = """
body { margin: 0; padding: 16px 24px; background: #111; color: #ddd; font: 14px system-ui, sans-serif; }
img { display: block; border: 1px solid #333; width: 900px; }
.step { display: flex; gap: 24px; align-items: flex-start; margin-top: 22px; }
.step .panel { width: 380px; color: #aaa; font-size: 13px; line-height: 1.45; }
.panel h4 { margin: 0 0 6px; font-size: 14px; color: #ddd; }
.panel p { margin: 0 0 8px; }
.num { color: #ddd; }
h1 { font-size: 20px; } h2 { margin: 30px 0 0; font-size: 17px; border-bottom: 1px solid #333; padding-bottom: 4px; max-width: 1310px; }
table { border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; margin-top: 8px; }
th { color: #aaa; font-weight: 500; padding: 2px 8px; border-bottom: 1px solid #333; text-align: right; }
td { padding: 2px 8px; text-align: right; }
th:first-child, td:first-child, td.src, th.src { text-align: left; }
td.src { color: #888; }
.pick { position: relative; width: 900px; border: 1px solid #333; line-height: 0; }
.pick img { border: none; }
.spot { position: absolute; box-sizing: border-box; border: 2px solid transparent; cursor: pointer; }
.spot:hover { border-color: rgba(255,255,255,0.6); }
.spot.on { border-color: #fff; }
a { color: #8cf; } .note { color: #888; font-size: 12px; max-width: 1300px; }
.w { color: #fff } .c { color: #4cf } .y { color: #fd3 } .r { color: #f44 } .g { color: #3e6 } .m { color: #f6f }
"""


def step(image, title, *paragraphs):
    notes = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f'<div class="step"><img src="{image}"><div class="panel"><h4>{title}</h4>{notes}</div></div>'


def pct(value, digits=2):
    return f"{100 * value:+.{digits}f}%"


def value_range(values, fmt):
    low, high = min(values), max(values)
    return fmt(low) if fmt(low) == fmt(high) else f"{fmt(low)} – {fmt(high)}"


def summary_table(results):
    columns = [
        ("Hand mark", "mark_error", lambda v: f"{v:.0f} px"),
        ("Low-res center", "low_center_error", lambda v: f"{v:.2f} px"),
        ("Refit center", "refit_center_error", lambda v: f"{v:.2f} px"),
        ("Spacing (refit)", "refit_spacing_error", lambda v: pct(v)),
        ("Trace rms", "trace_rms", lambda v: f"{v:.2f} px"),
        ("Wrong groove", "wrong_groove", lambda v: f"{100 * v:.1f}%"),
        ("Not cut", "not_cut", lambda v: f"{100 * v:.1f}%"),
        ("Sound corr.", "sound_correlation", lambda v: f"{v:.3f}"),
    ]
    head = "<tr><th>Preset (seeds)</th>" + "".join(f"<th>{name}</th>" for name, _, _ in columns) + "</tr>"
    rows = []
    failed = [r for r in results if "failed" in r]
    results = [r for r in results if "failed" not in r]
    for preset in PRESETS:
        runs = [r for r in results if r["preset_key"] == preset]
        if not runs:
            continue
        seeds = ", ".join(str(r["seed"]) for r in runs)
        cells = "".join(f"<td>{value_range([r[key] for r in runs], fmt)}</td>" for _, key, fmt in columns)
        rows.append(f"<tr><td>{escape(PRESETS[preset].label)} ({seeds})</td>{cells}</tr>")
    note = "".join(f"<p class='note'>Failed: {escape(r['preset_key'])} seed {r['seed']}, {escape(r['failed'])}.</p>" for r in failed)
    return f"<table>{head}{''.join(rows)}</table>{note}"


def params_table(params):
    rows = []
    for key, (name, unit, source) in PARAM_NOTES.items():
        value = getattr(params, key)
        shown = "–".join(str(v) for v in value) if isinstance(value, tuple) else str(value)
        rows.append(f"<tr><td>{name}</td><td>{shown} {unit}</td><td class='src'>{source}</td></tr>")
    return "<table><tr><th>Parameter</th><th>Value</th><th class='src'>Source</th></tr>" + "".join(rows) + "</table>"


def detail_spots(run, size):
    # the spots of step e: position in the low-res image (fractions, for the
    # clickable boxes in step a), and a description
    spiral, scale, theta = run.refit, run.low.scale, run.strip.theta
    trace_x, trace_y = figures.spiral_points(run.strip.spiral, theta, run.trace)
    spots = []
    for column in figures.detail_columns(run):
        x, y = figures.detail_spot(run, column)
        left, top = figures.detail_box(run, (x, y), size)
        inside = (trace_x >= left) & (trace_x < left + size) & (trace_y >= top) & (trace_y < top + size)
        spots.append({
            "column": column, "x": float(x), "y": float(y),
            "left": left / scale / run.low.image.shape[1], "top": top / scale / run.low.image.shape[0],
            "size": size / scale / run.low.image.shape[0],
            "turn": float((theta[column] - theta[0]) / figures.TAU + 1),
            "radius": float(np.hypot(x - spiral.x, y - spiral.y)),
            "wrong": int(np.sum(inside & run.score.wrong_groove)),
        })
    return spots


def make_figures(run, folder, detail_size=256):
    spots = detail_spots(run, detail_size)
    steps = {
        "a_input": lambda p: figures.low_res_input(run, p, detail_size, [(s["x"], s["y"]) for s in spots]),
        "b_fft": lambda p: figures.spectrum(run, p),
        "c_profile": lambda p: figures.radial_profile(run, p),
        "d_coherence": lambda p: figures.coherence_map(run, p),
        "f_explain": figures.offsets_explainer,
        "f_offsets": lambda p: figures.offsets_mod_spacing(run, p, run.strip, run.model),
        "f_truth": lambda p: figures.offsets_vs_truth(run, p),
        "g_strip": lambda p: figures.strip_image(run, p),
        "h_trace": lambda p: figures.trace_offset(run, p),
        "i_turns": lambda p: figures.errors_per_turn(run, p),
        "j_sound": lambda p: figures.sound(run, p),
    }
    for k, spot in enumerate(spots):
        steps[f"e_detail_{k:02d}"] = lambda p, spot=spot: figures.detail(run, p, detail_size, (spot["x"], spot["y"]))
    for name, draw in steps.items():
        draw(folder / f"{name}.png")
    for k, spot in enumerate(spots):
        spot["image"] = f"e_detail_{k:02d}"
    return spots


def picker_step(image, spots, selected, title, *paragraphs):
    # step a with a clickable box over each detail spot
    boxes = "".join(
        f'<div class="spot{" on" if k == selected else ""}" data-k="{k}" title="spot {k + 1}" style="left:{100 * s["left"]:.3f}%;'
        f'top:{100 * s["top"]:.3f}%;width:{100 * s["size"]:.3f}%;height:{100 * s["size"]:.3f}%"></div>'
        for k, s in enumerate(spots))
    notes = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f'<div class="step"><div class="pick"><img src="{image}">{boxes}</div><div class="panel"><h4>{title}</h4>{notes}</div></div>'


def spot_script(spots, image_folder, selected):
    data = [{"src": f"{image_folder}/{s['image']}.png", "turn": round(s["turn"], 1), "radius": round(s["radius"]),
             "wrong": s["wrong"]} for s in spots]
    return f"""<script>
const spots = {json.dumps(data)};
function showSpot(k) {{
  const s = spots[k];
  document.getElementById('detail').src = s.src;
  document.getElementById('detailInfo').textContent = `Spot ${{k + 1}} of ${{spots.length}}: turn ${{s.turn}}, radius ${{s.radius}} px` +
    (s.wrong ? `; ${{s.wrong}} trace columns here on the wrong groove.` : '; no wrong-groove columns here.');
  document.querySelectorAll('.spot').forEach(e => e.classList.toggle('on', +e.dataset.k === k));
}}
document.querySelectorAll('.spot').forEach(e => e.addEventListener('click', () => showSpot(+e.dataset.k)));
showSpot({selected});
</script>"""


def write_report(path, run, summary, results, image_folder, spots):
    img = lambda name: f"{image_folder}/{name}.png"
    s = summary
    card, low = run.card, run.low
    middle = len(run.strip.theta) // 2
    selected = int(np.argmin([abs(spot["column"] - middle) for spot in spots]))
    wrong_spots = sum(1 for spot in spots if spot["wrong"])
    moved = float(np.hypot(run.refit.x - low.spiral.x, run.refit.y - low.spiral.y))
    ideal = ideal_offset(card, run.strip)
    refit_error = float(np.sqrt(np.mean(wrap(run.model - ideal, card.spacing) ** 2)))
    drift = float(np.sqrt(np.mean(wrap(card.nearest_groove(*figures.spiral_points(run.strip.spiral, run.strip.theta))[0] - ideal, card.spacing) ** 2)))
    body = f"""
<h1>Spiral: an idealized card, whole pipeline</h1>
<p class="note">Built by <code>python build_card.py</code> (cardlab/, Python) and committed as static images.
Showcase: preset <b>{escape(card.params.label)}</b>, seed {card.seed}. <a href="index.html">← Experiments</a> ·
<a href="procedure.html#part3">Procedure</a> · the earlier in-browser version: <a href="card_js.html">card_js.html</a></p>

<h2>Summary over runs</h2>
{summary_table(results)}
<p class="note">Errors against the simulated card's truth, full-resolution px. Ranges over the seeds listed.</p>

<h2>1. Low resolution (1024², ×{low.scale:.2f}): spacing, center, phase</h2>
{picker_step(img("a_input"), spots, selected, "a. Input: masked to the hand-marked annulus",
      "The full-res height map averaged over each low-res pixel (cv2.INTER_AREA), times a soft mask from the hand-marked circles (dashed), minus its mean, unit rms. An idealized card: flat, grain only.",
      "<span class='w'>White +</span> hand mark, <span class='c'>cyan</span> low-res fit, <span class='y'>yellow</span> refit, <span class='r'>red +</span> truth. Red boxes: the {len(spots)} detail spots of step e (spread evenly along the groove{', some where the trace is on the wrong groove' if wrong_spots else ''}); <b>click one</b> to show it in step e.",
      f"<span class='num'>Hand mark {s['mark_error']:.1f} px from the true center.</span>")}
{step(img("b_fft"), "b. FFT of a × 1/√r about the mark (central half of log |FFT|)",
      "Weighting by 1/√r keeps the outer turns from dominating. The rings sit at radius N/spacing. Dashed: the search window, 0.5–1.5 × the radius expected from the nominal spacing (the device spec): from halfway to zero frequency to halfway to the second harmonic; <span class='c'>cyan</span>: the peak.")}
{step(img("c_profile"), "c. Radial profile → spacing",
      "Mean log |FFT| per radius; the spacing is the peak inside the window (grey: 0.5–1.5 × the expected radius, so only the fundamental fits for any spacing within ~0.67–1.33 × the nominal), refined below a bin by a parabola after removing the local slope; a peak on the window's edge → no reliable spacing, and the card fails. Profile smoothed by 1.5 bins.",
      "White dashed: nominal; <span class='r'>red</span>: true; <span class='c'>cyan</span>: measured.",
      f"<span class='num'>Measured {low.fft_spacing:.3f} px ({pct(s['fft_spacing_error'])} vs. true {card.spacing:.3f}).</span>")}
{step(img("d_coherence"), "d. Center, spacing and phase: the spiral coherence map",
      "Z(c) = −Σ v·e<sup>−i(|p−c|/b − angle(p−c))</sup> scores how well a spiral centered at c (spacing from c) lines up with the grooves. As a function of c it is a correlation of the image with a spiral-shaped kernel, so one FFT gives it at every pixel (~0.5 s); no search window, and the hand mark isn't needed.",
      "Around the true center: a bright spot with fainter rings half a spacing apart. If the card is stretched (even 1%) the spot splits into lobes and the brightest pixel is off center, but the map stays symmetric under a 180° turn about the center. So the center is the map's center of point symmetry: |Z| minus its mean, times a Gaussian window (σ 10 spacings) about the brightest pixel, convolved with itself on a crop; the maximum is at twice the center. The phase is the angle of Z there.",
      f"<span class='num'>Shown: |Z| around the answer. Answer {s['low_center_error']:.2f} px from the true center (hand mark {s['mark_error']:.1f} px); coherence {s['coherence']:.2f}.</span>")}

<h2>2. Full resolution: unrolled strip, refit, groove trace</h2>
<div class="step"><img id="detail" src="{image_folder}/{spots[selected]['image']}.png"><div class="panel"><h4>e. Detail at full resolution (256 px)</h4>
<p><span class='r'>Red</span>: trace (<span class='m'>magenta</span>: wrong groove); <span class='g'>green</span>: true centerline. Darker = deeper: the depth follows the sound.</p>
<p>Click a red box in step a to choose the spot.</p><p class="num" id="detailInfo"></p></div></div>
{step(img("f_explain"), "How to read step f (a cartoon)",
      "Top: a toy card with 4 turns. The strip follows the spiral from the low-res stage (<span class='c'>cyan</span>, dashed), which is a little off: here its center by 0.45 spacing and its spacing by 4%. Each column is a radial line ±1 spacing about it (grey bars). Where the line meets the groove (<span class='g'>green</span>), the distance from the cyan spiral, outward positive, is the column's offset (<span class='m'>magenta</span>).",
      "Middle: the offsets along the strip, unrolled. A center error gives one wave per turn, a spacing error a slow rise. Every turn of the groove shows up, one spacing apart, because each column crosses several.",
      "Bottom: what step f plots. A column can't tell which turn it sees, only where the nearest groove sits, so the offsets are taken modulo the spacing, in −S/2…+S/2; when a curve passes ±S/2 the next turn is nearer and it wraps around. The refit (<span class='y'>yellow</span> in f) fits exactly this kind of curve, modulo S.")}
{step(img("f_offsets"), "f1. Strip offsets and the geometry refit",
      f"Columns every {run.strip.step:g} px along the low-res spiral; each is a radial line sampled at ±1 spacing (scipy map_coordinates), detrended and demodulated: Z = Σ v·e<sup>−2πid/S</sup> gives the groove's offset (mod S) and a confidence |Z|.",
      "Relative to the strip's spiral a center error is a one-turn wave (its cos and sin amplitudes are the x and y errors), a spacing error a slope, a phase error an offset. The refit (<span class='y'>yellow</span>) fits exactly that modulo S: a grid over spacing and center, then scipy least_squares with a robust loss, and moves the spiral by what it reads off. <span class='r'>Red</span>: the true geometry; <span class='g'>green</span>: true grooves, which drift a few px from turn to turn; grey dots: measured (smoothed 24 px). The wave and slope are the low-res errors that the refit removes; f2 shows what is left. (A second pass along the refitted spiral would flatten these curves too, but it doesn't improve the center, which the drift limits, so it isn't used.)",
      f"<span class='num'>{s['columns']:,} columns, {s['turns']:.1f} turns. Wave read off: center moved {moved:.2f} px; the low-res center was {s['low_center_error']:.2f} px from the truth, the refitted one is {s['refit_center_error']:.2f} px; spacing {pct(s['refit_spacing_error'], 3)}; spiral vs. grooves {s['refit_vs_grooves']:.2f} px rms.</span>")}
{step(img("f_truth"), "f2. The same, relative to the true spiral",
      "Everything minus the true geometry (<span class='r'>red</span>, now the zero line); possible only on a simulated card. <span class='y'>Yellow</span>: what is left of the refit's error, a small one-turn wave (center) and slope (spacing); below, alone at ±1 px. <span class='g'>Green</span>: the groove's own drift from a perfect spiral, a few px from turn to turn; white: measured.",
      f"<span class='num'>Refit error {refit_error:.2f} px rms (center {s['refit_center_error']:.2f} px, spacing {pct(s['refit_spacing_error'], 3)}); drift {drift:.2f} px rms.</span>")}
{step(img("g_strip"), "g. Unrolled strip around the spot",
      "Rows across the groove (1 px, outward up), each column's mean removed. <span class='y'>Yellow</span>: refitted spiral (±S faint); <span class='r'>red</span>: trace; <span class='g'>green</span>: true groove.")}
{step(img("h_trace"), "h. The trace: offset from the refitted spiral",
      "Z smoothed along the groove (σ 48 px); the trace takes the groove nearest a reference = refitted spiral + slowly varying residual (σ 300 px, within ±S/2), so noise and gaps can't move it to another turn.",
      f"<span class='num'>Trace rms {s['trace_rms']:.2f} px; wrong groove {100 * s['wrong_groove']:.2f}%.</span>")}
{step(img("i_turns"), "i. Trace error per turn",
      "Bars: rms distance to the nearest true groove centerline (dotted: S/4). Red: share of the turn on the wrong groove.")}

<h2>3. Sound readout (hill-and-dale)</h2>
{step(img("j_sound"), "j. Depth at the groove bottom",
      "The land at ±S/2 minus the traced bottom (each ±3 px), relative to its own 300-px average, minus 1; a gap (nothing cut) reads −1.",
      f"<span class='num'>Correlation with the true sound {s['sound_correlation']:.3f}; error rms {s['sound_error']:.3f} (true rms {s['sound_rms']:.3f}); not cut {100 * s['not_cut']:.1f}%.</span>")}

<h2>Card parameters ({escape(card.params.label)})</h2>
{params_table(card.params)}
{spot_script(spots, image_folder, selected)}
"""
    path.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Spiral: idealized card</title><style>{STYLE}</style></head><body>{body}</body></html>")
