from dataclasses import dataclass, field

import numpy as np

from .lowres import LowResSettings, low_res_stage
from .model import make_card, render
from .params import PRESETS
from .readout import ReadoutSettings, read_sound
from .scoring import center_error, correlation, rms, score_trace, spacing_error, spiral_vs_grooves
from .strip import Strip
from .wedges import WedgeSettings, run_wedges


@dataclass
class Settings:
    low: LowResSettings = field(default_factory=LowResSettings)
    wedges: WedgeSettings = field(default_factory=WedgeSettings)
    readout: ReadoutSettings = field(default_factory=ReadoutSettings)


@dataclass
class Run:
    card: object
    image: np.ndarray
    low: object
    wedges: object          # wedges.WedgeRun
    strip: object           # the rectangle's columns along the low-res spiral (no demodulation): the frame
                            # of model, trace and score
    refit: object
    model: np.ndarray       # the refitted spiral's offset from the low-res one, per column, px
    trace: np.ndarray       # the groove's offset from the low-res spiral, per column, px
    sound: np.ndarray
    score: object


def run_pipeline(preset, seed, settings=Settings()):
    card = make_card(PRESETS[preset], seed)
    image = render(card)
    low = low_res_stage(image, card.mark, card.params.spacing, settings.low)
    wedges = run_wedges(image, low.spiral, card.mark, settings.wedges)
    unrolled = wedges.unrolled
    strip = Strip(low.spiral, unrolled.theta, unrolled.step, None, None, None)
    sound = read_sound(image, strip, wedges.path, settings.readout)
    return Run(card, image, low, wedges, strip, wedges.spiral, wedges.model, wedges.path, sound,
               score_trace(card, strip, wedges.path))


def summarize(run):
    card, score = run.card, run.score
    return {
        "preset": card.params.label,
        "seed": card.seed,
        "mark_error": center_error(card, run.card.mark),
        "fft_spacing_error": run.low.fft_spacing / card.spacing - 1,
        "low_center_error": center_error(card, run.low.spiral),
        "low_spacing_error": spacing_error(card, run.low.spiral),
        "low_vs_grooves": spiral_vs_grooves(card, score, 0),
        "refit_center_error": center_error(card, run.refit),
        "refit_spacing_error": spacing_error(card, run.refit),
        "refit_vs_grooves": spiral_vs_grooves(card, score, run.model),
        "coherence": run.low.coherence,
        "columns": len(run.strip.theta),
        "wedges": len(run.wedges.final.theta),
        "dropped_sectors": int(len(run.wedges.dropped)),
        "turns": float((run.strip.theta[-1] - run.strip.theta[0]) / (2 * np.pi)),
        "trace_rms": rms(score.distance),
        "off_quarter": float(np.mean(np.abs(score.distance) > card.spacing / 4)),
        "wrong_groove": float(np.mean(score.wrong_groove)),
        "not_cut": float(np.mean(score.true_sound <= -1)),
        "sound_rms": rms(score.true_sound),
        "sound_error": rms(run.sound - score.true_sound),
        "sound_correlation": correlation(run.sound, score.true_sound),
    }
