import json
import sys

import numpy as np

# Summarizes center_search.py results as markdown tables.

FAILURE = 3.0  # full-res px


def stats(errors):
    errors = np.asarray(errors)
    return (f"{np.median(errors):.3f} | {np.percentile(errors, 90):.3f} | {errors.max():.2f} | "
            f"{100 * np.mean(errors > FAILURE):.1f}%")


def table(rows, group_key, groups):
    methods = list(dict.fromkeys(r["method"] for r in rows))
    lines = [f"| method | {group_key} | median | 90% | max | > {FAILURE:g} px |", "|---|---|---|---|---|---|"]
    for method in methods:
        for group in groups:
            errors = [r["error"] for r in rows if r["method"] == method and r[group_key] == group]
            if errors:
                lines.append(f"| {method} | {group} | {stats(errors)} |")
    return "\n".join(lines)


def main():
    rows = sum((json.load(open(path)) for path in sys.argv[1:]), [])
    methods = list(dict.fromkeys(r["method"] for r in rows))
    cards = len({(r["preset"], r["seed"]) for r in rows})
    print(f"{cards} cards, {len(rows) // len(methods)} marks in all; errors in full-res px\n")
    print("| method | median | 90% | max | > 3 px | time (median s) |\n|---|---|---|---|---|---|")
    for method in methods:
        mine = [r for r in rows if r["method"] == method]
        print(f"| {method} | {stats([r['error'] for r in mine])} | {np.median([r['seconds'] for r in mine]):.2f} |")
    print("\nBy preset:\n")
    print(table(rows, "preset", list(dict.fromkeys(r["preset"] for r in rows))))
    print("\nBy hand-mark error (px):\n")
    print(table(rows, "mark_error", sorted({r["mark_error"] for r in rows})))


if __name__ == "__main__":
    main()
