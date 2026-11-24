import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardlab.strip as strip_module
from cardlab.wedges import drift_at
from cardlab.geometry import TAU, spiral_points, wrap
from cardlab.lowres import low_res_stage
from cardlab.model import make_card, render
from cardlab.params import PRESETS
from cardlab.readout import read_sound
from cardlab.scoring import correlation, rms, score_trace
from cardlab.strip import (Strip, StripSettings, build_strip, lock_trace, refit_basis, refit_geometry, refit_start, sample_at,
                           strip_columns)
from cell_coherence import run_cells
from strip_window import make_demodulate

# NOTE (Nov 2026): written for the old spiral convention r = pitch * theta,
# theta = angle - phase + 2 pi n. cardlab now uses r = pitch * (theta - phase),
# theta = the card's angle unwrapped; this script was not updated (results
# files record what it gave then).
# Offline experiment (Nov 2026, Adam's idea): the whole annulus unrolled into a
# rectangle along the ONE spiral from the low-res coherence map: columns at
# equal arc length along it, rows = radial offset d from it. Rows -S/2..S/2
# cover every annulus pixel once (offset +S is the next turn at the same
# angle). The rectangle is never built: `Unrolled.pull(columns, shift)`
# computes the points of just those columns (rows +-S/2 about d = shift per
# column) and samples them (bilinear). Wedges = blocks of columns, 40 per
# turn; per wedge Z = sum w v e^{-2 pi i d / S} (one period, untapered), its
# angle the groove's offset from the spiral (mod S). No image refit: the
# low-res spiral's own error is part of each wedge's offset. Pass 1: rows
# about the spiral; pass 2 (optional): rows shifted (run_unrolled).
# Wedge offsets are interpolated as phasors |Z| e^{i phase} (cells.drift_at).
# The strip's geometry refit, run on pass 1's wedge offsets (no resampling),
# gives an unwrapped model; the path = model + the wedges' offsets from it
# within +-S/2, as lock_trace. Variants: columns every 1 or 3 px; 1 pass, or a
# second with the rows centered on the groove or midway between its lands
# (see run_unrolled). Without the model (path within +-S/2 of the low-res spiral) and with it
# as the reference of pass 2 too: hard 1 2.2 px, 2% wrong groove. Tried and dropped (2 cards): a
# per-wedge tilt (slope from the phase step between neighbouring columns,
# path = each wedge's line): 1.9 / 4.9 px typical / hard, the slope too noisy.

SECTORS = 40
READ_STEP = 3.0


class Unrolled:
    def __init__(self, image, spiral, mark, column_step):
        self.image, self.spiral, self.spacing = image, spiral, spiral.spacing
        self.theta = strip_columns(spiral, mark, column_step)
        reach = int(np.ceil(self.spacing / 2))
        self.rows = np.arange(-reach, reach + 1, dtype=float)
        # one period exactly: rows within S/2 weigh 1, the end rows the fraction inside
        self.weights = np.clip(self.spacing / 2 - np.abs(self.rows) + 0.5, 0, 1)
        self.wedge = np.floor(self.theta / TAU * SECTORS).astype(int)

    def pull(self, columns, shift):
        # the sub-rectangle: rows about d = shift (px, per column), sampled now
        d = self.rows[:, None] + shift[None, :]
        x, y = spiral_points(self.spiral, self.theta[None, columns], d)
        return sample_at(self.image, x, y), d

    def column_phasors(self, shift, chunk=20000):
        # per column: sum over its rows of w v e^{-2 pi i d / S}
        out = np.empty(len(self.theta), complex)
        for start in range(0, len(self.theta), chunk):
            columns = slice(start, start + chunk)
            values, d = self.pull(columns, shift[columns])
            out[columns] = (self.weights[:, None] * values * np.exp(-1j * TAU * d / self.spacing)).sum(axis=0)
        return out


def wedges(unrolled, z_columns):
    # per wedge: center theta, Z, offset from the spiral (mod S), confidence |Z| / median
    ids, index, count = np.unique(unrolled.wedge, return_inverse=True, return_counts=True)
    z = np.bincount(index, z_columns.real) + 1j * np.bincount(index, z_columns.imag)
    theta = np.bincount(index, unrolled.theta) / count
    keep = count > 0.5 * np.median(count)  # drop the partial wedges at both ends
    z, theta = z[keep], theta[keep]
    offsets = -unrolled.spacing * np.angle(-z) / TAU  # groove = depression, as strip.offsets_from
    return Strip(unrolled.spiral, theta, 0.0, z, offsets, np.abs(z) / np.median(np.abs(z)))


def geometry_model(cells):
    # the strip's refit on the wedge offsets (no resampling): the low-res
    # spiral's error as a + beta (theta - theta_0) + ex cos + ey sin, unwrapped
    spacing = cells.spiral.spacing
    basis = refit_basis(cells)
    root_weights = np.sqrt(cells.confidence / cells.confidence.mean())
    residuals = lambda q: root_weights * wrap(cells.offsets - basis @ q, spacing)
    q = least_squares(residuals, refit_start(cells, 1.5, every=1), loss="soft_l1", f_scale=0.1 * spacing).x
    angle = lambda theta: theta + cells.spiral.phase
    return lambda theta: q[0] + q[1] * (theta - cells.theta[0]) + q[2] * np.cos(angle(theta)) + q[3] * np.sin(angle(theta))


def neighbours_mean(theta, offsets):
    # the mean offset of the turns either side (one turn = 2 pi along the
    # rectangle), each from its own turn; 0 where a neighbour is off the end
    total, count = np.zeros_like(offsets), np.zeros_like(offsets)
    for side in (TAU, -TAU):
        inside = (theta + side >= theta[0]) & (theta + side <= theta[-1])
        total += np.where(inside, np.interp(theta + side, theta, offsets), 0)
        count += inside
    return total / np.maximum(count, 1)


def run_unrolled(card, image, low, column_step, second_pass=None):
    # the path = the geometry model + the wedges' offsets from it (within
    # +-S/2, as lock_trace), so it can leave the low-res spiral by more than
    # S/2. A second pass shifts each column's rows (still one period) to
    #   "groove":  centered on pass 1's path
    #   "midway":  centered between the lands either side of the groove, i.e.
    #              halfway between the groove and the mean of its neighbours
    #              (the turns one 2 pi either side, from pass 1)
    # and keeps the new offsets within +-S/2 of pass 1's path
    started = time.time()
    unrolled = Unrolled(image, low.spiral, card.mark, column_step)
    cells = wedges(unrolled, unrolled.column_phasors(np.zeros(len(unrolled.theta))))
    model = geometry_model(cells)
    near = lambda reference, cells, theta: reference + wrap(drift_at(cells, theta) - reference, unrolled.spacing)
    theta = strip_columns(low.spiral, card.mark, READ_STEP)
    trace = near(model(theta), cells, theta)
    if second_pass:
        path = near(model(unrolled.theta), cells, unrolled.theta)
        shift = path if second_pass == "groove" else (path + neighbours_mean(unrolled.theta, path)) / 2
        trace = near(trace, wedges(unrolled, unrolled.column_phasors(shift)), theta)
    seconds = time.time() - started
    return {"seconds": seconds, "samples": len(unrolled.theta) * len(unrolled.rows)} | \
        score(card, image, Strip(low.spiral, theta, READ_STEP, None, None, None), trace)


def score(card, image, strip, trace):
    s = score_trace(card, strip, trace)
    return {"trace_rms": rms(s.distance), "wrong_groove": float(np.mean(s.wrong_groove)),
            "sound_correlation": correlation(read_sound(image, strip, trace), s.true_sound)}


def run_strip(card, image, low, window):
    strip_module.demodulate = make_demodulate(*window)
    started = time.time()
    strip = build_strip(image, low.spiral, card.mark, StripSettings())
    _, model = refit_geometry(strip, StripSettings())
    trace = lock_trace(strip, model, StripSettings())
    seconds = time.time() - started
    return {"seconds": seconds} | score(card, image, strip, trace)


def main():
    presets, seeds, out = sys.argv[1].split(","), sys.argv[2].split(","), Path(sys.argv[3])
    rows = []
    original = strip_module.demodulate
    for preset in presets:
        for seed in seeds:
            card = make_card(PRESETS[preset], int(seed))
            image = render(card)
            low = low_res_stage(image, card.mark, card.params.spacing)
            add = lambda method, result: rows.append({"preset": preset, "seed": int(seed), "method": method} | result)
            add("strip, cos2 +-S (now)", run_strip(card, image, low, ("cos2", 1.0, "trend")))
            add("strip, rect +-S/2", run_strip(card, image, low, ("rect", 0.5, "none")))
            strip_module.demodulate = original
            add("pixel sectors", run_cells(card, image, low, False, SECTORS, recenter=True))
            for column_step in (1.0, 3.0):
                for second_pass in (None, "groove", "midway"):
                    name = f", pass 2 rows {second_pass}" if second_pass else ", 1 pass"
                    add(f"unrolled, {column_step:g} px columns{name}", run_unrolled(card, image, low, column_step, second_pass))
            out.write_text(json.dumps(rows, indent=1))
            print(preset, seed, flush=True)
    print("| method | preset | path rms px | wrong groove | sound corr | seconds |")
    print("|---|---|---|---|---|---|")
    for method in dict.fromkeys(r["method"] for r in rows):
        for preset in presets:
            sel = [r for r in rows if r["method"] == method and r["preset"] == preset]
            med = lambda key: float(np.median([r[key] for r in sel]))
            print(f"| {method} | {preset} | {med('trace_rms'):.2f} | {100 * med('wrong_groove'):.2f}% | "
                  f"{med('sound_correlation'):.3f} | {med('seconds'):.2f} |")


if __name__ == "__main__":
    main()
