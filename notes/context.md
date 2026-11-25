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
7. Symmetry center: on the spacing page Adam saw that a stretched spiral
   (aspect ≠ 1) splits the map's bright spot into lobes (the J0 fit then
   locks onto one) but the map stays point-symmetric about the true center.
   The center is now that symmetry center (self-convolution of the windowed
   |Z| on a crop), in JS and cardlab; the J0 fit is dropped (Adam: sub-pixel
   accuracy isn't needed, the full-res refit fits the center anyway).
8. Aligned the spacing page with cardlab (Nov 2026): a simulated hand
   mark and donut mask, no Hann, ±50% window, profile smoothing 1.5, and the
   spacing as the peak of the smoothed profile; the harmonic sum and the
   gradient-line center were dropped from the page (the harmonic sum was
   more accurate on drawn spirals with varying spacing, but failed on
   cards). cardlab also dropped its 3%-from-nominal fallback, which broke
   cards cut on other machines (25.9 / 32.2 px vs. 29 nominal).

## Current pipeline (cardlab, see procedure.html steps 0–6)

Low res (1024²): mask to the hand-marked annulus → FFT spacing (peak within
±10% of nominal) → coherence map → its center of point symmetry (center),
arg Z there (phase). Full res (Nov 2026, Adam's idea; replaced the strip):
the annulus unrolled into a rectangle along that spiral (columns at equal
steps in theta, i.e. time, ~1 px apart on the outer turn; rows ±S/2, sampled
only when needed; the test sound is also a function of theta) → wedges of 1/40 turn, one
period of rows demodulated per column → geometry refit modulo the spacing on
the wedges (pass 1, on 4 px columns: the refit is limited by wedge noise and drift, not sampling) (grid start + robust least squares) → pass 2 with each column's
rows midway between the lands → path locked to the refitted spiral → sound =
land minus groove bottom, relative to its slow average. Typical cards:
center ~0.1–0.3 px, path ~0.15 px, no wrong groove, sound correlation ~0.9
(limited by the readout and the measured grain level, not the path).
Alternatives tried (strip with ±S or one-period windows, per-pixel sectors,
re-centering on the groove, per-wedge tilt): considered.html Part 3.

## Adam's preferences

- Constants: round and justifiable (he plans a paper), chosen inside the
  range the synthetic experiments allow, with the reason written down
  (e.g. a peak at least 2× its background rather than a fitted 0.65).
- Python for experiments: small, easy-to-read functions; descriptive names;
  a few comments, no docstrings; factor shared code; lean on vetted
  libraries (OpenCV, scipy, scikit-image/learn, their RANSAC) and vectorized
  numpy. Experiments offline; results written up with numbers.
- Report honestly with numbers; test claims (e.g. many seeds, many simulated
  hand marks) before adopting; drop features that don't help rather than
  keep options.
- Prefers RANSAC-style robust methods where they fit.
- Keep docs current: procedure.html (method step by step), considered.html
  (alternatives dropped), CLAUDE.md,
  README, index.html.
- Commit locally when asked ("check it in"), and never offer to; push when asked (works only
  from a session running on the Mac, e.g. remote-control; the Cowork sandbox
  can't push).
- Asks probing "why" questions; explain math concretely (e.g. the coherence
  score Z, its J0 ring pattern, why spacing errors matter).

## Real cards (data/cards/, Nov 2026)

- Ezra's card (`data/cards/ezra_card.jpg`, a 2000² grey rendering; results
  and lessons in `experiments/ezra_card/README.md`): cardlab runs on it as
  it is (spacing 9.9 px, 52.5 turns, coherence 0.75, path 0.064 S rms from a
  perfect spiral). Winding: outward counterclockwise as displayed, like
  Tomaz's sonorine_001 (coherence map with both senses: 89.7 vs 11.1, and
  40.2 vs 25.3 on Tomaz's groove mask). So since Nov 2026 cardlab and the
  JS pages measure angles counterclockwise from 3 o'clock as displayed (y
  up), and the simulated cards wind the same way.
- Done 24 Nov 2026 as the `ezra` preset (CLAUDE.md Handoff; slow surface
  height left out). Suggested then: sound rms ~0.3 (the
  card's relative depth modulation reads 0.29 vs ~0.46 for our typical
  card); a tonal component (~195 cycles/turn peak); maybe slow surface
  height variation (power below 50 cycles/turn) and an ~11% depth trend
  from inner to outer turns; presets spanning inner/outer radius 0.42–0.58
  and 40–52 turns. Drift: this card 0.064 S, sonorine_001 0.10–0.12 S.

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
- Spacing failures (Nov 2026): an FFT peak on the edge of the search window
  now fails the card (no fallback to the nominal; the later steps survive
  only ~±3–5% spacing error). Come back to such cards later (Adam). The
  full-res refit is on hold.
- Drift: the real card's groove offsets (Tomaz's images 21, 26) are ~3 px
  rms and change almost completely from one turn to the next; the model
  now matches (3.2 px rms, periods 0.3–1 turn), and Adam thinks real drift
  is slower still. Wobble was removed. A second strip pass along the
  refitted spiral flattened step f but didn't improve the center
  (drift-limited), so it was dropped (Nov 2026).
- Groove identity: every method names a groove's turn by the nearest turn of
  the geometry model's spiral, so a groove drifting more than S/2 from it lands on the
  wrong turn. Idea: grooves can't cross, so check their order across turns
  at each angle (easy in the rectangle).
- Put card imperfections back one at a time (warp, slow height drift, dust,
  damage) once the idealized pipeline is settled.
- Stretched cards: the low-res center now survives up to 3% stretch, but
  the full-res refit has no stretch term (r·cos 2α, r·sin 2α); needed if
  real scans can be off by more than ~0.3%.
- Run on real depth maps (sonorine_001) when available.
- Adam's idea for later: RANSAC over N > 2 lines.
