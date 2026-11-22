import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.lowres import LOW_SIZE, LowResSettings, annulus_mask, downsample, fft_spacing, normalize_in_mask
from cardlab.model import make_card, render
from cardlab.params import PRESETS

# Offline experiment (Nov 2026): the low-res FFT spacing on simulated cards,
# for aligning cardlab with the spacing page: search window (±10/20/50% of the
# nominal), profile smoothing (0/1/1.5 bins) and the fallback to the nominal
# when the peak is more than 3% off (cardlab's rule until this experiment).
# Result (results in spacing_window_results.md): window size makes no
# difference, smoothing 1.5 is a little better than 1 and 0 the worst, and
# the 3% fallback wrecks off-nominal cards; cardlab now uses ±50%, 1.5 bins,
# no fallback (only for a peak on the window's edge). Later the window was set
# in frequency (0.5-1.5 x the expected peak radius, halfway to zero frequency
# and to the second harmonic) instead of in spacing; the variants below are
# that version (the earlier table is in the results file). Besides the 20 standard
# cards, cards cut at 25.9 and 32.2 px (the range over Tomaz's five cards)
# are searched with the 29-px nominal, as a device spec would give.

CACHE = Path("/tmp/spacing_window_cards")
NOMINAL = 29.0
CARDS = [(preset, seed, None) for preset in PRESETS for seed in range(1, 6)] + \
        [("typical", seed, spacing) for spacing in (25.9, 32.2) for seed in range(1, 4)]
FALLBACK = 0.03  # the old rule: farther than this from the nominal -> use the nominal
VARIANTS = {  # name: (settings, apply the old 3% fallback); the window is now in frequency
    "±50% of the expected radius, smooth 1.5, no fallback (now)": (LowResSettings(), False),
    "±33% of the expected radius, smooth 1.5, no fallback": (LowResSettings(spacing_window=0.33), False),
    "±50% of the expected radius, smooth 1.5, 3% fallback": (LowResSettings(), True),
}


def card_and_low(preset, seed, spacing):
    params = PRESETS[preset] if spacing is None else replace(PRESETS[preset], spacing=spacing)
    card = make_card(params, seed)
    path = CACHE / f"{preset}_{seed}_{spacing}.npz"
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        np.savez(path, low=downsample(render(card)))
    return card, np.load(path)["low"]


def main():
    out = Path(sys.argv[1])
    rows = []
    for preset, seed, spacing in CARDS:
        card, low = card_and_low(preset, seed, spacing)
        scale = card.params.frame / LOW_SIZE
        nominal = NOMINAL / scale
        mask = annulus_mask(LOW_SIZE, card.mark, scale, ramp=nominal)
        image = normalize_in_mask(low, mask)
        for name, (settings, fallback) in VARIANTS.items():
            *_, measured, ok = fft_spacing(image, mask, card.mark, scale, nominal, settings)
            ok = ok and not (fallback and abs(measured / nominal - 1) > FALLBACK)
            used = measured if ok else nominal
            rows.append({"card": f"{preset}:{seed}" + (f" @{spacing}" if spacing else ""), "variant": name,
                         "error": float(used * scale / card.spacing - 1), "fallback": not ok})
        print(preset, seed, spacing, flush=True)
    out.write_text(json.dumps(rows))
    groups = {"standard cards": lambda c: "@" not in c, "cut at 25.9 px": lambda c: "@25.9" in c,
              "cut at 32.2 px": lambda c: "@32.2" in c}
    print("| variant | " + " | ".join(groups) + " |")
    print("|---|" + "---|" * len(groups))
    for name in VARIANTS:
        cells = []
        for test in groups.values():
            sel = [r for r in rows if r["variant"] == name and test(r["card"])]
            errors = np.abs([r["error"] for r in sel]) * 100
            cells.append(f"{np.median(errors):.3f} / {errors.max():.2f}% ({sum(r['fallback'] for r in sel)} fallbacks)")
        print(f"| {name} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
