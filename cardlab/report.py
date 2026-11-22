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
.w { color: #fff } .c { color: #4cf } .y { color: #fd3 } .o { color: #f93 } .g { color: #3e6 } .p { color: #a8f0b4 } .m { color: #f0f } .v { color: #b8f } .k { color: #aaa }

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
        "f_rectangle": lambda p: figures.rectangle_turns(run, p),
        "f_wedges": lambda p: figures.wedges_on_card(run, p),
        "f_explain": figures.offsets_explainer,
        "f_offsets": lambda p: figures.offsets_mod_spacing(run, p),
        "f_truth": lambda p: figures.offsets_vs_truth(run, p),
        "g_rectangle": lambda p: figures.rectangle_image(run, p),
        "h_trace": lambda p: figures.trace_offset(run, p),
        "h_rows": lambda p: figures.turns_rows(run, p),
        "h_row_errors": lambda p: figures.turns_rows(run, p, y_range=2, errors=True),
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
    wrong_note = " — none on this card" if s["wrong_groove"] == 0 else ""
    ideal = ideal_offset(card, run.strip)
    refit_error = float(np.sqrt(np.mean(wrap(run.model - ideal, card.spacing) ** 2)))
    drift = float(np.sqrt(np.mean(wrap(card.nearest_groove(*figures.spiral_points(run.strip.spiral, run.strip.theta))[0] - ideal, card.spacing) ** 2)))
    body = f"""
<h1>Spiral: an idealized card, whole pipeline</h1>
<p class="note">Built by <code>python build_card.py</code> (cardlab/, Python) and committed as static images.
Showcase: preset <b>{escape(card.params.label)}</b>, seed {card.seed}. <a href="index.html">← Experiments</a> ·
<a href="procedure.html#part3">Procedure</a> · the earlier in-browser version: <a href="card_js.html">card_js.html</a></p>

<p class="note key"><b>Colors, in every figure:</b> <span class='w'>white</span> input (hand mark, nominal spacing) ·
<span class='c'>cyan</span> low-res estimate · <span class='y'>yellow</span> refit (estimated geometry) ·
<span class='o'>orange</span> trace and read-out sound · <span class='g'>green</span> true groove and true sound ·
<span class='p'>pale green</span> true geometry (center, spacing, ideal spiral) · <span class='m'>magenta</span> wrong groove ·
<span class='k'>grey</span> raw measurements (the wedges) · <span class='v'>violet</span> annotations (detail-spot boxes, cartoon labels, the rectangle's rows and wedge edges)</p>

<h2>Summary over runs</h2>
{summary_table(results)}
<p class="note">Errors against the simulated card's truth, full-resolution px. Ranges over the seeds listed.</p>

<h2>1. Low resolution (1024², ×{low.scale:.2f}): spacing, center, phase</h2>
{picker_step(img("a_input"), spots, selected, "a. Input: masked to the hand-marked annulus",
      "The full-res height map averaged over each low-res pixel (cv2.INTER_AREA), times a soft mask from the hand-marked circles (dashed), minus its mean, unit rms. An idealized card: flat, grain only.",
      f"<span class='w'>White +</span> hand mark, <span class='c'>cyan</span> low-res fit, <span class='y'>yellow</span> refit, <span class='p'>pale green +</span> true center. <span class='v'>Violet boxes</span>: the {len(spots)} detail spots of step e (spread evenly along the groove{', some where the trace is on the wrong groove' if wrong_spots else ''}); <b>click one</b> to show it in step e.",
      f"<span class='num'>Hand mark {s['mark_error']:.1f} px from the true center.</span>")}
{step(img("b_fft"), "b. FFT of a × 1/√r about the mark (central half of log |FFT|)",
      "Weighting by 1/√r keeps the outer turns from dominating. The rings sit at radius N/spacing. Dashed: the search window, 0.5–1.5 × the radius expected from the nominal spacing (the device spec): from halfway to zero frequency to halfway to the second harmonic; <span class='c'>cyan</span>: the peak.")}
{step(img("c_profile"), "c. Radial profile → spacing",
      "Mean log |FFT| per radius; the spacing is the peak inside the window (grey: 0.5–1.5 × the expected radius, so only the fundamental fits for any spacing within ~0.67–1.33 × the nominal), refined below a bin by a parabola after removing the local slope; a peak on the window's edge, or one less than twice its background (less than ln 2 above the trough line in log magnitude), → no reliable spacing, and the card fails. Profile smoothed by 1 bin.",
      "White dashed: nominal; <span class='p'>pale green</span>: true; <span class='c'>cyan</span>: measured.",
      f"<span class='num'>Measured {low.fft_spacing:.3f} px ({pct(s['fft_spacing_error'])} vs. true {card.spacing:.3f}).</span>")}
{step(img("d_coherence"), "d. Center, spacing and phase: the spiral coherence map",
      "Z(c) = −Σ v·e<sup>−i(|p−c|/b − angle(p−c))</sup> scores how well a spiral centered at c (spacing from c) lines up with the grooves. As a function of c it is a correlation of the image with a spiral-shaped kernel, so one FFT gives it at every pixel (~0.5 s); no search window, and the hand mark isn't needed.",
      "Around the true center: a bright spot with fainter rings half a spacing apart. If the card is stretched (even 1%) the spot splits into lobes and the brightest pixel is off center, but the map stays symmetric under a 180° turn about the center. So the center is the map's center of point symmetry: |Z| minus its mean, times a Gaussian window (σ = 1/8 of the marked outer radius) about the brightest pixel, convolved with itself on a crop; the maximum, within 1.5σ of the peak, is at twice the center. The phase is the angle of Z there.",
      f"<span class='num'>Shown: |Z| around the answer. Answer {s['low_center_error']:.2f} px from the true center (hand mark {s['mark_error']:.1f} px); coherence {s['coherence']:.2f}.</span>")}

<h2>2. Full resolution: unrolled rectangle, wedges, refit, path</h2>
<div class="step"><img id="detail" src="{image_folder}/{spots[selected]['image']}.png"><div class="panel"><h4>e. Detail at full resolution (256 px)</h4>
<p><span class='o'>Orange</span>: the path; <span class='m'>magenta</span>: wrong groove{wrong_note}; <span class='g'>green</span>: true centerline. Darker = deeper: the depth follows the sound.</p>
<p>Click a violet box in step a to choose the spot.</p><p class="num" id="detailInfo"></p></div></div>
{step(img("f_rectangle"), "f0. The unrolled rectangle and its wedges",
      f"The annulus unrolled along the low-res spiral: columns at equal steps in angle θ ({run.wedges.unrolled.per_turn:,.0f} per turn), i.e. equal steps in time, since the card turns at a constant rate; about 1 px of groove apart on the outermost turn ({run.strip.step:.2f} px on the middle one), so no turn is undersampled and bilinear sampling needs no prefilter. Rows are the radial offset from the spiral (1 px, outward up). Rows −S/2..S/2 cover every annulus pixel exactly once: offset +S is the next turn at the same angle. The rectangle is never stored; each block of columns is sampled (bilinear, scipy map_coordinates) when it is needed. Shown: the same 4 wedges (36°) of 5 consecutive turns about the middle one, stacked outward up, so the stack tiles the card (stretched vertically). Turns are numbered from the spiral's center (r = turn × S), so this card's grooves are turns ~55–96; “card” counts from the first whole turn read.",
      "A wedge is 1/40 turn of columns (between the <span class='v'>violet</span> vertical lines). Per column, Z = Σ v·e<sup>−2πi d/S</sup> over exactly one period of rows, untapered: one period gives the groove's first Fourier component, while a taper or a wider window lets the neighbouring turns, which drift differently, pull it toward the spiral. Summed over the wedge, the angle of Z is the groove's offset (mod S), |Z| its strength.",
      "Pass 1: rows about the spiral (each turn's band, between the <span class='v'>violet</span> dotted lines) → the geometry refit (f1). Pass 2: each column's period of rows (<span class='v'>violet</span> solid) centered midway between the lands either side of the groove, at (groove + mean of the turns either side) / 2, so the window's ends fall in the land; centered on the groove itself was worse. <span class='o'>Orange</span>: the path; <span class='g'>green</span>: the true groove.",
      f"<span class='num'>{s['columns']:,} columns, {s['wedges']:,} wedges, {s['turns']:.1f} turns.</span>")}
{step(img("f_wedges"), "f0b. The same on the card",
      "A full-res crop at the default detail spot: <span class='v'>violet</span> pass 2's rows (one period about the midway line along each turn) and the wedge edges (radial; one turn's band sits beside the next, so its edges come in pairs); <span class='g'>green</span> (wide) the true groove; <span class='o'>orange</span> the path.")}
{step(img("f_explain"), "How to read step f (a cartoon)",
      "Top: a toy card with 4 turns. The rectangle follows the spiral from the low-res stage (<span class='c'>cyan</span>, dashed), which is a little off: here its center by 0.45 spacing and its spacing by 4%. Each column is a radial line ±S/2 about it (grey bars). Where the line meets the groove (<span class='g'>green</span>), the distance from the cyan spiral, outward positive, is the column's offset (<span class='v'>violet</span>).",
      "Middle: the offsets along the rectangle, unrolled. A center error gives one wave per turn, a spacing error a slow rise. Every turn of the groove shows up, one spacing apart.",
      "Bottom: what step f plots. A column can't tell which turn it sees, only where the nearest groove sits, so the offsets are taken modulo the spacing, in −S/2…+S/2; when a curve passes ±S/2 the next turn is nearer and it wraps around. The refit (<span class='y'>yellow</span> in f) fits exactly this kind of curve, modulo S.")}
{step(img("f_offsets"), "f1. Pass 1's wedges and the geometry refit",
      "Grey dots: pass 1's wedges (brighter = higher |Z|), as offsets from the low-res spiral, mod S. Relative to that spiral a center error is a one-turn wave (its cos and sin amplitudes are the x and y errors), a spacing error a slope, a phase error an offset. The refit (<span class='y'>yellow</span>) fits exactly that modulo S, on the wedges alone (no resampling): a grid over spacing and center, then scipy least_squares with a robust loss. <span class='p'>Pale green</span>: the true geometry; <span class='g'>green</span>: the true grooves, which drift a few px from turn to turn. The path then takes, in each wedge, the groove nearest the yellow curve (within ±S/2), so it can't jump to another turn.",
      f"<span class='num'>The low-res center was {s['low_center_error']:.2f} px from the truth, the refitted one is {s['refit_center_error']:.2f} px (moved {moved:.2f} px); spacing {pct(s['refit_spacing_error'], 3)}; spiral vs. grooves {s['refit_vs_grooves']:.2f} px rms.</span>")}
{step(img("f_truth"), "f2. The same, relative to the true spiral",
      "Everything minus the true geometry (<span class='p'>pale green</span>, now the zero line); possible only on a simulated card. <span class='y'>Yellow</span>: what is left of the refit's error, a small one-turn wave (center) and slope (spacing); below, alone at ±1 px. <span class='g'>Green</span>: the groove's own drift from a perfect spiral, a few px from turn to turn; grey: the wedges.",
      f"<span class='num'>Refit error {refit_error:.2f} px rms (center {s['refit_center_error']:.2f} px, spacing {pct(s['refit_spacing_error'], 3)}); drift {drift:.2f} px rms.</span>")}
{step(img("g_rectangle"), "g. The rectangle around the spot",
      "Rows across the groove (1 px, outward up, ±1.6 S), each column's mean removed. <span class='y'>Yellow</span>: refitted spiral (±S faint); <span class='v'>violet</span>: pass 2's rows; <span class='o'>orange</span>: the path; <span class='g'>green</span>: true groove.")}
{step(img("h_trace"), "h. The path: offset from the refitted spiral",
      "<span class='o'>Orange</span>: the path; <span class='g'>green</span>: the true groove, both relative to the refitted spiral. Between wedge centers the path interpolates the wedges' phasors |Z|e<sup>iφ</sup>, so weak wedges count little.",
      f"<span class='num'>Path rms {s['trace_rms']:.2f} px; wrong groove {100 * s['wrong_groove']:.2f}%.</span>")}
{step(img("h_rows"), "h2. One row per turn",
      "Each row is one turn, angle 0–360° left to right (inner turns at the top, ±12 px per row), offsets from the refitted spiral: <span class='g'>green</span> (wide) the true groove, grey dots the wedges, <span class='o'>orange</span> the path. The drift is smooth along each row and changes from row to row.")}
{step(img("h_row_errors"), "h3. Errors, one row per turn",
      "The same rows, each estimate minus the truth (<span class='g'>green</span>: zero), ±2 px per row: <span class='o'>orange</span> the path, grey dots the wedges.")}
{step(img("i_turns"), "i. Path error per turn",
      f"Per turn, rms distance from the <span class='o'>path</span> to the nearest true groove centerline (dotted: S/4). <span class='m'>Magenta</span>: share of the turn on the wrong groove{wrong_note}.")}

<h2>3. Sound readout (hill-and-dale)</h2>
{step(img("j_sound"), "j. Depth at the groove bottom",
      "<span class='o'>Orange</span>: the sound read out; <span class='g'>green</span>: the true sound. The land at ±S/2 minus the path's bottom (each ±3 px), relative to its own 300-px average (lengths along the groove are px at the middle turn; columns are equal steps in θ), minus 1; a gap (nothing cut) reads −1.",
      f"<span class='num'>Correlation with the true sound {s['sound_correlation']:.3f}; error rms {s['sound_error']:.3f} (true rms {s['sound_rms']:.3f}); not cut {100 * s['not_cut']:.1f}%.</span>")}

<h2>4. Alternatives tried for the full-res stage</h2>
<p class="note">On these simulated cards (5 seeds per preset; medians of the path rms, typical / loud / hard / clean, px). Details: procedure.html Part 3 and experiments/*_results.md.</p>
<table>
<tr><th>Method</th><th>Path rms</th><th>Hard: wrong groove</th><th>Time</th><th class='src'>Notes</th></tr>
<tr><td>Strip: columns every 3 px, rows ±S, detrended, cos² window; refit; trace locked to a smoothed reference</td><td>0.59 / 0.68 / 1.32 / 0.56</td><td>0.25%</td><td>0.54 s</td><td class='src'>the pipeline until Nov 2026 (cardlab/strip.py); the ±S window takes in the neighbouring turns and pulls the path ~10% toward the spiral (strip_window_results.md)</td></tr>
<tr><td>Strip with a one-period window (rows ±S/2, untapered)</td><td>0.27 / 0.32 / 1.21 / 0.16</td><td>0.15%</td><td>0.52 s</td><td class='src'>a two-period window: 1.6 px (strip_window_results.md)</td></tr>
<tr><td>Pixel sectors: every annulus pixel to its nearest arm and one of 40 sectors per turn; three full-frame passes</td><td>0.22 / 0.28 / 1.07 / 0.18</td><td>0.01%</td><td>3.3 s</td><td class='src'>tapered bands, mean removal, 20 or 80 sectors, low res: all worse (cell_coherence_results.md)</td></tr>
<tr><td>Unrolled rectangle, 1 pass</td><td>0.21 / 0.26 / 1.06 / 0.16</td><td>0.06%</td><td>0.20 s</td><td class='src'>1-px columns: the same (unrolled_wedges_results.md)</td></tr>
<tr><td>Unrolled rectangle, pass 2 rows centered on the groove</td><td>0.23 / 0.29 / 1.13 / 0.19</td><td>0.53%</td><td>0.37 s</td><td class='src'>re-centering on the groove brings the neighbours' edges in</td></tr>
<tr><td><b>Unrolled rectangle, pass 2 rows midway between the lands (now)</b></td><td>0.15 / 0.16 / 0.81 / 0.08</td><td>0.07%</td><td>0.37 s</td><td class='src'>per-wedge tilt (slope along the groove): 1.9 / 4.9 px on 2 cards, too noisy</td></tr>
</table>
<p class="note">The sound correlation is the same for all of them (within ~0.005): the readout and the grain limit it, not the path. All of them name a groove's turn by the nearest arm of the geometry model, so a groove drifting more than S/2 from it lands on the wrong turn in every method.</p>

<h2>Card parameters ({escape(card.params.label)})</h2>
{params_table(card.params)}
{spot_script(spots, image_folder, selected)}
"""
    path.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Spiral: idealized card</title><style>{STYLE}</style></head><body>{body}</body></html>")
