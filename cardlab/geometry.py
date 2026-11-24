from dataclasses import dataclass, replace

import numpy as np

TAU = 2 * np.pi


@dataclass(frozen=True)
class Spiral:
    # r = pitch * (theta - phase), phase = the spiral phase, theta = the angle about the center (from 3
    # o'clock), unwrapped: theta = angle + 2*pi*turn (Nov 2026, Adam; was
    # r = pitch * theta with theta = angle - phase + 2*pi*turn)
    x: float
    y: float
    pitch: float
    phase: float

    @property
    def spacing(self):
        return TAU * self.pitch

    def scaled(self, factor):
        return replace(self, x=self.x * factor, y=self.y * factor, pitch=self.pitch * factor)

    def radius(self, theta):
        return self.pitch * (theta - self.phase)

    def theta_at(self, radius):
        # the theta at which the spiral reaches `radius` (on any turn: + 2 pi n)
        return radius / self.pitch + self.phase


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
    # the canonical angle: counterclockwise from 3 o'clock as displayed (y up),
    # although image rows run down (Nov 2026: real cards wind outward this way)
    dx, dy = x - cx, y - cy
    return np.hypot(dx, dy), np.arctan2(-dy, dx)


def spiral_points(spiral, theta, offset=0.0):
    # points at radial distance `offset` outward from the spiral, at parameter theta
    radius = spiral.radius(theta) + offset
    return spiral.x + radius * np.cos(theta), spiral.y - radius * np.sin(theta)  # y up: rows run down


def nearest_turn_theta(spiral, x, y):
    # the spiral's theta on the turn nearest each point (ignoring any drift)
    r, angle = polar(x, y, spiral.x, spiral.y)
    return angle + TAU * np.round((spiral.theta_at(r) - angle) / TAU)
