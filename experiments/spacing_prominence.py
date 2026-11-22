import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.lowres import (LOW_SIZE, LowResSettings, annulus_mask, downsample, fft_spacing, normalize_in_mask,
                            peak_prominence)
from cardlab.model import make_card, render
from cardlab.params import PRESETS

# Offline experiment (Nov 2026): the FFT spacing peak's prominence (its height
# above the trough line through 0.5 and 1.5 x its radius, in log magnitude) on
# correct peaks and on wrong ones, to set a threshold below which the spacing
# counts as not found. Correct: the 20 standard cards and 6 cut at 25.9 / 32.2
# px, with the 29-px nominal. Wrong: typical and hard cards searched with a
# nominal 1.7 / 2 / 2.5 x too large (the window then misses the real peak), and
# frames of grain alone (no groove).

CACHE = Path("/tmp/spacing_window_cards")
NOMINAL = 29.0


def low_res(params, seed, tag):
    path = CACHE / f"{tag}.npz"
    card = make_card(params, seed)
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        np.savez(path, low=downsample(render(card)))
    return card, np.load(path)["low"]


def measure(card, low, nominal_full):
    scale = card.params.frame / LOW_SIZE
    nominal = nominal_full / scale
    mask = annulus_mask(LOW_SIZE, card.mark, scale, ramp=nominal)
    _, profile, window, peak, measured, ok = fft_spacing(normalize_in_mask(low, mask), mask, card.mark, scale, nominal,
                                                         LowResSettings())
    best = int(round(peak))
    return {"prominence": peak_prominence(profile, best), "edge": not ok,
            "error": float(measured * scale / card.spacing - 1)}


def main():
    out = Path(sys.argv[1])
    rows = []
    for preset in PRESETS:
        for seed in range(1, 6):
            card, low = low_res(PRESETS[preset], seed, f"{preset}_{seed}_None")
            rows.append({"kind": "correct", "case": f"{preset}:{seed}"} | measure(card, low, NOMINAL))
    for spacing in (25.9, 32.2):
        for seed in range(1, 4):
            card, low = low_res(replace(PRESETS["typical"], spacing=spacing), seed, f"typical_{seed}_{spacing}")
            rows.append({"kind": "correct", "case": f"typical:{seed} @{spacing}"} | measure(card, low, NOMINAL))
    for preset in ("typical", "hard"):
        for seed in range(1, 4):
            card, low = low_res(PRESETS[preset], seed, f"{preset}_{seed}_None")
            for factor in (1.7, 2.0, 2.5):
                rows.append({"kind": "nominal too large", "case": f"{preset}:{seed} x{factor}"} | measure(card, low, NOMINAL * factor))
    for seed in range(1, 4):  # grain alone: the card's grain spectrum, no groove
        card = make_card(PRESETS["typical"], seed)
        rng = np.random.default_rng(seed)
        grain = gaussian_filter(rng.standard_normal((LOW_SIZE, LOW_SIZE)), card.params.grain_size / (card.params.frame / LOW_SIZE))
        rows.append({"kind": "no groove", "case": f"grain {seed}"} | measure(card, grain, NOMINAL))
    out.write_text(json.dumps(rows, indent=1))
    for kind in ("correct", "nominal too large", "no groove"):
        sel = [r for r in rows if r["kind"] == kind]
        prom = np.array([r["prominence"] for r in sel])
        print(f"{kind:18s} n={len(sel):2d}  prominence min {prom.min():.3f}  median {np.median(prom):.3f}  max {prom.max():.3f}  "
              f"edge {sum(r['edge'] for r in sel)}  |error| > 3%: {sum(abs(r['error']) > 0.03 for r in sel)}")
    for r in rows:
        if r["kind"] != "correct":
            print(f"  {r['case']:22s} prominence {r['prominence']:.3f}  edge {r['edge']}  error {100 * r['error']:+.1f}%")


if __name__ == "__main__":
    main()
