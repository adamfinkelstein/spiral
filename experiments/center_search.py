import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.geometry import TAU, Mark, pitch_of
from cardlab.lowres import (LOW_SIZE, LowResSettings, annulus_mask, coherence_map, downsample, fft_spacing,
                            fit_ring_pattern, map_peak, map_points_near, normalize_in_mask)
from cardlab.model import make_card, render
from cardlab.params import PRESETS

# Offline experiment (Nov 2026): ways to find the spiral's center at low
# resolution, each started from many simulated hand marks per card.
#   grid+NM     the current method: |Z| on a grid (0.15 S, +-60 px) about the mark, then Nelder-Mead
#   fft+NM      Z at every pixel by one FFT correlation with a spiral-wave kernel, global argmax, then Nelder-Mead
#   fft+J0      the same map, then a fit of a J0 ring pattern to the complex map around its argmax
#   sparse+J0   Z on a coarse grid (0.45 S, +-60 px) about the mark, then a J0 fit to all of it
#   sparse+J0+NM  the same, polished by Nelder-Mead
# The complex map is Z(c) ~ a J0(2 pi |c - c0| / S) about the true center c0.
# Result: fft+J0 won and is now cardlab's method (lowres.find_center); the grid,
# direct sums and Nelder-Mead used by the other methods live here only.

CACHE = Path("/tmp/center_search_cards")
MARK_ERRORS = (5, 15, 30, 60, 100)      # full-res px
MARKS_PER_ERROR = 2
SETTINGS = LowResSettings()
SAMPLE_FRACTION = 0.05  # of the annulus pixels, for the direct sums


# ---------- Cards and marks ----------


def low_res_card(preset, seed):
    path = CACHE / f"{preset}_{seed}.npz"
    card = make_card(PRESETS[preset], seed)
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        np.savez(path, low=downsample(render(card)))
    return card, np.load(path)["low"]


def simulated_marks(card, rng):
    for error in MARK_ERRORS:
        for _ in range(MARKS_PER_ERROR):
            angle = rng.random() * TAU
            radii = card.params.r_inner, card.params.r_outer
            radius_errors = 1 + rng.standard_normal(2) * card.params.mark_radius_error
            yield error, Mark(card.spiral.x + error * np.cos(angle), card.spiral.y + error * np.sin(angle),
                              radii[0] * radius_errors[0], radii[1] * radius_errors[1])


# ---------- Direct sums (the earlier method) ----------


def sample_annulus(image, mask, fraction, rng):
    rows, cols = np.nonzero(mask > 0)
    keep = rng.random(len(rows)) < fraction
    return cols[keep] + 0.5, rows[keep] + 0.5, image[rows[keep], cols[keep]]


def spiral_coherence(x, y, values, cx, cy, pitch):
    dx, dy = x - cx, y - cy
    return -np.sum(values * np.exp(-1j * (np.hypot(dx, dy) / pitch - np.arctan2(dy, dx))), axis=-1)


def coherence_grid(x, y, values, center, pitch, radius, step):
    offsets = np.arange(-np.ceil(radius / step), np.ceil(radius / step) + 1) * step
    centers_x = center[0] + offsets
    scores = np.empty((len(offsets), len(offsets)))
    for row, cy in enumerate(center[1] + offsets):
        scores[row] = np.abs(spiral_coherence(x, y, values, centers_x[:, None], cy, pitch))
    return centers_x, center[1] + offsets, scores


def complex_grid(x, y, values, center, pitch, radius, step):
    offsets = np.arange(-np.ceil(radius / step), np.ceil(radius / step) + 1) * step
    gx, gy = np.meshgrid(center[0] + offsets, center[1] + offsets)
    scores = np.array([spiral_coherence(x, y, values, cx, cy, pitch) for cx, cy in zip(gx.ravel(), gy.ravel())])
    return np.stack([gx.ravel(), gy.ravel()], axis=1), scores


def refine_center(x, y, values, start, step, mid_turn):
    # Nelder-Mead over (x, y, pitch * mid_turn), all in px
    to_params = lambda q: (q[0], q[1], q[2] / mid_turn)
    negative_coherence = lambda q: -np.abs(spiral_coherence(x, y, values, *to_params(q)))
    q0 = np.array([start[0], start[1], start[2] * mid_turn])
    simplex = np.array([q0, q0 + [step / 2, 0, 0], q0 + [0, step / 2, 0], q0 + [0, 0, step / 2]])
    result = minimize(negative_coherence, q0, method="Nelder-Mead",
                      options={"initial_simplex": simplex, "xatol": 0.005, "fatol": 1e-6 * abs(negative_coherence(q0))})
    return to_params(result.x)


# ---------- Methods (all in low-res px) ----------


def method_grid_nm(data):
    xs, ys, scores = coherence_grid(*data["subset"], data["mark"], data["pitch"], data["radius"], 0.15 * data["spacing"])
    row, col = np.unravel_index(np.argmax(scores), scores.shape)
    return refine(data, [xs[col], ys[row]])


def method_fft_nm(data):
    return refine(data, map_peak(data["z_map"]))


def method_fft_j0(data):
    start = map_peak(data["z_map"])
    points, values = map_points_near(data["z_map"], start, 2.5 * data["spacing"])
    return fit_ring_pattern(points, values, start, data["spacing"])[0]


def sparse_fit(data):
    points, values = complex_grid(*data["subset"], data["mark"], data["pitch"], data["radius"], 0.45 * data["spacing"])
    start = points[np.argmax(np.abs(values))]
    return fit_ring_pattern(points, values, start, data["spacing"])[0]


def method_sparse_j0_nm(data):
    return refine(data, sparse_fit(data))


def refine(data, start):
    cx, cy, _ = refine_center(*data["sample"], np.array([start[0], start[1], data["pitch"]]),
                              0.15 * data["spacing"], data["mid_turn"])
    return np.array([cx, cy])


METHODS = {
    "grid+NM": method_grid_nm,
    "fft+NM": method_fft_nm,
    "fft+J0": method_fft_j0,
    "sparse+J0": sparse_fit,
    "sparse+J0+NM": method_sparse_j0_nm,
}


# ---------- Experiment ----------


def prepare(low, card, mark):
    scale = card.params.frame / LOW_SIZE
    nominal = card.params.spacing / scale
    mask = annulus_mask(LOW_SIZE, mark, scale, ramp=nominal)
    image = normalize_in_mask(low, mask)
    *_, measured, ok = fft_spacing(image, mask, mark, scale, nominal, SETTINGS)
    spacing = measured if ok else nominal
    pitch = pitch_of(spacing)
    x, y, values = sample_annulus(image, mask, SAMPLE_FRACTION, np.random.default_rng(0))
    every = max(1, len(x) // 8000)
    started = time.time()
    z_map = coherence_map(image, pitch, reach=int(mark.r_outer / scale + 150))
    map_time = time.time() - started
    return {
        "scale": scale, "spacing": spacing, "pitch": pitch, "mark": np.array([mark.x, mark.y]) / scale,
        "radius": 60 / scale, "mid_turn": (mark.r_inner + mark.r_outer) / 2 / scale / pitch,
        "sample": (x, y, values), "subset": (x[::every], y[::every], values[::every]), "z_map": z_map,
    }, map_time


def run_card(preset, seed):
    card, low = low_res_card(preset, seed)
    truth = np.array([card.spiral.x, card.spiral.y])
    rows = []
    for mark_error, mark in simulated_marks(card, np.random.default_rng(seed + 77)):
        data, map_time = prepare(low, card, mark)
        for name, method in METHODS.items():
            started = time.time()
            center = method(data) * data["scale"]
            seconds = time.time() - started + (map_time if name.startswith("fft") else 0)
            rows.append({"preset": preset, "seed": seed, "mark_error": mark_error, "method": name,
                         "error": float(np.hypot(*(center - truth))), "seconds": seconds})
    return rows


def main():
    presets, seeds, out = sys.argv[1].split(","), sys.argv[2].split(","), Path(sys.argv[3])
    rows = []
    for preset in presets:
        for seed in seeds:
            rows += run_card(preset, int(seed))
            out.write_text(json.dumps(rows))
            print(preset, seed, flush=True)


if __name__ == "__main__":
    main()
