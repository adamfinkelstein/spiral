# Local spiral coherence in cells vs. the full-res strip (Nov 2026)

`.venv/bin/python experiments/cell_coherence.py typical,loud,hard,clean 1,2,3,4,5 <out.json>`.
Both start from the same low-res spiral. **Strip** (cardlab now): columns
every 3 px along the spiral, each a radial line ±1 spacing demodulated; refit
of center, spacing and phase modulo S; trace locked to the refit plus a
slowly varying residual. **Cells**: every annulus pixel goes to its nearest
arm (turn) and an angular sector (K per turn); per cell Z = Σ v e^{-iu},
u = r/pitch − (angle − phase); the angle of Z is the groove's offset in the
cell (mod S), |Z| its strength. The same refit on the cells (~40 K numbers),
then the cells again about the refitted spiral; the path = the refitted
spiral + those cell offsets, interpolated (as phasors) to columns every 3 px;
the sound is read along it as now. Ranges over 5 seeds; time = median
seconds for everything after the low-res stage except the sound readout.

| method | preset | center px | spacing % | trace rms px | wrong groove | sound corr | seconds |
|---|---|---|---|---|---|---|---|
| strip | typical | 0.09 – 0.33 | +0.010% – +0.023% | 0.54 – 0.84 | 0.00% – 0.00% | 0.891 – 0.910 | 0.53 |
| strip | loud | 0.09 – 0.34 | +0.014% – +0.027% | 0.61 – 0.91 | 0.00% – 0.00% | 0.930 – 0.945 | 0.55 |
| strip | hard | 0.16 – 0.43 | +0.015% – +0.047% | 0.99 – 1.70 | 0.03% – 0.41% | 0.800 – 0.829 | 0.58 |
| strip | clean | 0.09 – 0.33 | +0.009% – +0.025% | 0.51 – 0.83 | 0.00% – 0.00% | 0.960 – 0.976 | 0.53 |
| cells low-res, 40/turn | typical | 0.13 – 0.34 | +0.001% – +0.028% | 0.30 – 0.84 | 0.00% – 0.00% | 0.886 – 0.906 | 0.09 |
| cells low-res, 40/turn | loud | 0.13 – 0.34 | +0.001% – +0.028% | 0.35 – 0.86 | 0.00% – 0.00% | 0.924 – 0.941 | 0.10 |
| cells low-res, 40/turn | hard | 0.11 – 0.54 | -0.016% – +0.055% | 1.22 – 1.67 | 0.21% – 0.81% | 0.795 – 0.824 | 0.10 |
| cells low-res, 40/turn | clean | 0.12 – 0.33 | +0.002% – +0.026% | 0.28 – 0.84 | 0.00% – 0.00% | 0.953 – 0.970 | 0.10 |
| cells low-res, 80/turn | typical | 0.13 – 0.34 | +0.002% – +0.028% | 0.32 – 0.85 | 0.00% – 0.00% | 0.886 – 0.906 | 0.13 |
| cells low-res, 80/turn | loud | 0.13 – 0.34 | +0.001% – +0.028% | 0.39 – 0.88 | 0.00% – 0.00% | 0.923 – 0.941 | 0.13 |
| cells low-res, 80/turn | hard | 0.11 – 0.53 | -0.016% – +0.055% | 1.23 – 1.72 | 0.19% – 0.83% | 0.794 – 0.824 | 0.14 |
| cells low-res, 80/turn | clean | 0.12 – 0.34 | +0.002% – +0.026% | 0.28 – 0.85 | 0.00% – 0.00% | 0.953 – 0.969 | 0.13 |
| cells full-res, 40/turn | typical | 0.08 – 0.39 | -0.025% – +0.008% | 0.22 – 0.37 | 0.00% – 0.00% | 0.886 – 0.906 | 1.48 |
| cells full-res, 40/turn | loud | 0.08 – 0.39 | -0.028% – +0.004% | 0.27 – 0.41 | 0.00% – 0.00% | 0.925 – 0.942 | 1.51 |
| cells full-res, 40/turn | hard | 0.16 – 0.52 | -0.059% – +0.008% | 0.85 – 1.44 | 0.00% – 0.32% | 0.794 – 0.824 | 1.54 |
| cells full-res, 40/turn | clean | 0.08 – 0.38 | -0.026% – +0.005% | 0.19 – 0.30 | 0.00% – 0.00% | 0.954 – 0.972 | 1.54 |
| cells full-res, 80/turn | typical | 0.08 – 0.39 | -0.025% – +0.007% | 0.25 – 0.41 | 0.00% – 0.00% | 0.886 – 0.906 | 1.53 |
| cells full-res, 80/turn | loud | 0.08 – 0.39 | -0.028% – +0.004% | 0.30 – 0.46 | 0.00% – 0.00% | 0.924 – 0.941 | 1.55 |
| cells full-res, 80/turn | hard | 0.16 – 0.52 | -0.059% – +0.007% | 0.89 – 1.54 | 0.00% – 0.43% | 0.794 – 0.824 | 1.60 |
| cells full-res, 80/turn | clean | 0.08 – 0.38 | -0.026% – +0.006% | 0.18 – 0.30 | 0.00% – 0.00% | 0.954 – 0.972 | 1.58 |

Findings:

- Full-res cells, 40 per turn, trace the groove 2–3× better than the strip:
  0.22–0.37 px on typical cards (strip 0.54–0.84), 0.19–0.30 clean; hard
  cards 0.85–1.44 px (strip 0.99–1.70), wrong groove 0–0.32% (0.03–0.41%).
  Center (0.08–0.39 px) and spacing (within 0.06%) as good as the strip's.
- The sound doesn't improve with the better path (0.886–0.906 vs.
  0.891–0.910 on typical cards, ~0.005 lower): it is limited by the readout
  and the grain, not by where the path is.
- Low-res cells are as good as the strip on typical, loud and clean cards
  (trace 0.28–0.86 px) at 0.1 s, but worse on hard cards (wrong groove
  0.2–0.8%).
- 80 sectors per turn are no better than 40; smoothing the cells along the
  groove (smoke test) and 20 sectors are worse.
- Full-res cells take ~1.5 s (every pixel of the frame is visited); the strip
  ~0.55 s. Visiting only the annulus, or sampling the cells on a grid, would
  cut that.
- Fewer moving parts: no per-column demodulation, no trace locking; ~1500
  strong cell measurements instead of ~160 000 weak columns.

## Taper, re-centering, weak cells (Nov 2026)

Radial taper (a few cards, path rms px, clean / typical / hard, 2 seeds):
plain band 0.26 0.19 / 0.28 0.22 / 1.09 1.44; cos² taper over ±S (as the
strip's columns) 0.53 0.51 / 0.54 0.53 / 1.13 1.49; cos² over ±S/2 1.25 /
1.26 / 1.5–1.8; removing each cell's mean 0.31 0.26 / 0.33 0.30 / 1.05 1.41.
Centering the tapers on the groove instead of the arm didn't rescue them
(±S 0.48–0.53, ±S/2 0.57–0.73 on clean cards). Reason: the plain band is
exactly one groove period wide, and over exactly one period an untapered
window gives the groove's first Fourier component exactly, whatever its
shape; a taper biases it, pulling the offset toward the window's center.
That is probably also why the strip's columns (cos² over ±S) sit at ~0.55 px.
So the band stays untapered, and no mean is removed.

All 20 cards, full res, 40 sectors per turn, median path rms px:

| method | typical | loud | hard | clean | hard: wrong groove |
|---|---|---|---|---|---|
| strip | 0.59 | 0.68 | 1.32 | 0.56 | 0.25% |
| cells | 0.26 | 0.31 | 1.09 | 0.24 | 0.05% |
| cells, bands re-centered on the groove | 0.22 | 0.28 | 1.07 | 0.18 | 0.01% |
| + weak cells (confidence < 0.3) interpolated over | 0.22 | 0.28 | 1.15 | 0.18 | 0.21% |
| + weak cells (confidence < 0.5) interpolated over | 0.25 | 0.28 | 1.29 | 0.22 | 0.25% |

Ranges:

| method | preset | center px | spacing % | trace rms px | wrong groove | sound corr | seconds |
|---|---|---|---|---|---|---|---|
| strip | typical | 0.09 – 0.33 | +0.010% – +0.023% | 0.54 – 0.84 | 0.00% – 0.00% | 0.891 – 0.910 | 0.56 |
| strip | loud | 0.09 – 0.34 | +0.014% – +0.027% | 0.61 – 0.91 | 0.00% – 0.00% | 0.930 – 0.945 | 0.56 |
| strip | hard | 0.16 – 0.43 | +0.015% – +0.047% | 0.99 – 1.70 | 0.03% – 0.41% | 0.800 – 0.829 | 0.57 |
| strip | clean | 0.09 – 0.33 | +0.009% – +0.025% | 0.51 – 0.83 | 0.00% – 0.00% | 0.960 – 0.976 | 0.53 |
| cells | typical | 0.08 – 0.39 | -0.025% – +0.008% | 0.22 – 0.37 | 0.00% – 0.00% | 0.886 – 0.906 | 2.14 |
| cells | loud | 0.08 – 0.39 | -0.028% – +0.004% | 0.27 – 0.41 | 0.00% – 0.00% | 0.925 – 0.942 | 2.14 |
| cells | hard | 0.16 – 0.52 | -0.059% – +0.008% | 0.85 – 1.44 | 0.00% – 0.32% | 0.794 – 0.824 | 2.15 |
| cells | clean | 0.08 – 0.38 | -0.026% – +0.005% | 0.19 – 0.30 | 0.00% – 0.00% | 0.954 – 0.972 | 2.10 |
| cells, re-centered | typical | 0.08 – 0.39 | -0.025% – +0.008% | 0.17 – 0.48 | 0.00% – 0.00% | 0.886 – 0.906 | 3.36 |
| cells, re-centered | loud | 0.08 – 0.39 | -0.028% – +0.004% | 0.20 – 0.49 | 0.00% – 0.00% | 0.924 – 0.942 | 3.38 |
| cells, re-centered | hard | 0.16 – 0.52 | -0.059% – +0.008% | 0.79 – 1.42 | 0.00% – 0.53% | 0.795 – 0.824 | 3.43 |
| cells, re-centered | clean | 0.08 – 0.38 | -0.026% – +0.005% | 0.12 – 0.29 | 0.00% – 0.00% | 0.954 – 0.972 | 3.34 |
| cells, re-centered, weak < 0.3 interpolated | typical | 0.08 – 0.39 | -0.025% – +0.008% | 0.17 – 0.40 | 0.00% – 0.00% | 0.887 – 0.906 | 3.37 |
| cells, re-centered, weak < 0.3 interpolated | loud | 0.08 – 0.39 | -0.028% – +0.004% | 0.20 – 0.42 | 0.00% – 0.00% | 0.924 – 0.942 | 3.38 |
| cells, re-centered, weak < 0.3 interpolated | hard | 0.16 – 0.52 | -0.059% – +0.008% | 0.84 – 1.28 | 0.00% – 0.32% | 0.795 – 0.824 | 3.37 |
| cells, re-centered, weak < 0.3 interpolated | clean | 0.08 – 0.38 | -0.026% – +0.005% | 0.12 – 0.37 | 0.00% – 0.00% | 0.953 – 0.972 | 3.34 |
| cells, re-centered, weak < 0.5 interpolated | typical | 0.08 – 0.39 | -0.025% – +0.008% | 0.23 – 0.48 | 0.00% – 0.00% | 0.886 – 0.906 | 3.36 |
| cells, re-centered, weak < 0.5 interpolated | loud | 0.08 – 0.39 | -0.028% – +0.004% | 0.21 – 0.48 | 0.00% – 0.00% | 0.924 – 0.942 | 3.39 |
| cells, re-centered, weak < 0.5 interpolated | hard | 0.16 – 0.52 | -0.059% – +0.008% | 1.11 – 1.54 | 0.00% – 0.45% | 0.794 – 0.824 | 3.43 |
| cells, re-centered, weak < 0.5 interpolated | clean | 0.08 – 0.38 | -0.026% – +0.005% | 0.18 – 0.43 | 0.00% – 0.00% | 0.953 – 0.970 | 3.33 |

- Re-centering each cell's band on the groove (a third pass, shifted by the
  drift from the second) helps a little everywhere (typical 0.26 → 0.22,
  clean 0.24 → 0.18 px), at ~1 s more.
- Interpolating over weak cells (confidence = |Z| / median |Z|) doesn't help
  and hurts on hard cards. The interpolation already weights each cell by
  |Z| (it interpolates phasors |Z| e^{iφ}), so weak cells count little;
  dropping them throws away what they do say. Confidence enters as that soft
  weight, not as a cutoff.
- Sound is unchanged throughout (as before).
