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


def detail_spot(run):
    middle = len(run.strip.theta) // 2
    return spiral_points(run.strip.spiral, run.strip.theta[middle], run.trace[middle])


def strip_window(run, columns):
    middle = len(run.strip.theta) // 2
    start = max(0, middle - columns // 2)
    return slice(start, min(len(run.strip.theta), start + columns))


# ---------- Low resolution ----------


def low_res_input(run, path, detail_size):
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
    spot_x, spot_y = detail_spot(run)
    half = detail_size / 2 / scale
    axes.add_patch(plt.Rectangle((spot_x / scale - half, spot_y / scale - half), 2 * half, 2 * half, fill=False, color=COLORS["truth"], lw=1.5))
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


def detail(run, path, size):
    spot_x, spot_y = detail_spot(run)
    left, top = int(spot_x - size / 2), int(spot_y - size / 2)
    figure = new_figure(900, 900)
    axes = image_axes(figure)
    show_grey(axes, run.image[top : top + size, left : left + size], extent=(left, left + size, top + size, top))
    trace_x, trace_y = spiral_points(run.strip.spiral, run.strip.theta, run.trace)
    true_x, true_y = spiral_points(run.strip.spiral, run.strip.theta, run.score.true_offset)
    inside = (np.abs(trace_x - spot_x) < size / 2) & (np.abs(trace_y - spot_y) < size / 2)
    axes.plot(true_x[inside], true_y[inside], ".", color=COLORS["true"], ms=4)
    axes.plot(trace_x[inside], trace_y[inside], ".", color=COLORS["trace"], ms=4)
    wrong = inside & run.score.wrong_groove
    axes.plot(trace_x[wrong], trace_y[wrong], ".", color="#f0f", ms=5)
    axes.set_xlim(left, left + size)
    axes.set_ylim(top + size, top)
    save(figure, path)


def offsets_mod_spacing(run, path, every=40):
    strip, spacing = run.strip, run.strip.spiral.spacing
    columns = np.arange(len(strip.theta))
    smoothed, confidence = offsets_from(strip.demod, spacing, 24 / strip.step)  # smoothed over 24 px for display
    figure = new_figure(900, 900)
    axes = figure.add_axes([0.08, 0.06, 0.9, 0.92])
    shown = columns[::every]
    brightness = np.clip(2 * confidence[shown] / confidence[shown].max(), 0.15, 1)
    axes.scatter(shown, wrap(smoothed[shown], spacing), s=3, c=np.stack([brightness] * 3, axis=1))
    axes.plot(shown, wrap(run.score.true_offset[shown], spacing), ".", color=COLORS["true"], ms=1.5)
    axes.plot(columns[::5], wrap(ideal_offset(run.card, strip)[::5], spacing), ".", color=COLORS["truth"], ms=1)
    axes.plot(columns[::5], wrap(run.model[::5], spacing), ".", color=COLORS["refit"], ms=1)
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
