import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.geometry import TAU, wrap
from cardlab.lowres import low_res_stage
from cardlab.model import make_card, render
from cardlab.params import PRESETS
from cardlab.readout import read_sound
from cardlab.scoring import center_error, correlation, rms, score_trace, spacing_error
from cardlab.strip import (Strip, StripSettings, build_strip, lock_trace, refit_basis, refit_geometry, refit_start,
                           strip_columns)

# NOTE (Nov 2026): written for the old spiral convention r = pitch * theta,
# theta = angle - phase + 2 pi n. cardlab now uses r = pitch * (theta - phase),
# theta = the card's angle unwrapped; this script was not updated (results
# files record what it gave then).
# Offline experiment (Nov 2026): local spiral coherence in cells instead of the
# full-res strip. With the low-res spiral (center, pitch, phase) known, every
# annulus pixel belongs to the turn nearest it (turn n) and to an angular sector
# k (K per turn); per cell Z = sum v e^{-iu}, u = r/pitch - (angle - phase)
# (mod 2 pi), whose angle gives the groove's offset from the spiral in that
# cell (mod S) and |Z| its strength. Then: the same geometry refit as the
# strip's (center, spacing, phase modulo S), on ~40 K cells instead of ~160k
# columns; the cells again about the refitted spiral give the drift; the path
# = the refitted spiral + the drift (phasor-smoothed over cells, interpolated
# to columns every 3 px); the sound is read along it as now. Compared with the
# strip pipeline (build_strip, refit_geometry, lock_trace) on the same cards.

STEP = 3.0  # px of groove between readout columns, as the strip


def cell_sums(image, spiral, scale, r_lo, r_hi, sectors, taper=False, remove_mean=True, path=None, rows_per_chunk=256):
    # image px = full-res px / scale; returns per cell (turn n, sector k): theta, Z, count.
    # Plain: each pixel goes to its nearest turn's band (+-S/2), all weights 1.
    # Taper (as the strip's columns): each pixel goes to both turns it lies
    # between, weighted cos^2(pi d / 2S) by its distance d from each (so a
    # cell's weights fall to 0 at +-S, centred on its turn), which keeps the
    # neighbouring grooves' edges out. Either way the cell's weighted mean is
    # removed: Z = sum w (v - mean) e^{-iu}.
    pitch, cx, cy, phase = spiral.pitch / scale, spiral.x / scale, spiral.y / scale, spiral.phase
    lo, hi = r_lo / scale, r_hi / scale
    totals = {}
    height, width = image.shape
    cols = np.arange(width) + 0.5
    for row0 in range(0, height, rows_per_chunk):
        rows = np.arange(row0, min(height, row0 + rows_per_chunk)) + 0.5
        dx, dy = cols[None, :] - cx, rows[:, None] - cy
        r = np.hypot(dx, dy)
        inside = (r >= lo) & (r <= hi)
        if not inside.any():
            continue
        r, values = r[inside], image[row0 : row0 + len(rows)][inside]
        around = np.mod(np.arctan2(dy, dx)[inside] - phase, TAU)  # angle - phase, 0..2 pi
        u = r / pitch - around
        sector = np.minimum((around / TAU * sectors).astype(int), sectors - 1)
        carrier = np.exp(-1j * u)
        # band position: about the spiral's turn, or (path) about the groove itself,
        # i.e. shifted by the current drift estimate at this pixel's spiral angle
        shift = 0.0 if path is None else TAU * path(np.rint(u / TAU) * TAU + around) / (pitch * TAU * scale)
        v = u - shift
        if taper == "full":
            inner = np.floor(v / TAU).astype(int)
            d = (v / TAU - inner)  # 0..1 spacings outward from the inner turn
            parts = [(inner, np.cos(np.pi * d / 2) ** 2), (inner + 1, np.cos(np.pi * (1 - d) / 2) ** 2)]
        elif taper == "half":
            turn = np.rint(v / TAU).astype(int)
            parts = [(turn, np.cos(np.pi * (v / TAU - turn)) ** 2)]  # 1 at the turn, 0 at +-S/2
        else:
            parts = [(np.rint(v / TAU).astype(int), np.ones_like(u))]
        for turn, weight in parts:
            cell = turn * sectors + sector
            ids, inverse = np.unique(cell, return_inverse=True)
            sums = [np.bincount(inverse, x) for x in (weight, weight * values, (weight * carrier).real, (weight * carrier).imag,
                                                       (weight * values * carrier).real, (weight * values * carrier).imag)]
            count = np.bincount(inverse)
            for i, c in enumerate(ids):
                row = np.array([s[i] for s in sums] + [count[i]])
                totals[c] = totals[c] + row if c in totals else row
    ids = np.array(sorted(totals))
    rows = np.array([totals[c] for c in ids])
    w, wv, we, wve, count = rows[:, 0], rows[:, 1], rows[:, 2] + 1j * rows[:, 3], rows[:, 4] + 1j * rows[:, 5], rows[:, 6]
    z = wve - (wv / w) * we if remove_mean else wve
    theta = (ids // sectors) * TAU + (ids % sectors + 0.5) / sectors * TAU
    return theta, z, count


def cell_strip(image, spiral, scale, mark, sectors, taper=False, remove_mean=True, path=None):
    # the cells as a Strip (one "column" per cell), offsets in full-res px;
    # confidence = |Z| relative to the median cell
    spacing = spiral.spacing
    theta, z, count = cell_sums(image, spiral, scale, mark.r_inner + 1.5 * spacing, mark.r_outer - 1.5 * spacing,
                                sectors, taper, remove_mean, path)
    keep = count > 0.5 * np.median(count)  # drop cells cut by the annulus edges
    theta, z = theta[keep], z[keep]
    offsets = -spacing * np.angle(-z) / TAU  # groove (a depression) offset from the spiral, as strip.offsets_from
    return Strip(spiral, theta, 0.0, z, offsets, np.abs(z) / np.median(np.abs(z)))


def refit_cells(strip, search=1.5):
    # as strip.refit_geometry, but the grid start uses every cell
    spacing = strip.spiral.spacing
    basis = refit_basis(strip)
    root_weights = np.sqrt(strip.confidence / strip.confidence.mean())
    residuals = lambda q: root_weights * wrap(strip.offsets - basis @ q, spacing)
    fit = least_squares(residuals, refit_start(strip, search, every=1), loss="soft_l1", f_scale=0.1 * spacing)
    a, beta, ex, ey = fit.x
    pitch = strip.spiral.pitch + beta
    phase = strip.spiral.phase - (a - beta * strip.theta[0]) / pitch
    return type(strip.spiral)(strip.spiral.x + ex, strip.spiral.y + ey, pitch, phase)


def drift_path(cells, theta, smoothing_cells=0, min_confidence=0.0):
    # cell offsets about the refitted spiral, phasor-smoothed along the cells and
    # interpolated to the readout columns (works modulo S). Cells below
    # min_confidence are left out, so their stretch is interpolated from the
    # confident cells on either side along the groove.
    spacing = cells.spiral.spacing
    usable = cells.confidence >= min_confidence
    cells = Strip(cells.spiral, cells.theta[usable], 0.0, cells.demod[usable], cells.offsets[usable], cells.confidence[usable])
    order = np.argsort(cells.theta)
    phasor = cells.confidence[order] * np.exp(1j * TAU * cells.offsets[order] / spacing)
    if smoothing_cells > 0:
        phasor = gaussian_filter1d(phasor.real, smoothing_cells) + 1j * gaussian_filter1d(phasor.imag, smoothing_cells)
    at = np.interp(theta, cells.theta[order], phasor.real) + 1j * np.interp(theta, cells.theta[order], phasor.imag)
    return spacing * np.angle(at) / TAU


def score(card, image, strip, trace):
    s = score_trace(card, strip, trace)
    return {"trace_rms": rms(s.distance), "wrong_groove": float(np.mean(s.wrong_groove)),
            "sound_correlation": correlation(read_sound(image, strip, trace), s.true_sound)}


def run_strip(card, image, low):
    started = time.time()
    strip = build_strip(image, low.spiral, card.mark, StripSettings())
    refit, model = refit_geometry(strip, StripSettings())
    trace = lock_trace(strip, model, StripSettings())
    seconds = time.time() - started
    return {"center_error": center_error(card, refit), "spacing_error": spacing_error(card, refit), "seconds": seconds} | \
        score(card, image, strip, trace)


def run_cells(card, image, low, use_low_res, sectors, taper=False, min_confidence=0.0, recenter=True):
    # 1: cells about the low-res spiral -> geometry refit; 2: cells about the
    # refitted spiral -> drift; 3 (recenter): cells with each band centered on
    # the groove (shifted by that drift) -> the final drift; the path is the
    # refitted spiral + the drift, cells under min_confidence interpolated over
    source, scale = (low.image, low.scale) if use_low_res else (image, 1.0)
    started = time.time()
    first = cell_strip(source, low.spiral, scale, card.mark, sectors, taper, False)
    spiral = refit_cells(first)
    cells = cell_strip(source, spiral, scale, card.mark, sectors, taper, False)
    if recenter:
        drift = lambda th, c=cells: drift_path(c, th)
        cells = cell_strip(source, spiral, scale, card.mark, sectors, taper, False, drift)
    theta = strip_columns(spiral, card.mark, STEP)
    trace = drift_path(cells, theta, 0, min_confidence)
    seconds = time.time() - started
    strip = Strip(spiral, theta, STEP, None, None, None)
    return {"center_error": center_error(card, spiral), "spacing_error": spacing_error(card, spiral), "seconds": seconds,
            "cells": len(cells.theta)} | score(card, image, strip, trace)


# earlier runs: 20 sectors and smoothing over 1 cell worse than 40; 80 no
# better; low res worse on hard cards; a radial taper (cos^2 over +-S/2 or
# +-S, about the turn or the groove) and removing each cell's mean worse than
# the plain one-period band (Nov 2026, see cell_coherence_results.md). Now:
# full res, 40 per turn, plain band, with and without re-centering the bands
# on the groove, and interpolating over weak cells (confidence < 0.3 / 0.5).
VARIANTS = [(False, 40, False, 0.0, False), (False, 40, False, 0.0, True), (False, 40, False, 0.3, True), (False, 40, False, 0.5, True)]


def main():
    presets, seeds, out = sys.argv[1].split(","), sys.argv[2].split(","), Path(sys.argv[3])
    rows = []
    for preset in presets:
        for seed in seeds:
            card = make_card(PRESETS[preset], int(seed))
            image = render(card)
            low = low_res_stage(image, card.mark, card.params.spacing)
            rows.append({"preset": preset, "seed": int(seed), "method": "strip"} | run_strip(card, image, low))
            for use_low, sectors, taper, min_conf, recenter in VARIANTS:
                name = f"cells{', re-centered' if recenter else ''}{f', weak < {min_conf} interpolated' if min_conf else ''}"
                rows.append({"preset": preset, "seed": int(seed), "method": name} |
                            run_cells(card, image, low, use_low, sectors, taper, min_conf, recenter))
            out.write_text(json.dumps(rows, indent=1))
            print(preset, seed, flush=True)
    methods = list(dict.fromkeys(r["method"] for r in rows))
    print("| method | preset | center px | spacing % | trace rms px | wrong groove | sound corr | seconds |")
    print("|---|---|---|---|---|---|---|---|")
    for method in methods:
        for preset in presets:
            sel = [r for r in rows if r["method"] == method and r["preset"] == preset]
            span = lambda key, fmt: " – ".join(fmt.format(f(r[key] for r in sel)) for f in (min, max))
            print(f"| {method} | {preset} | {span('center_error', '{:.2f}')} | {span('spacing_error', '{:+.3%}')} | "
                  f"{span('trace_rms', '{:.2f}')} | {span('wrong_groove', '{:.2%}')} | {span('sound_correlation', '{:.3f}')} | "
                  f"{np.median([r['seconds'] for r in sel]):.2f} |")


if __name__ == "__main__":
    main()
