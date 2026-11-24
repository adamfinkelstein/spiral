import sys; sys.path.insert(0, "/Users/af/Desktop/cc/spiral")
from pathlib import Path
import numpy as np, cv2, pickle
from cardlab.geometry import Mark, TAU, wrap
from cardlab.lowres import low_res_stage
from cardlab.wedges import run_wedges, WedgeSettings
from cardlab.strip import Strip
from cardlab.readout import read_sound, ReadoutSettings, mean_across
S = sys.argv[1]  # a scratch folder for the intermediates
CARD = Path(__file__).resolve().parents[2] / "data" / "cards" / "ezra_card.jpg"
grey = cv2.imread(str(CARD)).astype(float).mean(axis=2)
cx, cy, rh, s = np.load(f"{S}/geom.npy")
H = grey.shape[0]
image = grey.astype(np.float32)  # cardlab's angles are counterclockwise as displayed, like the card's winding
mark = Mark(cx, cy, 400.0, 950.0)
low = low_res_stage(image, mark, 9.9)
print("low-res: spacing %.3f px, center (%.1f, %.1f), spiral phase %.2f, coherence %.2f" %
      (low.fft_spacing, low.spiral.x, low.spiral.y, low.spiral.phase, low.coherence))
w = run_wedges(image, low.spiral, mark, WedgeSettings())
print("refit: spacing %.4f px, center (%.2f, %.2f), moved %.2f px" % (w.spiral.spacing, w.spiral.x, w.spiral.y,
      np.hypot(w.spiral.x - low.spiral.x, w.spiral.y - low.spiral.y)))
theta = w.unrolled.theta
strip = Strip(low.spiral, theta, w.unrolled.step, None, None, None)
drift = w.path - w.model
print("columns %d, turns %.1f, step at mid turn %.3f px" % (len(theta), (theta[-1] - theta[0]) / TAU, w.unrolled.step))
print("path minus refitted spiral: rms %.2f px = %.3f S, p1-p99 %.1f..%.1f px" % (drift.std(), drift.std() / w.spiral.spacing,
      *np.percentile(drift - drift.mean(), [1, 99])))
conf = w.final.confidence
print("wedge confidence: median 1 by definition; 5th pct %.2f, share < 0.25: %.3f" % (np.percentile(conf, 5), np.mean(conf < 0.25)))
half = w.spiral.spacing / 2
results = {}
for hw in (1, 3):
    bottom = mean_across(image, strip, w.path, hw)
    land = (mean_across(image, strip, w.path - half, hw) + mean_across(image, strip, w.path + half, hw)) / 2
    results[hw] = land - bottom
pickle.dump(dict(theta=theta, path=w.path, model=w.model, depth1=results[1], depth3=results[3], step=w.unrolled.step,
                 spacing=w.spiral.spacing, phase=w.spiral.phase, pitch=w.spiral.pitch,
                 sound=read_sound(image, strip, w.path, ReadoutSettings(smoothing=0))), open(f"{S}/track.pkl", "wb"))
