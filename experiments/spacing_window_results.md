# FFT spacing on simulated cards: window, smoothing, fallback (Nov 2026)

`.venv/bin/python experiments/spacing_window.py <out.json>`: the low-res FFT
spacing (1/√r about the hand mark, annulus mask as the window, profile peak
in the search window, parabolic refinement) on the 20 standard cards (4
presets × 5 seeds, drift 3.2 px) and on 6 typical cards cut at 25.9 or 32.2 px
(the range over Tomaz's five cards), all searched with the 29-px nominal.
|spacing error| median / max, and how often the nominal was used instead.

| variant | standard cards | cut at 25.9 px | cut at 32.2 px |
|---|---|---|---|
| ±10%, smooth 1, 3% fallback (before) | 0.062 / 0.18% (0 fallbacks) | 12.506 / 12.90% (3 fallbacks) | 9.506 / 9.96% (3 fallbacks) |
| ±20%, smooth 1, 3% fallback | 0.062 / 0.18% (0 fallbacks) | 12.506 / 12.90% (3 fallbacks) | 9.506 / 9.96% (3 fallbacks) |
| ±50%, smooth 1, 3% fallback | 0.062 / 0.18% (0 fallbacks) | 12.506 / 12.90% (3 fallbacks) | 9.506 / 9.96% (3 fallbacks) |
| ±20%, smooth 0, 3% fallback | 0.092 / 0.49% (0 fallbacks) | 12.506 / 12.90% (3 fallbacks) | 9.506 / 9.96% (3 fallbacks) |
| ±20%, smooth 1.5, 3% fallback | 0.049 / 0.14% (0 fallbacks) | 12.506 / 12.90% (3 fallbacks) | 9.506 / 9.96% (3 fallbacks) |
| ±20%, smooth 1, no fallback | 0.062 / 0.18% (0 fallbacks) | 0.024 / 0.08% (0 fallbacks) | 0.069 / 0.16% (0 fallbacks) |
| ±20%, smooth 1.5, no fallback | 0.049 / 0.14% (0 fallbacks) | 0.027 / 0.08% (0 fallbacks) | 0.072 / 0.08% (0 fallbacks) |
| ±50%, smooth 1.5, no fallback (now) | 0.049 / 0.14% (0 fallbacks) | 0.027 / 0.08% (0 fallbacks) | 0.072 / 0.08% (0 fallbacks) |

Findings:

- The window's width (±10/20/50%) makes no difference: the profile's peak
  is well inside it. ±50% lets one device spec cover every machine seen.
- The old fallback (use the nominal when the peak is more than 3% off) wrecks
  off-nominal cards: 9.5–12.9% error, where the measured peak was right to
  0.08%. Dropped; the nominal is used only when the peak is on the window's
  edge.
- Profile smoothing: 1.5 bins a little better than 1 (median 0.049 vs.
  0.062%, max 0.14 vs. 0.18%), none the worst (max 0.49%). 1.5 is also the
  spacing page's value, so both now use it.

## After setting the window in frequency (Nov 2026)

The window is now ±w of the expected peak radius (size / nominal), from
halfway to zero frequency to halfway to the second harmonic at w = 0.5,
instead of ±w of the spacing (which reached the second harmonic at the
nominal). Same cards:

| variant | standard cards | cut at 25.9 px | cut at 32.2 px |
|---|---|---|---|
| ±50% of the expected radius, smooth 1.5, no fallback (now) | 0.049 / 0.14% (0 fallbacks) | 0.027 / 0.08% (0 fallbacks) | 0.072 / 0.08% (0 fallbacks) |
| ±33% of the expected radius, smooth 1.5, no fallback | 0.049 / 0.14% (0 fallbacks) | 0.027 / 0.08% (0 fallbacks) | 0.072 / 0.08% (0 fallbacks) |
| ±50% of the expected radius, smooth 1.5, 3% fallback | 0.049 / 0.14% (0 fallbacks) | 12.506 / 12.90% (3 fallbacks) | 9.506 / 9.96% (3 fallbacks) |

No change on these cards (the fundamental always dominates); the new window
is chosen for its guarantee: for a true spacing within ~0.67–1.33 × the
nominal, the fundamental is inside and the second harmonic outside.
