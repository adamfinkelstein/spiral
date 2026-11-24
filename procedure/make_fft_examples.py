"""Figure for procedure.html step 1: the spacing page's default spiral
(render.js: radius 50-200 px, line width 4, soft edges, 512²) at spacings 7.5
and 15 px, its FFT and the FFT's radial profile. Needs node (render.js runs
unchanged in a vm). Run: .venv/bin/python procedure/make_fft_examples.py"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cardlab.figures import COLORS, new_figure, save  # noqa: E402
from cardlab.lowres import LOG_FLOOR, radial_profile  # noqa: E402

SPACINGS = (7.5, 15)
RENDER = """
const fs = require('fs'), vm = require('vm');
const ctx = { Math, Float32Array, Float64Array, Uint16Array, Uint32Array, Int32Array };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8') + '\\nthis.renderSpiral = renderSpiral; this.N = N;', ctx);
const images = {};
for (const spacing of JSON.parse(process.argv[2])) {
  const p = { spacing, rStart: 50, rEnd: 200, phase: 0, aspect: 1, offsets: [0, 0, 0, 0], lineWidth: 4,
              softness: 2, blur: 0, noise: 0, smooth: true, spiral: true };
  const out = new Float32Array(ctx.N * ctx.N);
  ctx.renderSpiral(p, { x: ctx.N / 2, y: ctx.N / 2 }, out);
  images[spacing] = Array.from(out);
}
process.stdout.write(JSON.stringify({ N: ctx.N, images }));
"""


def main():
    result = subprocess.run(["node", "-e", RENDER, str(ROOT / "render.js"), json.dumps(SPACINGS)],
                            capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    size = data["N"]
    figure = new_figure(900, 640)
    label = COLORS["label"]
    for row, spacing in enumerate(SPACINGS):
        image = np.array(data["images"][str(spacing)], dtype=float).reshape(size, size)
        spectrum = np.log(np.abs(np.fft.fftshift(np.fft.fft2(image - image.mean()))) + LOG_FLOOR)
        top = 0.53 - row * 0.47
        ax_image = figure.add_axes([0.01, top, 0.27, 0.42])
        ax_image.imshow(image, cmap="gray", vmin=0, vmax=1)
        ax_image.set_axis_off()
        ax_image.set_title(f"spiral, spacing S = {spacing:g} px", fontsize=10.5)
        ax_fft = figure.add_axes([0.30, top, 0.27, 0.42])
        lo, hi = np.percentile(spectrum, [2, 99.8])
        ax_fft.imshow(spectrum, cmap="gray", vmin=lo, vmax=hi, extent=(-size / 2, size / 2, size / 2, -size / 2))
        rho = size / spacing
        for k in (1, 2, 3):
            if k * rho < size / 2:
                ax_fft.add_patch(__import__("matplotlib.patches", fromlist=["Circle"]).Circle(
                    (0, 0), k * rho, fill=False, ls="--", lw=0.8, color=label))
        ax_fft.set_axis_off()
        ax_fft.set_title(f"log |FFT|: rings at N/S = {rho:.1f}, 2N/S, …", fontsize=10.5)
        ax_profile = figure.add_axes([0.63, top + 0.06, 0.35, 0.34])
        profile = radial_profile(spectrum, 1.0)
        radii = np.arange(4, size // 2)
        ax_profile.plot(radii, profile[radii], color="#ddd", lw=1.3)
        for k in (1, 2, 3):
            if k * rho < size / 2:
                ax_profile.axvline(k * rho, color=label, ls="--", lw=0.8)
        ax_profile.set_yticks([])
        ax_profile.set_xlim(0, size / 2)
        ax_profile.set_xlabel("radius in the FFT (bins)")
        ax_profile.set_title("radial profile (mean per radius)", fontsize=10.5)
    save(figure, ROOT / "procedure" / "fft_examples.png")


if __name__ == "__main__":
    main()
