"""Benchmark runner.

    python -m benchmarks.run --suite micro
    python -m benchmarks.run --suite gaia --driver anthropic --n 20
"""
from __future__ import annotations
import argparse
import importlib
import json
import pathlib
import time


_MICRO_BENCHES = [
    "benchmarks.micro.context_efficiency",
    "benchmarks.micro.coord_latency",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", choices=["micro", "gaia", "swebench", "agentbench",
                                       "webarena"], default="micro")
    p.add_argument("--driver", default="mock")
    p.add_argument("--n", type=int, default=None,
                   help="# of tasks (external suites)")
    p.add_argument("--out", default="benchmarks/results")
    args = p.parse_args()

    out_dir = pathlib.Path(args.out) / args.suite
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    out_path = out_dir / f"{stamp}.json"

    if args.suite == "micro":
        results = {}
        for mod in _MICRO_BENCHES:
            m = importlib.import_module(mod)
            r = m.run()
            # dataclass-friendly
            results[mod.rsplit(".", 1)[-1]] = (
                r.__dict__ if hasattr(r, "__dict__") else r
            )
        out_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"wrote {out_path}")
        for k, v in results.items():
            print(f"  {k}: {v}")
    else:
        print(f"{args.suite}: external suite not yet implemented in v0.1. "
              f"See benchmarks/{args.suite}/README.md for plan.")


if __name__ == "__main__":
    main()
