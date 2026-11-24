import numpy as np, pickle, sys
from scipy.ndimage import gaussian_filter1d
from scipy.signal import welch
S = sys.argv[1]
t = pickle.load(open(f"{S}/track.pkl", "rb"))
TAU = 2 * np.pi
theta, step, spacing, pitch, phase = t["theta"], t["step"], t["spacing"], t["pitch"], t["phase"]
radius = pitch * (theta - phase)
per_turn = TAU / (theta[1] - theta[0])
for hw in (1, 3):
    d = t[f"depth{hw}"]
    slow = gaussian_filter1d(d, 300 / step)
    rel = d / slow - 1
    print(f"depth (land - bottom, grey levels), bottom/land over +-{hw} px: mean {d.mean():.1f}, sd {d.std():.1f} (CV {d.std()/d.mean():.2f}); "
          f"p5/p50/p95 {np.percentile(d,5):.1f}/{np.percentile(d,50):.1f}/{np.percentile(d,95):.1f}; share <= 0: {np.mean(d<=0):.3f}")
    print(f"   relative to its 300-px average: rms {rel.std():.2f}, share below -0.9 (no cut): {np.mean(rel < -0.9):.3f}, p1/p99 {np.percentile(rel,1):.2f}/{np.percentile(rel,99):.2f}")
d = t["depth1"]
# slow trend of the depth across the card: mean per turn vs radius
turn = np.floor((theta - theta[0]) / TAU).astype(int)
means = np.array([d[turn == k].mean() for k in range(turn.max())])
rs = np.array([radius[turn == k].mean() for k in range(turn.max())])
print("mean depth per turn, every 8th turn: ", [(int(r), round(m, 1)) for r, m in zip(rs[::8], means[::8])])
# spectrum of the relative depth (the sound) vs theta, in cycles per turn
rel = d / gaussian_filter1d(d, 300 / step) - 1
f, p = welch(rel - rel.mean(), fs=per_turn, nperseg=int(per_turn), detrend="linear")
use = f > 2
cum = np.cumsum(p[use]); cum /= cum[-1]
fu = f[use]
q = lambda x: fu[np.searchsorted(cum, x)]
r_mid = np.median(radius)
print(f"columns per turn {per_turn:.0f} (Nyquist {per_turn/2:.0f} cycles/turn); mid radius {r_mid:.0f} px, circumference {TAU*r_mid:.0f} px")
print(f"sound spectrum, cycles per turn: power-weighted median {q(0.5):.0f}, 10-90% of power {q(0.1):.0f}-{q(0.9):.0f}, peak {fu[np.argmax(p[use])]:.0f}")
for name, cyc in (("median", q(0.5)), ("10%", q(0.1)), ("90%", q(0.9))):
    lam = TAU * r_mid / cyc
    print(f"   {name}: wavelength {lam:.1f} px at mid radius here = {lam/spacing:.2f} spacings")
# coarse spectrum table
edges = [2, 25, 50, 100, 200, 400, 800, 1600, 3200, per_turn / 2]
tot = p[use].sum()
for a, b in zip(edges[:-1], edges[1:]):
    m = (f >= a) & (f < b)
    print(f"   {a:5.0f}-{b:5.0f} cycles/turn: {100 * p[m].sum() / tot:5.1f}% of power")
np.save(f"{S}/psd.npy", np.c_[f, p])
