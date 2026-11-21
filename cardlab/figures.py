import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .geometry import TAU, spiral_points, wrap
from .scoring import ideal_offset
from .strip import offsets_from, sample_strip

# One function per step figure; all draw on a dark background and save PNGs.

COLORS = {"mark": "white", "low": "#4cf", "refit": "#fd3", "truth": "#f44", "trace": "#f44", "true": "#3e6"}
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
    plot_cross(axes, card.spiral.x / scale, card.spiral.y / scale, COLORS["truth"], 9)
    for spot in spots:
        left, top = detail_box(run, spot, detail_size)
        axes.add_patch(plt.Rectangle((left / scale, top / scale), detail_size / scale, detail_size / scale, fill=False, color=COLORS["truth"], lw=1.2))
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
    for spacing, style, color in ((card.params.spacing, "--", "white"), (card.spacing, "-", COLORS["truth"]), (low.fft_spacing, "-", COLORS["low"])):
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
    plot_cross(axes, card.spiral.x, card.spiral.y, COLORS["truth"], 14)
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
    axes.plot(true_x, true_y, "-", color=COLORS["true"], lw=1.5)
    axes.plot(trace_x, trace_y, "-", color=COLORS["trace"], lw=1.5)
    axes.plot(np.where(wrong, trace_x, np.nan), np.where(wrong, trace_y, np.nan), ".-", color="#f0f", lw=2, ms=4)
    axes.set_xlim(left, left + size)
    axes.set_ylim(top + size, top)
    save(figure, path)


def offsets_explainer(path):
    # a cartoon of pane f: a toy card (4 turns; the strip's spiral has its center
    # 0.45 spacing off and its spacing 4% off), the groove's offset from the
    # strip's spiral as the strip unrolls it, and the same offsets modulo the spacing
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
    groove, strip, mark_color = COLORS["true"], COLORS["low"], "#f6f"

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
        start, end = on_strip - direction, on_strip + direction
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
        ("cyan, dashed: the spiral the strip", strip),
        ("  follows (from the low-res stage;", strip),
        ("  here its center is 0.45 spacing", strip),
        ("  off and its spacing 4% off)", strip),
        ("+: each spiral's center", "#ddd"),
        ("", None),
        ("grey bars: strip columns, each a", "#aaa"),
        ("  radial line \u00b11 spacing (S) about", "#aaa"),
        ("  the cyan spiral (cyan dot)", "#aaa"),
        ("magenta dot: the nearest groove", mark_color),
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
        axes.set_xlabel("column: turns along the strip (inner turns left)")
        axes.set_title(title, color="#ddd", fontsize=13, loc="left")
        return axes

    middle = offsets_axes([0.09, 0.285, 0.88, 0.225], "Unrolled: the grooves' offsets from the cyan spiral (outward up)")
    middle.axhspan(-1, 1, color="#555", alpha=0.35, lw=0)
    for copy in (-2, -1, 1, 2):
        middle.plot(turns, unwrapped + copy * true_spacing, color=groove, lw=1.2, alpha=0.4)
    middle.plot(turns, unwrapped, color=groove, lw=2.5)
    middle.set_ylim(-2.45, 2.45)
    middle.set_yticks([-2, -1, 0, 1, 2], ["\u22122S", "\u2212S", "0", "S", "2S"])
    middle.text(0.04, 2.2, "every turn of the groove, one spacing apart; grey: the \u00b1S each column samples",
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


def offsets_mod_spacing(run, path, strip, model, every=40):  # strip and model: those of the pass to show
    spacing = strip.spiral.spacing
    # true groove: distance from each column's point on the strip's spiral to the nearest groove centerline
    true_offset = run.card.nearest_groove(*spiral_points(strip.spiral, strip.theta))[0]
    columns = np.arange(len(strip.theta))
    smoothed, confidence = offsets_from(strip.demod, spacing, 24 / strip.step)  # smoothed over 24 px for display
    figure = new_figure(900, 900)
    axes = figure.add_axes([0.08, 0.06, 0.9, 0.92])
    shown = columns[::every]
    brightness = np.clip(2 * confidence[shown] / confidence[shown].max(), 0.15, 1)
    axes.scatter(shown, wrap(smoothed[shown], spacing), s=3, c=np.stack([brightness] * 3, axis=1))
    axes.plot(shown, wrap(true_offset[shown], spacing), ".", color=COLORS["true"], ms=1.5)
    axes.plot(columns[::5], wrap(ideal_offset(run.card, strip)[::5], spacing), ".", color=COLORS["truth"], ms=1)
    axes.plot(columns[::5], wrap(model[::5], spacing), ".", color=COLORS["refit"], ms=1)
    axes.set_ylim(-spacing / 2, spacing / 2)
    axes.set_xlabel("column (inner turns left)")
    axes.set_ylabel("offset from the strip's spiral, px (mod spacing)")
    save(figure, path)


def strip_image(run, path, columns=1040):
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
    axes.plot(x, run.score.true_offset[window], color=COLORS["true"], lw=1.5)
    axes.plot(x, run.trace[window], color=COLORS["trace"], lw=1.5)
    save(figure, path)


def line_plot(path, series, ylabel, columns_label):
    figure = new_figure(1040, 280)
    axes = figure.add_axes([0.07, 0.12, 0.91, 0.84])
    for values, color in series:
        axes.plot(values, color=color, lw=1.3)
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
    turn = np.floor((run.strip.theta - run.strip.theta[0]) / TAU).astype(int)
    counts = np.bincount(turn)
    rms = np.sqrt(np.bincount(turn, run.score.distance**2) / counts)
    wrong = np.bincount(turn, run.score.wrong_groove) / counts
    figure = new_figure(1040, 220)
    axes = figure.add_axes([0.07, 0.18, 0.86, 0.78])
    axes.bar(np.arange(len(rms)), rms, color="#6a8")
    axes.axhline(run.card.spacing / 4, ls=":", color="#aaa")
    axes.set_ylim(0, max(run.card.spacing / 4 * 1.2, rms.max() * 1.1))
    axes.set_ylabel("rms px")
    axes.set_xlabel("turn, inner to outer")
    share = axes.twinx()
    share.bar(np.arange(len(rms)), wrong, width=0.35, color=COLORS["truth"])
    share.set_ylim(0, 1)
    share.set_ylabel("wrong groove")
    save(figure, path)


def sound(run, path, columns=350):
    window = strip_window(run, columns)
    line_plot(path, [(run.score.true_sound[window], COLORS["true"]), (run.sound[window], COLORS["trace"])],
              "relative depth", f"columns ({run.strip.step:g} px of groove each)")
