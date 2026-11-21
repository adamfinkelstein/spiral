# Symmetry center vs. J0 fit on simulated cards (Nov 2026)

`experiments/symmetry_center.py typical,loud,hard,clean 1,2,3,4,5 ...`: 20 cards,
each stretched by `aspect` (x × aspect, y / aspect about the true center, low-res
image warped with cv2), 3 hand marks each (5, 30, 100 px off). Errors in
full-res px (spacing 29 px; low-res scale 5.42). Center methods on the same
coherence map:

- **fft+J0**: cardlab now (J0 fit at the map's brightest pixel)
- **sym w3 / w10**: center of point symmetry of |Z| (self-convolution of the
  windowed zero-mean |Z|, Gaussian window σ = 3 or 10 spacings about the peak,
  on a ±4σ box: ~0.003 / 0.010 s)

Median / max error, px (share over 1 px):

| preset | aspect | fft+J0 | sym w3 | sym w10 |
|---|---|---|---|---|
| typical | 1.0 | 0.04 / 0.20 (0%) | 0.25 / 0.39 (0%) | 0.29 / 0.41 (0%) |
| typical | 0.99 | 58.65 / 59.07 (100%) | 0.25 / 0.43 (0%) | 0.19 / 0.39 (0%) |
| typical | 1.01 | 58.69 / 59.21 (100%) | 0.24 / 0.52 (0%) | 0.23 / 0.50 (0%) |
| typical | 0.98 | 130.50 / 132.50 (100%) | 136.19 / 139.18 (100%) | 0.20 / 0.37 (0%) |
| typical | 1.02 | 130.48 / 132.26 (100%) | 135.92 / 139.04 (100%) | 0.17 / 0.65 (0%) |
| typical | 1.03 | 208.35 / 224.79 (100%) | 221.42 / 228.44 (100%) | 0.30 / 0.65 (0%) |
| loud | 1.0 | 0.04 / 0.21 (0%) | 0.25 / 0.40 (0%) | 0.28 / 0.42 (0%) |
| loud | 0.99 | 58.63 / 59.08 (100%) | 0.25 / 0.43 (0%) | 0.19 / 0.39 (0%) |
| loud | 1.01 | 58.69 / 59.20 (100%) | 0.24 / 0.53 (0%) | 0.23 / 0.51 (0%) |
| loud | 0.98 | 130.56 / 132.61 (100%) | 137.07 / 139.38 (100%) | 0.20 / 0.37 (0%) |
| loud | 1.02 | 130.52 / 132.36 (100%) | 136.42 / 139.13 (100%) | 0.17 / 0.65 (0%) |
| loud | 1.03 | 209.02 / 224.99 (100%) | 222.00 / 228.60 (100%) | 0.30 / 0.66 (0%) |
| hard | 1.0 | 0.52 / 2.07 (33%) | 0.79 / 2.05 (40%) | 0.83 / 2.13 (40%) |
| hard | 0.99 | 59.20 / 60.43 (100%) | 1.01 / 2.31 (53%) | 0.86 / 1.86 (47%) |
| hard | 1.01 | 57.82 / 61.02 (100%) | 0.51 / 70.08 (33%) | 0.61 / 2.13 (33%) |
| hard | 0.98 | 133.50 / 145.01 (100%) | 136.10 / 150.91 (100%) | 0.85 / 11.53 (20%) |
| hard | 1.02 | 131.05 / 142.45 (100%) | 132.36 / 148.12 (100%) | 0.76 / 148.51 (20%) |
| hard | 1.03 | 219.61 / 225.83 (100%) | 225.88 / 231.92 (100%) | 220.43 / 228.42 (93%) |
| clean | 1.0 | 0.04 / 0.20 (0%) | 0.25 / 0.39 (0%) | 0.28 / 0.41 (0%) |
| clean | 0.99 | 58.63 / 59.06 (100%) | 0.24 / 0.43 (0%) | 0.18 / 0.38 (0%) |
| clean | 1.01 | 58.68 / 59.23 (100%) | 0.24 / 0.53 (0%) | 0.23 / 0.51 (0%) |
| clean | 0.98 | 130.49 / 132.55 (100%) | 136.14 / 139.22 (100%) | 0.20 / 0.37 (0%) |
| clean | 1.02 | 130.66 / 132.31 (100%) | 135.92 / 139.00 (100%) | 0.16 / 0.67 (0%) |
| clean | 1.03 | 208.26 / 224.79 (100%) | 221.23 / 228.38 (100%) | 0.29 / 0.65 (0%) |

Findings:

- Any stretch of 1% or more breaks the J0 fit: the turns (up to ~95 spacings
  out) no longer add in step at the center, the bright spot splits, and the fit
  locks onto a lobe ~2 / 4.5 / 7 spacings away at 1 / 2 / 3% (59 / 130 / 210
  px). On the spacing page's small spirals (≤ 20 spacings out) the same happens
  only at 2–5%: the tolerance scales with 1 / (radius in spacings).
- The symmetry center survives if its window reaches from the peak to the
  center: σ 3 spacings works at ±1% (0.2 px), σ 10 at up to ±3% on typical,
  loud and clean cards (median 0.16–0.30 px, max 0.67, none over 1 px).
- Unstretched, the J0 fit is more precise: median 0.04 vs. 0.25–0.28 px
  (0.05 low-res px; half-pixel grid + parabola). Both are far below the
  later full-res refit's needs.
- Hard cards (drift 6 px): ~0.5–0.8 px for both unstretched (drift limits
  them); with σ 10, 1% is fine, 2% fails on 1 of 5 cards, 3% on nearly all.
- Idea: symmetry center (σ 10) first, then the J0 fit started from it, kept
  only if it stays within ~1/2 spacing: J0 precision when unstretched,
  symmetry robustness otherwise. Not yet tried.
