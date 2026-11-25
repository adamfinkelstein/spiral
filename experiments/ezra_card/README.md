# Ezra's card visualization (Nov 2026)

Input: `data/cards/ezra_card.jpg`, a 2000² JPEG from Ezra's earlier groove
tracking (a grey rendering of the surface with his trace drawn faintly in
blue; the overlay is weak and mostly lost in JPEG chroma, so the mean of the
three channels is used). Each script takes a scratch folder for its
intermediates: `python analyze.py DIR` (hole circle, spacing) → `winding.py
DIR` → `pipeline_on_ezra.py DIR` (cardlab's low-res stage, wedges and depth
readout) → `stats.py DIR`. (First run, before cardlab's angles were flipped,
on the image flipped vertically; the same numbers came out after the flip on
the image as it is.)

## Winding

The spiral coherence map with both winding senses (cardlab's kernel and its
mirror), |Z| at the center of point symmetry over the map's median:

| image | outward clockwise as displayed (cardlab before Nov 2026) | outward counterclockwise as displayed (cardlab now) |
|---|---|---|
| Ezra's card | 11.1 | **89.7** |
| Tomaz's groove mask, sonorine_001 (image 25, green channel) | 25.3 | **40.2** |

Both real cards wind outward counterclockwise as displayed. Tracking one
turn of Tomaz's red fit agreed (radius −1 spacing per clockwise revolution).
cardlab's simulated cards wound the other way (angles measured with y down);
since Nov 2026 cardlab measures angles counterclockwise as displayed (y up),
and its cards wind like the real ones (typical card 1: 106 vs 2.8).

## Geometry (cardlab, annulus r 400–950 px)

Hole edge circle: center (1013.7, 1000.6), r 385.5 px. Spacing 9.91 px (FFT
and ray autocorrelation agree), 52.5 turns, mid radius 675 px (68 S; our
synthetic card 75 S). Coherence 0.75 (synthetic typical 0.54). Refit moved
the center 0.15 px. Groove vs. perfect spiral: 0.64 px rms = 0.064 S, p1–p99
−2.0..+1.3 px (synthetic: 0.11 S; Tomaz's sonorine_001 measured 0.10–0.12 S).
Wedge confidence: 5th percentile 0.74, 0.1% below 0.25.

## Groove depth (grey levels, land at ±S/2 minus bottom, ±1 px windows = our ±3 px scaled to S)

Mean 23.6, sd 7.6 (CV 0.32), p5/p50/p95 10.6/23.8/35.8; relative to its
300-px average: rms 0.29, p1/p99 −0.73/+0.68, no-cut (< −0.9) 0.1%
(synthetic: readout rms ~0.46 for true 0.40; 0.5% not cut). Mean depth per
turn falls ~11% from the inner turns (25.5) to the outer (22.6).
Cross-section: land 144.5, bottom 118.3, roughly sinusoidal; width at half
depth ~3.7 px = 0.37 S (model parabola: 0.6 S at the surface, 0.42 S at half
depth). Caveat: grey level is a rendering of the surface, not calibrated
depth.

## Sound spectrum (relative depth along the path, cycles per turn)

| band, cycles/turn | Ezra | synthetic typical |
|---|---|---|
| 2–25 | 9.6% | 0 |
| 25–50 | 8.3% | 0 |
| 50–100 | 3.0% | 17.2% |
| 100–200 | 16.5% | 14.0% |
| 200–400 | 51.3% | 44.4% |
| 400–800 | 9.2% | 23.4% |
| 800–1600 | 1.8% | 1.1% |

Power-weighted median 235 cycles/turn (synthetic 220); 10–90% of power
26–419 (synthetic 86–576); a narrow peak at 193–196 cycles/turn, ~5× the
100–400 mean. The 2–50 band may be surface shading (blotches visible in the
image) rather than sound; the weaker 400–800 band may be the image's
resolution (wavelength ~10 px there, ~1 S). In Hz: cycles/turn × turns per
second (unknown here).

## What we learned, and what it suggests for the simulated cards

Done (24 Nov 2026): cardlab's `ezra` preset (params.py) takes the sound
level (0.3), a tone at 195 cycles/turn with 8% of the power (measured here:
7–8% above the background in psd.npy), a depth trend (−10%), the drift
(1.9 px = 0.064 S) and the geometry (~53 turns, mid radius 68 S); the slow
surface variation was left out. Results: card.html and procedure.html step 0.

- **Winding**: the real cards wind outward counterclockwise as displayed.
  Done: cardlab's angles (and the JS pages') are now counterclockwise from
  3 o'clock as displayed, so the simulated cards match.
- **The pipeline works on a real image as it is**: spacing, center (0.15 px
  correction by the wedge fit), path and depth readout, with no tuning
  beyond the annulus and the nominal spacing. Coherence 0.75, higher than on
  our simulated cards (0.54): this card is cleaner than the model.
- **Drift is smaller here** (0.064 S rms) than on sonorine_001 (0.10–0.12 S)
  or our model (0.11 S, hard 0.17 S). Keep the model's drift as the harder
  case; cards evidently vary.
- **Sound level**: the depth's relative modulation reads 0.29 rms here, vs
  ~0.46 from our readout of the typical card (true 0.40). If grey level is
  proportional to depth, a true sound rms of ~0.25–0.3 would match; consider
  a preset at 0.3 (typical) and keep 0.6–0.7 as loud. Gaps (no cut) are
  rarer here (0.1% vs 0.5%).
- **Sound spectrum**: the centre matches (median ~235 vs 220 cycles/turn,
  most power 100–400 cycles/turn). Differences: a narrow tonal peak at ~195
  cycles/turn (consider adding a tone to the test sound); less power above
  400 cycles/turn (may be the image's resolution); power below 50
  cycles/turn (probably surface shading, not sound: a model of slow surface
  height variation would add it).
- **Groove shape**: roughly sinusoidal across the groove, half-depth width
  ~0.37 S, close to the model's parabola (0.42 S).
- **Depth trend**: ~11% shallower on the outer turns. The model's depth is
  constant apart from the end fades; a slow trend could be added.
- **Geometry range**: inner/outer radius ~0.42 here vs 0.58 on sonorine_001,
  52 turns vs ~40. The simulated presets should cover both.
- **Caveats**: one JPEG visualization, grey level not calibrated depth, a
  rotation speed unknown (cycles/turn × turns/s = Hz). More cards, ideally
  depth maps, would firm all of this up.
