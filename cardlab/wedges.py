from dataclasses import dataclass, replace

import numpy as np
from scipy.optimize import least_squares

from .geometry import TAU, nearest_turn_theta, polar, spiral_points, wrap
from .strip import Strip, refit_basis, refit_start, sample_at

# The full-res stage (Nov 2026; replaced the strip, see strip.py and
# experiments/unrolled_wedges.py): the annulus unrolled into a rectangle
# along the low-res spiral (Adam's idea). Columns run along the spiral at
# equal steps in theta (time: the card turns at a constant rate), about 1 px
# of groove apart on the outer turn (so no turn is undersampled and bilinear
# sampling needs no prefilter), rows are the radial offset d from it; rows -S/2..S/2
# cover every annulus pixel once (offset +S is the next turn at the same
# angle). The rectangle is never stored: `Unrolled.pull` samples just the
# columns and rows asked for. Wedges = blocks of columns, `sectors` per turn;
# per column the sum over one period of rows of v e^{-2 pi i d / S}
# (untapered: over one period that is the groove's first Fourier component;
# a taper or a wider window lets the neighbouring turns, which drift
# differently, pull it toward the spiral), summed over the wedge: the angle
# of Z is the groove's offset (mod S), |Z| its strength.
#   Pass 1: rows about the spiral, on coarser columns (every `pass1_step` px
#     on the outer turn: the refit is limited by the groove's drift, not by
#     sampling; 4 px gave the same center to 0.001 px on 20 cards, see
#     experiments/coarse_pass1.py); the geometry refit (as the strip's) on the
#     wedge offsets, no resampling, gives the geometry and an unwrapped model
#     of the low-res spiral's error; path = model + the wedges' offsets from
#     it within +-S/2.
#   Pass 2: each column's rows centered midway between the lands either side
#     of the groove, at (groove + mean of the neighbouring turns' offsets) / 2,
#     so the window's ends fall in the land (centered on the groove itself was
#     worse); path = pass 1's path + the new offsets from it within +-S/2.
# Offsets between wedges: phasors |Z| e^{i angle} interpolated (drift_at).


@dataclass
class WedgeSettings:
    sectors: int = 40         # wedges per turn
    column_step: float = 1.0  # px of groove between columns on the outermost turn (equal steps in theta)
    pass1_step: float = 4.0   # the same for pass 1 (the geometry refit only)


@dataclass
class WedgeRun:
    unrolled: object        # the rectangle, along the low-res spiral
    first: Strip            # pass 1's wedges, on the coarse columns (offsets from the low-res spiral, mod S)
    final: Strip            # pass 2's wedges (offsets from the low-res spiral, mod S)
    spiral: object          # refitted geometry
    model: np.ndarray       # the refitted spiral's offset from the low-res one at the columns, px
    window: np.ndarray      # pass 2's row centers at the columns, px from the low-res spiral
    path: np.ndarray        # the groove's offset from the low-res spiral at the columns, px


def theta_columns(spiral, mark, outer_step):
    # equal steps in theta from 1.5 spacings inside the marked inner edge to 1.5
    # inside the outer one, `outer_step` px of groove apart on the outermost turn
    first = spiral.theta_at(mark.r_inner + 1.5 * spiral.spacing)
    last = spiral.theta_at(mark.r_outer - 1.5 * spiral.spacing)
    return np.arange(first, last, outer_step / spiral.radius(last))


class Unrolled:
    def __init__(self, image, spiral, mark, column_step, sectors):
        self.image, self.spiral, self.spacing = image, spiral, spiral.spacing
        self.theta = theta_columns(spiral, mark, column_step)
        # px of groove per column at the middle turn (readout lengths are in px there)
        self.step = spiral.radius(np.median(self.theta)) * (self.theta[1] - self.theta[0])
        self.per_turn = TAU / (self.theta[1] - self.theta[0])
        reach = int(np.ceil(self.spacing / 2))
        self.rows = np.arange(-reach, reach + 1, dtype=float)
        # one period exactly: rows within S/2 weigh 1, the end rows the fraction inside
        self.weights = np.clip(self.spacing / 2 - np.abs(self.rows) + 0.5, 0, 1)
        self.wedge = np.floor(self.theta / TAU * sectors).astype(int)

    def pull(self, columns, rows, center=0.0):
        # the sub-rectangle: `rows` (px) about `center` (px, per column), sampled now
        d = rows[:, None] + np.broadcast_to(center, self.theta[columns].shape)[None, :]
        return sample_at(self.image, *spiral_points(self.spiral, self.theta[None, columns], d)), d

    def column_phasors(self, center, chunk=20000):
        # per column: sum over one period of rows of v e^{-2 pi i d / S}
        out = np.empty(len(self.theta), complex)
        for start in range(0, len(self.theta), chunk):
            columns = slice(start, start + chunk)
            values, d = self.pull(columns, self.rows, center[columns])
            out[columns] = (self.weights[:, None] * values * np.exp(-1j * TAU * d / self.spacing)).sum(axis=0)
        return out


def wedges(unrolled, z_columns):
    # per wedge: center theta, Z, offset from the spiral (mod S), confidence |Z| / median
    _, index, count = np.unique(unrolled.wedge, return_inverse=True, return_counts=True)
    z = np.bincount(index, z_columns.real) + 1j * np.bincount(index, z_columns.imag)
    theta = np.bincount(index, unrolled.theta) / count
    keep = count > 0.5 * np.median(count)  # drop the partial wedges at both ends
    z, theta = z[keep], theta[keep]
    offsets = -unrolled.spacing * np.angle(-z) / TAU  # the groove is a depression, as strip.offsets_from
    return Strip(unrolled.spiral, theta, 0.0, z, offsets, np.abs(z) / np.median(np.abs(z)))


def drift_at(cells, theta):
    # the wedges' offsets at any theta: phasors |Z| e^{i 2 pi o / S}, interpolated
    spacing = cells.spiral.spacing
    order = np.argsort(cells.theta)
    phasor = cells.confidence[order] * np.exp(1j * TAU * cells.offsets[order] / spacing)
    at = np.interp(theta, cells.theta[order], phasor.real) + 1j * np.interp(theta, cells.theta[order], phasor.imag)
    return spacing * np.angle(at) / TAU


def refit_wedges(cells, search=1.5):
    # the strip's geometry refit on the wedge offsets: relative to the low-res
    # spiral a center error is a one-turn wave, a spacing error a slope, a
    # spiral-phase error an offset (mod S). Returns the refitted spiral and the
    # (unwrapped) model of its offset from the low-res spiral at any theta.
    spacing, low = cells.spiral.spacing, cells.spiral
    basis = refit_basis(cells)
    root_weights = np.sqrt(cells.confidence / cells.confidence.mean())
    residuals = lambda q: root_weights * wrap(cells.offsets - basis @ q, spacing)
    a, beta, ex, ey = least_squares(residuals, refit_start(cells, search, every=1), loss="soft_l1",
                                    f_scale=0.1 * spacing).x
    pitch = low.pitch + beta
    # radius at theta: low.radius(theta) + a + beta (theta - theta_0) = pitch (theta - phase)
    spiral = replace(low, x=low.x + ex, y=low.y - ey, pitch=pitch,  # ey is up, rows run down
                     phase=(low.pitch * low.phase - a + beta * cells.theta[0]) / pitch)
    model = lambda theta: a + beta * (theta - cells.theta[0]) + ex * np.cos(theta) + ey * np.sin(theta)
    return spiral, model


def neighbours_mean(theta, offsets):
    # the mean offset of the turns either side (2 pi along), each from its own
    # turn; where one is off the end, the other alone (0 if neither)
    total, count = np.zeros_like(offsets), np.zeros_like(offsets)
    for side in (TAU, -TAU):
        inside = (theta + side >= theta[0]) & (theta + side <= theta[-1])
        total += np.where(inside, np.interp(theta + side, theta, offsets), 0)
        count += inside
    return total / np.maximum(count, 1)


def run_wedges(image, low_spiral, mark, settings=WedgeSettings()):
    coarse = Unrolled(image, low_spiral, mark, settings.pass1_step, settings.sectors)
    first = wedges(coarse, coarse.column_phasors(np.zeros(len(coarse.theta))))
    unrolled = Unrolled(image, low_spiral, mark, settings.column_step, settings.sectors)
    spacing, theta = unrolled.spacing, unrolled.theta
    near = lambda reference, cells: reference + wrap(drift_at(cells, theta) - reference, spacing)
    spiral, model = refit_wedges(first)
    path = near(model(theta), first)
    window = (path + neighbours_mean(theta, path)) / 2
    final = wedges(unrolled, unrolled.column_phasors(window))
    return WedgeRun(unrolled, first, final, spiral, model(theta), window, near(path, final))


def offsets_about(spiral, x, y):
    # points as (theta, offset px) about `spiral`: each one's nearest turn
    theta = nearest_turn_theta(spiral, x, y)
    radius, _ = polar(x, y, spiral.x, spiral.y)
    return theta, radius - spiral.radius(theta)
