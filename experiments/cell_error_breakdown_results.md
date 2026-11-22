# Where a cell's error comes from (Nov 2026)

`.venv/bin/python experiments/cell_error_breakdown.py typical,loud,hard,clean 1,2,3 <out.json>`.
About one shared refitted spiral per card (full-res cells, 40 per turn), the
true groove's offset t(θ) is known every 3 px. Per cell: **noise** = measured
offset − the true offset's circular mean over the cell (split into strong
cells and weak ones, |Z| under half the median, and their share);
**averaging** = t(θ) − its cell mean (the groove moving inside a cell);
**ideal path** = interpolated from the true cell means (averaging +
interpolation, no noise); **measured path** = interpolated from the measured
cells (everything). Medians over 3 seeds, rms px.

| preset | res | sectors/turn | noise, all cells | strong cells | weak cells (share) | averaging | ideal path | measured path |
|---|---|---|---|---|---|---|---|---|
| typical | low | 10 | 0.50 | 0.32 | 3.28 (1.3%) | 1.21 | 0.74 | 0.94 |
| typical | low | 20 | 0.51 | 0.34 | 3.41 (1.0%) | 0.62 | 0.21 | 0.64 |
| typical | low | 40 | 0.52 | 0.38 | 3.36 (1.0%) | 0.31 | 0.05 | 0.61 |
| typical | low | 80 | 0.56 | 0.42 | 3.21 (1.5%) | 0.16 | 0.01 | 0.63 |
| typical | low | 160 | 0.62 | 0.46 | 2.76 (3.1%) | 0.08 | 0.00 | 0.69 |
| typical | full | 10 | 0.24 | 0.16 | 0.63 (0.8%) | 1.21 | 0.74 | 0.75 |
| typical | full | 20 | 0.24 | 0.19 | 0.65 (0.7%) | 0.62 | 0.21 | 0.37 |
| typical | full | 40 | 0.26 | 0.22 | 0.84 (0.6%) | 0.31 | 0.05 | 0.28 |
| typical | full | 80 | 0.30 | 0.27 | 1.20 (0.8%) | 0.16 | 0.01 | 0.30 |
| typical | full | 160 | 0.38 | 0.35 | 1.65 (2.6%) | 0.08 | 0.00 | 0.34 |
| loud | low | 10 | 0.52 | 0.36 | 3.52 (1.0%) | 1.21 | 0.74 | 0.98 |
| loud | low | 20 | 0.53 | 0.44 | 3.47 (1.2%) | 0.62 | 0.21 | 0.69 |
| loud | low | 40 | 0.54 | 0.43 | 3.46 (1.1%) | 0.31 | 0.05 | 0.66 |
| loud | low | 80 | 0.59 | 0.46 | 3.23 (2.0%) | 0.16 | 0.01 | 0.70 |
| loud | low | 160 | 0.71 | 0.55 | 1.98 (6.2%) | 0.08 | 0.00 | 0.76 |
| loud | full | 10 | 0.30 | 0.23 | 0.81 (0.8%) | 1.21 | 0.74 | 0.77 |
| loud | full | 20 | 0.29 | 0.26 | 0.75 (0.7%) | 0.62 | 0.21 | 0.42 |
| loud | full | 40 | 0.29 | 0.28 | 0.84 (0.6%) | 0.31 | 0.05 | 0.34 |
| loud | full | 80 | 0.36 | 0.32 | 1.15 (1.6%) | 0.16 | 0.01 | 0.36 |
| loud | full | 160 | 0.47 | 0.40 | 1.33 (6.1%) | 0.08 | 0.00 | 0.40 |
| hard | low | 10 | 1.52 | 0.94 | 5.20 (4.8%) | 1.88 | 1.39 | 1.89 |
| hard | low | 20 | 1.58 | 0.99 | 5.74 (4.6%) | 0.97 | 0.33 | 1.49 |
| hard | low | 40 | 1.60 | 1.01 | 5.67 (4.9%) | 0.49 | 0.08 | 1.51 |
| hard | low | 80 | 1.68 | 1.08 | 5.20 (6.4%) | 0.24 | 0.02 | 1.58 |
| hard | low | 160 | 1.92 | 1.22 | 4.76 (9.8%) | 0.12 | 0.01 | 1.64 |
| hard | full | 10 | 1.19 | 0.75 | 4.17 (5.3%) | 1.88 | 1.39 | 1.66 |
| hard | full | 20 | 1.31 | 0.73 | 4.84 (5.1%) | 0.97 | 0.33 | 1.40 |
| hard | full | 40 | 1.42 | 0.78 | 5.23 (5.4%) | 0.49 | 0.08 | 1.41 |
| hard | full | 80 | 1.46 | 0.84 | 4.72 (6.6%) | 0.24 | 0.02 | 1.46 |
| hard | full | 160 | 1.73 | 1.03 | 4.45 (9.8%) | 0.12 | 0.01 | 1.57 |
| clean | low | 10 | 0.47 | 0.31 | 3.16 (1.3%) | 1.21 | 0.74 | 0.95 |
| clean | low | 20 | 0.48 | 0.38 | 3.18 (1.2%) | 0.62 | 0.21 | 0.63 |
| clean | low | 40 | 0.53 | 0.36 | 3.11 (1.1%) | 0.31 | 0.05 | 0.60 |
| clean | low | 80 | 0.51 | 0.36 | 3.02 (1.2%) | 0.16 | 0.01 | 0.60 |
| clean | low | 160 | 0.53 | 0.38 | 2.76 (2.6%) | 0.08 | 0.00 | 0.62 |
| clean | full | 10 | 0.23 | 0.15 | 0.78 (0.8%) | 1.21 | 0.74 | 0.75 |
| clean | full | 20 | 0.21 | 0.16 | 0.69 (0.7%) | 0.62 | 0.21 | 0.36 |
| clean | full | 40 | 0.18 | 0.17 | 0.70 (0.7%) | 0.31 | 0.05 | 0.26 |
| clean | full | 80 | 0.18 | 0.18 | 0.64 (0.8%) | 0.16 | 0.01 | 0.24 |
| clean | full | 160 | 0.18 | 0.18 | 0.54 (2.2%) | 0.08 | 0.00 | 0.24 |

Findings:

- Cell size is not the limit. The averaging error halves with every doubling
  of sectors (1.21 px at 10 per turn, 0.31 at 40), but interpolating between
  cell centers removes nearly all of it: the ideal path is 0.05 px at 40 per
  turn (0.08 on hard cards). So 40 sectors per turn is enough.
- Pixel count is not the limit at full res either: the noise hardly changes
  from 10 to 80 sectors (4× more pixels per cell at 10), and on clean cards
  (no grain at all) it is still 0.17–0.18 px at every size. That floor is
  systematic, not random. A likely cause: each cell's band (±S/2 about its
  arm) also takes in the edges of the neighbouring grooves, which drift
  independently, so the band isn't one clean period of one groove.
- Grain adds a little on top (strong cells 0.22 px typical vs 0.17 clean).
- Weak cells (where the sound makes the groove shallow or absent) are rare
  but bad: ~0.7% of cells on typical / loud / clean with 0.6–0.8 px errors,
  5% on hard cards with 4–5 px, which is most of the hard cards' path error
  (strong cells 0.78 px, all 1.42).
- Low res: the noise is about twice full res (strong cells 0.36–0.46 px
  typical, 1.0 hard) and weak cells reach 3 px: fine for geometry, not for
  the path.
- The measured full-res path at 40 per turn is thus mostly that systematic
  floor plus the weak cells: 0.28 px typical (ideal 0.05), 1.41 hard.

Next to test: weight each cell's pixels across the band (e.g. cos² about the
arm, as the strip does) or center the band on the groove itself, to remove
the neighbours' edges (clean cards would show it directly); and, for weak
cells, borrow from neighbouring windows along the groove (adaptive windows)
or weight the interpolation by |Z|.
