from dataclasses import asdict
from html import escape

from . import figures
from .params import PARAM_NOTES, PRESETS

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
    for preset in PRESETS:
        runs = [r for r in results if r["preset_key"] == preset]
        if not runs:
            continue
        seeds = ", ".join(str(r["seed"]) for r in runs)
        cells = "".join(f"<td>{value_range([r[key] for r in runs], fmt)}</td>" for _, key, fmt in columns)
        rows.append(f"<tr><td>{escape(PRESETS[preset].label)} ({seeds})</td>{cells}</tr>")
    return f"<table>{head}{''.join(rows)}</table>"


def params_table(params):
    rows = []
    for key, (name, unit, source) in PARAM_NOTES.items():
        value = getattr(params, key)
        shown = "–".join(str(v) for v in value) if isinstance(value, tuple) else str(value)
        rows.append(f"<tr><td>{name}</td><td>{shown} {unit}</td><td class='src'>{source}</td></tr>")
    return "<table><tr><th>Parameter</th><th>Value</th><th class='src'>Source</th></tr>" + "".join(rows) + "</table>"


def make_figures(run, folder, detail_size=256):
    steps = {
        "a_input": lambda p: figures.low_res_input(run, p, detail_size),
        "b_fft": lambda p: figures.spectrum(run, p),
        "c_profile": lambda p: figures.radial_profile(run, p),
        "d_coherence": lambda p: figures.coherence_grid(run, p),
        "f_detail": lambda p: figures.detail(run, p, detail_size),
        "g_offsets": lambda p: figures.offsets_mod_spacing(run, p),
        "h_strip": lambda p: figures.strip_image(run, p),
        "i_trace": lambda p: figures.trace_offset(run, p),
        "j_turns": lambda p: figures.errors_per_turn(run, p),
        "k_sound": lambda p: figures.sound(run, p),
    }
    paths = {}
    for name, draw in steps.items():
        path = folder / f"{name}.png"
        draw(path)
        paths[name] = path
    return paths


def write_report(path, run, summary, results, image_folder):
    img = lambda name: f"{image_folder}/{name}.png"
    s = summary
    card, low = run.card, run.low
    body = f"""
<h1>Spiral: an idealized card, whole pipeline</h1>
<p class="note">Built by <code>python build_card.py</code> (cardlab/, Python) and committed as static images.
Showcase: preset <b>{escape(card.params.label)}</b>, seed {card.seed}. <a href="index.html">← Experiments</a> ·
<a href="procedure.html#part3">Procedure</a> · the earlier in-browser version: <a href="card_js.html">card_js.html</a></p>

<h2>Summary over runs</h2>
{summary_table(results)}
<p class="note">Errors against the simulated card's truth, full-resolution px. Ranges over the seeds listed.</p>

<h2>1. Low resolution (1024², ×{low.scale:.2f}): spacing, center, phase</h2>
{step(img("a_input"), "a. Input: masked to the hand-marked annulus",
      "The full-res height map averaged over each low-res pixel (cv2.INTER_AREA), times a soft mask from the hand-marked circles (dashed), minus its mean, unit rms. An idealized card: flat, grain only.",
      "<span class='w'>White +</span> hand mark, <span class='c'>cyan</span> low-res fit, <span class='y'>yellow</span> refit, <span class='r'>red +</span> truth; red box: the detail spot.",
      f"<span class='num'>Hand mark {s['mark_error']:.1f} px from the true center.</span>")}
{step(img("b_fft"), "b. FFT of a × 1/√r about the mark (central half of log |FFT|)",
      "Weighting by 1/√r keeps the outer turns from dominating. The rings sit at radius N/spacing. Dashed: the search window (±10% of nominal); <span class='c'>cyan</span>: the peak.")}
{step(img("c_profile"), "c. Radial profile → spacing",
      "Mean log |FFT| per radius; the spacing is the peak inside the window (grey), refined parabolically; more than 3% from the nominal → nominal used.",
      "White dashed: nominal; <span class='r'>red</span>: true; <span class='c'>cyan</span>: measured.",
      f"<span class='num'>Measured {low.fft_spacing:.3f} px ({pct(s['fft_spacing_error'])} vs. true {card.spacing:.3f}).</span>")}
{step(img("d_coherence"), "d. Center search: spiral coherence",
      "|Z| = |Σ v·e<sup>−i(r/b − α)</sup>| for candidate centers on a grid about the hand mark (step 0.15 spacing, ±60 px), then Nelder–Mead (scipy) over center and spacing. The bright lobe is only ~0.4 spacing wide. arg Z is the phase.",
      f"<span class='num'>Answer {s['low_center_error']:.2f} px from the true center, spacing {pct(s['low_spacing_error'], 3)}; coherence {s['coherence']:.2f}.</span>")}
<p class="note">e. Gradient-based centers (lines + RANSAC; tilt about the hand mark) are not ported yet.</p>

<h2>2. Full resolution: unrolled strip, refit, groove trace</h2>
{step(img("f_detail"), "f. Detail at full resolution",
      "<span class='r'>Red</span>: trace (<span class='m'>magenta</span>: wrong groove); <span class='g'>green</span>: true centerline. Darker = deeper: the depth follows the sound.")}
{step(img("g_offsets"), "g. Strip offsets and the geometry refit",
      f"Columns every {run.strip.step:g} px along the low-res spiral; each is a radial line sampled at ±1 spacing (cv2.remap), detrended and demodulated: Z = Σ v·e<sup>−2πid/S</sup> gives the groove's offset (mod S) and a confidence |Z|.",
      "Relative to the strip's spiral a center error is a one-turn wave, a spacing error a slope, a phase error an offset. The refit (<span class='y'>yellow</span>) fits exactly that modulo S: a grid over spacing and center, then scipy least_squares with a robust loss. <span class='r'>Red</span>: the true geometry; <span class='g'>green</span>: true grooves; grey dots: measured (smoothed 24 px).",
      f"<span class='num'>{s['columns']:,} columns, {s['turns']:.1f} turns. Refit center {s['refit_center_error']:.2f} px, spacing {pct(s['refit_spacing_error'], 3)}; spiral vs. grooves {s['refit_vs_grooves']:.2f} px rms.</span>")}
{step(img("h_strip"), "h. Unrolled strip around the spot",
      "Rows across the groove (1 px, outward up), each column's mean removed. <span class='y'>Yellow</span>: refitted spiral (±S faint); <span class='r'>red</span>: trace; <span class='g'>green</span>: true groove.")}
{step(img("i_trace"), "i. The trace: offset from the refitted spiral",
      "Z smoothed along the groove (σ 48 px); the trace takes the groove nearest a reference = refitted spiral + slowly varying residual (σ 300 px, within ±S/2), so noise and gaps can't move it to another turn.",
      f"<span class='num'>Trace rms {s['trace_rms']:.2f} px; wrong groove {100 * s['wrong_groove']:.2f}%.</span>")}
{step(img("j_turns"), "j. Trace error per turn",
      "Bars: rms distance to the nearest true groove centerline (dotted: S/4). Red: share of the turn on the wrong groove.")}

<h2>3. Sound readout (hill-and-dale)</h2>
{step(img("k_sound"), "k. Depth at the groove bottom",
      "The land at ±S/2 minus the traced bottom (each ±3 px), relative to its own 300-px average, minus 1; a gap (nothing cut) reads −1.",
      f"<span class='num'>Correlation with the true sound {s['sound_correlation']:.3f}; error rms {s['sound_error']:.3f} (true rms {s['sound_rms']:.3f}); not cut {100 * s['not_cut']:.1f}%.</span>")}

<h2>Card parameters ({escape(card.params.label)})</h2>
{params_table(card.params)}
"""
    path.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Spiral: idealized card</title><style>{STYLE}</style></head><body>{body}</body></html>")
