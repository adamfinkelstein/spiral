# Step 4's geometry fit: wedges vs. columns, noise weights, damage (Nov 2026)

`experiments/fit_columns_vs_wedges.py`; 4 presets × seeds 1–5, each clean
and with two kinds of damage. "lost": a 40° sector of grooves replaced by
noise 3× the groove rms, plus 8 deep scratches (data lost). "shifted": a
30° sector whose grooves are moved outward by S/3 (a warped or lifted
patch: clean-looking but wrong offsets). All fits on step 4's coarse
columns (every 4 px of the outer turn). Center error, px: median (max) over
5 cards, typical / loud / hard / clean; median |spacing error|; time of the
fit alone.

| method | clean | lost | shifted | time |
|---|---|---|---|---|
| A wedges, \|Z\| weights (the pipeline) | 0.11 (0.38) / 0.11 (0.38) / 0.21 (0.50) / 0.11 (0.37) | 0.12 / 0.11 / 0.22 / 0.11 | **1.19 (1.39) / 1.19 / 1.37 / 1.18** | 0.04 s |
| B every column's angle, same fit | 0.10 / 0.11 / 0.23 / 0.11 | 0.11 / 0.11 / 0.28 / 0.11 | 1.13 / 1.08 / 1.33 / 1.14 | 3.2 s |
| C every column's phasor, coherence loss | 0.08 / 0.08 / 0.26 / 0.08 | 0.09 / 0.10 / 0.30 / 0.09 | 1.01 / 1.01 / 1.28 / 1.00 | 0.3 s |
| D wedges, noise weights (within-wedge coherence) | 0.12 / 0.11 / 0.25 / 0.27 | 0.13 / 0.12 / 0.28 / 0.30 | 0.84 / 0.75 / 1.16 / 0.46 | 0.05 s |
| E wedges, Cauchy loss | 0.20 / 0.20 / 0.20 / 0.22 | 0.20 / 0.18 / 0.34 / 0.20 | 1.06 / 1.06 / 1.44 / 1.07 | 0.05 s |
| F wedges, drop wedges > S/6 off, refit | 0.27 / 0.28 / 0.26 / 0.28 | 0.27 / 0.25 / 0.37 / 0.29 | 0.98 / 0.99 / 1.33 / 0.93 | 0.08 s |
| **G wedges, drop bad angular sectors, refit** | **0.11 (0.38) / 0.11 / 0.21 / 0.11** | **0.10 / 0.11 / 0.22 / 0.11** | **0.12 (0.35) / 0.12 / 0.26 / 0.12** | 0.12 s |

Spacing errors are all 0.01–0.04%.

Findings:

- **Wedges vs. all columns**: fitting every column's angle (B) gives the
  same center as the wedges, 80× slower; maximizing the coherence of all
  column phasors (C) is a little better on the grainy-but-normal cards
  (0.08 vs 0.11 px) and worse on hard ones (0.26 vs 0.21), 7× slower. The
  fit is limited by the groove's drift, not by how the columns are
  combined, so the wedges cost nothing in accuracy.
- **Noise weights (D)**: no help, and worse on the clean preset (0.27 vs
  0.11 px): without grain the within-wedge coherence R is close to 1, and
  what spreads the columns' angles is the drift's curvature, not noise, so
  the weights end up dominated by a few wedges. Lost data (noise, scratches)
  is already harmless for A: such wedges have small |Z|.
- **Coherent damage is the real threat**: a patch of grooves that is
  displaced but clean pulls every per-wedge method by ~1 px. Per-wedge
  outlier tests (E, F) can't separate it from the drift (patch ~7 px off,
  drift ±3.4 px per turn) and cost accuracy on good cards.
- **Sector consistency (G) works**: grouping the residuals by angle on the
  card, over all turns, averages the drift away (~3.4/√38 ≈ 0.55 px) while
  a damaged patch stays (~7 px); dropping sectors beyond 3 MADs of the
  sectors' medians and refitting brings the shifted cards back to 0.12 px
  and changes nothing on undamaged ones (it drops nothing there). Removing
  the patch exactly gave 0.05 px on typical card 1.
- So the wedges earn their place in step 4 beyond speed: each one is a
  reliable local measurement with an angle and a turn, which is what makes
  sector (and, by the same idea, band-of-turns) consistency tests possible.
