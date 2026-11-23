# Coarse pass 1 (Nov 2026)

`experiments/coarse_pass1.py` (Adam's question): the geometry refit is
limited by the groove's drift, not noise, so can pass 1 (the wedges the refit
reads) use coarser columns, with only pass 2 at 1 px? 4 presets × seeds 1–5,
medians; seconds = the full-res stage only (no rendering, low-res, readout).

| pass 1 columns | preset | center px | spacing ppm | path rms px | wrong groove | sound corr | pass 1 s | total s |
|---|---|---|---|---|---|---|---|---|
| 1 px | typical | 0.126 | 58 | 0.146 | 0.00% | 0.8959 | 0.56 | 1.11 |
| 1 px | loud | 0.130 | 74 | 0.165 | 0.00% | 0.9335 | 0.57 | 1.14 |
| 1 px | hard | 0.197 | 235 | 0.787 | 0.08% | 0.8095 | 0.60 | 1.19 |
| 1 px | clean | 0.129 | 99 | 0.070 | 0.00% | 0.9595 | 0.60 | 1.18 |
| 2 px | typical | 0.126 | 58 | 0.146 | 0.00% | 0.8959 | 0.31 | 0.86 |
| 2 px | loud | 0.130 | 74 | 0.165 | 0.00% | 0.9335 | 0.31 | 0.88 |
| 2 px | hard | 0.197 | 236 | 0.793 | 0.08% | 0.8095 | 0.33 | 0.92 |
| 2 px | clean | 0.129 | 99 | 0.070 | 0.00% | 0.9595 | 0.33 | 0.91 |
| 4 px | typical | 0.126 | 58 | 0.146 | 0.00% | 0.8959 | 0.18 | 0.73 |
| 4 px | loud | 0.130 | 74 | 0.165 | 0.00% | 0.9335 | 0.18 | 0.75 |
| 4 px | hard | 0.197 | 236 | 0.796 | 0.10% | 0.8096 | 0.19 | 0.79 |
| 4 px | clean | 0.129 | 99 | 0.070 | 0.00% | 0.9595 | 0.19 | 0.78 |
| 8 px | typical | 0.126 | 55 | 0.146 | 0.00% | 0.8959 | 0.12 | 0.67 |
| 8 px | loud | 0.130 | 70 | 0.165 | 0.00% | 0.9335 | 0.12 | 0.69 |
| 8 px | hard | 0.196 | 243 | 0.814 | 0.12% | 0.8095 | 0.13 | 0.72 |
| 8 px | clean | 0.129 | 99 | 0.070 | 0.00% | 0.9595 | 0.13 | 0.76 |

Per card vs 1 px: the refit center changes by < 0.001 px at 2 and 4 px
(0.008 px at 8); the path rms rises by at most 0.005 / 0.008 / 0.026 px
(all on hard seed 1), wrong groove by at most 0.03% (4 px). Same center,
same sound: the refit is drift-limited. 4 px columns in pass 1 cut the
full-res stage by about a third (1.1 → 0.75 s).
