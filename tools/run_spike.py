#!/usr/bin/env python3
"""Reproduce the SIGAP-Banjir spike from the command line.

Segments one or more concepts in one aerial image through SAM 3.1 on the
Meta Model API, writes the raw responses and a JSON summary per prompt,
and (when Pillow is available and --image-file is given) draws an overlay
PNG per prompt.

Requires MODEL_API_KEY in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sigap.sam_client import segment_image  # noqa: E402


def slugify(text: str) -> str:
    return "-".join(text.lower().split())


def draw_overlay(image_path: str, segments, out_path: str) -> None:
    from PIL import Image, ImageDraw

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for seg in segments:
        color = (0, 255, 0) if (seg.confidence or 0) >= 0.7 else (255, 200, 0)
        draw.rectangle([seg.x1, seg.y1, seg.x2, seg.y2], outline=color, width=2)
    image.save(out_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--image-file", help="local copy of the image, for overlays")
    parser.add_argument("--prompts", nargs="+", required=True)
    parser.add_argument("--outdir", default="out")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    for prompt in args.prompts:
        result = segment_image(prompt, args.image_url)
        slug = slugify(prompt)
        summary = {
            "prompt": prompt,
            "response_id": result.response_id,
            "status": result.status,
            "objects": len(result.segments),
            "boxes": [
                {"box": seg.box, "confidence": seg.confidence}
                for seg in result.segments
            ],
        }
        with open(os.path.join(args.outdir, f"{slug}.json"), "w") as fh:
            json.dump(summary, fh, indent=2)
        with open(os.path.join(args.outdir, f"{slug}.txt"), "w") as fh:
            fh.write(result.raw_text)
        print(f"{prompt}: {len(result.segments)} objects")
        if args.image_file:
            try:
                draw_overlay(args.image_file, result.segments,
                             os.path.join(args.outdir, f"{slug}_overlay.png"))
            except ImportError:
                print("  (Pillow not installed, overlay skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
