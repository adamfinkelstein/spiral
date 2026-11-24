import sys; sys.path.insert(0, "/Users/af/Desktop/cc/spiral")
import numpy as np, cv2
from scipy.signal import fftconvolve
from cardlab.lowres import symmetry_center, map_peak, map_at
S = sys.argv[1]
v = np.load(f"{S}/v.npy"); cx, cy, rh, spacing = np.load(f"{S}/geom.npy")
k = 2  # work at half resolution
small = cv2.resize(v, (v.shape[1] // k, v.shape[0] // k), interpolation=cv2.INTER_AREA)
b = spacing / k / (2 * np.pi)
reach = int(940 / k)
q = np.arange(-reach, reach + 1, dtype=float)
qx, qy = np.meshgrid(-q, -q)  # K(-q), as cardlab.lowres.spiral_wave_kernel
rad = np.hypot(qx, qy)
results = {}
for name, sign in (("outward clockwise as displayed (cardlab before Nov 2026)", -1), ("outward counterclockwise as displayed (cardlab now)", +1)):
    kernel = np.where(rad <= reach, np.exp(-1j * (rad / b + sign * np.arctan2(qy, qx))), 0)
    z = -fftconvolve(small, kernel, mode="same")
    peak = map_peak(z)
    center = symmetry_center(z, 940 / k / 8, 1.5)
    zc = map_at(z, center)
    # how strong vs the background: |Z| at the center over the median |Z| in the frame
    print(f"{name}: peak |Z| {np.abs(z).max():.3g} at ({peak[0]*k:.1f}, {peak[1]*k:.1f}); symmetry center ({center[0]*k:.1f}, {center[1]*k:.1f}); "
          f"|Z| there / median |Z| = {abs(zc) / np.median(np.abs(z)):.1f}; spiral phase {np.angle(zc):.2f} rad")
    results[name] = (z, center)
print(f"hole center ({cx:.1f}, {cy:.1f})")
