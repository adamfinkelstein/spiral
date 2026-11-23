import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.lowres import low_res_stage
from cardlab.model import make_card, render
from cardlab.params import PRESETS
from cardlab.readout import read_sound
from cardlab.scoring import center_error, correlation, rms, score_trace, spacing_error
from cardlab.strip import Strip
from cardlab.geometry import wrap
from cardlab.wedges import Unrolled, WedgeSettings, drift_at, neighbours_mean, refit_wedges, wedges

# Offline experiment (Nov 2026, Adam's question): the geometry refit (center,
# spacing, phase from the one-turn wave and slope of pass 1's wedge offsets)
# is limited by the groove's drift, not by noise, so can pass 1 use coarser
# columns (every 2 or 4 px on the outer turn) and only pass 2 run at 1 px?
# Per pass-1 column step: refit center and spacing errors, path rms, wrong
# groove, sound correlation, seconds for pass 1 (+ refit) and for the whole
# full-res stage (excluding rendering, the low-res stage and the readout).

STEPS = (1.0, 2.0, 4.0, 8.0)


def run(card, image, low, step):
    settings = WedgeSettings()
    start = time.perf_counter()
    coarse = Unrolled(image, low.spiral, card.mark, step, settings.sectors)
    first = wedges(coarse, coarse.column_phasors(np.zeros(len(coarse.theta))))
    spiral, model = refit_wedges(first)
    pass1 = time.perf_counter() - start
    full = Unrolled(image, low.spiral, card.mark, settings.column_step, settings.sectors)
    theta, spacing = full.theta, full.spacing
    near = lambda reference, cells: reference + wrap(drift_at(cells, theta) - reference, spacing)
    path = near(model(theta), first)
    window = (path + neighbours_mean(theta, path)) / 2
    final = wedges(full, full.column_phasors(window))
    path = near(path, final)
    seconds = time.perf_counter() - start
    strip = Strip(low.spiral, theta, full.step, None, None, None)
    s = score_trace(card, strip, path)
    return {"center_error": center_error(card, spiral), "spacing_error": spacing_error(card, spiral),
            "trace_rms": rms(s.distance), "wrong_groove": float(np.mean(s.wrong_groove)),
            "sound_correlation": correlation(read_sound(image, strip, path), s.true_sound),
            "pass1_seconds": pass1, "seconds": seconds}


def main():
    presets, seeds, out = sys.argv[1].split(","), sys.argv[2].split(","), Path(sys.argv[3])
    rows = []
    for preset in presets:
        for seed in seeds:
            card = make_card(PRESETS[preset], int(seed))
            image = render(card)
            low = low_res_stage(image, card.mark, card.params.spacing)
            for step in STEPS:
                rows.append({"preset": preset, "seed": int(seed), "step": step} | run(card, image, low, step))
            out.write_text(json.dumps(rows, indent=1))
            print(preset, seed, flush=True)
    print("| pass 1 columns | preset | center px | spacing ppm | path rms px | wrong groove | sound corr | pass 1 s | total s |")
    print("|---|---|---|---|---|---|---|---|---|")
    for step in STEPS:
        for preset in presets:
            sel = [r for r in rows if r["step"] == step and r["preset"] == preset]
            med = lambda key: float(np.median([r[key] for r in sel]))
            print(f"| {step:g} px | {preset} | {med('center_error'):.3f} | "
                  f"{1e6 * float(np.median([abs(r['spacing_error']) for r in sel])):.0f} | {med('trace_rms'):.3f} | "
                  f"{100 * med('wrong_groove'):.2f}% | {med('sound_correlation'):.4f} | "
                  f"{med('pass1_seconds'):.2f} | {med('seconds'):.2f} |")


if __name__ == "__main__":
    main()
