from dataclasses import dataclass, replace

import numpy as np

TAU = 2 * np.pi


@dataclass(frozen=True)
class Spiral:
    # r = pitch * theta, where theta = angle - phase + 2*pi*turn (angle about the center)
    x: float
    y: float
    pitch: float
    phase: float

    @property
    def spacing(self):
        return TAU * self.pitch

    def scaled(self, factor):
        return replace(self, x=self.x * factor, y=self.y * factor, pitch=self.pitch * factor)


@dataclass(frozen=True)
class Mark:
    x: float
    y: float
    r_inner: float
    r_outer: float


def pitch_of(spacing):
    return spacing / TAU


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def wrap(values, period):
    return values - period * np.round(values / period)


def polar(x, y, cx, cy):
    dx, dy = x - cx, y - cy
    return np.hypot(dx, dy), np.arctan2(dy, dx)


def spiral_points(spiral, theta, offset=0.0):
    # points at radial distance `offset` outward from the spiral, at parameter theta
    angle = theta + spiral.phase
    radius = spiral.pitch * theta + offset
    return spiral.x + radius * np.cos(angle), spiral.y + radius * np.sin(angle)


def nearest_turn_theta(spiral, x, y):
    # the spiral's theta on the arm nearest each point (ignoring any drift)
    r, angle = polar(x, y, spiral.x, spiral.y)
    angle = angle - spiral.phase
    return angle + TAU * np.round((r / spiral.pitch - angle) / TAU)
