from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter

from .geometry import TAU, Mark, Spiral, pitch_of, polar, smoothstep

# An idealized card: flat at height 0 plus grain. A round stylus (a parabola)
# follows r = pitch*theta + drift and moves up and down with the sound
# (hill-and-dale): cut depth = 1 + sound. Where the stylus is above the card
# nothing is cut, so the surface is min(0, stylus) over the nearest turns.
# The sound is a function of theta (time: the card turns at a constant rate),
# so a given frequency is cut longer on the outer turns (wavelength ~ r).


def band_limited(rng, positions, rms, wavelengths, n_waves=40):
    if rms <= 0:
        return np.zeros_like(positions)
    shortest, longest = wavelengths
    lengths = shortest * (longest / shortest) ** rng.random(n_waves)
    phases = rng.random(n_waves) * TAU
    amplitudes = rng.standard_normal(n_waves)
    signal = np.zeros_like(positions)
    for length, phase, amplitude in zip(lengths, phases, amplitudes):
        signal += amplitude * np.sin(TAU * positions / length + phase)
    return signal * rms / np.sqrt(np.mean(signal**2))


def parabola_groove_rms(width):
    # rms over one spacing of a unit-depth parabolic groove `width` spacings wide
    return np.sqrt(8 * width / 15 - (2 * width / 3) ** 2)


@dataclass
class Card:
    params: object
    seed: int
    spiral: Spiral
    mark: Mark
    theta_grid: np.ndarray
    drift: np.ndarray
    sound_theta: np.ndarray
    sound_track: np.ndarray

    @property
    def spacing(self):
        return self.spiral.spacing

    def lateral_offset(self, theta):
        return np.interp(theta, self.theta_grid, self.drift)

    def sound(self, theta):
        return np.interp(theta, self.sound_theta, self.sound_track)

    def cut_depth(self, theta):
        r = self.spiral.radius(theta)
        fade = self.params.edge_fade
        envelope = smoothstep((r - self.params.r_inner) / fade) * smoothstep((self.params.r_outer - r) / fade)
        return envelope * (1 + self.sound(theta))

    def arms_near(self, x, y):
        # theta of the nearest turn and its two neighbours, and the radial distance to each groove
        r, angle = polar(x, y, self.spiral.x, self.spiral.y)
        nearest = np.round((self.spiral.theta_at(r) - angle) / TAU)
        for shift in (-1, 0, 1):
            theta = angle + TAU * (nearest + shift)
            yield theta, r - self.spiral.radius(theta) - self.lateral_offset(theta)

    def groove_height(self, x, y):
        curvature = 4 / (self.params.groove_width * self.spacing) ** 2
        height = np.zeros(np.shape(x), dtype=np.float32)
        for theta, distance in self.arms_near(x, y):
            stylus = -self.cut_depth(theta) + curvature * distance**2
            height = np.minimum(height, stylus)
        return height

    def nearest_groove(self, x, y):
        # signed distance from each point to the nearest groove centerline (outward +), and that groove's theta
        best_distance = best_theta = None
        for theta, distance in self.arms_near(x, y):
            if best_distance is None:
                best_distance, best_theta = distance, theta
                continue
            closer = np.abs(distance) < np.abs(best_distance)
            best_distance = np.where(closer, distance, best_distance)
            best_theta = np.where(closer, theta, best_theta)
        return -best_distance, best_theta


def make_card(params, seed):
    rng = np.random.default_rng(seed)
    spacing = params.spacing * (1 + (2 * rng.random() - 1) * params.spacing_tolerance)
    pitch = pitch_of(spacing)
    center = params.frame / 2 + rng.standard_normal(2) * params.center_jitter
    spiral = Spiral(center[0], center[1], pitch, rng.random() * TAU)
    mark_center = center + rng.standard_normal(2) * params.mark_error
    radius_errors = 1 + rng.standard_normal(2) * params.mark_radius_error
    mark = Mark(mark_center[0], mark_center[1], params.r_inner * radius_errors[0], params.r_outer * radius_errors[1])

    margin = 6 * spacing
    theta_grid = np.arange(spiral.theta_at(max(pitch, params.r_inner - margin)), spiral.theta_at(params.r_outer + margin), 0.005)
    drift_wavelengths = tuple(TAU * turns for turns in params.drift_turns)
    drift = band_limited(rng, theta_grid, params.drift_rms, drift_wavelengths, n_waves=60)
    # sound wavelengths are given in px of groove at the mid radius; in theta
    # they are that / the mid radius; sampled every <= 0.5 px of groove
    mid_radius = (params.r_inner + params.r_outer) / 2
    sound_theta = np.arange(theta_grid[0], theta_grid[-1], 0.5 / (params.r_outer + margin))
    sound_wavelengths = tuple(length / mid_radius for length in params.sound_wavelengths)
    sound_track = band_limited(rng, sound_theta, params.sound_rms, sound_wavelengths)
    return Card(params, seed, spiral, mark, theta_grid, drift, sound_theta, sound_track)


def grain_image(card, size):
    if card.params.grain <= 0:
        return np.zeros((size, size), np.float32)
    rng = np.random.default_rng(card.seed + 1000)
    # white noise blurred so its autocorrelation halves at ~1.2 grain sizes
    noise = gaussian_filter(rng.standard_normal((size, size), dtype=np.float32), 0.72 * card.params.grain_size)
    noise *= card.params.grain * parabola_groove_rms(card.params.groove_width) / noise.std()
    return noise


def render(card, rows_per_block=256):
    size = card.params.frame
    image = grain_image(card, size)
    xs = np.arange(size, dtype=np.float64) + 0.5
    for top in range(0, size, rows_per_block):
        ys = np.arange(top, min(size, top + rows_per_block)) + 0.5
        x, y = np.meshgrid(xs, ys)
        image[top : top + len(ys)] += card.groove_height(x, y)
    return image
