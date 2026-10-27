"""Mask-level exposure analysis.

Two findings from the spike shape this module:

1. A roof is never water. House masks and water masks are pixel-precise
   and essentially disjoint, so "affected" cannot mean mask overlap.
   Following the FloodNet definition (a flooded building is one water
   touches or surrounds), a house is scored by how much of the ring
   around its footprint is water: the contact fraction.

2. Not all water in an "after" photo is floodwater. A permanent lake or
   river must be removed with a baseline: segment water in a "before"
   image of the same area and subtract it (dilated, to absorb small
   registration differences). What remains is new water.

Masks are decoded with Meta's official parser (see sam_client.decode_raster)
and placed on a shared grid at their box origins; in every response
observed, raster size equals inclusive box size.
"""
from __future__ import annotations

from .sam_client import Segment, decode_raster


def build_grid(segments: list[Segment], frame_w: int, frame_h: int) -> bytearray:
    """Rasterize segments onto a shared frame-sized 0/1 grid."""
    grid = bytearray(frame_w * frame_h)
    for segment in segments:
        raster = decode_raster(segment)
        for row in range(segment.mask_h):
            base = (segment.y1 + row) * frame_w + segment.x1
            line = raster[row * segment.mask_w:(row + 1) * segment.mask_w]
            for col, value in enumerate(line):
                if value:
                    grid[base + col] = 1
    return grid


def dilate(grid: bytearray, frame_w: int, frame_h: int, radius: int) -> bytearray:
    out = bytearray(frame_w * frame_h)
    for y in range(frame_h):
        for x in range(frame_w):
            if grid[y * frame_w + x]:
                for dy in range(-radius, radius + 1):
                    yy = y + dy
                    if 0 <= yy < frame_h:
                        for dx in range(-radius, radius + 1):
                            xx = x + dx
                            if 0 <= xx < frame_w:
                                out[yy * frame_w + xx] = 1
    return out


def flood_grid(after_water: list[Segment], before_water: list[Segment],
               frame_w: int, frame_h: int, baseline_margin: int = 10) -> bytearray:
    """New water only: after-water minus the dilated before-water."""
    after = build_grid(after_water, frame_w, frame_h)
    if not before_water:
        return after
    before = dilate(build_grid(before_water, frame_w, frame_h),
                    frame_w, frame_h, baseline_margin)
    return bytearray(1 if a and not b else 0 for a, b in zip(after, before))


def contact_fraction(house: Segment, grid: bytearray,
                     frame_w: int, frame_h: int, ring: int = 4) -> float:
    """Share of the ring around a house footprint that is water."""
    total = 0
    wet = 0
    for y in range(max(0, house.y1 - ring), min(frame_h - 1, house.y2 + ring) + 1):
        for x in range(max(0, house.x1 - ring), min(frame_w - 1, house.x2 + ring) + 1):
            if house.x1 <= x <= house.x2 and house.y1 <= y <= house.y2:
                continue
            total += 1
            if grid[y * frame_w + x]:
                wet += 1
    return (wet / total) if total else 0.0


def mask_exposure_summary(houses: list[Segment], water_grid: bytearray,
                          frame_w: int, frame_h: int,
                          contact_threshold: float = 0.2) -> dict:
    """Score every house against a water grid by contact fraction."""
    per_house = []
    affected = 0
    for house in houses:
        fraction = contact_fraction(house, water_grid, frame_w, frame_h)
        if fraction >= contact_threshold:
            affected += 1
        per_house.append({
            "box": house.box,
            "confidence": house.confidence,
            "water_contact": round(fraction, 3),
            "affected": fraction >= contact_threshold,
        })
    return {
        "houses_total": len(houses),
        "houses_affected": affected,
        "contact_threshold": contact_threshold,
        "method": "water contact fraction around footprint (FloodNet-style), "
                  "on baseline-subtracted flood grid when a baseline is used",
        "per_house": per_house,
    }
