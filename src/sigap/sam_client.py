"""Minimal SAM 3.1 client for the Meta Model API.

Contract verified against the official docs on 2026-10-27:
- POST https://api.meta.ai/v1/responses with a Bearer API key
- model "sam-3.1"; one user message holding one input_text part (a single
  short noun phrase, one concept per request) and one input_image part
  whose image_url is a public URL or a base64 data URL
- segmentation comes back as output_text lines, one record per object,
  each record holding one box token and one mask token; confidence is
  only present when metadata.include_confidence is the string "true"

The API key is read from the MODEL_API_KEY environment variable. Never
hardcode it and never commit it.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field

BASE_URL = "https://api.meta.ai/v1"
MODEL = "sam-3.1"

BOX_RE = re.compile(
    r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)"
    r"(?:;c=([0-9.]+))?\|>"
)
MASK_RE = re.compile(r"<\|mask;x=0;y=0(?:;c=[0-9.]+)?;data=(\d+),(\d+),([~!])([^|]*)\|>")


@dataclass
class Segment:
    """One detected instance: a box plus the raw mask payload."""

    x1: int
    y1: int
    x2: int
    y2: int
    frame_w: int
    frame_h: int
    confidence: float | None = None
    mask_h: int | None = None
    mask_w: int | None = None
    mask_encoding: str | None = None  # "~" lossless, "!" one_bit
    mask_payload: str | None = None  # base85, decoding is separate work

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass
class SegmentationResult:
    prompt: str
    response_id: str | None
    status: str | None
    segments: list[Segment] = field(default_factory=list)
    raw_text: str = ""


def _collect_text(node, acc: list) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "text" and isinstance(value, str):
                acc.append(value)
            else:
                _collect_text(value, acc)
    elif isinstance(node, list):
        for item in node:
            _collect_text(item, acc)


def parse_output_text(text: str) -> list[Segment]:
    """Pair each box token with the mask token that follows it."""
    segments: list[Segment] = []
    masks = list(MASK_RE.finditer(text))
    for i, match in enumerate(BOX_RE.finditer(text)):
        x1, y1, x2, y2, w, h, conf = match.groups()
        segment = Segment(
            x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2),
            frame_w=int(w), frame_h=int(h),
            confidence=float(conf) if conf else None,
        )
        # The mask token starts exactly where the box token ends (the two
        # tokens are adjacent inside a record), so the comparison must be
        # >=, not >. A strict > silently pairs every box with the NEXT
        # record's mask.
        following = [m for m in masks if m.start() >= match.end()]
        if following:
            mh, mw, enc, payload = following[0].groups()
            segment.mask_h, segment.mask_w = int(mh), int(mw)
            segment.mask_encoding = enc
            segment.mask_payload = payload
        segments.append(segment)
    return segments


def decode_raster(segment: "Segment") -> bytes:
    """Decode a segment's mask payload into a row-major 0/1 raster.

    Uses Meta's official parser package (meta-sam-parser); the wire
    payload handed to it must include the encoding marker as its first
    character. The raster has mask_h rows and mask_w columns, and in
    every response observed so far its size equals the inclusive box
    size, so it maps 1:1 onto the box at (x1, y1).
    """
    if segment.mask_payload is None or segment.mask_encoding is None:
        raise ValueError("segment has no mask payload")
    from meta_sam_parser import SegmentationMask, decode_mask_to_raster

    encoding = "lossless" if segment.mask_encoding == "~" else "one_bit"
    mask = SegmentationMask(
        height=segment.mask_h,
        width=segment.mask_w,
        encoding=encoding,
        payload=segment.mask_encoding + segment.mask_payload,
    )
    return decode_mask_to_raster(mask)


def segment_image(prompt: str, image_url: str, api_key: str | None = None,
                  timeout: int = 180) -> SegmentationResult:
    """Segment every instance of one concept in one image."""
    key = api_key or os.environ.get("MODEL_API_KEY")
    if not key:
        raise RuntimeError("MODEL_API_KEY is not set")
    payload = {
        "model": MODEL,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
        "metadata": {"include_confidence": "true"},
    }
    request = urllib.request.Request(
        BASE_URL + "/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    texts: list = []
    _collect_text(body, texts)
    seg_text = max(texts, key=len) if texts else ""
    return SegmentationResult(
        prompt=prompt,
        response_id=body.get("id"),
        status=body.get("status"),
        segments=parse_output_text(seg_text),
        raw_text=seg_text,
    )
