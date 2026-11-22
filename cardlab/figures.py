import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .geometry import TAU, nearest_turn_theta, polar, spiral_points, wrap
from .scoring import ideal_offset
from .strip import sample_strip
from .wedges import offsets_about

# One function per step figure; all draw on a dark background and save PNGs.

# One meaning per color, in every figure (and the report's text): white = input
# (hand mark, nominal); cyan = low-res estimates; yellow = the refit (estimated
# geometry); orange = the final estimates along the groove (trace, read-out
# sound); green = truth along the groove (true groove, true sound); pale green
# = true geometry (center, spacing, ideal spiral); magenta = wrong groove;
# grey = raw measurements; violet = annotations (cartoon labels, detail-spot
# boxes, the rectangle's rows and wedge edges).
COLORS = {"mark": "white", "low": "#4cf", "refit": "#fd3", "trace": "#f93", "true": "#3e6", "geometry": "#a8f0b4",
          "wrong": "#f0f", "measured": "#aaa", "label": "#b8f"}
plt.rcParams.update({
    "figure.facecolor": "black", "axes.facecolor": "black", "savefig.facecolor": "black",
    "text.color": "#ccc", "axes.labelcolor": "#ccc", "axes.edgecolor": "#444",
    "xtick.color": "#999", "ytick.color": "#999", "font.size": 11,
})


def new_figure(width, height):
    return plt.figure(figsize=(width / 100, height / 100), dpi=100)


def save(figure, path):
    figure.savefig(path, dpi=100)
    plt.close(figure)


def image_axes(figure):
    axes = figure.add_axes([0, 0, 1, 1])
    axes.set_axis_off()
    return axes


def show_grey(axes, image, extent=None, percentiles=(2, 98), aspect="equal"):
    low, high = np.percentile(image, percentiles)
    axes.imshow(image, cmap="gray", vmin=low, vmax=high, extent=extent, interpolation="nearest", aspect=aspect)


def plot_cross(axes, x, y, color, size=12):
    axes.plot(x, y, "+", color=color, markersize=size, markeredgewidth=2)


def plot_ring(axes, x, y, color, size=14):
    axes.plot(x, y, "o", color=color, markersize=size, fillstyle="none", markeredgewidth=2)


def circle(axes, x, y, radius, color, dashed=True):
    angle = np.linspace(0, TAU, 400)
    axes.plot(x + radius * np.cos(angle), y + radius * np.sin(angle), "--" if dashed else "-", color=color, lw=1)


def detail_spot(run, column=None):
    column = len(run.strip.theta) // 2 if column is None else column
    return spiral_points(run.strip.spiral, run.strip.theta[column], run.trace[column])


def detail_box(run, spot, size):
    # top-left corner of the size x size crop about a spot, kept inside the frame
    height, width = run.image.shape
    return (int(np.clip(spot[0] - size / 2, 0, width - size)), int(np.clip(spot[1] - size / 2, 0, height - size)))


def wrong_runs(wrong):
    # (start, end) column ranges where the trace is on the wrong groove, longest first
    edges = np.flatnonzero(np.diff(np.concatenate([[0], wrong.astype(int), [0]])))
    runs = list(zip(edges[::2], edges[1::2]))
    return sorted(runs, key=lambda run: run[0] - run[1])


def detail_columns(run, count=16, wrong_spots=4):
    # spot k: turn (k + 1/2) / count of the way out, at angle k x the golden
    # angle (evenly along the groove alone would repeat a few angles); up to
    # `wrong_spots` of them replaced by the middles of the longest wrong-groove runs
    theta = run.strip.theta
    golden = TAU * (1 - 1 / ((1 + 5**0.5) / 2))
    columns = []
    for k in range(count):
        target = theta[0] + (k + 0.5) / count * (theta[-1] - theta[0])
        angle = target + run.strip.spiral.phase  # angle about the center, as in strip.refit_basis
        target += wrap(k * golden - angle, TAU)
        columns.append(int(np.clip(np.searchsorted(theta, target), 0, len(theta) - 1)))
    for k, (start, end) in enumerate(wrong_runs(run.score.wrong_groove)[:wrong_spots]):
        columns[count - 1 - k] = (start + end) // 2
    return sorted(columns)


def strip_window(run, columns):
    middle = len(run.strip.theta) // 2
    start = max(0, middle - columns // 2)
    return slice(start, min(len(run.strip.theta), start + columns))


# ---------- Low resolution ----------


def low_res_input(run, path, detail_size, spots):
    low, card, scale = run.low, run.card, run.low.scale
    figure = new_figure(900, 900)
    axes = image_axes(figure)
    show_grey(axes, low.image, extent=(0, low.image.shape[1], low.image.shape[0], 0))
    for radius in (card.mark.r_inner, card.mark.r_outer):
        circle(axes, card.mark.x / scale, card.mark.y / scale, radius / scale, "white")
    plot_cross(axes, card.mark.x / scale, card.mark.y / scale, COLORS["mark"])
    plot_ring(axes, low.spiral.x / scale, low.spiral.y / scale, COLORS["low"], 10)
    plot_ring(axes, run.refit.x / scale, run.refit.y / scale, COLORS["refit"], 16)
    plot_cross(axes, card.spiral.x / scale, card.spiral.y / scale, COLORS["geometry"], 9)
    for spot in spots:
        left, top = detail_box(run, spot, detail_size)
        axes.add_patch(plt.Rectangle((left / scale, top / scale), detail_size / scale, detail_size / scale, fill=False, color=COLORS["label"], lw=1.5))
    axes.set_xlim(0, low.image.shape[1])
    axes.set_ylim(low.image.shape[0], 0)
    save(figure, path)


def spectrum(run, path):
    low = run.low
    size = low.spectrum.shape[0]
    quarter = size // 4
    figure = new_figure(900, 900)
    axes = image_axes(figure)
    central = low.spectrum[quarter:-quarter, quarter:-quarter]
    show_grey(axes, central, extent=(-quarter, quarter, quarter, -quarter), percentiles=(2, 99.9))
    for radius in low.window:
        circle(axes, 0, 0, radius, "white")
    circle(axes, 0, 0, low.peak_radius, COLORS["low"], dashed=False)
    save(figure, path)


def radial_profile(run, path):
    low, scale, card = run.low, run.low.scale, run.card
    size = low.spectrum.shape[0]
    radii = np.arange(60, 401)
    figure = new_figure(1040, 520)
    axes = figure.add_axes([0.05, 0.13, 0.93, 0.82])
    axes.axvspan(*low.window, color="white", alpha=0.12)
    for spacing, style, color in ((card.params.spacing, "--", "white"), (card.spacing, "-", COLORS["geometry"]), (low.fft_spacing, "-", COLORS["low"])):
        axes.axvline(size * scale / spacing, ls=style, color=color, lw=1.5)
    axes.plot(radii, low.profile[radii], color="#ddd", lw=1.5)
    ticks = [s for s in (80, 50, 35, 29, 25, 20, 15) if 60 <= size * scale / s <= 400]
    axes.set_xticks([size * scale / s for s in ticks], [str(s) for s in ticks])
    axes.set_xlabel("spacing (full-res px) → finer to the right")
    axes.set_yticks([])
    save(figure, path)


def coherence_map(run, path, half_width=30):
    # |Z| around the answer (low-res px half-width), in full-res coordinates
    low, card, scale = run.low, run.card, run.low.scale
    cx, cy = int(low.spiral.x / scale), int(low.spiral.y / scale)
    crop = np.abs(low.coherence_map[cy - half_width : cy + half_width, cx - half_width : cx + half_width])
    extent = tuple(np.array([cx - half_width, cx + half_width, cy + half_width, cy - half_width]) * scale)
    figure = new_figure(900, 900)
    axes = image_axes(figure)
    axes.imshow(crop, cmap="inferno", extent=extent, interpolation="nearest")
    plot_cross(axes, card.mark.x, card.mark.y, COLORS["mark"], 16)
    plot_ring(axes, low.spiral.x, low.spiral.y, COLORS["low"], 14)
    plot_cross(axes, card.spiral.x, card.spiral.y, COLORS["geometry"], 14)
    axes.set_xlim(extent[0], extent[1])
    axes.set_ylim(extent[2], extent[3])
    save(figure, path)


# ---------- Full resolution ----------


def detail(run, path, size, spot):
    # the whole spiral as polylines (consecutive columns are neighbours along the
    # groove), clipped by the axes; wrong-groove stretches in magenta, with dots
    # so that a single wrong column still shows
    left, top = detail_box(run, spot, size)
    figure = new_figure(900, 900)
    axes = image_axes(figure)
    show_grey(axes, run.image[top : top + size, left : left + size], extent=(left, left + size, top + size, top))
    trace_x, trace_y = spiral_points(run.strip.spiral, run.strip.theta, run.trace)
    true_x, true_y = spiral_points(run.strip.spiral, run.strip.theta, run.score.true_offset)
    wrong = run.score.wrong_groove
    axes.plot(true_x, true_y, "-", color=COLORS["true"], lw=7, alpha=0.55)  # truth: a wide line under the estimates
    axes.plot(trace_x, trace_y, "-", color=COLORS["trace"], lw=1.3)
    axes.plot(np.where(wrong, trace_x, np.nan), np.where(wrong, trace_y, np.nan), ".-", color=COLORS["wrong"], lw=2, ms=4)
    axes.set_xlim(left, left + size)
    axes.set_ylim(top + size, top)
    save(figure, path)


def offsets_explainer(path):
    # a cartoon of pane f: a toy card (4 turns; the rectangle's spiral has its
    # center 0.45 spacing off and its spacing 4% off), the groove's offset from
    # that spiral as the rectangle unrolls it, and the same offsets modulo the spacing
    true_spacing, center_error = 1.04, np.array([0.4, -0.2])
    strip_pitch, true_pitch = 1 / TAU, true_spacing / TAU
    theta = np.linspace(3 * TAU, 7 * TAU, 4000)
    strip_x, strip_y = strip_pitch * theta * np.cos(theta), strip_pitch * theta * np.sin(theta)
    true_x, true_y = center_error[0] + true_pitch * theta * np.cos(theta), center_error[1] + true_pitch * theta * np.sin(theta)
    radius = np.hypot(strip_x - center_error[0], strip_y - center_error[1])
    angle = np.unwrap(np.arctan2(strip_y - center_error[1], strip_x - center_error[0]))
    folded = -wrap(radius - true_pitch * angle, true_spacing)  # radial offset from the strip's spiral to the nearest groove
    unwrapped = np.unwrap(folded * TAU / true_spacing) * true_spacing / TAU
    unwrapped -= true_spacing * np.round(np.mean(unwrapped) / true_spacing)  # follow the groove nearest the strip's spiral
    turns = (theta - theta[0]) / TAU
    marks = {"A": 600, "B": 1450, "C": 3100}
    groove, strip, mark_color = COLORS["true"], COLORS["low"], COLORS["label"]

    figure = new_figure(900, 1300)
    top = figure.add_axes([0.0, 0.56, 0.56, 0.43])
    top.set_aspect("equal")
    top.set_axis_off()
    top.plot(true_x, true_y, color=groove, lw=2.5)
    top.plot(strip_x, strip_y, "--", color=strip, lw=1.5)
    top.plot(*center_error, "+", color=groove, ms=14, mew=2.5)
    top.plot(0, 0, "+", color=strip, ms=14, mew=2.5)
    for name, k in marks.items():
        direction = np.array([np.cos(theta[k]), np.sin(theta[k])])
        on_strip = np.array([strip_x[k], strip_y[k]])
        start, end = on_strip - 0.5 * direction, on_strip + 0.5 * direction
        top.plot([start[0], end[0]], [start[1], end[1]], color="#999", lw=5, alpha=0.5, solid_capstyle="butt")
        top.plot(*on_strip, "o", color=strip, ms=6)
        top.plot(*(on_strip + folded[k] * direction), "o", color=mark_color, ms=8)
        top.text(*(end + 0.4 * direction), name, color=mark_color, fontsize=16, weight="bold", ha="center", va="center")
    top.set_xlim(-7.9, 7.9)
    top.set_ylim(7.9, -7.9)
    notes = [
        ("A toy card, 4 turns", "#ddd"),
        ("", None),
        ("green: the real groove", groove),
        ("cyan, dashed: the spiral the", strip),
        ("  rectangle follows (low-res stage;", strip),
        ("  here its center is 0.45 spacing", strip),
        ("  off and its spacing 4% off)", strip),
        ("+: each spiral's center", "#ddd"),
        ("", None),
        ("grey bars: columns, each a radial", "#aaa"),
        ("  line \u00b1S/2 (one spacing) about", "#aaa"),
        ("  the cyan spiral (cyan dot)", "#aaa"),
        ("violet dot: the nearest groove", mark_color),
        ("  on that line; its distance from", mark_color),
        ("  the cyan dot (outward +) is the", mark_color),
        ("  column's offset", mark_color),
        ("", None),
        ("A, B, C: three columns,", mark_color),
        ("  followed in the plots below", mark_color),
    ]
    for row, (text, color) in enumerate(notes):
        if text:
            figure.text(0.585, 0.975 - row * 0.0215, text, color=color, fontsize=12.5, va="top")

    def offsets_axes(rect, title):
        axes = figure.add_axes(rect)
        axes.axhline(0, color=strip, ls="--", lw=1.5)
        axes.set_xlim(0, 4)
        axes.set_xlabel("column: turns along the rectangle (inner turns left)")
        axes.set_title(title, color="#ddd", fontsize=13, loc="left")
        return axes

    middle = offsets_axes([0.09, 0.285, 0.88, 0.225], "Unrolled: the grooves' offsets from the cyan spiral (outward up)")
    middle.axhspan(-0.5, 0.5, color="#555", alpha=0.35, lw=0)
    for copy in (-2, -1, 1, 2):
        middle.plot(turns, unwrapped + copy * true_spacing, color=groove, lw=1.2, alpha=0.4)
    middle.plot(turns, unwrapped, color=groove, lw=2.5)
    middle.set_ylim(-2.45, 2.45)
    middle.set_yticks([-2, -1, 0, 1, 2], ["\u22122S", "\u2212S", "0", "S", "2S"])
    middle.text(0.04, 2.2, "every turn of the groove, one spacing apart; grey: the \u00b1S/2 each column sums",
                color="#ccc", fontsize=11, va="center")
    middle.text(0.04, -2.2, "one wave per turn: the center error;  the slow rise: the spacing error",
                color="#ccc", fontsize=11, va="center")

    bottom = offsets_axes([0.09, 0.05, 0.88, 0.165], "Modulo S (pane f): nearest groove only; past \u00b1S/2 the next is nearer (arrow)")
    breaks = np.concatenate([[False], np.abs(np.diff(folded)) > true_spacing / 2])
    bottom.plot(turns, np.where(breaks, np.nan, folded), color=groove, lw=2.5)
    for edge in (-0.5, 0.5):
        bottom.axhline(edge * true_spacing, color="#888", ls=":", lw=1)
    jump = np.flatnonzero(breaks & (turns > 2.2))[0]
    bottom.annotate("", xy=(turns[jump], folded[jump]), xytext=(turns[jump - 1], folded[jump - 1]),
                    arrowprops=dict(arrowstyle="->", color="#fff", lw=1.5, connectionstyle="arc3,rad=0.5"))
    bottom.set_ylim(-0.66, 0.66)
    bottom.set_yticks([-0.5, 0, 0.5], ["\u2212S/2", "0", "S/2"])
    for axes in (middle, bottom):
        for name, k in marks.items():
            axes.plot(turns[k], folded[k], "o", color=mark_color, ms=8, zorder=5)
            axes.text(turns[k] - 0.07, folded[k], name, color=mark_color, fontsize=14, weight="bold", ha="right", va="center")
    save(figure, path)


def wedge_dots(run, cells, every_wedge=1):
    # the wedges as (column index, offset, grey brightness by |Z|)
    columns = np.interp(cells.theta, run.strip.theta, np.arange(len(run.strip.theta)))
    brightness = np.clip(cells.confidence, 0.25, 1)  # median wedge: white
    return columns[::every_wedge], cells.offsets[::every_wedge], np.stack([brightness[::every_wedge]] * 3, axis=1)


def offsets_mod_spacing(run, path):
    # pass 1's wedges (grey, brighter = higher |Z|) as offsets from the low-res
    # spiral, mod S; green the true groove, pale green the true spiral, yellow
    # the refit (the geometry model)
    strip, spacing = run.strip, run.strip.spiral.spacing
    true_offset = run.card.nearest_groove(*spiral_points(strip.spiral, strip.theta))[0]
    columns = np.arange(len(strip.theta))
    figure = new_figure(900, 900)
    axes = figure.add_axes([0.08, 0.06, 0.9, 0.92])
    x, offsets, grey = wedge_dots(run, run.wedges.first)
    axes.plot(columns[::40], wrap(true_offset[::40], spacing), ".", color=COLORS["true"], ms=1.5)
    axes.plot(columns[::5], wrap(ideal_offset(run.card, strip)[::5], spacing), ".", color=COLORS["geometry"], ms=1)
    axes.plot(columns[::5], wrap(run.model[::5], spacing), ".", color=COLORS["refit"], ms=1)
    axes.scatter(x, wrap(offsets, spacing), s=9, c=grey, zorder=3)
    axes.set_ylim(-spacing / 2, spacing / 2)
    axes.set_xlabel("column (inner turns left)")
    axes.set_ylabel("offset from the low-res spiral, px (mod spacing)")
    save(figure, path)


def offsets_vs_truth(run, path):
    # step f1 again, relative to the true spiral (pale green = 0, possible only
    # on a simulated card): yellow = the refit's remaining error, green = the
    # groove's drift, grey = the wedges; below, yellow alone at +-1 px
    strip, spacing, card = run.strip, run.strip.spiral.spacing, run.card
    ideal = ideal_offset(card, strip)
    true_offset = card.nearest_groove(*spiral_points(strip.spiral, strip.theta))[0]
    columns = np.arange(len(strip.theta))
    x, offsets, grey = wedge_dots(run, run.wedges.first)
    figure = new_figure(900, 900)
    axes = figure.add_axes([0.08, 0.33, 0.9, 0.65])
    axes.plot(columns[::40], wrap(true_offset[::40] - ideal[::40], spacing), ".", color=COLORS["true"], ms=1.5)
    axes.axhline(0, color=COLORS["geometry"], lw=1.5)
    axes.plot(columns[::5], wrap(run.model[::5] - ideal[::5], spacing), ".", color=COLORS["refit"], ms=1)
    axes.scatter(x, wrap(offsets - np.interp(x, columns, ideal), spacing), s=9, c=grey, zorder=3)
    axes.set_ylim(-spacing / 2, spacing / 2)
    axes.tick_params(labelbottom=False)
    axes.set_ylabel("offset from the true spiral, px (mod spacing)")
    zoom = figure.add_axes([0.08, 0.06, 0.9, 0.22], sharex=axes)
    zoom.axhline(0, color=COLORS["geometry"], lw=1.5)
    zoom.plot(columns[::5], wrap(run.model[::5] - ideal[::5], spacing), "-", color=COLORS["refit"], lw=1.5)
    zoom.set_ylim(-1, 1)
    zoom.set_ylabel("refit error, px")
    zoom.set_xlabel("column (inner turns left)")
    save(figure, path)


def rectangle_image(run, path, columns=1040):
    # the rectangle around the detail spot, rows +-1.6 S (outward up), each
    # column's mean removed; yellow the refitted spiral (+-S faint), violet
    # pass 2's rows, green (wide) the true groove, orange the path
    strip, spacing = run.strip, run.strip.spiral.spacing
    window = strip_window(run, columns)
    reach = int(round(1.6 * spacing))
    rows = np.arange(-reach, reach + 1, dtype=float)
    samples = sample_strip(run.image, strip.spiral, strip.theta[window], rows)
    samples -= samples.mean(axis=0)
    figure = new_figure(1040, 260)
    axes = image_axes(figure)
    count = window.stop - window.start
    show_grey(axes, samples[::-1], extent=(0, count, -reach, reach), aspect="auto")  # outward up
    axes.set_ylim(-reach, reach)
    x = np.arange(count)
    for shift, alpha in ((0, 0.9), (-spacing, 0.35), (spacing, 0.35)):
        axes.plot(x, run.model[window] + shift, color=COLORS["refit"], lw=1, alpha=alpha)
    for side in (-spacing / 2, spacing / 2):
        axes.plot(x, run.wedges.window[window] + side, color=COLORS["label"], lw=1)
    axes.plot(x, run.score.true_offset[window], color=COLORS["true"], lw=7, alpha=0.55)
    axes.plot(x, run.trace[window], color=COLORS["trace"], lw=1.3)
    save(figure, path)


def line_plot(path, series, ylabel, columns_label):
    figure = new_figure(1040, 280)
    axes = figure.add_axes([0.07, 0.12, 0.91, 0.84])
    for k, (values, color) in enumerate(series):  # the first series is the truth: wider, underneath
        axes.plot(values, color=color, lw=3.5 if k == 0 else 1.3, alpha=0.8 if k == 0 else 1)
    axes.set_ylabel(ylabel)
    axes.set_xlabel(columns_label)
    axes.grid(color="#333")
    save(figure, path)


def trace_offset(run, path, columns=1040):
    window = strip_window(run, columns)
    model = run.model[window]
    line_plot(path, [(run.score.true_offset[window] - model, COLORS["true"]), (run.trace[window] - model, COLORS["trace"])],
              "px from the refitted spiral", f"columns ({run.strip.step:g} px of groove each)")


def errors_per_turn(run, path):
    # per turn: the path's rms distance to the true groove (orange) and the
    # share on the wrong groove (magenta)
    score, theta = run.score, run.strip.theta
    figure = new_figure(1040, 220)
    axes = figure.add_axes([0.07, 0.18, 0.86, 0.78])
    share = axes.twinx()
    turn = np.floor((theta - theta[0]) / TAU).astype(int)
    counts = np.bincount(turn)
    rms = np.sqrt(np.bincount(turn, score.distance ** 2) / np.maximum(counts, 1))
    wrong = np.bincount(turn, score.wrong_groove) / np.maximum(counts, 1)
    axes.bar(np.arange(len(rms)), rms, width=0.7, color=COLORS["trace"])
    share.bar(np.arange(len(rms)), wrong, width=0.3, color=COLORS["wrong"])
    axes.axhline(run.card.spacing / 4, ls=":", color="#aaa")
    axes.set_ylim(0, max(run.card.spacing / 4 * 1.2, rms.max() * 1.1))
    axes.set_ylabel("rms px")
    axes.set_xlabel("turn, inner to outer")
    share.set_ylim(0, 1)
    share.set_ylabel("wrong groove")
    save(figure, path)


def sound(run, path, columns=350):
    window = strip_window(run, columns)
    line_plot(path, [(run.score.true_sound[window], COLORS["true"]), (run.sound[window], COLORS["trace"])],
              "relative depth", f"columns ({run.strip.step:g} px of groove each)")


# ---------- The unrolled rectangle and its wedges (cardlab/wedges.py) ----------


def rectangle_turns(run, path, turns=5, per_turn=4, sectors=40):
    # the unrolled rectangle along the low-res spiral: the same `per_turn`
    # wedges (same angles) of `turns` consecutive turns about the middle one,
    # stacked outward up. Each turn's rows are exactly -S/2..S/2 about its arm,
    # so the stack tiles the card with no gap or overlap (the turn boundaries,
    # dotted violet, are pass 1's rows). Violet solid: pass 2's rows (one
    # period about the midway line); violet vertical lines: wedge edges; green
    # (wide): the true groove; orange: the path. Turns are numbered from the
    # spiral's center (r = turn x S).
    wedges = run.wedges
    unrolled, spacing = wedges.unrolled, wedges.unrolled.spacing
    theta, wedge = unrolled.theta, unrolled.wedge
    middle = int(np.floor((theta[0] + theta[-1]) / 2 / TAU))
    first_turn = int(np.ceil(theta[0] / TAU))  # the first whole turn of the columns
    count = int(round(spacing))
    rows = (np.arange(count) + 0.5) / count * spacing - spacing / 2  # tiles -S/2..S/2
    figure = new_figure(1040, 120 + 110 * turns)
    axes = figure.add_axes([0.11, 70 / figure.bbox.height, 0.87, 1 - 90 / figure.bbox.height])
    for k, turn in enumerate(range(middle - turns // 2, middle - turns // 2 + turns)):
        lo = turn * sectors
        columns = np.flatnonzero((wedge >= lo) & (wedge < lo + per_turn))
        x = theta[columns] / TAU * sectors - lo  # in wedges
        base = k * spacing
        values, _ = unrolled.pull(columns, rows)
        show_grey(axes, values[::-1], extent=(x[0], x[-1], base - spacing / 2, base + spacing / 2), aspect="auto")
        for side in (-spacing / 2, spacing / 2):
            axes.plot(x, base + wedges.window[columns] + side, "-", color=COLORS["label"], lw=1.5)
        true = run.card.nearest_groove(*spiral_points(unrolled.spiral, theta[columns]))[0]
        axes.plot(x, base + true, color=COLORS["true"], lw=7, alpha=0.55)
        axes.plot(x, base + wedges.path[columns], color=COLORS["trace"], lw=1.5)
        axes.text(-0.04, base, f"turn {turn}\n(card {turn - first_turn + 1})", color="#ccc", fontsize=9,
                  ha="right", va="center")
    for k in range(turns + 1):
        axes.axhline((k - 0.5) * spacing, ls=":", color=COLORS["label"], lw=1.2)
    for edge in range(1, per_turn):
        axes.axvline(edge, color=COLORS["label"], lw=2)
    axes.set_xlim(0, per_turn)
    axes.set_ylim(-spacing / 2, (turns - 0.5) * spacing)
    axes.set_yticks([])
    axes.set_xticks(range(per_turn + 1))
    axes.set_xticklabels([f"{360 / sectors * w:g}°" for w in range(per_turn + 1)])
    axes.set_xlabel(f"angle along the turn (wedges of {360 / sectors:g}°); outward up, one band of S per turn")
    save(figure, path)


def wedges_on_card(run, path, size=320):
    # a full-res crop at the default detail spot: pass 2's rows (violet: the
    # midway line +- S/2 along each turn) and the wedge edges (violet, radial),
    # on the low-res spiral; the true groove (green, wide) and the path (orange)
    spot = detail_spot(run)
    left, top = detail_box(run, spot, size)
    wedges = run.wedges
    unrolled, half = wedges.unrolled, wedges.unrolled.spacing / 2
    low, theta = unrolled.spiral, unrolled.theta
    figure = new_figure(900, 900)
    axes = image_axes(figure)
    show_grey(axes, run.image[top : top + size, left : left + size], extent=(left, left + size, top + size, top))
    for side in (-half, half):
        axes.plot(*spiral_points(low, theta, wedges.window + side), "-", color=COLORS["label"], lw=1, alpha=0.8)
    edges = np.flatnonzero(np.diff(unrolled.wedge))
    x0, y0 = spiral_points(low, theta[edges], wedges.window[edges] - half)
    x1, y1 = spiral_points(low, theta[edges], wedges.window[edges] + half)
    gap = np.full_like(x0, np.nan)
    axes.plot(np.stack([x0, x1, gap]).T.ravel(), np.stack([y0, y1, gap]).T.ravel(), "-", color=COLORS["label"], lw=1, alpha=0.8)
    axes.plot(*spiral_points(low, theta, run.score.true_offset), "-", color=COLORS["true"], lw=7, alpha=0.55)
    axes.plot(*spiral_points(low, theta, wedges.path), "-", color=COLORS["trace"], lw=1.3)
    axes.set_xlim(left, left + size)
    axes.set_ylim(top + size, top)
    save(figure, path)


def about_refit(run):
    # along the groove, offsets from the refitted spiral: the path's columns
    # (theta, path, truth) and the final wedges (theta, offsets)
    wedges, low, refit, spacing = run.wedges, run.strip.spiral, run.refit, run.strip.spiral.spacing
    theta, path = offsets_about(refit, *spiral_points(low, run.strip.theta, run.trace))
    true = run.card.nearest_groove(*spiral_points(refit, theta))[0]
    at_wedge = np.interp(wedges.final.theta, run.strip.theta, run.trace)
    wedge_theta, wedge_path = offsets_about(refit, *spiral_points(low, wedges.final.theta, at_wedge))
    wedge_offsets = wedge_path + wrap(wedges.final.offsets - at_wedge, spacing)
    return theta, path, true, wedge_theta, wedge_offsets


def turns_rows(run, path, row_height=48, y_range=12, errors=False):
    # one row per turn, 2 pi wide: offsets from the refitted spiral vs. angle;
    # green (wide) the truth, grey dots the wedges (brighter = higher |Z|),
    # orange the path. errors: each minus the truth (green: the zero line)
    spacing, confidence = run.strip.spiral.spacing, run.wedges.final.confidence
    theta, trace, true, wedge_theta, wedge_offsets = about_refit(run)
    order = np.argsort(theta)
    if errors:
        wedge_offsets = wrap(wedge_offsets - np.interp(wedge_theta, theta[order], true[order]), spacing)
        trace, true = wrap(trace - true, spacing), np.zeros_like(true)
    turn_of = lambda th: np.floor(th / TAU).astype(int)
    turns = np.arange(turn_of(theta.min()), turn_of(theta.max()) + 1)
    total = 70 + row_height * len(turns)
    figure = new_figure(900, total)
    for row, turn in enumerate(turns):
        axes = figure.add_axes([0.07, 1 - (20 + row_height * (row + 1)) / total, 0.91, 0.92 * row_height / total])
        keep = order[turn_of(theta[order]) == turn]
        angle = np.degrees(np.mod(theta[keep], TAU))
        axes.axhline(0, color="#333", lw=0.8)
        axes.plot(angle, true[keep], color=COLORS["true"], lw=3, alpha=0.8)
        axes.plot(angle, trace[keep], color=COLORS["trace"], lw=1)
        in_turn = turn_of(wedge_theta) == turn
        axes.scatter(np.degrees(np.mod(wedge_theta[in_turn], TAU)), wedge_offsets[in_turn], s=9,
                     c=np.stack([np.clip(confidence[in_turn], 0.25, 1)] * 3, axis=1), zorder=3)
        axes.set_xlim(0, 360)
        axes.set_ylim(-y_range, y_range)
        axes.set_yticks([])
        axes.text(-4, 0, str(turn), color="#999", fontsize=8, ha="right", va="center")
        axes.tick_params(labelbottom=row == len(turns) - 1)
    axes.set_xlabel(f"angle (degrees); one row per turn (number from the center at left), inner at the top; each row ±{y_range} px")
    save(figure, path)
