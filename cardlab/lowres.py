from dataclasses import dataclass

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import minimize

from .geometry import TAU, Spiral, pitch_of, smoothstep

LOW_SIZE = 1024


@dataclass
class LowResSettings:
    turn_weight_power: float = 0.5   # FFT input weighted by r^-power about the mark
    spacing_window: float = 0.1      # search ± this fraction of the nominal spacing
    spacing_tolerance: float = 0.03  # farther than this from nominal: use nominal
    search_radius: float = 60        # full-res px about the mark
    grid_step: float = 0.15          # spacings
    sample_fraction: float = 0.05    # of the annulus pixels, for the coherence


@dataclass
class LowResResult:
    scale: float
    image: np.ndarray
    mask: np.ndarray
    spectrum: np.ndarray
    profile: np.ndarray
    window: tuple
    peak_radius: float
    fft_spacing: float
    fft_ok: bool
    grid_centers: np.ndarray
    grid_scores: np.ndarray
    coherence: float
    spiral: Spiral


def downsample(full):
    return cv2.resize(full, (LOW_SIZE, LOW_SIZE), interpolation=cv2.INTER_AREA)


def pixel_radius(size, cx, cy):
    coords = np.arange(size) + 0.5
    return np.hypot(coords[None, :] - cx, coords[:, None] - cy)


def annulus_mask(size, mark, scale, ramp):
    r = pixel_radius(size, mark.x / scale, mark.y / scale)
    return smoothstep((r - mark.r_inner / scale) / ramp) * smoothstep((mark.r_outer / scale - r) / ramp)


def normalize_in_mask(image, mask):
    mean = np.sum(image * mask) / np.sum(mask)
    masked = (image - mean) * mask
    return masked / np.sqrt(np.sum(masked**2) / np.sum(mask))


def log_spectrum(image, mask):
    # the soft annulus mask is the window (no Hann on top: it starved the outer
    # turns; 10 seeds each of typical, loud and clean: spacing rms error
    # 0.071 -> 0.046 %, peak 11 -> 8 bins wide; hard cards about the same).
    # Subtract the mean inside the mask only, so the frame outside stays 0.
    centered = image - (np.sum(image * mask) / np.sum(mask)) * mask
    return np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(centered))))


def radial_profile(spectrum):
    size = spectrum.shape[0]
    radius = np.rint(pixel_radius(size, size / 2 + 0.5, size / 2 + 0.5)).astype(int).ravel()
    sums = np.bincount(radius, spectrum.ravel())
    counts = np.bincount(radius)
    return gaussian_filter1d(sums / np.maximum(counts, 1), 1)


def parabolic_peak(values, index):
    left, center, right = values[index - 1 : index + 2]
    curvature = left - 2 * center + right
    return index + (0.5 * (left - right) / curvature if curvature < 0 else 0.0)


def fft_spacing(image, mask, mark, scale, nominal, settings):
    size = image.shape[0]
    radius = pixel_radius(size, mark.x / scale, mark.y / scale)
    weight = np.maximum(radius, 2 * nominal) ** -settings.turn_weight_power
    spectrum = log_spectrum(image * weight / weight.mean(), mask)
    profile = radial_profile(spectrum)
    low = int(np.floor(size / ((1 + settings.spacing_window) * nominal)))
    high = int(np.ceil(size / ((1 - settings.spacing_window) * nominal)))
    best = low + int(np.argmax(profile[low : high + 1]))
    on_edge = best in (low, high)
    peak = best if on_edge else parabolic_peak(profile, best)
    spacing = size / peak
    ok = not on_edge and abs(spacing / nominal - 1) < settings.spacing_tolerance
    return spectrum, profile, (low, high), peak, spacing, ok


def sample_annulus(image, mask, fraction, rng):
    rows, cols = np.nonzero(mask > 0)
    keep = rng.random(len(rows)) < fraction
    return cols[keep] + 0.5, rows[keep] + 0.5, image[rows[keep], cols[keep]]


def spiral_coherence(x, y, values, cx, cy, pitch):
    # the height has a component -cos(r/pitch - angle + phase) about the true
    # center, so this sum is ~ (n/2) e^{i phase} there and small elsewhere
    dx, dy = x - cx, y - cy
    u = np.hypot(dx, dy) / pitch - np.arctan2(dy, dx)
    return -np.sum(values * np.exp(-1j * u), axis=-1)


def coherence_grid(x, y, values, center, pitch, radius, step):
    offsets = np.arange(-np.ceil(radius / step), np.ceil(radius / step) + 1) * step
    centers_x = center[0] + offsets
    scores = np.empty((len(offsets), len(offsets)))
    for row, cy in enumerate(center[1] + offsets):
        scores[row] = np.abs(spiral_coherence(x, y, values, centers_x[:, None], cy, pitch))
    return centers_x, center[1] + offsets, scores


def refine_center(x, y, values, start, step, mid_turn):
    # Nelder-Mead over (x, y, pitch * mid_turn): the third parameter is the
    # mid radius in px, so all three are in px and one tolerance fits them all
    to_params = lambda q: (q[0], q[1], q[2] / mid_turn)
    negative_coherence = lambda q: -np.abs(spiral_coherence(x, y, values, *to_params(q)))
    q0 = np.array([start[0], start[1], start[2] * mid_turn])
    simplex = np.array([q0, q0 + [step / 2, 0, 0], q0 + [0, step / 2, 0], q0 + [0, 0, step / 2]])
    result = minimize(negative_coherence, q0, method="Nelder-Mead",
                      options={"initial_simplex": simplex, "xatol": 0.005, "fatol": 1e-6 * abs(negative_coherence(q0))})
    return to_params(result.x)


def find_center(image, mask, mark, scale, spacing, settings, rng):
    x, y, values = sample_annulus(image, mask, settings.sample_fraction, rng)
    pitch = pitch_of(spacing)
    step = settings.grid_step * spacing
    subset = slice(None, None, max(1, len(x) // 8000))
    start_center = np.array([mark.x, mark.y]) / scale
    xs, ys, scores = coherence_grid(x[subset], y[subset], values[subset], start_center, pitch, settings.search_radius / scale, step)
    row, col = np.unravel_index(np.argmax(scores), scores.shape)
    mid_turn = (mark.r_inner + mark.r_outer) / 2 / scale / pitch  # theta at the middle of the annulus
    cx, cy, pitch = refine_center(x, y, values, np.array([xs[col], ys[row], pitch]), step, mid_turn)
    z = spiral_coherence(x, y, values, cx, cy, pitch)
    coherence = 2 * np.abs(z) / np.sum(np.abs(values)) / (np.pi / 2)
    grid_centers = np.stack(np.meshgrid(xs, ys), axis=-1) * scale
    return Spiral(cx, cy, pitch, float(np.angle(z))).scaled(scale), grid_centers, scores, coherence


def low_res_stage(full, mark, nominal_spacing, settings=LowResSettings(), seed=0):
    scale = full.shape[0] / LOW_SIZE
    nominal = nominal_spacing / scale
    mask = annulus_mask(LOW_SIZE, mark, scale, ramp=nominal)
    image = normalize_in_mask(downsample(full), mask)
    spectrum, profile, window, peak, measured, ok = fft_spacing(image, mask, mark, scale, nominal, settings)
    spacing = measured if ok else nominal
    rng = np.random.default_rng(seed)
    spiral, grid_centers, grid_scores, coherence = find_center(image, mask, mark, scale, spacing, settings, rng)
    return LowResResult(scale, image, mask, spectrum, profile, window, peak, measured * scale, ok,
                        grid_centers, grid_scores, coherence, spiral)
