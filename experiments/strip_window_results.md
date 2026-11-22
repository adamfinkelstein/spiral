# Strip demodulation window (Nov 2026)

`experiments/strip_window.py`, 4 presets × seeds 1–5, medians. The strip's
path error regressed on the true drift (the true groove's offset from the
refitted spiral): slope −0.1 = the path follows only 90% of the drift.

|---|---|---|---|---|---|
| cos2 +-S, trend | typical | 0.59 | 0.00% | 0.896 | -0.57, -0.106 |
| cos2 +-S, trend | loud | 0.68 | 0.00% | 0.934 | -0.58, -0.121 |
| cos2 +-S, trend | hard | 1.32 | 0.25% | 0.802 | -0.31, -0.090 |
| cos2 +-S, trend | clean | 0.56 | 0.00% | 0.966 | -0.62, -0.106 |
| cos2 +-S, mean | typical | 0.50 | 0.00% | 0.895 | -0.63, -0.099 |
| cos2 +-S, mean | loud | 0.57 | 0.00% | 0.934 | -0.63, -0.111 |
| cos2 +-S, mean | hard | 1.28 | 0.19% | 0.802 | -0.30, -0.087 |
| cos2 +-S, mean | clean | 0.45 | 0.00% | 0.965 | -0.70, -0.099 |
| cos2 +-S, none | typical | 0.50 | 0.00% | 0.895 | -0.63, -0.099 |
| cos2 +-S, none | loud | 0.57 | 0.00% | 0.934 | -0.63, -0.111 |
| cos2 +-S, none | hard | 1.28 | 0.19% | 0.802 | -0.30, -0.087 |
| cos2 +-S, none | clean | 0.45 | 0.00% | 0.965 | -0.70, -0.099 |
| rect +-S/2, none | typical | 0.27 | 0.00% | 0.893 | -0.21, -0.017 |
| rect +-S/2, none | loud | 0.32 | 0.00% | 0.931 | -0.29, -0.028 |
| rect +-S/2, none | hard | 1.21 | 0.15% | 0.799 | -0.21, -0.057 |
| rect +-S/2, none | clean | 0.16 | 0.00% | 0.962 | -0.36, -0.017 |
| rect +-S, none | typical | 1.62 | 0.00% | 0.896 | -0.77, -0.386 |
| rect +-S, none | loud | 1.65 | 0.00% | 0.937 | -0.75, -0.391 |
| rect +-S, none | hard | 2.97 | 0.36% | 0.786 | -0.60, -0.303 |
| rect +-S, none | clean | 1.61 | 0.00% | 0.970 | -0.78, -0.386 |
| sectors (re-centered) | typical | 0.22 | 0.00% | 0.892 | +nan, +nan |
| sectors (re-centered) | loud | 0.28 | 0.00% | 0.930 | +nan, +nan |
| sectors (re-centered) | hard | 1.07 | 0.01% | 0.797 | +nan, +nan |
| sectors (re-centered) | clean | 0.18 | 0.00% | 0.961 | +nan, +nan |

Findings:

- The pull toward the spiral comes from the neighbouring turns inside the
  window, not from the taper's shape. Each column is centered on the
  spiral; a window wider than one period also takes in the grooves of the
  turns either side, whose drift is unrelated (corr ~0 one turn apart), so
  the estimate is pulled toward their average, i.e. the spiral. More of the
  neighbours, more pull: rect ±S (two full periods) slope −0.39, cos² ±S
  −0.10, rect ±S/2 (one period) −0.02.
- Removing the linear trend costs a little more (0.59 → 0.50 px typical);
  removing the mean or nothing is the same (the window sums a full period).
- rect ±S/2, nothing removed: path 0.27 / 0.32 / 1.21 / 0.16 px
  (typical / loud / hard / clean) vs 0.59 / 0.68 / 1.32 / 0.56 now, close to
  the re-centered sectors (0.22 / 0.28 / 1.07 / 0.18); hard wrong groove
  0.15% vs 0.25% (sectors 0.01%). Sound within 0.003 of now everywhere.
- What the sectors still have over it, mostly on hard cards: bands
  re-centered on the groove (the strip's window stays on the spiral, so a
  groove drifted 3 px still lets a little of a neighbour in) and weighting
  by cell strength.
