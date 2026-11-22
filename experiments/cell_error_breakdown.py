import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cardlab.geometry import TAU, spiral_points, wrap
from cardlab.lowres import low_res_stage
from cardlab.model import make_card, render
from cardlab.params import PRESETS
from cardlab.strip import strip_columns
from cell_coherence import cell_strip, drift_path, refit_cells

# Offline experiment (Nov 2026): where does a cell's error come from? About a
# refitted spiral (full-res cells, 40 per turn), the true groove's offset t(theta)
# is known at columns every 3 px. Per cell (K sectors per turn):
#   noise     = measured cell offset - the true offset's mean over the cell
#   averaging = the true offset - its cell mean, at every column (what a cell
#               can't see: the groove moving within it)
# and two paths, interpolated from the cells as in cell_coherence.py:
#   ideal path    from the true cell means (no noise: averaging + interpolation)
#   measured path from the measured cells (everything)
# all rms in px, at low and full resolution, for K = 10 ... 160.

SECTORS = (10, 20, 40, 80, 160)
STEP = 3.0


def circular_mean(values, weights, spacing):
    phasor = np.bincount(weights[0], np.cos(TAU * values / spacing)) + 1j * np.bincount(weights[0], np.sin(TAU * values / spacing))
    return spacing * np.angle(phasor) / TAU


def breakdown(card, image, low, spiral, sectors, use_low):
    spacing = spiral.spacing
    theta = strip_columns(spiral, card.mark, STEP)
    true = card.nearest_groove(*spiral_points(spiral, theta))[0]  # true groove offset from the spiral, px
    cell_of_column = (np.floor(theta / TAU) * sectors + np.floor(np.mod(theta, TAU) / TAU * sectors)).astype(int)
    ids, index = np.unique(cell_of_column, return_inverse=True)
    true_mean = circular_mean(true, (index,), spacing)  # per cell, over its columns
    source, scale = (low.image, low.scale) if use_low else (image, 1.0)
    cells = cell_strip(source, spiral, scale, card.mark, sectors)
    measured_ids = (np.floor(cells.theta / TAU) * sectors + np.floor(np.mod(cells.theta, TAU) / TAU * sectors)).astype(int)
    common, in_true, in_measured = np.intersect1d(ids, measured_ids, return_indices=True)
    noise = wrap(cells.offsets[in_measured] - true_mean[in_true], spacing)
    averaging = wrap(true - true_mean[index], spacing)
    ideal = type(cells)(spiral, (ids // sectors) * TAU + (ids % sectors + 0.5) / sectors * TAU, 0.0, None, true_mean,
                        np.ones(len(ids)))
    ideal_path = wrap(drift_path(ideal, theta, 0) - true, spacing)
    measured_path = wrap(drift_path(cells, theta, 0) - true, spacing)
    rms = lambda v: float(np.sqrt(np.mean(np.square(v))))
    strength = np.abs(cells.demod[in_measured])
    weak = strength < 0.5 * np.median(strength)
    return {"noise": rms(noise), "noise_weak_cells": rms(noise[weak]) if weak.any() else float("nan"),
            "noise_strong_cells": rms(noise[~weak]),
            "weak_share": float(np.mean(weak)), "averaging": rms(averaging),
            "ideal_path": rms(ideal_path), "measured_path": rms(measured_path)}


def main():
    presets, seeds, out = sys.argv[1].split(","), sys.argv[2].split(","), Path(sys.argv[3])
    rows = []
    for preset in presets:
        for seed in seeds:
            card = make_card(PRESETS[preset], int(seed))
            image = render(card)
            low = low_res_stage(image, card.mark, card.params.spacing)
            spiral = refit_cells(cell_strip(image, low.spiral, 1.0, card.mark, 40))  # one shared geometry
            for use_low in (True, False):
                for sectors in SECTORS:
                    rows.append({"preset": preset, "seed": int(seed), "res": "low" if use_low else "full",
                                 "sectors": sectors} | breakdown(card, image, low, spiral, sectors, use_low))
            out.write_text(json.dumps(rows, indent=1))
            print(preset, seed, flush=True)
    print("| preset | res | sectors/turn | noise, all cells | strong cells | weak cells (share) | averaging | ideal path | measured path |")
    print("|---|---|---|---|---|---|---|---|---|")
    for preset in presets:
        for res in ("low", "full"):
            for sectors in SECTORS:
                sel = [r for r in rows if r["preset"] == preset and r["res"] == res and r["sectors"] == sectors]
                med = lambda key: np.nanmedian([r[key] for r in sel])
                print(f"| {preset} | {res} | {sectors} | {med('noise'):.2f} | {med('noise_strong_cells'):.2f} | "
                      f"{med('noise_weak_cells'):.2f} ({100 * med('weak_share'):.1f}%) | "
                      f"{med('averaging'):.2f} | {med('ideal_path'):.2f} | {med('measured_path'):.2f} |")


if __name__ == "__main__":
    main()
