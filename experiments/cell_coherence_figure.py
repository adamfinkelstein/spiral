import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cardlab.geometry import TAU
from cardlab.lowres import low_res_stage
from cardlab.model import make_card, render
from cardlab.params import PRESETS
from cell_coherence import cell_strip, refit_cells

# NOTE (Nov 2026): written for the old spiral convention r = pitch * theta,
# theta = angle - phase + 2 pi n. cardlab now uses r = pitch * (theta - phase),
# theta = the card's angle unwrapped; this script was not updated (results
# files record what it gave then).
# The cells of experiments/cell_coherence.py, drawn: (a) a toy spiral with 12
# sectors per turn, each cell one turn's band (+-S/2 about its turn) times one
# sector; (b) the cells on a real (simulated) card at low resolution, 40 per
# turn; (c) what the cells measure: each cell's groove offset from the
# refitted spiral, as a map of turn x angle.

plt.rcParams.update({"figure.facecolor": "black", "savefig.facecolor": "black", "text.color": "#ddd",
                     "axes.labelcolor": "#ccc", "xtick.color": "#999", "ytick.color": "#999", "axes.edgecolor": "#444"})


def cell_ids(x, y, cx, cy, pitch, phase, sectors):
    r = np.hypot(x - cx, y - cy)
    around = np.mod(np.arctan2(y - cy, x - cx) - phase, TAU)
    turn = np.rint((r / pitch - around) / TAU).astype(int)
    sector = np.minimum((around / TAU * sectors).astype(int), sectors - 1)
    return r, turn, sector


def toy(axes, sectors=12, spacing=1.0, turns=(2, 6)):
    # one color per turn (alternating), thin lines for the sector edges and for
    # the band edges (the spirals halfway between turns); turns in white
    pitch = spacing / TAU
    grid = np.linspace(-6.6, 6.6, 1000)
    x, y = np.meshgrid(grid, grid)
    r, turn, sector = cell_ids(x, y, 0, 0, pitch, 0, sectors)
    inside = (r > turns[0] * spacing) & (r < turns[1] * spacing)
    colors = np.array([[0.20, 0.42, 0.75], [0.85, 0.55, 0.20]])
    rgb = colors[turn % 2]
    rgb[~inside] = 0.08
    axes.imshow(rgb, extent=(-6.6, 6.6, 6.6, -6.6), interpolation="nearest")
    theta = np.linspace(0, TAU * turns[1] + TAU, 6000)
    for shift, color, width in ((-spacing / 2, "#111", 1.0), (0, "white", 1.8)):
        radius = pitch * theta + shift
        keep = (radius > turns[0] * spacing) & (radius < turns[1] * spacing)
        axes.plot(np.where(keep, radius * np.cos(theta), np.nan), np.where(keep, radius * np.sin(theta), np.nan), color=color, lw=width)
    for k in range(sectors):
        a_ = k / sectors * TAU
        axes.plot([turns[0] * np.cos(a_), turns[1] * np.cos(a_)], [turns[0] * np.sin(a_), turns[1] * np.sin(a_)], color="#111", lw=1.0)
    # one cell, outlined: turn 4, sector 2
    k, n = 2, 4
    a_ = np.linspace(k / sectors * TAU, (k + 1) / sectors * TAU, 50)
    inner, outer = pitch * (a_ + TAU * n) - spacing / 2, pitch * (a_ + TAU * n) + spacing / 2
    xs = np.concatenate([inner * np.cos(a_), outer[::-1] * np.cos(a_[::-1]), [inner[0] * np.cos(a_[0])]])
    ys = np.concatenate([inner * np.sin(a_), outer[::-1] * np.sin(a_[::-1]), [inner[0] * np.sin(a_[0])]])
    axes.fill(xs, ys, color="#ffe680", alpha=0.85)
    axes.plot(xs, ys, color="#ffe680", lw=2)
    axes.annotate("one cell: the band of\none turn (between two\ndark spirals) × one sector", xy=(np.mean(xs), np.mean(ys)),
                  xytext=(1.6, 6.4), color="#ffe680", fontsize=10.5, arrowprops=dict(arrowstyle="->", color="#ffe680"))
    axes.set_xlim(-6.6, 6.6)
    axes.set_ylim(7.6, -6.6)
    axes.set_axis_off()
    axes.set_title("a. Toy spiral, 12 sectors per turn. White: the arms (grooves);\ncolor: which arm each pixel belongs to; dark lines: cell edges",
                   fontsize=11, loc="left", color="#ddd")


def card_crop(axes, low, card, sectors=40, half=70):
    scale, spiral = low.scale, low.spiral
    cx, cy = spiral.x / scale, spiral.y / scale
    angle = np.deg2rad(-35)
    radius = (card.mark.r_inner + card.mark.r_outer) / 2 / scale
    px, py = cx + radius * np.cos(angle), cy + radius * np.sin(angle)
    x0, y0 = int(px - half), int(py - half)
    crop = low.image[y0 : y0 + 2 * half, x0 : x0 + 2 * half]
    ys, xs = np.mgrid[y0 : y0 + 2 * half, x0 : x0 + 2 * half] + 0.5
    _, turn, sector = cell_ids(xs, ys, cx, cy, spiral.pitch / scale, spiral.phase, sectors)
    edge = np.zeros(turn.shape, bool)
    for t in (turn, sector):
        edge[:, 1:] |= t[:, 1:] != t[:, :-1]
        edge[1:, :] |= t[1:, :] != t[:-1, :]
    lo, hi = np.percentile(crop, (2, 98))
    grey = np.clip((crop - lo) / (hi - lo), 0, 1)
    rgb = np.stack([grey] * 3, axis=-1)
    rgb[edge] = [1.0, 0.75, 0.1]
    axes.imshow(rgb, interpolation="nearest")
    axes.set_axis_off()
    axes.set_title(f"b. A real (simulated) card, low res: cell edges (yellow),\n40 sectors per turn; dark = groove; {2 * half}×{2 * half} px of {low.image.shape[0]}²",
                   fontsize=11, loc="left", color="#ddd")


def offset_map(axes, image, low, card, sectors=40):
    first = cell_strip(image, low.spiral, 1.0, card.mark, sectors)
    spiral = refit_cells(first)
    cells = cell_strip(image, spiral, 1.0, card.mark, sectors)
    turn = np.floor(cells.theta / TAU).astype(int)
    sector = ((cells.theta / TAU - turn) * sectors).astype(int)
    grid = np.full((turn.max() - turn.min() + 1, sectors), np.nan)
    grid[turn - turn.min(), sector] = cells.offsets
    image_ = axes.imshow(grid, aspect="auto", cmap="RdBu_r", vmin=-8, vmax=8, interpolation="nearest",
                         extent=(0, 360, turn.max() + 0.5, turn.min() - 0.5))
    axes.set_xlabel("angle (degrees)")
    axes.set_ylabel("turn (outward ↓)")
    bar = plt.colorbar(image_, ax=axes, fraction=0.05)
    bar.set_label("groove offset from the refitted spiral, px", color="#ccc")
    bar.ax.yaxis.set_tick_params(color="#999")
    axes.set_title("c. What the cells measure (full res): each cell's groove\noffset, turn × angle: the drift, smooth along each turn",
                   fontsize=11, loc="left", color="#ddd")


def main():
    out = Path(sys.argv[1])
    card = make_card(PRESETS["typical"], 1)
    image = render(card)
    low = low_res_stage(image, card.mark, card.params.spacing)
    figure = plt.figure(figsize=(16, 5.6), dpi=100)
    toy(figure.add_axes([0.01, 0.03, 0.3, 0.82]))
    card_crop(figure.add_axes([0.33, 0.03, 0.3, 0.82]), low, card)
    offset_map(figure.add_axes([0.68, 0.1, 0.28, 0.75]), image, low, card)
    figure.savefig(out, dpi=100)


if __name__ == "__main__":
    main()
