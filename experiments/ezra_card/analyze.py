import sys; sys.path.insert(0, "/Users/af/Desktop/cc/spiral")
from pathlib import Path
import numpy as np, cv2
from scipy.signal import fftconvolve
from scipy.ndimage import map_coordinates, gaussian_filter1d
from cardlab.lowres import radial_profile, symmetry_center, map_peak, map_at
S = sys.argv[1]  # a scratch folder for the intermediates
CARD = Path(__file__).resolve().parents[2] / "data" / "cards" / "ezra_card.jpg"
img = cv2.imread(str(CARD)).astype(float)
grey = img.mean(axis=2)
H, W = grey.shape
def sample(x, y):
    return map_coordinates(grey, [np.asarray(y) - 0.5, np.asarray(x) - 0.5], order=1)
# (a) the hole's edge: darkest point within r 300-480 on 720 rays about a rough center, circle fit
rough = np.array([1017.0, 1001.0])
angles = np.linspace(0, 2 * np.pi, 720, endpoint=False)
radii = np.arange(300, 480, 0.5)
pts = []
for a in angles:
    prof = sample(rough[0] + radii * np.cos(a), rough[1] + radii * np.sin(a))
    rr = radii[np.argmin(gaussian_filter1d(prof, 2))]
    pts.append(rough + rr * np.array([np.cos(a), np.sin(a)]))
pts = np.array(pts)
A = np.c_[2 * pts, np.ones(len(pts))]; sol = np.linalg.lstsq(A, (pts ** 2).sum(1), rcond=None)[0]
hole_c = sol[:2]; hole_r = np.sqrt(sol[2] + hole_c @ hole_c)
resid = np.hypot(*(pts - hole_c).T) - hole_r
print(f"hole circle: center ({hole_c[0]:.1f}, {hole_c[1]:.1f}), r {hole_r:.1f} px, rms resid {resid.std():.2f}")
# (b) radial profile of the grooves along many rays: spacing by FFT of the annulus
yy, xx = np.mgrid[0:H, 0:W] + 0.5
r_all = np.hypot(xx - hole_c[0], yy - hole_c[1])
r_in, r_out = hole_r + 15, 900
mask = ((r_all > r_in) & (r_all < r_out)).astype(float)
mask = cv2.GaussianBlur(mask, (0, 0), 6)
v = -(grey - (grey * mask).sum() / mask.sum()) * mask     # grooves dark -> deep -> negative height; v = -height... (sign irrelevant for |Z|)
weight = np.where(r_all > 20, r_all, 20) ** -0.5
x = v * weight
spec = np.log(np.abs(np.fft.fftshift(np.fft.fft2(x))) + 1e-12)
prof = radial_profile(spec, 1.0)
lo, hi = int(W / 25), int(W / 8)           # spacings 8-25 px
best = lo + int(np.argmax(prof[lo:hi]))
print(f"FFT: peak at radius {best} of {W} -> spacing ~ {W / best:.2f} px")
np.save(f"{S}/v.npy", v); np.save(f"{S}/geom.npy", np.r_[hole_c, hole_r, W / best])
