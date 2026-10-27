#!/usr/bin/env python3
"""Generate a SIGAP-Banjir situation report from a measurements file.

Reads a measurements JSON file (house counts, per-house water contact
fractions, new-water pixel area, road segments — see
docs/SITREP_SCHEMA.md), asks Muse Spark for the sitrep via
sigap.sitrep, and writes the validated sitrep JSON.

Requires MODEL_API_KEY in the environment, unless --dry-run is given:
dry-run makes no API call and emits a deterministic synthetic sitrep
with the same schema, for offline smoke tests.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sigap.sitrep import generate_sitrep  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements", required=True,
                        help="path to a measurements JSON file")
    parser.add_argument("--out", default="sitrep.json",
                        help="where to write the sitrep JSON (default: sitrep.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="no API call; emit a synthetic sitrep with the same schema")
    args = parser.parse_args()

    with open(args.measurements) as fh:
        measurements = json.load(fh)
    sitrep = generate_sitrep(measurements, dry_run=args.dry_run)
    with open(args.out, "w") as fh:
        json.dump(sitrep, fh, indent=2, ensure_ascii=False)
    mode = "dry-run, no API call" if args.dry_run else "live"
    print(f"sitrep written to {args.out} ({mode}): "
          f"{sitrep['rumah_terdeteksi']} houses, "
          f"{sitrep['rumah_terdampak_prioritas']} priority, "
          f"{sitrep['area_air_baru_piksel']} px new water")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
