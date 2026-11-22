# FFT spacing peak prominence (Nov 2026)

`.venv/bin/python experiments/spacing_prominence.py <out.json>`: the peak's
height above the trough line (through the smoothed profile at 0.5 and 1.5 ×
its radius), in log magnitude, i.e. a log ratio of peak to background.

Cards (low-res, 29-px nominal unless noted):

| case | n | prominence | spacing |
|---|---|---|---|
| correct: 20 standard + 6 cut at 25.9 / 32.2 px | 26 | 0.89 – 1.91 (median 1.62) | all within 0.11% |
| nominal 1.7 / 2 / 2.5 × too large (typical, hard, seeds 1–3) | 18 | −0.10 – 0.49 (2 on the window's edge) | all wrong (+27 to +404%) |
| grain alone, no groove | 3 | 0.04 – 0.06 | wrong |

Drawn spirals on the spacing page (node; 6 per case, hand mark σ 4 px):
correct peaks 1.08 – 4.0 (perfect at spacing 5–40, noise up to 3, offsets
±0.25–0.5, aspect 1.05, rings, thin lines, few turns); nominal 2 / 2.5 × too
large ≤ 0.17; nominal 1.7 × on the window's edge (already caught); no spiral
≤ 0.21. Spirals with strongly varying spacing can be > 3% off with prominent
peaks (1.6–2.8): a real peak, at the varying-spacing limit, which a
prominence test can't and shouldn't reject.

Threshold: `min_prominence = 0.65` (cardlab `LowResSettings`, fftspacing.js
`profilePeak`): every correct peak ≥ 0.89, every wrong one not already on the
window's edge ≤ 0.41 (≤ 0.49 including edge ones); the peak must be about
twice its background (e^0.65 ≈ 1.9). Below it, the spacing counts as not
found (`SpacingNotFound`; the page skips the coherence center). To check on
real depth maps: their correct peaks may be weaker.
