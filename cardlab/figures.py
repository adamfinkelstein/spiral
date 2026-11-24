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
        target += wrap(k * golden - target, TAU)  # theta is the angle about the center
        columns.append(int(np.clip(np.searchsorted(theta, target), 0, len(theta) - 1)))
    for k, (start, end) in enumerate(wrong_runs(run.score.wrong_groove)[:wrong_spots]):
        columns[count - 1 - k] = (start + end) // 2
    return sorted(columns)


def strip_window(run, turns):
    # the columns of `turns` turns about the middle one (columns are equal steps in theta)
    columns = int(round(turns * TAU / (run.strip.theta[1] - run.strip.theta[0])))
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
    figure = new_figure(1040, 560)
    axes = figure.add_axes([0.05, 0.12, 0.93, 0.74])
    axes.axvspan(*low.window, color="white", alpha=0.12)
    axes.text(low.window[0] + 3, 0.03, "search region:\nexpected radius N/S$_0$ ± 50%", transform=axes.get_xaxis_transform(),
              color="#ccc", fontsize=10, va="bottom")
    # nominal, true and measured nearly coincide: the main plot shows only the
    # nominal; the inset (a zoom on the peak) shows all three, the truth wide
    # and faint underneath, the measurement thin on top
    lines = ((card.spacing, "-", COLORS["geometry"], 9, 0.7), (card.params.spacing, "--", "white", 1.5, 1),
             (low.fft_spacing, "-", COLORS["low"], 1.5, 1))
    axes.axvline(size * scale / card.params.spacing, ls="--", color="white", lw=1.5)
    axes.plot(radii, low.profile[radii], color="#ddd", lw=1.5)
    peak = size * scale / low.fft_spacing
    # inset: the 5 bins of the sub-bin fit (step 2) minus the trough line, as
    # the fit sees them, and its parabola, whose vertex is the measurement
    from .lowres import trough_line
    best = low.window[0] + int(np.argmax(low.profile[low.window[0]:low.window[1] + 1]))
    offsets = np.arange(-2, 3)
    line = trough_line(low.profile, best)
    a, b, c = np.polyfit(offsets, low.profile[best + offsets] - line(best + offsets), 2)
    fine = np.linspace(-2.5, 2.5, 200)
    inset = axes.inset_axes([0.62, 0.56, 0.36, 0.42])
    near = np.arange(best - 3, best + 4)
    inset.plot(near, low.profile[near] - line(near), "-", color="#ddd", lw=1.2)
    inset.plot(best + offsets, low.profile[best + offsets] - line(best + offsets), "o", color="#ddd", ms=4)
    inset.plot(best + fine, np.polyval([a, b, c], fine), color=COLORS["low"], lw=1.2, ls=":")
    for spacing, style, color, width, alpha in lines:
        inset.axvline(size * scale / spacing, ls=style, color=color, lw=min(width, 4), alpha=alpha)
    inset.set_xlim(best - 2.5, best + 2.5)
    shown = np.concatenate([low.profile[best + offsets] - line(best + offsets), np.polyval([a, b, c], fine)])
    inset.set_ylim(shown.min() - 0.1 * np.ptp(shown), shown.max() + 0.1 * np.ptp(shown))
    inset.set_yticks([])
    inset.set_xticks([])
    inset.text(0.5, -0.04, "the fit: 5 bins minus the trough line,\nand the parabola (cyan dotted)",
               transform=inset.transAxes, ha="center", va="top", fontsize=9.5, color="#ccc")
    inset.set_facecolor("black")
    top_bin = int(round(peak))
    axes.annotate("", xy=(peak, low.profile[top_bin]), xytext=(0.62, 0.62), textcoords="axes fraction",
                  arrowprops=dict(arrowstyle="->", color="#ccc", lw=1.2, shrinkA=0, shrinkB=4))
    ticks = [s for s in (80, 50, 35, 29, 25, 20, 15) if 60 <= size * scale / s <= 400]
    axes.set_xticks([size * scale / s for s in ticks], [str(s) for s in ticks])
    axes.set_xlabel("groove spacing (px in the full-res card image) → finer to the right")
    axes.set_xlim(radii[0], radii[-1])
    top = axes.secondary_xaxis("top")
    top.set_xlabel("radius in the FFT (bins of the 1024² low-res transform)")
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


def turns_along(run, theta):
    # turns from the first column (columns are equal steps in theta)
    return (theta - run.strip.theta[0]) / TAU


def wedge_dots(run, cells, every_wedge=1):
    # the wedges as (turns along the groove, offset, grey brightness by |Z|)
    columns = turns_along(run, cells.theta)
    brightness = np.clip(cells.confidence, 0.25, 1)  # median wedge: white
    return columns[::every_wedge], cells.offsets[::every_wedge], np.stack([brightness[::every_wedge]] * 3, axis=1)


def offsets_mod_spacing(run, path):
    # pass 1's wedges (grey, brighter = higher |Z|) as offsets from the low-res
    # spiral, mod S; green the true groove, pale green the true spiral, yellow
    # the refit (the geometry model)
    strip, spacing = run.strip, run.strip.spiral.spacing
    true_offset = run.card.nearest_groove(*spiral_points(strip.spiral, strip.theta))[0]
    columns = turns_along(run, strip.theta)
    figure = new_figure(900, 900)
    axes = figure.add_axes([0.08, 0.06, 0.9, 0.92])
    x, offsets, grey = wedge_dots(run, run.wedges.first)
    axes.plot(columns[::120], wrap(true_offset[::120], spacing), ".", color=COLORS["true"], ms=1.5)
    axes.plot(columns[::15], wrap(ideal_offset(run.card, strip)[::15], spacing), ".", color=COLORS["geometry"], ms=1)
    axes.plot(columns[::15], wrap(run.model[::15], spacing), ".", color=COLORS["refit"], ms=1)
    axes.scatter(x, wrap(offsets, spacing), s=9, c=grey, zorder=3)
    axes.set_ylim(-spacing / 2, spacing / 2)
    axes.set_xlabel("turns along the groove (inner turns left)")
    axes.set_ylabel("offset from the low-res spiral, px (mod spacing)")
    save(figure, path)


def offsets_vs_truth(run, path):
    # step 4c again, relative to the true spiral (pale green = 0, possible only
    # on a simulated card): yellow = the refit's remaining error, green = the
    # groove's drift, grey = the wedges; below, yellow alone at +-1 px
    strip, spacing, card = run.strip, run.strip.spiral.spacing, run.card
    ideal = ideal_offset(card, strip)
    true_offset = card.nearest_groove(*spiral_points(strip.spiral, strip.theta))[0]
    columns = turns_along(run, strip.theta)
    x, offsets, grey = wedge_dots(run, run.wedges.first)
    figure = new_figure(900, 900)
    axes = figure.add_axes([0.08, 0.33, 0.9, 0.65])
    axes.plot(columns[::120], wrap(true_offset[::120] - ideal[::120], spacing), ".", color=COLORS["true"], ms=1.5)
    axes.axhline(0, color=COLORS["geometry"], lw=1.5)
    axes.plot(columns[::15], wrap(run.model[::15] - ideal[::15], spacing), ".", color=COLORS["refit"], ms=1)
    axes.scatter(x, wrap(offsets - np.interp(x, columns, ideal), spacing), s=9, c=grey, zorder=3)
    axes.set_ylim(-spacing / 2, spacing / 2)
    axes.tick_params(labelbottom=False)
    axes.set_ylabel("offset from the true spiral, px (mod spacing)")
    zoom = figure.add_axes([0.08, 0.06, 0.9, 0.22], sharex=axes)
    zoom.axhline(0, color=COLORS["geometry"], lw=1.5)
    zoom.plot(columns[::15], wrap(run.model[::15] - ideal[::15], spacing), "-", color=COLORS["refit"], lw=1.5)
    zoom.set_ylim(-1, 1)
    zoom.set_ylabel("refit error, px")
    zoom.set_xlabel("turns along the groove (inner turns left)")
    save(figure, path)


def rectangle_image(run, path, turns=0.25):
    # the rectangle around the detail spot, rows +-1.6 S (outward up), each
    # column's mean removed; yellow the refitted spiral (+-S faint), violet
    # pass 2's rows, green (wide) the true groove, orange the path
    strip, spacing = run.strip, run.strip.spiral.spacing
    window = strip_window(run, turns)
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


def window_degrees(run, window):
    theta = run.strip.theta[window]
    return np.degrees(theta - theta[0])


def line_plot(path, x, series, ylabel, columns_label):
    figure = new_figure(1040, 300)
    axes = figure.add_axes([0.07, 0.19, 0.91, 0.78])
    for k, (values, color) in enumerate(series):  # the first series is the truth: wider, underneath
        axes.plot(x, values, color=color, lw=3.5 if k == 0 else 1.3, alpha=0.8 if k == 0 else 1)
    axes.set_xlim(x[0], x[-1])
    axes.set_ylabel(ylabel)
    axes.set_xlabel(columns_label)
    axes.grid(color="#333")
    save(figure, path)


def trace_offset(run, path, turns=0.25):
    window = strip_window(run, turns)
    model = run.model[window]
    line_plot(path, window_degrees(run, window), [(run.score.true_offset[window] - model, COLORS["true"]), (run.trace[window] - model, COLORS["trace"])],
              "px from the refitted spiral", "degrees along the groove (middle turn)")


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


def sound(run, path, turns=0.075):
    window = strip_window(run, turns)
    line_plot(path, window_degrees(run, window), [(run.score.true_sound[window], COLORS["true"]), (run.sound[window], COLORS["trace"])],
              "relative depth", "degrees along the groove (middle turn)")


# ---------- The unrolled rectangle and its wedges (cardlab/wedges.py) ----------


def rectangle_turns(run, path, turns=5, per_turn=4, sectors=40):
    # the unrolled rectangle along the low-res spiral: the same `per_turn`
    # wedges (same angles) of `turns` consecutive turns about the middle one,
    # stacked outward up. Each turn's rows are exactly -S/2..S/2 about its turn,
    # so the stack tiles the card with no gap or overlap (the turn boundaries,
    # dotted violet, are pass 1's rows). Violet solid: pass 2's rows (one
    # period about the midway line); violet vertical lines: wedge edges; green
    # (wide): the true groove; orange: the path. Turn n = floor(theta / 2 pi),
    # counted from the spiral's center, starts at 3 o'clock (r ~ (n - phi/2 pi) S).
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


def pass1_compare(run):
    # the full-res stage again with pass 1 on 1 px columns (before Nov 2026)
    # and on the default 4 px (now), timed; for step 4e
    from time import perf_counter
    from dataclasses import replace
    from .scoring import center_error, rms, score_trace, spacing_error
    from .wedges import WedgeSettings, run_wedges
    out = {}
    for name, step in (("before", 1.0), ("after", WedgeSettings().pass1_step)):
        start = perf_counter()
        wedge_run = run_wedges(run.image, run.low.spiral, run.card.mark, replace(WedgeSettings(), pass1_step=step))
        seconds = perf_counter() - start
        score = score_trace(run.card, run.strip, wedge_run.path)
        out[name] = {"run": wedge_run, "step": step, "seconds": seconds, "wedges": len(wedge_run.first.theta),
                     "columns": int(np.ceil(len(run.strip.theta) / step)),
                     "center": center_error(run.card, wedge_run.spiral), "spacing": spacing_error(run.card, wedge_run.spiral),
                     "path_rms": rms(score.distance)}
    return out


def pass1_before_after(run, compare, path):
    # step 4e: step 4 on every column (before) vs every 4th (now). Top: each
    # wedge's offset, 4 px minus 1 px (grey); middle: the refit's error against
    # the true spiral, before (wide, faint) and now (thin), yellow; bottom: the
    # path, now minus before (orange)
    before, after = compare["before"]["run"], compare["after"]["run"]
    spacing = run.strip.spiral.spacing
    columns = turns_along(run, run.strip.theta)
    ideal = ideal_offset(run.card, run.strip)
    match = np.clip(np.searchsorted(before.first.theta, after.first.theta), 1, len(before.first.theta) - 1)
    nearer = np.abs(before.first.theta[match - 1] - after.first.theta) < np.abs(before.first.theta[match] - after.first.theta)
    match = match - nearer
    wedge_change = wrap(after.first.offsets - before.first.offsets[match], spacing)
    x, _, grey = wedge_dots(run, after.first)
    figure = new_figure(900, 760)
    panels = [figure.add_axes([0.12, y, 0.86, 0.25]) for y in (0.71, 0.395, 0.08)]
    top, middle, bottom = panels
    top.scatter(x, wedge_change, s=9, c=grey)
    top.set_ylim(-0.05, 0.05)
    top.set_ylabel("wedges, px\n(4 px − 1 px)")
    middle.axhline(0, color=COLORS["geometry"], lw=1.5)
    middle.plot(columns[::15], wrap(before.model[::15] - ideal[::15], spacing), color=COLORS["refit"], lw=6, alpha=0.35)
    middle.plot(columns[::15], wrap(after.model[::15] - ideal[::15], spacing), color=COLORS["refit"], lw=1.3)
    middle.set_ylim(-0.5, 0.5)
    middle.set_ylabel("refit error, px\n(wide 1 px, thin 4 px)")
    bottom.plot(columns[::5], (after.path - before.path)[::5], color=COLORS["trace"], lw=1)
    bottom.set_ylim(-0.01, 0.01)
    bottom.set_ylabel("path, px\n(4 px − 1 px)")
    bottom.set_xlabel("turns along the groove (inner turns left)")
    for axes in panels:
        axes.set_xlim(columns[0], columns[-1])
        axes.grid(color="#333")
    for axes in (top, middle):
        axes.tick_params(labelbottom=False)
    save(figure, path)
    return wedge_change


def coherence_explainer(path):
    # a cartoon of step 3 (procedure.html): a toy spiral (spacing S = 1, spiral phase
    # phi), a candidate center c and a pixel p with the quantities in Z(c); the
    # kernel (a spiral wave); and |Z| against the distance of c from the true
    # center, |J0(2 pi e / S)|
    from matplotlib.patches import Arc
    from scipy.special import j0
    pitch, phase = 1 / TAU, 0.6
    groove, low, label, true_center = COLORS["true"], COLORS["low"], COLORS["label"], COLORS["geometry"]
    figure = new_figure(900, 760)
    axes = figure.add_axes([0.0, 0.29, 0.6, 0.71])
    from matplotlib import patheffects
    halo = [patheffects.withStroke(linewidth=4, foreground="black")]
    text = lambda x, y, words, color, **kw: axes.text(x, y, words, color=color, fontsize=kw.pop("fontsize", 11.5),
                                                     fontweight="bold", path_effects=halo, **kw)
    t = np.linspace(0, 6 * TAU, 4000)  # continued all the way in to the true center
    axes.plot(pitch * t * np.cos(t + phase), pitch * t * np.sin(t + phase), color=groove, lw=1.5, alpha=0.45)
    axes.plot([0], [0], "+", color=true_center, ms=14, mew=2)
    text(0, -0.75, "true center", true_center, ha="center")
    # the spiral phase: the turns cross the ray at angle phi at r = S, 2S, ...
    ray = np.array([0, 6.4])
    axes.plot(ray * np.cos(phase), ray * np.sin(phase), "--", color=true_center, lw=1)
    for n in range(1, 7):
        axes.plot(n * np.cos(phase), n * np.sin(phase), "o", color=true_center, ms=4)
    axes.add_patch(Arc((0, 0), 2.6, 2.6, theta1=0, theta2=np.degrees(phase), color=true_center, lw=1))
    axes.plot([0, 1.8], [0, 0], color=true_center, lw=0.8)
    text(1.45, 0.25, "φ", true_center, fontsize=14)
    text(6.7, 4.75, "spiral phase φ: turns\ncross at r = S, 2S, …\n(θ = φ + 2πn)", true_center, fontsize=10, ha="right")
    # the spacing S between two turns
    a = np.radians(205)
    r0 = pitch * ((a - phase) % TAU + 3 * TAU)
    axes.annotate("", xy=((r0 + 1) * np.cos(a), (r0 + 1) * np.sin(a)), xytext=(r0 * np.cos(a), r0 * np.sin(a)),
                  arrowprops=dict(arrowstyle="<->", color=label, lw=1.8))
    text((r0 + 0.5) * np.cos(a) - 0.2, (r0 + 0.5) * np.sin(a) - 0.8, "S = 2πb", label, fontsize=12, ha="center")
    # a candidate center c (above left of the true center) and a pixel p
    c = np.array([-1.2, 1.0])
    p = np.array([-2.6, 4.6])
    axes.plot(*c, "+", color=low, ms=14, mew=2.5)
    text(c[0] - 0.3, c[1] - 0.15, "c (candidate\ncenter)", low, ha="right", va="top")
    axes.plot(*p, "o", color=label, ms=8)
    text(p[0], p[1] + 0.35, "p (a pixel, value v(p))", label, ha="center")
    axes.plot([c[0], p[0]], [c[1], p[1]], color=label, lw=1.8)
    mid = (c + p) / 2
    text(mid[0] - 0.25, mid[1], "|q|, q = p − c", label, ha="right")
    axes.plot([c[0], c[0] + 1.8], [c[1], c[1]], color=label, lw=1)
    angle = np.degrees(np.arctan2(p[1] - c[1], p[0] - c[0]))
    axes.add_patch(Arc(tuple(c), 1.6, 1.6, theta1=0, theta2=angle, color=label, lw=1.2))
    text(c[0] + 0.75, c[1] + 0.85, "α$_q$", label, fontsize=14)
    axes.set_xlim(-6.8, 6.8)
    axes.set_ylim(-6.6, 6.8)
    axes.set_aspect("equal")
    axes.set_axis_off()
    # the kernel: Re e^{-i(|q|/b - alpha_q)}, a spiral wave of the same spacing
    kernel_axes = figure.add_axes([0.62, 0.40, 0.36, 0.45])
    q = np.linspace(-5, 5, 500)
    qx, qy = np.meshgrid(q, q)
    kernel = np.cos(np.hypot(qx, qy) / pitch - np.arctan2(qy, qx))
    kernel_axes.imshow(kernel, cmap="gray", extent=(-5, 5, -5, 5), origin="lower")
    kernel_axes.plot([0], [0], "+", color=low, ms=10, mew=2)
    kernel_axes.set_axis_off()
    kernel_axes.set_title("the kernel, centered on c:\nRe e$^{-iu}$, u = |q|/b − α$_q$", fontsize=10.5, color="#ccc")
    # |Z| against the distance e of c from the true center
    curve = figure.add_axes([0.09, 0.08, 0.88, 0.17])
    e = np.linspace(0, 2.2, 600)
    curve.plot(e, np.abs(j0(TAU * e)), color=COLORS["measured"], lw=2)
    for zero in (2.405, 5.520, 8.654):
        curve.axvline(zero / TAU, color=label, lw=0.8, ls=":")
    curve.text(2.405 / TAU + 0.02, 0.8, "0.38 S", color=label, fontsize=10)
    curve.set_xlim(0, 2.2)
    curve.set_ylim(0, 1.05)
    curve.set_xlabel("distance e of c from the true center, in spacings S")
    curve.set_ylabel("|Z(c)| / |Z(true)|")
    curve.text(1.0, 0.75, "|J$_0$(2π e / S)|: a bright spot, then rings half a spacing apart", color="#ccc", fontsize=10)
    curve.grid(color="#333")
    save(figure, path)


def spiral_coordinate_plot(path):
    # procedure.html step 3: the spiral coordinate u = |q|/b - alpha_q about
    # the true center of a toy spiral (S = 1, spiral phase 0.6), alpha_q in [0, 2 pi)
    # from 3 o'clock: along a ray a ramp, +2 pi per spacing; along the groove a
    # staircase (flat within a turn, +2 pi where alpha_q wraps, at 3 o'clock;
    # theta - phi = r / b = u + alpha_q, pale green, rises steadily);
    # around a circle a sawtooth; turns (green) where u = 2 pi n - phi
    pitch, phase = 1 / TAU, 0.6
    groove, label = COLORS["true"], COLORS["label"]
    wrapped = lambda a: a % TAU  # alpha_q in [0, 2 pi), from 3 o'clock
    figure = new_figure(900, 320)
    panels = [figure.add_axes([0.065 + k * 0.33, 0.19, 0.26, 0.6]) for k in range(3)]
    ray, along, circle = panels
    levels = [(TAU * n - phase) / TAU for n in range(-1, 9)]  # u / 2 pi on the turns
    # along a ray at angle alpha
    alpha = phase + 1.0
    r = np.linspace(2, 6, 400)
    u = r / pitch - alpha
    ray.plot(r, u / TAU, color="#ddd", lw=1.8)
    crossings = pitch * (alpha - phase + TAU * np.arange(2, 7))
    for x in crossings[(crossings >= 2) & (crossings <= 6)]:
        ray.axvline(x, color=groove, lw=2, alpha=0.8)
    ray.set_xlabel("r = |q|, in spacings")
    ray.set_title("along a ray: a ramp\n(+2π per spacing)", fontsize=10.5)
    # along the groove for four turns, starting just past the wrap
    turned = np.linspace(0, 4 * TAU - 0.02, 2000)
    start_angle, first = 1e-3, 3
    angle = start_angle + turned
    radius_along = pitch * (angle - phase + TAU * first)
    u_groove = radius_along / pitch - wrapped(angle)
    jumps = np.flatnonzero(np.diff(u_groove) > np.pi) + 1
    for piece in np.split(np.arange(len(turned)), jumps):
        along.plot(turned[piece] / TAU, u_groove[piece] / TAU, color=groove, lw=2.5)
    for k, edge in enumerate(np.concatenate([[0], turned[jumps], [turned[-1]]])[:-1]):
        along.text(edge / TAU + 0.5, u_groove[min(len(turned) - 1, int(np.searchsorted(turned, edge)) + 5)] / TAU + 0.18,
                   "n" if k == 0 else f"n+{k}", color=groove, ha="center", fontsize=9.5)
    for edge in turned[jumps]:
        along.axvline(edge / TAU, color=label, lw=0.9, ls=":")
    theta = radius_along / pitch  # theta - phi = r / b = u + alpha_q on the groove
    along.plot(turned / TAU, theta / TAU, color=COLORS["geometry"], lw=1.3, ls="--")
    along.text(1.35, theta[0] / TAU + 1.75, "(θ − φ)/2π\n= r/S", color=COLORS["geometry"], fontsize=10, ha="right")
    along.set_xlabel("turns along the groove")
    along.set_title("along the groove: u a staircase\n(+2π at 3 o'clock); r/S a ramp", fontsize=10.5)
    along.set_xticks([0, 1, 2, 3, 4])
    # around a circle of radius 4.3 S, one revolution
    radius = 4.3
    around = np.linspace(0, TAU, 600)
    u_circle = radius / pitch - wrapped(alpha + around)
    jumps = np.flatnonzero(np.abs(np.diff(u_circle)) > np.pi) + 1
    for piece in np.split(np.arange(len(around)), jumps):
        circle.plot(np.degrees(around[piece]), u_circle[piece] / TAU, color="#ddd", lw=1.8)
    for edge in around[jumps]:
        circle.axvline(np.degrees(edge), color=label, lw=0.9, ls=":")
    hits = (radius / pitch - alpha - (TAU * np.arange(-2, 10) - phase)) % TAU
    for x in np.unique(np.round(hits, 9)):
        circle.axvline(np.degrees(x), color=groove, lw=2, alpha=0.8)
    circle.set_xlabel("angle around the circle, °")
    circle.set_title("around a circle: a sawtooth\n(−2π per revolution)", fontsize=10.5)
    circle.set_xticks([0, 90, 180, 270, 360])
    for axes, values in ((ray, u), (along, np.concatenate([u_groove, theta])), (circle, u_circle)):
        low, high = values.min() / TAU - 0.3, values.max() / TAU + 0.4
        for level in levels:
            if low <= level <= high:
                axes.axhline(level, color=groove, lw=0.8, ls=":")
        axes.set_ylim(low, high)
        axes.grid(color="#333")
    ray.set_ylabel("u / 2π")
    along.set_ylabel("u / 2π,  r / S")
    save(figure, path)


def spiral_coordinate_map(path):
    # procedure.html step 3: u = |q|/b - alpha_q at every pixel about the
    # toy spiral's true center (S = 1, spiral phase 0.6): left u / 2 pi (rainbow;
    # the jump across the ray to the right, 3 o'clock, is where alpha_q wraps), right
    # u mod 2 pi (cyclic: no jump; all that e^{-iu} sees). Black: the turns.
    pitch, phase = 1 / TAU, 0.6
    extent = 4.5
    q = np.linspace(-extent, extent, 700)
    qx, qy = np.meshgrid(q, q)
    u = np.hypot(qx, qy) / pitch - np.arctan2(qy, qx) % TAU  # alpha_q in [0, 2 pi)
    t = np.linspace(0, 6 * TAU, 4000)
    spiral_x, spiral_y = pitch * t * np.cos(t + phase), pitch * t * np.sin(t + phase)
    figure = new_figure(900, 440)
    maps = ((u / TAU, "turbo", "u / 2π: jumps at 3 o'clock", None),
            ((u % TAU) / TAU, "hsv", "(u mod 2π) / 2π: no jump", (0, 1)))
    for k, (values, cmap, title, limits) in enumerate(maps):
        axes = figure.add_axes([0.02 + k * 0.5, 0.05, 0.38, 0.8])
        shown = axes.imshow(values, cmap=cmap, extent=(-extent, extent, -extent, extent), origin="lower",
                            vmin=None if limits is None else limits[0], vmax=None if limits is None else limits[1])
        axes.plot(spiral_x, spiral_y, color="black", lw=2)
        axes.plot([0], [0], "+", color="white", ms=10, mew=2)
        axes.set_xlim(-extent, extent)
        axes.set_ylim(-extent, extent)
        axes.set_axis_off()
        axes.set_title(title, fontsize=11)
        bar = figure.colorbar(shown, ax=axes, fraction=0.046, pad=0.02)
        bar.ax.tick_params(labelsize=9)
    save(figure, path)


def stretch_lobes(run, path, aspects=(1.0, 1.01, 1.02, 1.03), half_width=8):
    # procedure.html step 3, "why symmetry": the coherence map |Z| near the
    # true center of this card's low-res image stretched by x * aspect,
    # y / aspect about the true center (a slightly non-circular scan). Marks:
    # pale green + the true center, violet square the brightest pixel, cyan
    # ring the center of point symmetry. half_width in spacings.
    import cv2
    from .lowres import LowResSettings, coherence_map as z_of, pitch_of, symmetry_center, map_peak
    low, card, scale = run.low, run.card, run.low.scale
    spacing = low.spiral.spacing / scale
    truth = np.array([card.spiral.x, card.spiral.y]) / scale
    settings = LowResSettings()
    r_outer = card.mark.r_outer / scale
    figure = new_figure(900, 300)
    for k, aspect in enumerate(aspects):
        # output pixel p comes from input (p - c) / (aspect, 1/aspect) + c, pixel centers at i + 0.5
        matrix = np.array([[1 / aspect, 0, (truth[0] - 0.5) * (1 - 1 / aspect)], [0, aspect, (truth[1] - 0.5) * (1 - aspect)]])
        image = low.image if aspect == 1 else cv2.warpAffine(
            low.image.astype(np.float32), matrix, low.image.shape[::-1], flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_REFLECT)
        z_map = z_of(image, pitch_of(spacing), reach=int(np.ceil(r_outer + 2 * spacing)))
        center = symmetry_center(z_map, settings.symmetry_window * r_outer, settings.symmetry_search)
        peak = map_peak(z_map)
        reach = half_width * spacing
        lo = (truth - reach).astype(int)
        hi = (truth + reach).astype(int) + 1
        crop = np.abs(z_map[lo[1]:hi[1], lo[0]:hi[0]])
        to_s = lambda point: (np.asarray(point) - truth) / spacing  # spacings from the true center
        axes = figure.add_axes([0.01 + k * 0.25, 0.02, 0.23, 0.72])
        axes.imshow(crop, cmap="inferno", interpolation="bicubic",
                    extent=(*(to_s(lo) * [1, 0] + to_s(hi) * [0, 1])[[0]], to_s(hi)[0], to_s(hi)[1], to_s(lo)[1]))
        axes.plot(*to_s(truth), "+", color=COLORS["geometry"], ms=12, mew=2)
        axes.plot(*to_s(peak), "s", mfc="none", mec=COLORS["label"], ms=9, mew=1.8)
        axes.plot(*to_s(center), "o", mfc="none", mec=COLORS["low"], ms=11, mew=1.8)
        axes.set_xlim(-half_width, half_width)
        axes.set_ylim(half_width, -half_width)
        axes.set_axis_off()
        off = np.hypot(*to_s(peak))
        axes.set_title(f"{'not stretched' if aspect == 1 else f'stretched {100 * (aspect - 1):.0f}%'}\n"
                       f"brightest pixel: {off:.1f} S off\nsymmetry center: {np.hypot(*to_s(center)) * spacing * scale:.1f} px off",
                       fontsize=9.5)
    save(figure, path)
