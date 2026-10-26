"""Exposure summary: which detected houses sit in or near flood water.

This is the box-level proxy used by the spike. A water box is a rectangle,
so it overstates the flooded area; the production count must intersect the
decoded pixel masks instead. The function signature stays the same when
the mask version lands.
"""
from __future__ import annotations

from .sam_client import Segment


def _intersection(a: tuple, b: tuple) -> int:
    x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return x * y


def _area(box: tuple) -> int:
    return (box[2] - box[0]) * (box[3] - box[1])


def exposure_summary(houses: list[Segment], water: list[Segment],
                     overlap_fraction: float = 0.25) -> dict:
    """Count houses whose box overlaps a water box by > overlap_fraction."""
    exposed = 0
    touching = 0
    for house in houses:
        overlaps = [_intersection(house.box, w.box) for w in water]
        if overlaps and max(overlaps) > 0:
            touching += 1
            if max(overlaps) > overlap_fraction * _area(house.box):
                exposed += 1
    return {
        "houses_total": len(houses),
        "houses_exposed_box_proxy": exposed,
        "houses_touching_water_box": touching,
        "water_regions": len(water),
        "method": "box-overlap proxy; mask intersection pending",
    }
