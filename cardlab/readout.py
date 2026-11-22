from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter1d

from .strip import sample_strip

# Hill-and-dale: the sound is the depth of the cut. Per column, the land on
# both sides (at +-S/2) minus the traced bottom, each averaged over +-window
# px, relative to its own slow average along the groove, minus 1. A gap in the
# groove (nothing cut) reads -1.


@dataclass
class ReadoutSettings:
    half_window: int = 3            # px across the groove
    average_length: float = 300     # px along the groove at the middle turn (columns are equal steps in theta)
    smoothing: float = 3            # px along the groove at the middle turn


def mean_across(image, strip, centers, half_window):
    offsets = np.arange(-half_window, half_window + 1, dtype=float)
    return sample_strip(image, strip.spiral, strip.theta, offsets, centers).mean(axis=0)


def read_sound(image, strip, trace, settings=ReadoutSettings()):
    half_spacing = strip.spiral.spacing / 2
    bottom = mean_across(image, strip, trace, settings.half_window)
    land = (mean_across(image, strip, trace - half_spacing, settings.half_window)
            + mean_across(image, strip, trace + half_spacing, settings.half_window)) / 2
    depth = land - bottom
    average = gaussian_filter1d(depth, settings.average_length / strip.step)
    usable = average > 0.25 * np.median(average)
    ratio = np.clip(depth / np.where(usable, average, 1) - 1, -1, 3)
    sound = np.where(usable, ratio, 0)
    if settings.smoothing > 0:
        sound = gaussian_filter1d(sound, settings.smoothing / strip.step)
    return sound
