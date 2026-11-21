# Runs the Python card pipeline and dumps its inputs and intermediate results
# for js_compare_tail.js (see compare_with_js.sh).
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cardlab.params import PRESETS
from cardlab.model import make_card, render
from cardlab.lowres import LowResSettings, low_res_stage, downsample
from cardlab.strip import StripSettings, build_strip, refit_geometry, lock_trace
from cardlab.readout import read_sound

preset, seed, out = sys.argv[1], int(sys.argv[2]), sys.argv[3].rstrip('/') + '/'
card = make_card(PRESETS[preset], seed)
image = render(card)
low = low_res_stage(image, card.mark, card.params.spacing, LowResSettings(sample_fraction=1.0), seed)
settings = StripSettings()
strip = build_strip(image, low.spiral, card.mark, settings)
refit, model = refit_geometry(strip, settings)
trace = lock_trace(strip, model, settings)
sound = read_sound(image, strip, trace)
f32 = lambda name, a: np.asarray(a, np.float32).tofile(out + name + '.bin')
f64 = lambda name, a: np.asarray(a, np.float64).tofile(out + name + '.bin')
f32('image', image); f32('low_raw', downsample(image))
f64('theta', strip.theta); f64('demod_re', strip.demod.real); f64('demod_im', strip.demod.imag)
f64('offsets', strip.offsets); f64('confidence', strip.confidence); f64('model', model); f64('trace', trace); f64('sound', sound)
sp = lambda s: dict(x=s.x, y=s.y, b=s.pitch, ph=s.phase)
json.dump(dict(F=card.params.frame, nominal=card.params.spacing, mark=dict(x=card.mark.x, y=card.mark.y, rIn=card.mark.r_inner, rOut=card.mark.r_outer),
               true=sp(card.spiral), low=sp(low.spiral), fft_spacing=low.fft_spacing, coherence=low.coherence, refit=sp(refit), n=len(strip.theta)),
          open(out + 'meta.json', 'w'), indent=1)
print('dumped', preset, seed, len(strip.theta), 'columns')
