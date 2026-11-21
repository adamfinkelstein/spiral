import argparse
import json
import time
from pathlib import Path

from cardlab.params import PRESETS
from cardlab.pipeline import run_pipeline, summarize
from cardlab.report import make_figures, write_report

# Builds card.html and card/img/*.png. Summaries of every run are cached in
# card/results.json, so adding seeds only computes the new ones.

ROOT = Path(__file__).parent
RESULTS = ROOT / "card" / "results.json"
IMAGES = ROOT / "card" / "img"


def parse_seeds(text):
    seeds = []
    for part in text.split(","):
        first, _, last = part.partition("-")
        seeds += range(int(first), int(last or first) + 1)
    return seeds


def load_results():
    return json.loads(RESULTS.read_text()) if RESULTS.exists() else {}


def save_results(results):
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1, default=float))


def run_and_summarize(preset, seed):
    started = time.time()
    run = run_pipeline(preset, seed)
    summary = summarize(run) | {"preset_key": preset}
    print(f"{preset} {seed}: {time.time() - started:.1f} s, trace {summary['trace_rms']:.2f} px, "
          f"sound corr {summary['sound_correlation']:.3f}")
    return run, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--presets", default=",".join(PRESETS))
    parser.add_argument("--seeds", default="1-5")
    parser.add_argument("--showcase", default="typical:1")
    parser.add_argument("--rerun", action="store_true", help="recompute cached runs")
    args = parser.parse_args()

    results = load_results()
    showcase_preset, showcase_seed = args.showcase.split(":")
    showcase_key = f"{showcase_preset}:{int(showcase_seed)}"
    showcase, results[showcase_key] = run_and_summarize(showcase_preset, int(showcase_seed))
    for preset in args.presets.split(","):
        for seed in parse_seeds(args.seeds):
            key = f"{preset}:{seed}"
            if args.rerun or key not in results:
                results[key] = run_and_summarize(preset, seed)[1]
                save_results(results)
    save_results(results)

    IMAGES.mkdir(parents=True, exist_ok=True)
    make_figures(showcase, IMAGES)
    write_report(ROOT / "card.html", showcase, results[showcase_key], list(results.values()), "card/img")
    print("wrote card.html")


if __name__ == "__main__":
    main()
