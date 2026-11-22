from dataclasses import dataclass, field

import numpy as np

from .lowres import LowResSettings, low_res_stage
from .model import make_card, render
from .params import PRESETS
from .readout import ReadoutSettings, read_sound
from .scoring import center_error, correlation, rms, score_trace, spacing_error, spiral_vs_grooves
from .strip import StripSettings, build_strip, lock_trace, refit_geometry


@dataclass
class Settings:
    low: LowResSettings = field(default_factory=LowResSettings)
    strip: StripSettings = field(default_factory=StripSettings)
    readout: ReadoutSettings = field(default_factory=ReadoutSettings)


@dataclass
class Run:
    card: object
    image: np.ndarray
    low: object
    strip: object
    refit: object
    model: np.ndarray
    trace: np.ndarray
    sound: np.ndarray
    score: object


def run_pipeline(preset, seed, settings=Settings()):
    card = make_card(PRESETS[preset], seed)
    image = render(card)
    low = low_res_stage(image, card.mark, card.params.spacing, settings.low)
    strip = build_strip(image, low.spiral, card.mark, settings.strip)
    refit, model = refit_geometry(strip, settings.strip)
    trace = lock_trace(strip, model, settings.strip)
    sound = read_sound(image, strip, trace, settings.readout)
    return Run(card, image, low, strip, refit, model, trace, sound, score_trace(card, strip, trace))


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
        "turns": float((run.strip.theta[-1] - run.strip.theta[0]) / (2 * np.pi)),
        "trace_rms": rms(score.distance),
        "off_quarter": float(np.mean(np.abs(score.distance) > card.spacing / 4)),
        "wrong_groove": float(np.mean(score.wrong_groove)),
        "not_cut": float(np.mean(score.true_sound <= -1)),
        "sound_rms": rms(score.true_sound),
        "sound_error": rms(run.sound - score.true_sound),
        "sound_correlation": correlation(run.sound, score.true_sound),
    }
