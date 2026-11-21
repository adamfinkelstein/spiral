from dataclasses import dataclass

import numpy as np

from .geometry import TAU, spiral_points, wrap

# Scores against the card's truth (only possible on simulated cards).


@dataclass
class TraceScore:
    distance: np.ndarray        # traced point to the nearest true groove centerline (outward +), px
    wrong_groove: np.ndarray    # bool per column
    true_offset: np.ndarray     # true groove position as an offset from the strip's spiral, px
    true_sound: np.ndarray      # sound of the traced groove, floored at -1 (no cut)


def center_error(card, spiral):
    return float(np.hypot(spiral.x - card.spiral.x, spiral.y - card.spiral.y))


def spacing_error(card, spiral):
    return spiral.spacing / card.spacing - 1


def ideal_offset(card, strip):
    # the true spiral (center, spacing, phase; no drift) as an offset from the strip's spiral
    x, y = spiral_points(strip.spiral, strip.theta)
    r = np.hypot(x - card.spiral.x, y - card.spiral.y)
    along = r - card.spiral.pitch * (np.arctan2(y - card.spiral.y, x - card.spiral.x) - card.spiral.phase)
    return -wrap(along, card.spacing)


def score_trace(card, strip, trace):
    x, y = spiral_points(strip.spiral, strip.theta, trace)
    distance, groove_theta = card.nearest_groove(x, y)
    turn_index = groove_theta - strip.theta
    wrong = np.round((turn_index - np.median(turn_index)) / TAU) != 0
    true_sound = np.maximum(card.sound(groove_theta), -1)
    return TraceScore(distance, wrong, trace + distance, true_sound)


def rms(values):
    return float(np.sqrt(np.mean(np.square(values))))


def spiral_vs_grooves(card, score, model):
    return rms(wrap(score.true_offset - model, card.spacing))


def correlation(a, b):
    return float(np.corrcoef(a, b)[0, 1])
