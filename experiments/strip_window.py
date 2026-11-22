import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardlab.strip as strip_module
from cardlab.geometry import TAU, wrap
from cardlab.lowres import low_res_stage
from cardlab.model import make_card, render
from cardlab.params import PRESETS
from cardlab.readout import read_sound
from cardlab.scoring import correlation, rms, score_trace
from cardlab.strip import StripSettings, build_strip, lock_trace, refit_geometry
from cell_coherence import run_cells

# Offline experiment (Nov 2026): is the strip's slow path error (pulled ~9%
# toward its spiral, see k3b) a bias of its demodulation window? The strip
# demodulates each column over rows +-S: it removes the column's linear trend,
# then correlates with e^{-2 pi i d / S} under a cos^2 window. Variants:
#   cos2 +-S, trend    (the pipeline)
#   cos2 +-S, mean     only the mean removed
#   cos2 +-S, none     nothing removed
#   rect +-S/2, none   one period, untapered (as the cells)
#   rect +-S, none     two periods, untapered
# Per variant: path rms, wrong groove, sound correlation, and the path error's
# regression on the true drift (the true groove's offset from the refitted
# spiral): slope -0.09 = the path follows only 91% of the drift.

VARIANTS = {"cos2 +-S, trend": ("cos2", 1.0, "trend"), "cos2 +-S, mean": ("cos2", 1.0, "mean"),
            "cos2 +-S, none": ("cos2", 1.0, "none"), "rect +-S/2, none": ("rect", 0.5, "none"),
            "rect +-S, none": ("rect", 1.0, "none")}


def make_demodulate(shape, half_width, remove):
    def demodulate(samples, rows, spacing, _half_width=1.0):
        if remove == "trend":
            samples = samples - samples.mean(axis=0) - np.outer(rows, (rows @ samples) / (rows @ rows))
        elif remove == "mean":
            samples = samples - samples.mean(axis=0)
        inside = np.abs(rows) <= half_width * spacing
        if shape == "cos2":
            window = np.cos(np.pi * rows / (2 * half_width * spacing)) ** 2 * inside
        else:  # rect: end rows weighted so the window spans exactly 2 half_width S
            window = inside.astype(float)
            edge = np.abs(rows) == np.abs(rows[inside]).max()
            window[edge] = (half_width * spacing - np.abs(rows[edge]) + 0.5)
            window = np.clip(window, 0, 1)
        return (window * np.exp(-1j * TAU * rows / spacing)) @ samples
    return demodulate


def run_strip(card, image, low, variant):
    strip_module.demodulate = make_demodulate(*VARIANTS[variant])
    strip = build_strip(image, low.spiral, card.mark, StripSettings())
    _, model = refit_geometry(strip, StripSettings())
    trace = lock_trace(strip, model, StripSettings())
    s = score_trace(card, strip, trace)
    drift = wrap(s.true_offset - model, card.spacing)
    error = trace - s.true_offset
    return {"trace_rms": rms(s.distance), "wrong_groove": float(np.mean(s.wrong_groove)),
            "sound_correlation": correlation(read_sound(image, strip, trace), s.true_sound),
            "drift_corr": correlation(error, drift), "drift_slope": float(np.polyfit(drift, error, 1)[0])}


def main():
    presets, seeds, out = sys.argv[1].split(","), sys.argv[2].split(","), Path(sys.argv[3])
    rows = []
    for preset in presets:
        for seed in seeds:
            card = make_card(PRESETS[preset], int(seed))
            image = render(card)
            low = low_res_stage(image, card.mark, card.params.spacing)
            for variant in VARIANTS:
                rows.append({"preset": preset, "seed": int(seed), "method": variant} | run_strip(card, image, low, variant))
            cells = run_cells(card, image, low, False, 40, recenter=True)
            rows.append({"preset": preset, "seed": int(seed), "method": "sectors (re-centered)"} |
                        {k: cells[k] for k in ("trace_rms", "wrong_groove", "sound_correlation")})
            out.write_text(json.dumps(rows, indent=1))
            print(preset, seed, flush=True)
    print("| method | preset | path rms px | wrong groove | sound corr | error vs drift: corr, slope |")
    print("|---|---|---|---|---|---|")
    for method in dict.fromkeys(r["method"] for r in rows):
        for preset in presets:
            sel = [r for r in rows if r["method"] == method and r["preset"] == preset]
            med = lambda key: float(np.median([r[key] for r in sel])) if key in sel[0] else float("nan")
            print(f"| {method} | {preset} | {med('trace_rms'):.2f} | {100 * med('wrong_groove'):.2f}% | "
                  f"{med('sound_correlation'):.3f} | {med('drift_corr'):+.2f}, {med('drift_slope'):+.3f} |")


if __name__ == "__main__":
    main()
