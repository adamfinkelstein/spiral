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
h1 { font-size: 20px; } h2 .xref { font-size: 13px; font-weight: 400; margin-left: 12px; } h2 { margin: 30px 0 0; font-size: 17px; border-bottom: 1px solid #333; padding-bottom: 4px; max-width: 1310px; }
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
        ("Center, step 3", "low_center_error", lambda v: f"{v:.2f} px"),
        ("Center, step 4", "refit_center_error", lambda v: f"{v:.2f} px"),
        ("Spacing, step 4", "refit_spacing_error", lambda v: pct(v)),
        ("Path rms", "trace_rms", lambda v: f"{v:.2f} px"),
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
    # the spots of step 5a: position in the low-res image (fractions, for the
    # clickable boxes in step 0a), and a description
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
    run.pass1 = figures.pass1_compare(run)
    steps = {
        "a_input": lambda p: figures.low_res_input(run, p, detail_size, [(s["x"], s["y"]) for s in spots]),
        "b_fft": lambda p: figures.spectrum(run, p),
        "c_profile": lambda p: figures.radial_profile(run, p),
        "d_coherence": lambda p: figures.coherence_map(run, p),
        "d_explain": figures.coherence_explainer,  # procedure.html step 3 only
        "d_coordinate": figures.spiral_coordinate_plot,  # procedure.html step 3 only
        "d_coordinate_map": figures.spiral_coordinate_map,  # procedure.html step 3 only
        "d_lobes": lambda p: figures.stretch_lobes(run, p),  # procedure.html step 3 only
        "f_rectangle": lambda p: figures.rectangle_turns(run, p),
        "f_wedges": lambda p: figures.wedges_on_card(run, p),
        "f_explain": figures.offsets_explainer,
        "f_fit": lambda p: setattr(run, "fit_demo", figures.fit_residuals(run, p)),
        "f_check": lambda p: setattr(run, "check_demo", figures.check_on_damage(run, p)),
        "f_truth": lambda p: figures.offsets_vs_truth(run, p),
        "f_pass1": lambda p: setattr(run, "pass1_wedge_change", figures.pass1_before_after(run, run.pass1, p)),
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
    # step 0a with a clickable box over each detail spot
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


def pass1_step(image, run):
    b, a = run.pass1["before"], run.pass1["after"]
    change = run.pass1_wedge_change
    path_change = a["run"].path - b["run"].path
    return step(image, "4f. Every 4th column: before / after",
        f"Until Nov 2026 this step read every column, as step 5 does. But the fit only needs the wedges' offsets, and its error is set by the groove's drift (4e), not by how densely the wedges are sampled: a wedge's offset from 1/4 of its columns differs only by noise, which the least-squares fit over ~1500 wedges averages away. So this step reads every 4th column (every {a['step']:g} px of the outer turn; the same wedges and rows), and step 5 reads all of them.",
        "Top: each wedge's offset from every 4th column minus from every column (grey, brighter = higher |Z|). Middle: the fit's error against the true spiral (<span class='p'>pale green</span> = 0), before (<span class='y'>yellow</span>, wide and faint) and now (yellow, thin): they lie on top of each other. Bottom: the path, now minus before (<span class='o'>orange</span>). Note the scales: ±0.05 px top, ±0.01 px bottom.",
        f"<span class='num'>This card, before → now: columns {b['columns']:,} → {a['columns']:,}; wedges differ by {np.sqrt(np.mean(change ** 2)):.3f} px rms; corrected center {b['center']:.4f} → {a['center']:.4f} px, spacing {pct(b['spacing'], 4)} → {pct(a['spacing'], 4)}; path rms {b['path_rms']:.4f} → {a['path_rms']:.4f} px (paths differ by {np.sqrt(np.mean(path_change ** 2)):.4f} px rms); steps 4–5 {b['seconds']:.2f} → {a['seconds']:.2f} s. On all 20 cards: the table below.</span>")


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
    fd, cd = run.fit_demo, run.check_demo
    true_at = card.nearest_groove(*figures.spiral_points(run.strip.spiral, run.strip.theta))[0]
    wedge_noise = float(np.sqrt(np.mean(wrap(run.wedges.first.offsets - np.interp(run.wedges.first.theta, run.strip.theta, true_at), card.spacing) ** 2)))
    drift = float(np.sqrt(np.mean(wrap(card.nearest_groove(*figures.spiral_points(run.strip.spiral, run.strip.theta))[0] - ideal, card.spacing) ** 2)))
    body = f"""
<h1>Spiral: the procedure on a simulated card</h1>
<p class="note">Each step of the procedure run on an idealized, simulated card, with its result and how well it works over many cards.
Built by <code>python build_card.py</code> (cardlab/, Python) and committed as static images.
Showcase: preset <b>{escape(card.params.label)}</b>, seed {card.seed}. Alternatives tried for each step: <a href="considered.html#part3">Considered and dropped, Part 3</a>.</p>

<p class="note key"><b>Colors, in every figure:</b> <span class='w'>white</span> input (hand mark, nominal spacing) ·
<span class='c'>cyan</span> low-res estimate · <span class='y'>yellow</span> the corrected geometry (step 4) ·
<span class='o'>orange</span> path and read-out sound · <span class='g'>green</span> true groove and true sound ·
<span class='p'>pale green</span> true geometry (center, spacing, ideal spiral) · <span class='m'>magenta</span> wrong groove (in step 4, the sectors the check drops) ·
<span class='k'>grey</span> raw measurements (the wedges) · <span class='v'>violet</span> annotations (detail-spot boxes, cartoon labels, the rectangle's rows and wedge edges)</p>

<h2>Summary over runs</h2>
{summary_table(results)}
<p class="note">Errors against the simulated card's truth, full-resolution px. Ranges over the seeds listed. Step 3: the low-res spiral; step 4: the corrected one.</p>

<h2 id="step0">0. Input <a class="xref" href="procedure.html#step0">procedure →</a></h2>
{picker_step(img("a_input"), spots, selected, "0a. The low-res card, masked to the hand-marked annulus",
      f"The simulated card's height map ({card.params.label.lower().split(' (')[0]} preset; parameters at the end of the page), averaged down to 1024² (×{low.scale:.2f}), times a soft mask from the hand-marked circles (dashed), minus its mean, unit rms. An idealized card: flat, grain only.",
      f"<span class='w'>White +</span> hand mark, <span class='c'>cyan</span> step 3's center, <span class='y'>yellow</span> step 4's, <span class='p'>pale green +</span> true center. <span class='v'>Violet boxes</span>: the {len(spots)} detail spots of step 5a (spread evenly along the groove{', some where the path is on the wrong groove' if wrong_spots else ''}); <b>click one</b> to show it there.",
      f"<span class='num'>Hand mark {s['mark_error']:.1f} px from the true center.</span>")}

<h2 id="step1">1. FFT of the masked card <a class="xref" href="procedure.html#step1">procedure →</a></h2>
{step(img("b_fft"), "1a. FFT of the card × 1/√r about the mark (central half of log |FFT|)",
      "Weighting by 1/√r keeps the outer turns from dominating. The rings sit at radius N/spacing. Dashed: step 2's search window, 0.5–1.5 × the radius expected from the nominal spacing; <span class='c'>cyan</span>: the peak.")}

<h2 id="step2">2. Spacing: the peak of the radial profile <a class="xref" href="procedure.html#step2">procedure →</a></h2>
{step(img("c_profile"), "2a. Radial profile → spacing",
      "Mean log |FFT| per radius, smoothed by a Gaussian of σ = 1 bin; the spacing is the peak inside the window (grey: 0.5–1.5 × the expected radius), refined below a bin by a parabola after removing the local slope. A peak on the window's edge, or less than twice its background, fails the card.",
      "Radius in the FFT along the top, the groove spacing it stands for along the bottom. Shaded: the search region, 0.5–1.5 × the radius the nominal spacing predicts; white dashed: nominal. Inset (arrow: its place on the peak): the sub-bin fit, ±2.5 bins about the peak bin: the 5 bins used (dots) minus the trough line and the parabola (<span class='c'>cyan</span> dotted), whose vertex is the measured spacing (<span class='c'>cyan</span>), beside the true (<span class='p'>pale green</span>) and nominal (white dashed).",
      f"<span class='num'>Measured {low.fft_spacing:.3f} px ({pct(s['fft_spacing_error'])} vs. true {card.spacing:.3f}).</span>")}

<h2 id="step3">3. Center and spiral phase: the spiral coherence map <a class="xref" href="procedure.html#step3">procedure →</a></h2>
{step(img("d_coherence"), "3a. The spiral coherence map",
      "Z(c) = −Σ v·e<sup>−i(|p−c|/b − angle(p−c))</sup> scores how well a spiral centered at c lines up with the grooves; one FFT correlation gives it at every pixel. Around the true center: a bright spot with fainter rings half a spacing apart.",
      "The center is the map's center of point symmetry near its brightest pixel (robust to a slightly stretched scan, where the spot splits into lobes); the spiral phase is the angle of Z there.",
      f"<span class='num'>Shown: |Z| around the answer. Center {s['low_center_error']:.2f} px from the truth (hand mark {s['mark_error']:.1f} px); coherence {s['coherence']:.2f}.</span>")}

<h2 id="step4">4. Geometry correction: coarse wedges <a class="xref" href="procedure.html#step4">procedure →</a></h2>
{step(img("f_explain"), "4a. How to read the offsets (a cartoon)",
      "Top: a toy card with 6 turns. The rectangle follows the initial estimate from steps 1–3 (<span class='c'>cyan</span>, dashed), here off in all three ways: center by 0.2 spacing, spacing by 8%, spiral phase by 0.6 rad. Each column is a radial line ±S/2 about it (grey bars). Where the line meets the groove (<span class='g'>green</span>), the distance from the cyan spiral, outward positive, is the column's offset (<span class='v'>violet</span>).",
      "Second: the offsets along the rectangle, unrolled; every turn of the groove shows up, one spacing apart. Third: the bold curve's three parts (<span class='v'>violet</span>): the center error gives one wave per turn, the spacing error a slope, the spiral-phase error a constant. They add up to the bold curve; the fit (4c) fits exactly this.",
      "Bottom: what 4c plots. A column can't tell which turn it sees, only where the nearest groove sits, so the offsets are taken modulo the spacing, in −S/2…+S/2; when a curve passes ±S/2 the next turn is nearer and it wraps around.")}
{step(img("f_rectangle"), "4b. The unrolled rectangle and its wedges",
      f"The annulus unrolled along the low-res spiral: columns at equal steps in angle θ ({run.wedges.unrolled.per_turn:,.0f} per turn at full resolution), i.e. equal steps in time; rows are the radial offset from the spiral (1 px, outward up); rows −S/2..S/2 cover every annulus pixel exactly once. Sampled (bilinear) only when needed. Shown: the same 4 wedges (36°) of 5 consecutive turns about the middle one, stacked outward up, so the stack tiles the card (stretched vertically). Turns are numbered from the spiral's center (r = turn × S); “card” counts from the first whole turn read.",
      "A wedge is 1/40 turn of columns (between the <span class='v'>violet</span> vertical lines). Per column, z = Σ v·e<sup>−2πi d/S</sup> over exactly one period of rows; summed over the wedge, the angle of Z is the groove's offset (mod S), |Z| its strength. This step reads every 4th column on the rows about the spiral (<span class='v'>violet</span> dotted); step 5 reads every column on rows midway between the lands (<span class='v'>violet</span> solid). <span class='o'>Orange</span>: the path; <span class='g'>green</span>: the true groove.",
      f"<span class='num'>{s['columns']:,} columns ({run.pass1['after']['columns']:,} in this step), {s['wedges']:,} wedges, {s['turns']:.1f} turns.</span>")}
{step(img("f_fit"), "4c. The geometry fit: residuals before and after",
      f"The fit updates the spiral's globals (center, spacing, spiral phase) from the coarse wedges: grid search, then robust least squares on the residuals wrapped to ±S/2 (4a's model: a one-turn wave for the center, a slope for the spacing, a constant for the spiral phase). Step 3 is already so close on this card (center {s['low_center_error']:.2f} px off) that before and after would look alike, so this figure starts from a deliberately worse initial estimate: center {fd['start_center']:.1f} px off, spacing {pct(fd['start_spacing'])}, spiral phase 0.3 rad.",
      "Top, before: each wedge's offset from that estimate, mod S (grey, brighter = higher |Z|), with the fitted model (<span class='y'>yellow</span>; under it, <span class='p'>pale green</span>, the same curve for the true geometry) and the true grooves (<span class='g'>green</span>). Middle, after: offset minus model, wrapped, on the same scale: the wave and the slope are gone; what is left is the groove's own drift from turn to turn. Bottom: the consistency check, the residuals' median in each of 40 angular sectors (9°) over all turns; a sector outside the band (<span class='v'>violet</span>, median ± 3 MADs) would be dropped and the fit repeated. Here none is.",
      f"<span class='num'>From this start: residual {fd['before_rms']:.1f} → {fd['after_rms']:.1f} px rms; center {fd['start_center']:.1f} → {fd['center']:.2f} px from the truth, spacing {pct(fd['start_spacing'])} → {pct(fd['spacing'], 3)}. From step 3's estimate (the pipeline): center {s['low_center_error']:.2f} → {s['refit_center_error']:.2f} px (moved {moved:.2f} px); spacing {pct(s['refit_spacing_error'], 3)}; spiral vs. grooves {s['refit_vs_grooves']:.2f} px rms; {len(run.wedges.dropped)} of 40 sectors dropped.</span>")}
{step(img("f_check"), "4d. The consistency check on a damaged card",
      "The same card with a damaged patch: a 30° sector (60°–90°) whose grooves look clean but sit S/3 further out, as on a warped or lifted patch. Its wedges have high |Z|, so the plain fit follows them part way. Top: residuals after the plain fit; the patch's wedges (<span class='m'>magenta</span>) stand out at the same angle on every turn. Middle: the sector medians against the final model; the check drops the sectors outside the band (<span class='m'>magenta</span>; the first round drops the three inside the patch, the second the one it overlaps at 54–63°) and fits again. Bottom: the final fit: the rest is flat and the patch sits S/3 off, ignored.",
      f"<span class='num'>Center from the truth: plain fit {cd['plain']:.2f} px, with the check {cd['checked']:.2f} px ({cd['dropped']} sectors dropped); undamaged {s['refit_center_error']:.2f} px.</span>")}
{step(img("f_truth"), "4e. The same, relative to the true spiral",
      "Everything minus the true geometry (<span class='p'>pale green</span>, now the zero line); possible only on a simulated card. <span class='y'>Yellow</span>: what is left of the fit's error, a small one-turn wave (center) and slope (spacing); below, alone at ±1 px. Grey: the wedges; <span class='g'>green</span>: the groove's drift.",
      "The error is random, different on every card, and nothing in the data can remove it: a one-turn wave or slope that is really in the measured offsets can't be told from a center or spacing error. Two things put one there by chance, about equally: the wedges' measurement noise (the grain; each wedge's offset is off from the true groove at its angle by a fraction of a px) and the groove's drift (a few px from turn to turn, whose own one-turn wave over all turns is a few hundredths of a px). The robust loss weights the wedges by how far they sit from the model, so the error is not simply either part's least-squares fit. It is tiny next to one turn's rise in radius (S per turn): plotted as radius against θ it would not show at all, only after subtracting the true spiral as here. And step 5's path follows the groove itself, so it hardly matters downstream.",
      f"<span class='num'>Fit error {refit_error:.2f} px rms (center {s['refit_center_error']:.2f} px, spacing {pct(s['refit_spacing_error'], 3)}); wedges vs. the true groove {wedge_noise:.2f} px rms; drift {drift:.2f} px rms.</span>")}
{pass1_step(img("f_pass1"), run)}
<p class="note" style="margin-top:14px"><b>Every 4th column vs. others</b> (experiments/coarse_pass1_results.md). Medians over the 20 cards, typical / loud / hard / clean; time for steps 4–5 only.</p>
<table>
<tr><th>Step 4 columns</th><th>Corrected center, px</th><th>Path rms, px</th><th>Hard: wrong groove</th><th>Sound corr.</th><th>Step 4</th><th>Steps 4–5</th></tr>
<tr><td>every column (1 px, before Nov 2026)</td><td>0.126 / 0.130 / 0.197 / 0.129</td><td>0.146 / 0.165 / 0.787 / 0.070</td><td>0.08%</td><td>0.896 / 0.934 / 0.810 / 0.960</td><td>0.58 s</td><td>1.15 s</td></tr>
<tr><td>every 2nd (2 px)</td><td>0.126 / 0.130 / 0.197 / 0.129</td><td>0.146 / 0.165 / 0.793 / 0.070</td><td>0.08%</td><td>the same</td><td>0.32 s</td><td>0.89 s</td></tr>
<tr><td><b>every 4th (4 px, now)</b></td><td>0.126 / 0.130 / 0.197 / 0.129</td><td>0.146 / 0.165 / 0.796 / 0.070</td><td>0.10%</td><td>the same</td><td>0.18 s</td><td>0.76 s</td></tr>
<tr><td>every 8th (8 px)</td><td>0.126 / 0.130 / 0.196 / 0.129</td><td>0.146 / 0.165 / 0.814 / 0.070</td><td>0.12%</td><td>the same</td><td>0.12 s</td><td>0.70 s</td></tr>
</table>
<p class="note">Card by card, every 2nd or 4th column changes the corrected center by less than 0.001 px (every 8th: 0.008) and the path rms by at most 0.005 / 0.008 / 0.026 px, all on hard seed 1.</p>

<h2 id="step5">5. The groove's path at full resolution <a class="xref" href="procedure.html#step5">procedure →</a></h2>
<div class="step"><img id="detail" src="{image_folder}/{spots[selected]['image']}.png"><div class="panel"><h4>5a. Detail at full resolution (256 px)</h4>
<p><span class='o'>Orange</span>: the path; <span class='m'>magenta</span>: wrong groove{wrong_note}; <span class='g'>green</span>: true centerline. Darker = deeper: the depth follows the sound.</p>
<p>Click a violet box in 0a to choose the spot.</p><p class="num" id="detailInfo"></p></div></div>
{step(img("f_wedges"), "5b. The rows on the card",
      "A full-res crop at the default detail spot: <span class='v'>violet</span> this step's rows (one period about the midway line between the lands, along each turn) and the wedge edges (radial; one turn's band sits beside the next, so its edges come in pairs); <span class='g'>green</span> (wide) the true groove; <span class='o'>orange</span> the path.",
      "Every column; each column's rows centered midway between the lands either side of the groove, at (groove + mean of the turns either side) / 2, so the window's ends fall in the land. Each column keeps the groove nearest the corrected spiral (within ±S/2), so it can't slip to another turn.")}
{step(img("g_rectangle"), "5c. The rectangle around the spot",
      "Rows across the groove (1 px, outward up, ±1.6 S), each column's mean removed. <span class='y'>Yellow</span>: corrected spiral (±S faint); <span class='v'>violet</span>: this step's rows; <span class='o'>orange</span>: the path; <span class='g'>green</span>: true groove.")}
{step(img("h_trace"), "5d. The path: offset from the corrected spiral",
      "<span class='o'>Orange</span>: the path; <span class='g'>green</span>: the true groove, both relative to the corrected spiral. Between wedge centers the path interpolates the wedges' phasors |Z|e<sup>iφ</sup>, so weak wedges count little.",
      f"<span class='num'>Path rms {s['trace_rms']:.2f} px; wrong groove {100 * s['wrong_groove']:.2f}%.</span>")}
{step(img("h_rows"), "5e. One row per turn",
      "Each row is one turn, angle 0–360° left to right (inner turns at the top, ±12 px per row), offsets from the corrected spiral: <span class='g'>green</span> (wide) the true groove, grey dots the wedges, <span class='o'>orange</span> the path. The drift is smooth along each row and changes from row to row.")}
{step(img("h_row_errors"), "5f. Errors, one row per turn",
      "The same rows, each estimate minus the truth (<span class='g'>green</span>: zero), ±2 px per row: <span class='o'>orange</span> the path, grey dots the wedges.")}
{step(img("i_turns"), "5g. Path error per turn",
      f"Per turn, rms distance from the <span class='o'>path</span> to the nearest true groove centerline (dotted: S/4). <span class='m'>Magenta</span>: share of the turn on the wrong groove{wrong_note}.")}

<h2 id="step6">6. Sound: the groove's depth along the path <a class="xref" href="procedure.html#step6">procedure →</a></h2>
{step(img("j_sound"), "6a. Depth at the groove bottom",
      "<span class='o'>Orange</span>: the sound read out; <span class='g'>green</span>: the true sound. The land at ±S/2 minus the path's bottom (each ±3 px), relative to its own 300-px average (lengths along the groove are px at the middle turn; columns are equal steps in θ), minus 1; a gap (nothing cut) reads −1.",
      "The readout is a little louder than the truth: averaging a rounded bottom over ±3 px reads it a fixed amount shallower (gain ~1.05), and the land samples pick up the neighbouring grooves' edges (added noise).",
      f"<span class='num'>Correlation with the true sound {s['sound_correlation']:.3f}; error rms {s['sound_error']:.3f} (true rms {s['sound_rms']:.3f}); not cut {100 * s['not_cut']:.1f}%.</span>")}
<p class="note">Other methods tried for each step, with their results on these cards: <a href="considered.html#part3">considered.html, Part 3</a>.</p>

<h2>Card parameters ({escape(card.params.label)})</h2>
{params_table(card.params)}
{spot_script(spots, image_folder, selected)}
"""
    path.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Spiral: the procedure on a simulated card</title><style>{STYLE}</style><script src='nav.js' defer></script></head><body>{body}</body></html>")
