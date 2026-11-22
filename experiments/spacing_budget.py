import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.lowres import LowResSettings, find_center, low_res_stage
from cardlab.model import make_card, render
from cardlab.params import PRESETS
from cardlab.readout import read_sound
from cardlab.scoring import center_error, correlation, rms, score_trace, spacing_error
from cardlab.strip import StripSettings, build_strip, lock_trace, refit_geometry

# Offline experiment (Nov 2026): the spacing error budget. How wrong can the
# low-res spacing be before the rest of the card pipeline breaks? The FFT
# spacing is replaced by the true spacing x (1 + error); the center search
# (coherence map + symmetry center), the strip, the refit (which searches
# +-2.5 % of the spacing it is given), the trace and the sound readout then
# run as usual. Results in spacing_budget_results.md.

ERRORS = (-0.10, -0.05, -0.03, -0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.10)
CARDS = [(preset, seed) for preset in ("typical", "hard") for seed in (1, 2, 3)]


def run_with_spacing(card, image, low, error):
    spacing = card.spacing / low.scale * (1 + error)  # low-res px
    spiral, _, _ = find_center(low.image, card.mark, low.scale, spacing, LowResSettings())
    strip = build_strip(image, spiral, card.mark, StripSettings())
    refit, model = refit_geometry(strip, StripSettings())
    trace = lock_trace(strip, model, StripSettings())
    score = score_trace(card, strip, trace)
    sound = read_sound(image, strip, trace)
    return {
        "low_center_error": center_error(card, spiral),
        "refit_center_error": center_error(card, refit),
        "refit_spacing_error": spacing_error(card, refit),
        "trace_rms": rms(score.distance),
        "wrong_groove": float(np.mean(score.wrong_groove)),
        "sound_correlation": correlation(sound, score.true_sound),
    }


def main():
    out = Path(sys.argv[1])
    rows = []
    for preset, seed in CARDS:
        card = make_card(PRESETS[preset], seed)
        image = render(card)
        low = low_res_stage(image, card.mark, card.params.spacing)
        for error in ERRORS:
            rows.append({"preset": preset, "seed": seed, "error": error} | run_with_spacing(card, image, low, error))
            out.write_text(json.dumps(rows))
        print(preset, seed, flush=True)
    print("| spacing error | preset | low-res center px | refit center px | refit spacing % | trace rms px | wrong groove | sound corr |")
    print("|---|---|---|---|---|---|---|---|")
    for error in ERRORS:
        for preset in ("typical", "hard"):
            sel = [r for r in rows if r["error"] == error and r["preset"] == preset]
            cell = lambda key, fmt: " – ".join(fmt.format(f(r[key] for r in sel)) for f in (min, max))
            print(f"| {100 * error:+.1f}% | {preset} | {cell('low_center_error', '{:.2f}')} | {cell('refit_center_error', '{:.2f}')} | "
                  f"{cell('refit_spacing_error', '{:+.3%}').replace('%', '')} | {cell('trace_rms', '{:.2f}')} | "
                  f"{cell('wrong_groove', '{:.1%}')} | {cell('sound_correlation', '{:.3f}')} |")


if __name__ == "__main__":
    main()
