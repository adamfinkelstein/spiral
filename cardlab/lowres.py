from dataclasses import dataclass

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares
from scipy.signal import fftconvolve
from scipy.special import j0

from .geometry import TAU, Spiral, pitch_of, smoothstep

LOW_SIZE = 1024


@dataclass
class LowResSettings:
    turn_weight_power: float = 0.5   # FFT input weighted by r^-power about the mark
    spacing_window: float = 0.1      # search ± this fraction of the nominal spacing
    spacing_tolerance: float = 0.03  # farther than this from nominal: use nominal
    fit_radius: float = 2.5          # spacings about the map's peak, for the ring-pattern fit


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
    coherence_map: np.ndarray        # complex Z at every low-res pixel
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


# ---------- Center, spacing and phase: the spiral coherence map ----------
# About the true center the height has a component -cos(r/pitch - angle + phase),
# so Z(c) = -sum_p v(p) exp(-i (|p - c|/pitch - angle(p - c))) is ~ (n/2) e^{i phase}
# at c = center and small elsewhere. As a function of the candidate center it is
# a sum of plane waves of one wavelength (the spacing S), Z(c) ~ a J0(2 pi |c - c0| / S):
# a bright spot ringed by fainter rings. It is a correlation of the image with a
# "spiral wave" kernel, so one FFT gives it at every pixel; a fit of the J0
# pattern around its peak gives the center to a fraction of a pixel.


def spiral_wave_kernel(pitch, reach):
    # K(-q) for K(q) = exp(-i (|q|/pitch - angle(q))), zero beyond `reach` px
    q = np.arange(-reach, reach + 1, dtype=float)
    qx, qy = np.meshgrid(-q, -q)
    radius = np.hypot(qx, qy)
    return np.where(radius <= reach, np.exp(-1j * (radius / pitch - np.arctan2(qy, qx))), 0)


def coherence_map(image, pitch, reach):
    return -fftconvolve(image, spiral_wave_kernel(pitch, reach), mode="same")


def map_peak(z_map):
    row, col = np.unravel_index(np.argmax(np.abs(z_map)), z_map.shape)
    return np.array([col + 0.5, row + 0.5])


def map_points_near(z_map, center, radius):
    rows, cols = np.mgrid[0 : z_map.shape[0], 0 : z_map.shape[1]]
    near = np.hypot(cols + 0.5 - center[0], rows + 0.5 - center[1]) <= radius
    return np.stack([cols[near] + 0.5, rows[near] + 0.5], axis=1), z_map[near]


def ring_pattern(points, center, spacing):
    return j0(TAU / spacing * np.hypot(points[:, 0] - center[0], points[:, 1] - center[1]))


def best_amplitude(pattern, values):
    return np.vdot(pattern, values) / np.vdot(pattern, pattern)


def fit_ring_pattern(points, values, start, spacing):
    # values ~ a J0(2 pi |c - c0| / S); for a given c0 the best complex a is linear
    def residuals(center):
        pattern = ring_pattern(points, center, spacing)
        misfit = values - best_amplitude(pattern, values) * pattern
        return np.concatenate([misfit.real, misfit.imag])

    center = least_squares(residuals, start, x_scale=spacing / 4).x
    return center, best_amplitude(ring_pattern(points, center, spacing), values)


def find_center(image, mark, scale, spacing, settings):
    pitch = pitch_of(spacing)
    z_map = coherence_map(image, pitch, reach=int(mark.r_outer / scale + 100))
    peak = map_peak(z_map)
    points, values = map_points_near(z_map, peak, settings.fit_radius * spacing)
    center, amplitude = fit_ring_pattern(points, values, peak, spacing)
    coherence = 2 * np.abs(amplitude) / np.sum(np.abs(image)) / (np.pi / 2)
    return Spiral(center[0], center[1], pitch, float(np.angle(amplitude))).scaled(scale), z_map, coherence


def low_res_stage(full, mark, nominal_spacing, settings=LowResSettings()):
    scale = full.shape[0] / LOW_SIZE
    nominal = nominal_spacing / scale
    mask = annulus_mask(LOW_SIZE, mark, scale, ramp=nominal)
    image = normalize_in_mask(downsample(full), mask)
    spectrum, profile, window, peak, measured, ok = fft_spacing(image, mask, mark, scale, nominal, settings)
    spacing = measured if ok else nominal
    spiral, z_map, coherence = find_center(image, mark, scale, spacing, settings)
    return LowResResult(scale, image, mask, spectrum, profile, window, peak, measured * scale, ok, z_map, coherence, spiral)
