# Project context (for new Claude sessions)

A condensed record of the long Cowork conversation (Nov 2026) that built most
of this repo, so a new session — e.g. `claude --remote-control` started in
~/Desktop/cc — can continue with the same understanding. CLAUDE.md has the
technical notes per page and module; this file is the story, the goals,
Adam's preferences and the open questions.

## Goal

Recover audio from scanned "sonorine" recording cards (paper cards with a
spiral groove; ~40 turns, 29 px groove spacing at full resolution, annulus
r ≈ 1600–2770 px in a ~5551² frame). The sound is hill-and-dale: cut into the
groove's depth, not sideways like vinyl. Real data and someone else's
pipeline (Tomaz's: photometric stereo → depth → groove mask → FFT spacing →
RANSAC spiral fit; groove tracing failed) are in ../tomaz-results (read-only).
Adam will try to get real depth maps; until then we work on simulated cards
calibrated from those images.

## How the work went (in order)

1. spacing.html — ring spacing from the 2D FFT (harmonic sum, coarse-to-fine
   window ×0.5–2 of a target, 1/√r turn weighting about a gradient-line
   center found by RANSAC on line pairs with tangential blur). Robust to
   noise; fails when local spacing varies beyond ~±30%.
2. center.html — center and phase from chunks of a spiral (components →
   robust per-chunk fits → shared median start → RANSAC combination over
   chunks). "Start 2" (median of per-chunk fits) was the best center under
   imperfect spirals.
3. card_js.html (first version of the third app, in the browser) — a
   simulated card through the whole pipeline. Went through several models:
   "realistic" (warp, slow height drift, dust, scratches, banding, damage,
   lateral audio) → Adam: audio is vertical (hill-and-dale), too much
   sideways wiggle, drop the local-contrast step and the imperfections, use
   an idealized flat card with grain; the stylus depth follows the sound and
   the groove disappears where the stylus would rise above the card.
4. Ported the third app to Python (cardlab/, build_card.py → static
   card.html + card/img, committed for GitHub Pages). Checked stage by stage
   against the JS (checks/compare_with_js.sh): agree to rounding; fixed
   cv2.remap's 1/32-px interpolation (now scipy map_coordinates).
5. FFT spacing: the annulus mask alone is the window (no Hann) — better.
6. Center search: Adam's idea of using the ring structure of the score map
   led to the current method — the spiral coherence map Z at every pixel by
   one FFT correlation with a spiral-wave kernel, then a J0 ring-pattern fit
   (experiments/center_search.py: median 0.07 px, never fails, no search
   window). Later ported to JS (coherence.js) and shown live on spacing.html. Gradient-based centers (RANSAC lines; Adam's "tilt" idea) were
   tested and dropped (sound in the depth makes along-groove gradients).

## Current pipeline (cardlab, see procedure.html Part 3)

Low res (1024²): mask to the hand-marked annulus → FFT spacing (peak within
±10% of nominal) → coherence map + J0 fit (center, phase). Full res: unrolled
strip along that spiral (a column every 3 px of groove, ±1 spacing),
demodulation per column → geometry refit modulo the spacing (grid start +
robust least squares) → trace locked to the refitted spiral (σ 48 px along
the groove) → sound = land minus groove bottom, relative to its slow average.
Typical cards: center ~0.1 px, trace ~0.5 px, no wrong groove, sound
correlation ~0.9 (limited by the measured grain level).

## Adam's preferences

- Python for experiments: small, easy-to-read functions; descriptive names;
  a few comments, no docstrings; factor shared code; lean on vetted
  libraries (OpenCV, scipy, scikit-image/learn, their RANSAC) and vectorized
  numpy. Experiments offline; results written up with numbers.
- Report honestly with numbers; test claims (e.g. many seeds, many simulated
  hand marks) before adopting; drop features that don't help rather than
  keep options.
- Prefers RANSAC-style robust methods where they fit.
- Keep docs current: procedure.html (method step by step), CLAUDE.md,
  README, index.html.
- Commit locally when asked ("check it in"); push when asked (works only
  from a session running on the Mac, e.g. remote-control; the Cowork sandbox
  can't push).
- Asks probing "why" questions; explain math concretely (e.g. the coherence
  score Z, its J0 ring pattern, why spacing errors matter).

## Open questions and ideas

- Robustness of the coherence map when the spacing wobbles over the card
  (untested): idea — sum |Z| over radial bands with free phase per band.
- Sensitivity of the center search to a wrong spacing: tested on the
  spacing page's spirals (7–15 turns, JS port): the center stays within
  ~0.15 px up to ±5% with no failures, but the phase shifts by ≈ 360° ×
  (mean radius / S) × ε. Untested on cards (~40 turns, ~76 spacings of mean
  radius); the full-res refit fits the spacing anyway.
- Better sound readout: fit the groove cross-section per column (matched
  filter), filter along the groove with the grain's spectrum.
- Put card imperfections back one at a time (warp, slow height drift, dust,
  damage) once the idealized pipeline is settled.
- Run on real depth maps (sonorine_001) when available.
- Adam's idea for later: RANSAC over N > 2 lines.
