from dataclasses import dataclass, replace

# Lengths in full-resolution pixels, heights in units of the nominal groove
# depth. "Measured" values come from sonorine_001 (tomaz-results images 21-22).


@dataclass(frozen=True)
class CardParams:
    label: str = "Typical"
    frame: int = 5551
    spacing: float = 29.0
    spacing_tolerance: float = 0.01
    r_inner: float = 1600
    r_outer: float = 2770
    center_jitter: float = 40
    mark_error: float = 12
    mark_radius_error: float = 0.01
    groove_width: float = 0.6
    edge_fade: float = 60
    sound_rms: float = 0.4
    sound_wavelengths: tuple = (15, 300)
    grain: float = 0.52
    grain_size: float = 2.5
    drift_rms: float = 3.2
    drift_turns: tuple = (0.3, 1.0)


TYPICAL = CardParams()

PRESETS = {
    "typical": TYPICAL,
    "loud": replace(TYPICAL, label="Loud (sound often cuts out)", sound_rms=0.7),
    "hard": replace(
        TYPICAL, label="Hard (more grain, drift, loud sound)", spacing_tolerance=0.02,
        mark_error=25, mark_radius_error=0.02, edge_fade=80, sound_rms=0.6, grain=1.0,
        drift_rms=5.0,
    ),
    "clean": replace(TYPICAL, label="Clean (no grain)", grain=0.0),
}

# (name, unit, where the value comes from)
PARAM_NOTES = {
    "frame": ("Frame size", "px", "card ~5551² after crop (image 22)"),
    "spacing": ("Nominal groove spacing", "px", "measured 29.0 (image 21; FFT 29.1 on sonorine_001)"),
    "spacing_tolerance": ("True spacing within ±", "×", "assumed (cards 25.9–32.2 px across machines)"),
    "r_inner": ("Inner groove radius", "px", "image 22 (~1600)"),
    "r_outer": ("Outer groove radius", "px", "image 22 (~2770): ~40 turns"),
    "center_jitter": ("Card center vs. frame center (σ)", "px", "assumed"),
    "mark_error": ("Hand-mark error (σ per axis)", "px", "assumed"),
    "mark_radius_error": ("Hand-marked radii error (σ)", "×", "assumed"),
    "groove_width": ("Groove width at nominal depth", "× spacing", "assumed; round stylus (parabola)"),
    "edge_fade": ("Depth fade at the ends", "px", "assumed"),
    "sound_rms": ("Sound: depth modulation (rms)", "× depth", "assumed; at −1 the stylus leaves the card"),
    "sound_wavelengths": ("Sound wavelengths along the groove at the mid radius", "px", "assumed; the sound is a function of the angle (the card turns at a constant rate), so a wavelength scales with the radius"),
    "grain": ("Grain (rms)", "× groove rms", "measured: 2.6 vs. groove 5.0 rms (image 21)"),
    "grain_size": ("Grain size", "px", "measured ACF 0.5 at ~3–5 px"),
    "drift_rms": ("Groove drift from the spiral (rms)", "px", "measured 2.9 / 3.5 px rms per turn vs. Tomaz's fitted spiral (images 21 / 26)"),
    "drift_turns": ("Drift periods", "turns", "fit to the same: neighbouring turns uncorrelated, ~1.5 px change per 0.06 turn"),
}
