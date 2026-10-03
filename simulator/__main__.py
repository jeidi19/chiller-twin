"""CLI: ``python -m simulator --config configs/default.yaml --out data/run.csv``."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from simulator.config import load_config
from simulator.simulation import RECORD_FIELDS, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="simulator", description=__doc__)
    parser.add_argument("--config", default="configs/default.yaml", type=Path)
    parser.add_argument("--out", default="data/run.csv", type=Path)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    try:
        records = run(config)
    except NotImplementedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    print(f"Wrote {len(records)} samples to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
