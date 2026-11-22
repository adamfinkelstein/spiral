# Unrolled rectangle + wedges (Nov 2026)

`experiments/unrolled_wedges.py` (Adam's idea): the annulus unrolled along
the low-res coherence spiral (columns at equal arc length, rows = radial
offset; rows ±S/2 cover every pixel once), sampled lazily per block of
columns; wedges of 40 per turn, Z = one untapered period per column summed
over the wedge; no image refit (the strip's geometry refit runs on the
wedge offsets only, to lock the path to the right groove). 4 presets ×
seeds 1–5, medians; seconds exclude rendering and the low-res stage.

| method | preset | path rms px | wrong groove | sound corr | seconds |
|---|---|---|---|---|---|
| strip, cos2 +-S (now) | typical | 0.59 | 0.00% | 0.896 | 0.54 |
| strip, cos2 +-S (now) | loud | 0.68 | 0.00% | 0.934 | 0.55 |
| strip, cos2 +-S (now) | hard | 1.32 | 0.25% | 0.802 | 0.57 |
| strip, cos2 +-S (now) | clean | 0.56 | 0.00% | 0.966 | 0.54 |
| strip, rect +-S/2 | typical | 0.27 | 0.00% | 0.893 | 0.52 |
| strip, rect +-S/2 | loud | 0.32 | 0.00% | 0.931 | 0.54 |
| strip, rect +-S/2 | hard | 1.21 | 0.15% | 0.799 | 0.56 |
| strip, rect +-S/2 | clean | 0.16 | 0.00% | 0.962 | 0.52 |
| pixel sectors | typical | 0.22 | 0.00% | 0.892 | 3.34 |
| pixel sectors | loud | 0.28 | 0.00% | 0.930 | 3.32 |
| pixel sectors | hard | 1.07 | 0.01% | 0.797 | 3.38 |
| pixel sectors | clean | 0.18 | 0.00% | 0.961 | 3.39 |
| unrolled, 1 px columns, 1 pass | typical | 0.21 | 0.00% | 0.893 | 0.49 |
| unrolled, 1 px columns, 1 pass | loud | 0.26 | 0.00% | 0.931 | 0.48 |
| unrolled, 1 px columns, 1 pass | hard | 1.06 | 0.06% | 0.800 | 0.50 |
| unrolled, 1 px columns, 1 pass | clean | 0.16 | 0.00% | 0.962 | 0.49 |
| unrolled, 1 px columns, pass 2 rows groove | typical | 0.23 | 0.00% | 0.891 | 0.94 |
| unrolled, 1 px columns, pass 2 rows groove | loud | 0.29 | 0.00% | 0.928 | 0.94 |
| unrolled, 1 px columns, pass 2 rows groove | hard | 1.13 | 0.52% | 0.796 | 0.97 |
| unrolled, 1 px columns, pass 2 rows groove | clean | 0.19 | 0.00% | 0.960 | 0.94 |
| unrolled, 1 px columns, pass 2 rows midway | typical | 0.15 | 0.00% | 0.893 | 0.95 |
| unrolled, 1 px columns, pass 2 rows midway | loud | 0.16 | 0.00% | 0.930 | 0.94 |
| unrolled, 1 px columns, pass 2 rows midway | hard | 0.82 | 0.07% | 0.800 | 0.97 |
| unrolled, 1 px columns, pass 2 rows midway | clean | 0.08 | 0.00% | 0.962 | 0.95 |
| unrolled, 3 px columns, 1 pass | typical | 0.21 | 0.00% | 0.893 | 0.20 |
| unrolled, 3 px columns, 1 pass | loud | 0.26 | 0.00% | 0.931 | 0.20 |
| unrolled, 3 px columns, 1 pass | hard | 1.06 | 0.06% | 0.800 | 0.21 |
| unrolled, 3 px columns, 1 pass | clean | 0.16 | 0.00% | 0.962 | 0.20 |
| unrolled, 3 px columns, pass 2 rows groove | typical | 0.23 | 0.00% | 0.891 | 0.37 |
| unrolled, 3 px columns, pass 2 rows groove | loud | 0.29 | 0.00% | 0.928 | 0.37 |
| unrolled, 3 px columns, pass 2 rows groove | hard | 1.13 | 0.53% | 0.796 | 0.38 |
| unrolled, 3 px columns, pass 2 rows groove | clean | 0.19 | 0.00% | 0.960 | 0.37 |
| unrolled, 3 px columns, pass 2 rows midway | typical | 0.15 | 0.00% | 0.893 | 0.37 |
| unrolled, 3 px columns, pass 2 rows midway | loud | 0.16 | 0.00% | 0.930 | 0.37 |
| unrolled, 3 px columns, pass 2 rows midway | hard | 0.81 | 0.07% | 0.800 | 0.38 |
| unrolled, 3 px columns, pass 2 rows midway | clean | 0.08 | 0.00% | 0.962 | 0.37 |

Findings:

- One pass already matches or beats the pixel sectors (0.21 / 0.26 / 1.06
  / 0.16 px vs 0.22 / 0.28 / 1.07 / 0.18) at 0.20 s (3 px columns) instead
  of 3.3 s. Columns every 1 px give the same as every 3 px.
- Where the one-period window sits matters. Centered on the groove (the
  pixel sectors' re-centering) it is slightly worse than on the spiral, and
  on hard cards it lands on the wrong groove more (0.5%). Best is centered
  midway between the lands either side of the groove, i.e. at
  (groove + mean of its neighbours' offsets) / 2, the neighbours being the
  same column one turn (2π) either side in the rectangle: the cut then falls
  in the land on both sides, where the window's ends see the least groove.
  Their drift is unrelated to this turn's, so this is about half the drift.
  Typical 1: spiral 0.21, groove 0.37, midway 0.16, midway with the true
  offsets 0.158 px.
- Midway, 3 px columns: 0.15 / 0.16 / 0.81 / 0.08 px (typical / loud /
  hard / clean), hard wrong groove 0.07%, 0.37 s: the best path of
  everything tried, at under the strip's time. Sound the same as all others
  (within 0.005).
- Tried and dropped (2 cards): a per-wedge tilt (slope from the phase step
  between neighbouring columns): 1.9 / 4.9 px, the slope too noisy.
- Not tried yet: the midway rule in the strip (one-period window) and the
  pixel sectors; a stretch term (needed on real cards: the low-res spiral's
  error must stay within the rows).
