from dataclasses import dataclass, replace

import numpy as np
from scipy.ndimage import gaussian_filter1d, map_coordinates
from scipy.optimize import least_squares

from .geometry import TAU, spiral_points, wrap

# The full-res stage works on an "unrolled strip": columns along a spiral
# (one every `column_step` px of groove), each a radial line through it.


@dataclass
class StripSettings:
    column_step: float = 3.0        # px of groove between columns
    turns: float = 0                # 0: all turns, else that many in the middle
    refit_search: float = 1.5       # spacings, center search of the refit
    trace_smoothing: float = 48     # px along the groove
    reference_smoothing: float = 300


@dataclass
class Strip:
    spiral: object
    theta: np.ndarray
    step: float
    demod: np.ndarray               # complex, one per column
    offsets: np.ndarray             # groove offset from the spiral (mod spacing), px
    confidence: np.ndarray


def strip_columns(spiral, mark, step, turns=0):
    pitch, spacing = spiral.pitch, spiral.spacing
    theta_first = spiral.theta_at(mark.r_inner + 1.5 * spacing)
    theta_last = spiral.theta_at(mark.r_outer - 1.5 * spacing)
    if turns and (theta_last - theta_first) / TAU > turns:
        middle = (theta_first + theta_last) / 2
        theta_first, theta_last = middle - turns * np.pi, middle + turns * np.pi
    # equal steps in arc length s = pitch * (theta - phase)^2 / 2
    t0, t1 = theta_first - spiral.phase, theta_last - spiral.phase
    arc = np.arange(pitch * t0**2 / 2, pitch * t1**2 / 2, step)
    return np.sqrt(2 * arc / pitch) + spiral.phase


def sample_at(image, x, y):
    # bilinear samples at arbitrary points (pixel centers at i + 0.5); scipy's
    # map_coordinates interpolates exactly, where cv2.remap rounds the
    # weights to 1/32 px
    coords = np.stack([np.ravel(y) - 0.5, np.ravel(x) - 0.5])
    return map_coordinates(image, coords, order=1, mode="nearest").reshape(np.shape(x))


def sample_strip(image, spiral, theta, offsets, centers=0.0):
    # rows at `offsets` (px, outward +) from a center line per column (default: the spiral)
    rows = np.asarray(offsets)[:, None] + np.asarray(centers)[None, ...]
    x, y = spiral_points(spiral, theta[None, :], rows)
    return sample_at(image, x, y)


def row_offsets(spacing, half_width=1.0):
    reach = int(np.ceil(half_width * spacing))
    return np.arange(-reach, reach + 1, dtype=float)


def demodulate(samples, rows, spacing, half_width=1.0):
    # remove each column's linear trend, then correlate with e^{-2 pi i d / S}
    # under a cos^2 window: a groove at offset o gives Z the angle -2 pi o / S
    trend = samples.mean(axis=0) + np.outer(rows, (rows @ samples) / (rows @ rows))
    window = np.cos(np.pi * rows / (2 * half_width * spacing)) ** 2 * (np.abs(rows) < half_width * spacing)
    carrier = window * np.exp(-1j * TAU * rows / spacing)
    return carrier @ (samples - trend)


def offsets_from(demod, spacing, smoothing_columns=0):
    if smoothing_columns > 0:
        demod = gaussian_filter1d(demod.real, smoothing_columns) + 1j * gaussian_filter1d(demod.imag, smoothing_columns)
    return -spacing * np.angle(-demod) / TAU, np.abs(demod)


def build_strip(image, spiral, mark, settings):
    theta = strip_columns(spiral, mark, settings.column_step, settings.turns)
    rows = row_offsets(spiral.spacing)
    demod = np.concatenate([
        demodulate(sample_strip(image, spiral, chunk, rows), rows, spiral.spacing)
        for chunk in np.array_split(theta, max(1, len(theta) // 20000))
    ])
    offsets, confidence = offsets_from(demod, spiral.spacing)
    return Strip(spiral, theta, settings.column_step, demod, offsets, confidence)


# ---------- Geometry refit ----------
# Relative to the strip's spiral, a center error (ex, ey), a spacing error beta
# and a spiral-phase error show up in the offsets as
#   o(theta) = a + beta (theta - theta_0) + ex cos(alpha) + ey sin(alpha)   (mod S)


def refit_basis(strip):
    angle = strip.theta
    return np.stack([np.ones_like(angle), strip.theta - strip.theta[0], np.cos(angle), np.sin(angle)], axis=1)


def circular_score(offsets, weights, model, spacing):
    return np.abs(np.sum(weights * np.exp(1j * TAU * (offsets - model) / spacing), axis=-1))


def refit_start(strip, search, every=20):
    # grid over beta (+-2.5 %, steps moving the last turn by S/4) and the
    # center error (+-search spacings, steps S/4); the constant comes out as the angle of the sum
    spacing, pitch = strip.spiral.spacing, strip.spiral.pitch
    basis = refit_basis(strip)[::every]
    offsets, weights = strip.offsets[::every], strip.confidence[::every]
    beta_step = spacing / 4 / (strip.theta[-1] - strip.theta[0])
    betas = np.arange(-np.ceil(0.025 * pitch / beta_step), np.ceil(0.025 * pitch / beta_step) + 1) * beta_step
    shifts = np.arange(-np.ceil(4 * search), np.ceil(4 * search) + 1) * spacing / 4
    ex, ey = [grid.ravel() for grid in np.meshgrid(shifts, shifts)]
    best_score, best = -1, None
    for beta in betas:
        model = beta * basis[:, 1] + np.outer(ex, basis[:, 2]) + np.outer(ey, basis[:, 3])
        scores = circular_score(offsets, weights, model, spacing)
        if scores.max() > best_score:
            k = int(np.argmax(scores))
            phasor = np.sum(weights * np.exp(1j * TAU * (offsets - model[k]) / spacing))
            best_score, best = scores[k], np.array([spacing * np.angle(phasor) / TAU, beta, ex[k], ey[k]])
    return best


def refit_geometry(strip, settings):
    spacing = strip.spiral.spacing
    basis = refit_basis(strip)
    root_weights = np.sqrt(strip.confidence / strip.confidence.mean())
    residuals = lambda q: root_weights * wrap(strip.offsets - basis @ q, spacing)
    fit = least_squares(residuals, refit_start(strip, settings.refit_search), loss="soft_l1", f_scale=0.1 * spacing)
    a, beta, ex, ey = fit.x
    pitch = strip.spiral.pitch + beta
    phase = (strip.spiral.pitch * strip.spiral.phase - a + beta * strip.theta[0]) / pitch
    spiral = replace(strip.spiral, x=strip.spiral.x + ex, y=strip.spiral.y - ey, pitch=pitch, phase=phase)  # ey is up
    return spiral, basis @ fit.x


# ---------- Trace ----------


def lock_trace(strip, model, settings):
    # reference = refitted spiral + slowly varying residual (kept within +-S/2);
    # each column takes the groove nearest the reference
    spacing, step = strip.spiral.spacing, strip.step
    offsets, confidence = offsets_from(strip.demod, spacing, settings.trace_smoothing / step)
    phasor = confidence * np.exp(1j * TAU * (offsets - model) / spacing)
    sigma = settings.reference_smoothing / step
    slow = gaussian_filter1d(phasor.real, sigma) + 1j * gaussian_filter1d(phasor.imag, sigma)
    reference = model + spacing * np.angle(slow) / TAU
    return reference + wrap(offsets - reference, spacing)
