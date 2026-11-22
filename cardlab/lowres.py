from dataclasses import dataclass

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d, map_coordinates
from scipy.signal import fftconvolve

from .geometry import Spiral, pitch_of, smoothstep

LOW_SIZE = 1024


class SpacingNotFound(Exception):
    # no clear peak: the profile's maximum is on the edge of the search window,
    # or it stands less than min_prominence above the trough line.
    # The card fails here (falling back to the nominal would be up to ~33% off,
    # far outside what the later steps survive: experiments/spacing_budget.py)
    pass


@dataclass
class LowResSettings:
    turn_weight_power: float = 0.5   # FFT input weighted by r^-power about the mark
    spacing_window: float = 0.5      # search ± this fraction of the expected peak radius (frequency): 0.5-1.5 x size / nominal
    profile_smoothing: float = 1.0   # bins, Gaussian, before the peak search
    min_prominence: float = float(np.log(2))  # peak at least 2x its background (log magnitude above the trough line)
    symmetry_window: float = 1 / 8   # sigma of the Gaussian window about the map's peak, x the marked outer radius
    symmetry_search: float = 1.5     # the symmetry center lies within this many sigma of the peak


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


def radial_profile(spectrum, smoothing):
    size = spectrum.shape[0]
    radius = np.rint(pixel_radius(size, size / 2 + 0.5, size / 2 + 0.5)).astype(int).ravel()
    sums = np.bincount(radius, spectrum.ravel())
    counts = np.bincount(radius)
    profile = sums / np.maximum(counts, 1)
    return gaussian_filter1d(profile, smoothing) if smoothing > 0 else profile


def trough_line(profile, index):
    # the local background under a peak: a line through the profile at the
    # halfway troughs, 0.5 and 1.5 x the peak's radius
    x1, x2 = 0.5 * index, 1.5 * index
    y1, y2 = np.interp([x1, x2], np.arange(len(profile)), profile)
    return lambda x: y1 + (y2 - y1) / (x2 - x1) * (np.asarray(x) - x1)


def peak_prominence(profile, index):
    # height of the peak above that background, in log magnitude (a log ratio)
    return float(profile[index] - trough_line(profile, index)(index))


def peak_without_slope(profile, index):
    # sub-bin peak position: subtract the local background (trough_line) from the
    # 5 bins around the peak, then the vertex of a least-squares parabola. The
    # peak sits on a falling background, which pulls a plain parabola toward
    # smaller radii (Nov 2026: cards 0.049 -> 0.024 % median spacing error).
    offsets = np.arange(-2, 3)
    values = profile[index - 2 : index + 3] - trough_line(profile, index)(index + offsets)
    a, b, _ = np.polyfit(offsets, values, 2)
    vertex = -b / (2 * a) if a < 0 else 0.0
    return index + float(np.clip(vertex, -2, 2))


def fft_spacing(image, mask, mark, scale, nominal, settings):
    size = image.shape[0]
    radius = pixel_radius(size, mark.x / scale, mark.y / scale)
    weight = np.maximum(radius, 2 * nominal) ** -settings.turn_weight_power
    spectrum = log_spectrum(image * weight / weight.mean(), mask)
    profile = radial_profile(spectrum, settings.profile_smoothing)
    # window in frequency, about the expected peak radius size / nominal: from
    # halfway to zero frequency to halfway to the second harmonic (window 0.5),
    # so for a true spacing within ~0.67-1.33 x nominal only the fundamental fits
    expected = size / nominal
    low = int(np.floor((1 - settings.spacing_window) * expected))
    high = int(np.ceil((1 + settings.spacing_window) * expected))
    best = low + int(np.argmax(profile[low : high + 1]))
    on_edge = best in (low, high)
    peak = best if on_edge else peak_without_slope(profile, best)
    spacing = size / peak
    # no reliable spacing: a maximum on the window's edge, or a weak one
    # (correct peaks on cards and drawn spirals: >= 0.89; wrong ones not on the
    # edge: <= 0.41; experiments/spacing_prominence.py)
    ok = not on_edge and peak_prominence(profile, best) >= settings.min_prominence
    return spectrum, profile, (low, high), peak, spacing, ok


# ---------- Center, spacing and phase: the spiral coherence map ----------
# About the true center the height has a component -cos(r/pitch - angle + phase),
# so Z(c) = -sum_p v(p) exp(-i (|p - c|/pitch - angle(p - c))) is ~ (n/2) e^{i phase}
# at c = center and small elsewhere: every turn adds in step there. It is a
# correlation of the image with a "spiral wave" kernel, so one FFT gives it at
# every pixel. Near the center it is a bright spot ringed by fainter rings, but
# if the card is stretched even 1% (turns reach ~95 spacings out) the turns no
# longer add in step, the spot splits into lobes and the brightest pixel is 2+
# spacings off. The map stays symmetric under a 180-degree turn about the
# center, so the center is the map's center of point symmetry near its peak,
# and the phase is the angle of Z there.


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


def map_at(z_map, point):
    # bilinear, pixel i's center at i + 0.5
    coords = [[point[1] - 0.5], [point[0] - 0.5]]
    return complex(map_coordinates(z_map.real, coords, order=1)[0], map_coordinates(z_map.imag, coords, order=1)[0])


def parabola_offset(left, middle, right):
    curvature = left - 2 * middle + right
    return 0.5 * (left - right) / curvature if curvature < 0 else 0.0


def symmetry_center(z_map, sigma, search=1.5):
    # g = (|Z| - its window mean) * a Gaussian window (sigma px) about the peak,
    # on a crop of +-3 sigma. C = g * g (self-convolution) is largest at index
    # sums i1 + i2 = 2 c - 1, where every term is g^2; searched for c within
    # `search` sigma of the peak, in half-pixel steps, then a parabola along x
    # and y. (Same rule as coherence.js symmetryCenter.)
    peak = map_peak(z_map)
    half = int(np.ceil(3 * sigma))
    col0, row0 = max(int(peak[0]) - half, 0), max(int(peak[1]) - half, 0)
    crop = np.abs(z_map[row0 : int(peak[1]) + half + 1, col0 : int(peak[0]) + half + 1])
    rows, cols = np.mgrid[0 : crop.shape[0], 0 : crop.shape[1]]
    window = np.exp(-((cols + col0 + 0.5 - peak[0]) ** 2 + (rows + row0 + 0.5 - peak[1]) ** 2) / (2 * sigma**2))
    g = window * (crop - np.sum(window * crop) / np.sum(window))
    conv = fftconvolve(g, g, mode="full")
    center_k = np.round(2 * peak - 1 - 2 * np.array([col0, row0])).astype(int)  # index sum of the peak
    reach = int(np.ceil(2 * search * sigma))
    lo = np.maximum(center_k - reach, 1)
    hi = np.minimum(center_k + reach, np.array(conv.shape[::-1]) - 2)
    sub = conv[lo[1] : hi[1] + 1, lo[0] : hi[0] + 1]
    row, col = np.unravel_index(np.argmax(sub), sub.shape)
    row, col = row + lo[1], col + lo[0]
    dx = parabola_offset(conv[row, col - 1], conv[row, col], conv[row, col + 1])
    dy = parabola_offset(conv[row - 1, col], conv[row, col], conv[row + 1, col])
    return (np.array([col + dx, row + dy]) + 2 * np.array([col0, row0]) + 1) / 2


def find_center(image, mark, scale, spacing, settings):
    pitch = pitch_of(spacing)
    r_outer = mark.r_outer / scale
    z_map = coherence_map(image, pitch, reach=int(np.ceil(r_outer + 2 * spacing)))  # the annulus, plus a margin
    center = symmetry_center(z_map, settings.symmetry_window * r_outer, settings.symmetry_search)
    z = map_at(z_map, center)
    coherence = 2 * np.abs(z) / np.sum(np.abs(image)) / (np.pi / 2)
    return Spiral(center[0], center[1], pitch, float(np.angle(z))).scaled(scale), z_map, coherence


def low_res_stage(full, mark, nominal_spacing, settings=LowResSettings()):
    scale = full.shape[0] / LOW_SIZE
    nominal = nominal_spacing / scale
    mask = annulus_mask(LOW_SIZE, mark, scale, ramp=nominal)
    image = normalize_in_mask(downsample(full), mask)
    spectrum, profile, window, peak, measured, ok = fft_spacing(image, mask, mark, scale, nominal, settings)
    if not ok:
        best = int(round(peak))
        on_edge = best in window
        reason = "is on the edge of the search window" if on_edge else \
            f"is too weak (prominence {peak_prominence(profile, best):.2f} < ln 2: less than 2x its background)"
        raise SpacingNotFound(f"the profile's maximum {reason} ({measured * scale:.2f} px, nominal {nominal_spacing:.2f} px)")
    spiral, z_map, coherence = find_center(image, mark, scale, measured, settings)
    return LowResResult(scale, image, mask, spectrum, profile, window, peak, measured * scale, z_map, coherence, spiral)
