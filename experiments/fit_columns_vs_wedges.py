import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.geometry import TAU, polar, wrap
from cardlab.lowres import low_res_stage
from cardlab.model import make_card, render
from cardlab.params import PRESETS
from cardlab.scoring import center_error, spacing_error
from cardlab.strip import Strip, refit_basis, refit_start
from cardlab.wedges import Unrolled, WedgeSettings, refit_wedges, wedges

# Offline experiment (Nov 2026, Adam's questions): step 4's geometry fit
# (center, spacing, spiral phase from the coarse columns), four ways:
#   A wedges (now): 40 per turn, offset = angle of the summed phasors,
#     weights |Z|, robust least squares on wrapped residuals
#   B columns: each column's own angle, fitted the same way (no averaging)
#   C coherence: no angles at all; the parameters maximize the coherence of
#     all column phasors with the model, sum |z| cos(2 pi (o - model) / S)
#   D wedges weighted by their noise: within a wedge the columns' phasors
#     agree to R = |sum z| / sum |z|; a column's angular spread is then
#     sqrt(-2 ln R) (circular sd), so the wedge's offset has variance
#     ~ -2 ln R / n; weights 1 / that (instead of |Z|)
# On clean cards and two kinds of damage, separately: "lost" = a ruined 40-degree sector (grooves
# replaced by noise 3x the groove rms: data lost) plus 8 deep scratches; "shifted" = a 30-degree sector whose
# grooves are shifted outward by S/3 (a warped or lifted patch: clean but
# wrong offsets). E, F and G target the shifted kind (G: by angular sector).

METHODS = ("A wedges |Z|", "B columns", "C coherence", "D wedges by noise", "E wedges, Cauchy loss", "F wedges, trim and refit", "G wedges, drop bad sectors")
CONDITIONS = ("clean", "lost", "shifted")


def damage(image, card, rng, kinds=("lost", "shifted")):
    out = image.copy()
    size = image.shape[0]
    rows, cols = np.mgrid[0:size, 0:size] + 0.5
    r, angle = polar(cols, rows, card.spiral.x, card.spiral.y)
    inside = (r > card.params.r_inner - 50) & (r < card.params.r_outer + 50)
    scale = image[inside].std()
    start = rng.random() * TAU
    sector = inside & (wrap(angle - start, TAU) % TAU < np.radians(40))
    if "lost" in kinds:
        out[sector] = rng.standard_normal(sector.sum()).astype(np.float32) * 3 * scale
    # a second sector, opposite, with the grooves shifted outward by S/3
    import cv2
    shifted = inside & (wrap(angle - start - np.pi, TAU) % TAU < np.radians(30))
    scale_r = np.where(r > 0, (r - card.spacing / 3) / np.maximum(r, 1), 1)
    map_x = (card.spiral.x + (cols - card.spiral.x) * scale_r - 0.5).astype(np.float32)
    map_y = (card.spiral.y + (rows - card.spiral.y) * scale_r - 0.5).astype(np.float32)
    moved = cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR)
    if "shifted" in kinds:
        out[shifted] = moved[shifted]
    for _ in range(8 if "lost" in kinds else 0):  # straight scratches 8 px wide, as deep as 1.5 grooves
        a = rng.random() * np.pi
        through = np.array([card.spiral.x, card.spiral.y]) + (rng.random(2) - 0.5) * 2 * card.params.r_outer
        distance = np.abs((cols - through[0]) * np.sin(a) - (rows - through[1]) * np.cos(a))
        out[(distance < 4) & inside] -= 1.5 * 4 * scale
    return out


def wedge_noise(unrolled, z_columns):
    _, index, count = np.unique(unrolled.wedge, return_inverse=True, return_counts=True)
    z = np.bincount(index, z_columns.real) + 1j * np.bincount(index, z_columns.imag)
    total = np.bincount(index, np.abs(z_columns))
    keep = count > 0.5 * np.median(count)
    coherence = np.clip(np.abs(z[keep]) / total[keep], 1e-3, 0.999)
    return -2 * np.log(coherence) / count[keep]  # variance of the wedge's angle, rad^2


def coherence_fit(cells, search=1.5):
    spacing, low = cells.spiral.spacing, cells.spiral
    basis = refit_basis(cells)
    weights = np.sqrt(cells.confidence)
    start = refit_start(cells, search, every=40)

    def residuals(q):
        angle = TAU * (cells.offsets - basis @ q) / spacing
        return np.concatenate([weights * (np.cos(angle) - 1), weights * np.sin(angle)])  # sum of squares = 2 sum w (1 - cos)
    a, beta, ex, ey = least_squares(residuals, start).x
    pitch = low.pitch + beta
    return type(low)(low.x + ex, low.y - ey, pitch, (low.pitch * low.phase - a + beta * cells.theta[0]) / pitch)


def cauchy_fit(cells, search=1.5):
    # as refit_wedges, with a redescending-like Cauchy loss (scale 0.1 S)
    spacing, low = cells.spiral.spacing, cells.spiral
    basis = refit_basis(cells)
    root_weights = np.sqrt(cells.confidence / cells.confidence.mean())
    residuals = lambda q: root_weights * wrap(cells.offsets - basis @ q, spacing)
    a, beta, ex, ey = least_squares(residuals, refit_start(cells, search, every=1), loss="cauchy", f_scale=0.1 * spacing).x
    pitch = low.pitch + beta
    return type(low)(low.x + ex, low.y - ey, pitch, (low.pitch * low.phase - a + beta * cells.theta[0]) / pitch)


def trimmed_fit(cells, keep_within=1 / 6):
    # fit, drop the wedges more than S/6 from the model (wrapped), fit again
    spiral, model = refit_wedges(cells)
    residual = wrap(cells.offsets - model(cells.theta), cells.spiral.spacing)
    ok = np.abs(residual) < keep_within * cells.spiral.spacing
    kept = Strip(cells.spiral, cells.theta[ok], 0.0, cells.demod[ok], cells.offsets[ok], cells.confidence[ok])
    return refit_wedges(kept)[0]


def sector_trimmed_fit(cells, sectors=40, rounds=2):
    # fit; group the wedges' residuals by angle on the card (40 sectors, all
    # turns together); drift is random from turn to turn and averages out
    # over ~38 turns, a damaged patch doesn't: drop sectors whose median
    # residual is beyond 3 MADs of the sectors' medians; fit again
    spacing = cells.spiral.spacing
    sector = np.floor((cells.theta % TAU) / TAU * sectors).astype(int)
    keep = np.ones(len(cells.theta), bool)
    for _ in range(rounds):
        kept = Strip(cells.spiral, cells.theta[keep], 0.0, cells.demod[keep], cells.offsets[keep], cells.confidence[keep])
        spiral, model = refit_wedges(kept)
        residual = wrap(cells.offsets - model(cells.theta), spacing)
        medians = np.array([np.median(residual[sector == k]) for k in range(sectors)])
        center = np.median(medians)
        mad = 1.4826 * np.median(np.abs(medians - center))
        bad = np.abs(medians - center) > 3 * max(mad, 0.02 * spacing)
        keep = ~bad[sector]
    kept = Strip(cells.spiral, cells.theta[keep], 0.0, cells.demod[keep], cells.offsets[keep], cells.confidence[keep])
    return refit_wedges(kept)[0]


def column_strip(unrolled, z_columns):
    offsets = -unrolled.spacing * np.angle(-z_columns) / TAU
    confidence = np.abs(z_columns) / np.median(np.abs(z_columns))
    return Strip(unrolled.spiral, unrolled.theta, 0.0, z_columns, offsets, confidence)


def fits(image, low, mark):
    unrolled = Unrolled(image, low.spiral, mark, WedgeSettings().pass1_step, WedgeSettings().sectors)
    z_columns = unrolled.column_phasors(np.zeros(len(unrolled.theta)))
    cells = wedges(unrolled, z_columns)
    columns = column_strip(unrolled, z_columns)
    variance = wedge_noise(unrolled, z_columns)
    by_noise = Strip(cells.spiral, cells.theta, 0.0, cells.demod, cells.offsets,
                     (1 / variance) / np.mean(1 / variance))
    out = {}
    for name, run in (("A wedges |Z|", lambda: refit_wedges(cells)[0]),
                      ("B columns", lambda: refit_wedges(columns)[0]),
                      ("C coherence", lambda: coherence_fit(columns)),
                      ("D wedges by noise", lambda: refit_wedges(by_noise)[0]),
                      ("E wedges, Cauchy loss", lambda: cauchy_fit(cells)),
                      ("F wedges, trim and refit", lambda: trimmed_fit(cells)),
                      ("G wedges, drop bad sectors", lambda: sector_trimmed_fit(cells))):
        started = time.perf_counter()
        spiral = run()
        out[name] = (spiral, time.perf_counter() - started)
    return out


def main():
    presets, seeds, out = sys.argv[1].split(","), sys.argv[2].split(","), Path(sys.argv[3])
    rows = []
    for preset in presets:
        for seed in seeds:
            card = make_card(PRESETS[preset], int(seed))
            clean = render(card)
            images = {"clean": clean,
                      "lost": damage(clean, card, np.random.default_rng(int(seed)), ("lost",)),
                      "shifted": damage(clean, card, np.random.default_rng(int(seed)), ("shifted",))}
            for condition, image in images.items():
                low = low_res_stage(image, card.mark, card.params.spacing)
                for name, (spiral, seconds) in fits(image, low, card.mark).items():
                    rows.append({"preset": preset, "seed": int(seed), "condition": condition, "method": name,
                                 "low_center": center_error(card, low.spiral), "center": center_error(card, spiral),
                                 "spacing": spacing_error(card, spiral), "seconds": seconds})
            out.write_text(json.dumps(rows, indent=1))
            print(preset, seed, flush=True)
    print("| condition | method | preset | center px, median (max) | spacing %, median abs | seconds |")
    print("|---|---|---|---|---|---|")
    for condition in CONDITIONS:
        for name in METHODS:
            for preset in presets:
                sel = [r for r in rows if r["condition"] == condition and r["method"] == name and r["preset"] == preset]
                c = [r["center"] for r in sel]
                print(f"| {condition} | {name} | {preset} | {np.median(c):.3f} ({max(c):.2f}) | "
                      f"{100 * np.median([abs(r['spacing']) for r in sel]):.4f} | {np.median([r['seconds'] for r in sel]):.2f} |")


if __name__ == "__main__":
    main()
