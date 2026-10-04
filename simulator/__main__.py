"""CLI.

python -m simulator --config configs/default.yaml --out data/run.csv    (batch → CSV)
python -m simulator serve --config configs/default.yaml --speed 60     (OPC UA server)
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from simulator.config import load_config
from simulator.simulation import RECORD_FIELDS, run


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "serve":
        return serve_main(argv[1:])

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


def serve_main(argv: list[str]) -> int:
    import asyncio
    import logging

    from simulator.opcua_server import DEFAULT_ENDPOINT, serve

    parser = argparse.ArgumentParser(prog="simulator serve", description="Run the OPC UA server.")
    parser.add_argument("--config", default="configs/default.yaml", type=Path)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument(
        "--speed", default=60.0, type=float, help="simulated seconds per real second (0 = max)"
    )
    parser.add_argument("--loop", action="store_true", help="restart the batch when it ends")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    try:
        asyncio.run(serve(load_config(args.config), args.endpoint, args.speed, args.loop))
    except NotImplementedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
