# Spacing error budget on simulated cards (Nov 2026)

`.venv/bin/python experiments/spacing_budget.py <out.json>`: 6 cards (typical
and hard, seeds 1–3); the low-res FFT spacing replaced by the true spacing ×
(1 + error), then the usual pipeline: coherence center, strip along that
spiral, refit (grid ±2.5% spacing, ±1.5 spacings center, then robust least
squares), trace, sound. Ranges over the 3 seeds. (For scale: the FFT itself
is within 0.08% on typical cards, 0.11% on hard ones.)

| spacing error | preset | low-res center px | refit center px | refit spacing % | trace rms px | wrong groove | sound corr |
|---|---|---|---|---|---|---|---|
| -10.0% | typical | 3.02 – 8.69 | 5.62 – 16.37 | -12.390 – -8.348 | 2.14 – 3.86 | 70.7% – 80.6% | 0.791 – 0.863 |
| -10.0% | hard | 8.61 – 15.83 | 9.25 – 17.32 | -9.571 – -8.544 | 3.20 – 6.43 | 72.2% – 78.3% | 0.600 – 0.749 |
| -5.0% | typical | 5.31 – 11.69 | 0.28 – 0.54 | -0.234 – -0.228 | 2.75 – 3.48 | 0.0% – 0.0% | 0.813 – 0.845 |
| -5.0% | hard | 2.35 – 11.77 | 0.23 – 17.04 | -0.257 – -0.120 | 4.48 – 5.26 | 0.8% – 46.3% | 0.659 – 0.696 |
| -3.0% | typical | 1.70 – 7.48 | 0.06 – 0.23 | -0.093 – -0.076 | 2.91 – 2.93 | 0.0% – 0.0% | 0.846 – 0.848 |
| -3.0% | hard | 6.24 – 8.72 | 0.23 – 0.51 | -0.090 – -0.063 | 4.04 – 5.13 | 0.8% – 1.6% | 0.677 – 0.719 |
| -2.0% | typical | 0.29 – 9.18 | 0.09 – 0.21 | -0.024 – -0.006 | 1.11 – 1.47 | 0.0% – 0.0% | 0.884 – 0.890 |
| -2.0% | hard | 2.41 – 8.48 | 0.18 – 0.38 | -0.018 – +0.005 | 2.30 – 2.81 | 0.2% – 1.2% | 0.766 – 0.785 |
| -1.0% | typical | 0.21 – 0.45 | 0.09 – 0.23 | +0.030 – +0.041 | 0.71 – 0.93 | 0.0% – 0.0% | 0.890 – 0.898 |
| -1.0% | hard | 0.31 – 0.62 | 0.17 – 0.33 | +0.049 – +0.071 | 1.63 – 1.85 | 0.2% – 0.5% | 0.795 – 0.796 |
| -0.5% | typical | 0.22 – 0.29 | 0.09 – 0.24 | +0.034 – +0.043 | 0.62 – 0.87 | 0.0% – 0.0% | 0.890 – 0.899 |
| -0.5% | hard | 0.27 – 0.33 | 0.16 – 0.34 | +0.051 – +0.068 | 1.41 – 1.75 | 0.2% – 0.4% | 0.798 – 0.799 |
| +0.0% | typical | 0.12 – 0.27 | 0.09 – 0.24 | +0.012 – +0.027 | 0.55 – 0.84 | 0.0% – 0.0% | 0.891 – 0.901 |
| +0.0% | hard | 0.19 – 0.30 | 0.16 – 0.32 | +0.016 – +0.038 | 1.34 – 1.70 | 0.2% – 0.4% | 0.800 – 0.802 |
| +0.5% | typical | 0.18 – 0.24 | 0.08 – 0.23 | -0.018 – +0.001 | 0.56 – 0.70 | 0.0% – 0.0% | 0.891 – 0.902 |
| +0.5% | hard | 0.14 – 0.75 | 0.19 – 0.26 | -0.031 – +0.003 | 1.34 – 1.71 | 0.2% – 0.4% | 0.801 – 0.803 |
| +1.0% | typical | 0.12 – 0.31 | 0.08 – 0.20 | -0.027 – -0.016 | 0.63 – 0.76 | 0.0% – 0.0% | 0.892 – 0.902 |
| +1.0% | hard | 0.05 – 1.19 | 0.20 – 0.22 | -0.063 – -0.019 | 1.50 – 1.68 | 0.3% – 0.4% | 0.800 – 0.803 |
| +2.0% | typical | 0.20 – 9.04 | 0.07 – 0.22 | -0.034 – -0.018 | 0.90 – 1.45 | 0.0% – 0.0% | 0.889 – 0.902 |
| +2.0% | hard | 1.78 – 8.66 | 0.09 – 0.35 | -0.051 – -0.010 | 1.75 – 5.56 | 0.3% – 2.7% | 0.670 – 0.797 |
| +3.0% | typical | 7.66 – 10.60 | 0.25 – 0.38 | -0.070 – -0.054 | 2.16 – 3.26 | 0.0% – 0.2% | 0.840 – 0.878 |
| +3.0% | hard | 8.39 – 10.83 | 0.06 – 0.47 | -0.081 – -0.047 | 4.50 – 5.73 | 1.1% – 2.5% | 0.666 – 0.724 |
| +5.0% | typical | 0.54 – 8.78 | 0.09 – 0.52 | -0.235 – -0.215 | 2.75 – 2.94 | 0.0% – 0.2% | 0.852 – 0.857 |
| +5.0% | hard | 2.13 – 6.40 | 16.41 – 18.32 | +0.210 – +7.299 | 3.54 – 4.39 | 47.4% – 65.1% | 0.729 – 0.748 |
| +10.0% | typical | 4.29 – 10.44 | 17.23 – 20.51 | +6.694 – +10.017 | 3.04 – 4.49 | 55.9% – 71.4% | 0.754 – 0.817 |
| +10.0% | hard | 4.39 – 10.28 | 9.83 – 20.35 | +6.984 – +11.301 | 3.32 – 5.89 | 58.3% – 73.5% | 0.649 – 0.755 |

Findings:

- Within ±1% nothing changes: centers, refit, trace (0.55–0.93 px typical)
  and sound (0.89–0.90) are as with the true spacing.
- The low-res (symmetry) center is the most sensitive step on cards: up to
  ~9 px off at ±2%, 2–16 px at ±3–10%. On the spacing page's spirals
  (15–20 turns) it tolerated 5%; cards reach ~95 spacings out, so a spacing
  error puts their turns out of step ~5× sooner.
- The refit rescues the geometry up to ±3%: center 0.1–0.5 px, spacing
  within 0.1%, even when the low-res center was 9 px off (its grid searches
  ±1.5 spacings). At ±5% it still does on typical cards, but fails on 1 of 3
  hard cards at −5% and all 3 at +5%; at ±10% every card fails (center
  10–20 px off, spacing 7–12% off, 56–80% wrong groove).
- But the trace and sound degrade from ±2%: trace 1.1–1.5 px at ±2%, 2–3 px
  at ±3% (typical), sound 0.85 instead of 0.90; hard cards worse. The
  geometry is right, but the strip was sampled along the wrong spiral
  (columns ±1 wrong spacing about a spiral that drifts off the groove), so
  the offsets the trace uses are worse. A second strip pass along the
  refitted spiral, only when the refit corrected a lot, should recover
  that (not yet tested).
- Budget: ~±1% for full quality, ~±3% before the geometry fails. The FFT is
  10–40× inside it. The nominal spacing (used when the FFT's peak is on the
  window's edge) could be off by up to ~33% across machines: far outside, so
  that fallback should be treated as a failure, not silently used.
