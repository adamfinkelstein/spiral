import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.geometry import TAU, Mark, pitch_of
from cardlab.lowres import (LOW_SIZE, LowResSettings, annulus_mask, coherence_map, downsample, fft_spacing,
                            map_peak, normalize_in_mask, symmetry_center)
from experiments.center_search import fit_ring_pattern, map_points_near
from cardlab.model import make_card, render
from cardlab.params import PRESETS

# Offline experiment (Nov 2026): the coherence map's center of point symmetry
# (Adam's idea, first tried on spacing.html) vs. cardlab's J0 fit at the map's
# peak, on simulated cards, optionally stretched by `aspect` (x * aspect,
# y / aspect about the true center) to model a slightly non-circular scan.
#   fft+J0    cardlab's method until this experiment: J0 fit around the brightest pixel
# Result: the symmetry center (sigma 10) replaced the J0 fit in cardlab
# (lowres.symmetry_center, crop +-3 sigma); see symmetry_center_results.md.
# Later (aligning with the spacing page): sigma = 0.12 x the marked outer
# radius, search within 1.5 sigma of the peak, kernel reach = outer radius +
# 2 spacings; compared here with the sigma-10-spacings version.
#   sym wN    self-convolution of the windowed zero-mean |Z| (Gaussian window,
#             sigma N spacings, on a crop around the peak); its maximum is at
#             twice the center of symmetry (results file: crop +-4 sigma)

CACHE = Path("/tmp/center_search_cards")
MARK_ERRORS = (5, 30, 100)  # full-res px
ASPECTS = (1.0, 0.99, 1.01, 0.98, 1.02, 1.03)
SETTINGS = LowResSettings()


def low_res_card(preset, seed):
    path = CACHE / f"{preset}_{seed}.npz"
    card = make_card(PRESETS[preset], seed)
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        np.savez(path, low=downsample(render(card)))
    return card, np.load(path)["low"]


def stretched(low, center, aspect):
    if aspect == 1:
        return low
    # output pixel p comes from input (p - c) / (aspect, 1/aspect) + c, pixel centers at i + 0.5
    scale = np.array([1 / aspect, aspect])
    shift = (np.asarray(center) - 0.5) * (1 - scale)
    matrix = np.array([[scale[0], 0, shift[0]], [0, scale[1], shift[1]]])
    return cv2.warpAffine(low, matrix, low.shape[::-1], flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                          borderMode=cv2.BORDER_REFLECT)


def simulated_marks(card, rng):
    for error in MARK_ERRORS:
        angle = rng.random() * TAU
        radius_errors = 1 + rng.standard_normal(2) * card.params.mark_radius_error
        yield error, Mark(card.spiral.x + error * np.cos(angle), card.spiral.y + error * np.sin(angle),
                          card.params.r_inner * radius_errors[0], card.params.r_outer * radius_errors[1])


def j0_center(z_map, spacing):
    start = map_peak(z_map)
    points, values = map_points_near(z_map, start, 2.5 * spacing)
    return fit_ring_pattern(points, values, start, spacing)[0]


METHODS = {  # name: function of (z_map with the old reach, z_map with the current reach, spacing, outer radius), low-res px
    "fft+J0": lambda z_old, z_new, spacing, r_outer: j0_center(z_old, spacing),
    "sym σ 10 S (before)": lambda z_old, z_new, spacing, r_outer: symmetry_center(z_old, 10 * spacing, search=3),
    "sym σ 0.12 r_outer (now)": lambda z_old, z_new, spacing, r_outer: symmetry_center(z_new, 0.12 * r_outer, search=1.5),
}


def run_card(preset, seed):
    card, low = low_res_card(preset, seed)
    scale = card.params.frame / LOW_SIZE
    truth = np.array([card.spiral.x, card.spiral.y])
    rows = []
    for aspect in ASPECTS:
        image_low = stretched(low, truth / scale, aspect)
        for mark_error, mark in simulated_marks(card, np.random.default_rng(seed + 77)):
            nominal = card.params.spacing / scale
            mask = annulus_mask(LOW_SIZE, mark, scale, ramp=nominal)
            image = normalize_in_mask(image_low, mask)
            *_, measured, ok = fft_spacing(image, mask, mark, scale, nominal, SETTINGS)
            spacing = measured if ok else nominal
            z_old = coherence_map(image, pitch_of(spacing), reach=int(mark.r_outer / scale + 100))
            z_new = coherence_map(image, pitch_of(spacing), reach=int(np.ceil(mark.r_outer / scale + 2 * spacing)))
            peak_error = np.hypot(*(map_peak(z_old) * scale - truth))
            for name, method in METHODS.items():
                started = time.time()
                center = method(z_old, z_new, spacing, mark.r_outer / scale) * scale
                rows.append({"preset": preset, "seed": seed, "aspect": aspect, "mark_error": mark_error,
                             "method": name, "error": float(np.hypot(*(center - truth))),
                             "peak_error": float(peak_error), "seconds": time.time() - started})
    return rows


def summary(rows):
    lines = ["| preset | aspect | method | median px | 90th pct px | max px | > 1 px | seconds |",
             "|---|---|---|---|---|---|---|---|"]
    for preset in dict.fromkeys(r["preset"] for r in rows):
        for aspect in ASPECTS:
            for name in METHODS:
                errors = np.array([r["error"] for r in rows
                                   if r["preset"] == preset and r["aspect"] == aspect and r["method"] == name])
                seconds = np.median([r["seconds"] for r in rows
                                     if r["preset"] == preset and r["aspect"] == aspect and r["method"] == name])
                if len(errors):
                    lines.append(f"| {preset} | {aspect} | {name} | {np.median(errors):.3f} | "
                                 f"{np.percentile(errors, 90):.3f} | {errors.max():.2f} | "
                                 f"{np.mean(errors > 1):.0%} | {seconds:.3f} |")
    return "\n".join(lines)


def main():
    presets, seeds, out = sys.argv[1].split(","), sys.argv[2].split(","), Path(sys.argv[3])
    rows = []
    for preset in presets:
        for seed in seeds:
            rows += run_card(preset, int(seed))
            out.write_text(json.dumps(rows))
            print(preset, seed, flush=True)
    print(summary(rows))


if __name__ == "__main__":
    main()
