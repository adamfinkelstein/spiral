# Center search at low resolution: grid vs. FFT map vs. sparse J0 fit

Offline experiment (Nov 2026), `experiments/center_search.py`; tables by
`experiments/center_search_report.py`. 32 cards (typical, loud, hard, clean ×
seeds 1–8), 10 simulated hand marks per card (2 each at 5, 15, 30, 60, 100 px
from the true center, random directions; radii with the preset's error). All
methods use the same masked low-res image and the FFT spacing.

- grid+NM: the current method — |Z| on a grid (0.15 spacing, ±60 px) about the
  mark from ~8000 sampled pixels, then Nelder–Mead on 5% of the annulus pixels.
- fft+NM: Z at every pixel at once (one FFT correlation of the image with a
  spiral-wave kernel, all pixels), global argmax, then the same Nelder–Mead.
- fft+J0: the same map, then a least-squares fit of a·J0(2π|c − c0|/S)
  (complex a) to the map within 2.5 spacings of its argmax.
- sparse+J0: complex Z on a coarse grid (0.45 spacing, ±60 px) about the mark,
  J0 fit to all of it; sparse+J0+NM: then Nelder–Mead.

32 cards, 320 marks in all; errors in full-res px

| method | median | 90% | max | > 3 px | time (median s) |
|---|---|---|---|---|---|
| grid+NM | 0.166 | 32.872 | 61.21 | 20.0% | 0.47 |
| fft+NM | 0.123 | 0.689 | 2.33 | 0.0% | 0.53 |
| fft+J0 | 0.069 | 0.573 | 2.12 | 0.0% | 0.47 |
| sparse+J0 | 0.254 | 31.812 | 94.43 | 20.6% | 0.06 |
| sparse+J0+NM | 0.163 | 32.484 | 91.78 | 20.3% | 0.14 |

By preset:

| method | preset | median | 90% | max | > 3 px |
|---|---|---|---|---|---|
| grid+NM | typical | 0.115 | 32.586 | 47.49 | 20.0% |
| grid+NM | loud | 0.129 | 32.652 | 47.46 | 20.0% |
| grid+NM | hard | 0.698 | 33.820 | 61.21 | 20.0% |
| grid+NM | clean | 0.111 | 32.596 | 47.46 | 20.0% |
| fft+NM | typical | 0.092 | 0.192 | 0.28 | 0.0% |
| fft+NM | loud | 0.109 | 0.205 | 0.33 | 0.0% |
| fft+NM | hard | 0.603 | 1.588 | 2.33 | 0.0% |
| fft+NM | clean | 0.092 | 0.188 | 0.27 | 0.0% |
| fft+J0 | typical | 0.049 | 0.164 | 0.18 | 0.0% |
| fft+J0 | loud | 0.051 | 0.164 | 0.18 | 0.0% |
| fft+J0 | hard | 0.538 | 1.882 | 2.12 | 0.0% |
| fft+J0 | clean | 0.043 | 0.161 | 0.18 | 0.0% |
| sparse+J0 | typical | 0.167 | 31.686 | 46.44 | 20.0% |
| sparse+J0 | loud | 0.202 | 31.726 | 46.36 | 18.8% |
| sparse+J0 | hard | 0.817 | 32.306 | 94.43 | 23.8% |
| sparse+J0 | clean | 0.168 | 31.780 | 46.35 | 20.0% |
| sparse+J0+NM | typical | 0.117 | 32.441 | 46.38 | 20.0% |
| sparse+J0+NM | loud | 0.127 | 32.392 | 47.22 | 18.8% |
| sparse+J0+NM | hard | 0.698 | 32.720 | 91.78 | 22.5% |
| sparse+J0+NM | clean | 0.110 | 32.408 | 46.43 | 20.0% |

By hand-mark error (px):

| method | mark_error | median | 90% | max | > 3 px |
|---|---|---|---|---|---|
| grid+NM | 5 | 0.116 | 0.750 | 2.33 | 0.0% |
| grid+NM | 15 | 0.127 | 0.697 | 2.30 | 0.0% |
| grid+NM | 30 | 0.127 | 0.602 | 2.08 | 0.0% |
| grid+NM | 60 | 0.120 | 0.652 | 2.13 | 0.0% |
| grid+NM | 100 | 32.908 | 47.331 | 61.21 | 100.0% |
| fft+NM | 5 | 0.114 | 0.748 | 2.33 | 0.0% |
| fft+NM | 15 | 0.124 | 0.694 | 2.30 | 0.0% |
| fft+NM | 30 | 0.124 | 0.605 | 2.07 | 0.0% |
| fft+NM | 60 | 0.120 | 0.653 | 2.13 | 0.0% |
| fft+NM | 100 | 0.134 | 0.639 | 2.06 | 0.0% |
| fft+J0 | 5 | 0.050 | 0.549 | 2.08 | 0.0% |
| fft+J0 | 15 | 0.064 | 0.589 | 2.08 | 0.0% |
| fft+J0 | 30 | 0.103 | 0.560 | 2.12 | 0.0% |
| fft+J0 | 60 | 0.064 | 0.576 | 2.06 | 0.0% |
| fft+J0 | 100 | 0.071 | 0.632 | 1.87 | 0.0% |
| sparse+J0 | 5 | 0.182 | 0.762 | 2.35 | 0.0% |
| sparse+J0 | 15 | 0.247 | 0.877 | 2.51 | 0.0% |
| sparse+J0 | 30 | 0.157 | 0.770 | 17.44 | 3.1% |
| sparse+J0 | 60 | 0.236 | 0.919 | 33.05 | 6.2% |
| sparse+J0 | 100 | 31.794 | 46.357 | 94.43 | 93.8% |
| sparse+J0+NM | 5 | 0.118 | 0.749 | 2.33 | 0.0% |
| sparse+J0+NM | 15 | 0.128 | 0.698 | 2.30 | 0.0% |
| sparse+J0+NM | 30 | 0.125 | 0.604 | 17.22 | 1.6% |
| sparse+J0+NM | 60 | 0.128 | 0.955 | 33.04 | 6.2% |
| sparse+J0+NM | 100 | 32.482 | 46.415 | 91.78 | 93.8% |

Findings:

- The FFT map never failed: it doesn't use the mark at all (the map covers the
  frame, and the true center is its global maximum on every card), so marks
  100 px off are no problem. The grid methods only search ±60 px, so every
  100-px mark failed (by construction).
- sparse+J0 is fastest (0.06 s) but locks onto a side ring 3–6% of the time
  for marks 30–60 px off: with a 0.45-spacing grid the brightest sample can
  sit on a ring, and the J0 fit then stays there. Not robust.
- fft+J0 is the most accurate (median 0.07 px vs. 0.17 for grid+NM; typical
  cards 0.05 vs. 0.12) at the same speed (~0.5 s, almost all of it the FFT).
  The gain is from using all pixels, not from the J0 model: Nelder–Mead on all
  pixels reaches the same answer (typical seeds 1–3: 0.037 / 0.016 / 0.183 px
  vs. fft+J0 0.037 / 0.013 / 0.184) but takes 1.4 s; the J0 fit on the map
  takes 0.04 s. As expected, the ring pattern carries no extra information,
  but it makes using all the data cheap.
- Hard cards: fft+J0 0.54 px median, about the same as the others (drift
  limits it, not the search).
