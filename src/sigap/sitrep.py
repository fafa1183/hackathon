"""Muse Spark situation-report (sitrep) generator.

Turns verified segmentation measurements (house counts, per-house water
contact fractions, new-water area, road segments — the outputs of
sam_client + exposure_mask) into a short JSON situation report for a
response-team duty officer. The report schema is the data contract the
dashboard consumes; see docs/SITREP_SCHEMA.md.

Contract, proven in the 2026-10-27 spike (docs/SPIKE_RESULTS.md):
- POST https://api.meta.ai/v1/responses with a Bearer API key, model
  "muse-spark-1.3", one user message with one input_text part
- the model answers with JSON only, exactly the keys in SITREP_KEYS
- the numbers it echoes back (houses detected, new-water pixels) must
  match the measurements it was given; a mismatch is a schema error

The API key is read from the MODEL_API_KEY environment variable. Never
hardcode it and never commit it.
"""
from __future__ import annotations

import json
import os
import urllib.request

from .sam_client import BASE_URL, _collect_text

MODEL = "muse-spark-1.3"

# A house counts as a priority when at least this share of the ring
# around its footprint touches new water; SEVERE_CONTACT marks the
# houses needing first attention. These are the thresholds the spike
# prompt reported on.
PRIORITY_CONTACT = 0.10
SEVERE_CONTACT = 0.20

SITREP_KEYS = (
    "ringkasan",
    "rumah_terdeteksi",
    "rumah_terdampak_prioritas",
    "area_air_baru_piksel",
    "prioritas",
    "catatan_ketidakpastian",
)

# The instruction half of the spike prompt, verbatim except for the two
# echoed numbers, which the measurements fill in.
_INSTRUCTION = """Write a short situation report (sitrep) for a response-team duty officer in JSON only, no prose outside the JSON, with exactly these keys:
{{
  "ringkasan": "2-3 sentence plain-language summary in Bahasa Indonesia",
  "rumah_terdeteksi": {houses},
  "rumah_terdampak_prioritas": number of houses needing first attention based on the contact numbers,
  "area_air_baru_piksel": {new_water},
  "prioritas": ["up to 3 concrete first actions, in Bahasa Indonesia"],
  "catatan_ketidakpastian": "one sentence in Bahasa Indonesia on what these numbers cannot yet tell us"
}}"""


class SitrepError(ValueError):
    """Measurements or a model response do not fit the sitrep schema."""


def _require_int(measurements: dict, key: str) -> int:
    value = measurements.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SitrepError(f"measurements[{key!r}] must be an int, got {value!r}")
    if value < 0:
        raise SitrepError(f"measurements[{key!r}] must be >= 0, got {value}")
    return value


def validate_measurements(measurements: dict) -> dict:
    """Check a measurements dict and return a normalized copy.

    Required: houses_detected, new_water_px, priority_houses (a list of
    {"water_contact": float, ...} entries, e.g. the per_house list from
    exposure_mask.mask_exposure_summary). Optional: location,
    image_width, image_height, water_area_after_px,
    water_area_baseline_px, new_water_notes, road_segments (an int
    count, or a list whose length is the count).
    """
    if not isinstance(measurements, dict):
        raise SitrepError(f"measurements must be a dict, got {type(measurements).__name__}")
    houses = _require_int(measurements, "houses_detected")
    new_water = _require_int(measurements, "new_water_px")

    priority = measurements.get("priority_houses")
    if not isinstance(priority, list):
        raise SitrepError("measurements['priority_houses'] must be a list")
    contacts = []
    for i, entry in enumerate(priority):
        if not isinstance(entry, dict) or "water_contact" not in entry:
            raise SitrepError(
                f"priority_houses[{i}] must be a dict with a 'water_contact' value")
        contact = entry["water_contact"]
        if isinstance(contact, bool) or not isinstance(contact, (int, float)):
            raise SitrepError(f"priority_houses[{i}]['water_contact'] must be a number")
        if not 0.0 <= contact <= 1.0:
            raise SitrepError(f"priority_houses[{i}]['water_contact'] must be in [0, 1]")
        contacts.append(float(contact))

    roads = measurements.get("road_segments", 0)
    if isinstance(roads, list):
        roads = len(roads)
    if isinstance(roads, bool) or not isinstance(roads, int) or roads < 0:
        raise SitrepError("measurements['road_segments'] must be an int count or a list")

    normalized = dict(measurements)
    normalized.update({
        "houses_detected": houses,
        "new_water_px": new_water,
        "road_segments": roads,
        "houses_priority": sum(1 for c in contacts if c >= PRIORITY_CONTACT),
        "houses_severe": sum(1 for c in contacts if c >= SEVERE_CONTACT),
        "max_contact": max(contacts) if contacts else 0.0,
    })
    return normalized


def build_prompt(measurements: dict) -> str:
    """Render the spike-proven Spark prompt for one measurements dict."""
    m = validate_measurements(measurements)
    size = ""
    if m.get("image_width") and m.get("image_height"):
        size = f" ({m['image_width']}x{m['image_height']} px)"
    location = m.get("location") or "a flooded residential area"
    lines = [
        "You are the reasoning agent of SIGAP-Banjir, a flood response "
        "support system. Below are verified measurements from SAM 3.1 "
        f"segmentation of an aerial photo{size} of {location}, compared "
        "against a pre-flood baseline image of the same area.",
        "",
        "Measurements:",
        f"- Houses detected: {m['houses_detected']:,}",
    ]
    if m.get("water_area_after_px") is not None:
        baseline = m.get("water_area_baseline_px")
        baseline_text = f"{baseline:,} px" if baseline is not None else "not measured"
        lines.append(
            f"- Water area after the flood: {m['water_area_after_px']:,} px; "
            f"water area in the baseline: {baseline_text}")
    notes = f", {m['new_water_notes']}" if m.get("new_water_notes") else ""
    lines.append(
        "- Genuinely new water (after minus baseline, permanent lake/river "
        f"excluded): {m['new_water_px']:,} px{notes}")
    lines.append(
        "- Houses whose immediate surroundings make substantial contact "
        f"with the new water: {m['houses_priority']} houses at contact "
        f">= {PRIORITY_CONTACT:.2f} of their surrounding ring, "
        f"{m['houses_severe']} house(s) at >= {SEVERE_CONTACT:.2f}")
    lines.append(f"- Road segments detected: {m['road_segments']} main segments")
    lines.append("")
    lines.append(_INSTRUCTION.format(
        houses=m["houses_detected"], new_water=m["new_water_px"]))
    return "\n".join(lines)


def _check_int_field(sitrep: dict, key: str) -> int:
    value = sitrep.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SitrepError(f"sitrep[{key!r}] must be an int, got {value!r}")
    if value < 0:
        raise SitrepError(f"sitrep[{key!r}] must be >= 0, got {value}")
    return value


def validate_sitrep(sitrep: dict, measurements: dict | None = None) -> dict:
    """Validate a parsed sitrep against the schema; return it unchanged.

    When measurements are given, the echoed numbers must match them.
    """
    if not isinstance(sitrep, dict):
        raise SitrepError(f"sitrep must be a JSON object, got {type(sitrep).__name__}")
    missing = [key for key in SITREP_KEYS if key not in sitrep]
    if missing:
        raise SitrepError(f"sitrep is missing required keys: {', '.join(missing)}")
    for key in ("ringkasan", "catatan_ketidakpastian"):
        if not isinstance(sitrep[key], str) or not sitrep[key].strip():
            raise SitrepError(f"sitrep[{key!r}] must be a non-empty string")
    _check_int_field(sitrep, "rumah_terdeteksi")
    _check_int_field(sitrep, "rumah_terdampak_prioritas")
    _check_int_field(sitrep, "area_air_baru_piksel")
    prioritas = sitrep["prioritas"]
    if (not isinstance(prioritas, list) or not 1 <= len(prioritas) <= 3
            or any(not isinstance(p, str) or not p.strip() for p in prioritas)):
        raise SitrepError("sitrep['prioritas'] must be a list of 1-3 non-empty strings")
    if measurements is not None:
        m = validate_measurements(measurements)
        if sitrep["rumah_terdeteksi"] != m["houses_detected"]:
            raise SitrepError(
                f"sitrep echoes rumah_terdeteksi={sitrep['rumah_terdeteksi']} "
                f"but measurements say {m['houses_detected']}")
        if sitrep["area_air_baru_piksel"] != m["new_water_px"]:
            raise SitrepError(
                f"sitrep echoes area_air_baru_piksel={sitrep['area_air_baru_piksel']} "
                f"but measurements say {m['new_water_px']}")
    return sitrep


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a model response, defensively.

    The prompt asks for JSON only, but tolerate code fences or stray
    prose around the object rather than failing the whole report.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        raise SitrepError("model response contains no JSON object")
    try:
        return json.loads(stripped[start:end + 1])
    except json.JSONDecodeError as exc:
        raise SitrepError(f"model response is not valid JSON: {exc}") from exc


def parse_sitrep(text: str, measurements: dict | None = None) -> dict:
    """Parse and validate a raw Spark response text into a sitrep dict."""
    return validate_sitrep(_extract_json(text), measurements)


def _synthetic_sitrep(m: dict) -> dict:
    """Deterministic offline stand-in sitrep for a normalized measurement.

    Used by --dry-run smoke tests only; no API call is made. The wording
    follows the spike report's shape so downstream consumers (dashboard)
    see exactly the production schema.
    """
    def fmt(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    sitrep = {
        "ringkasan": (
            f"Terdeteksi {m['houses_detected']} rumah di area permukiman "
            f"yang dipantau. Terdapat genangan baru seluas "
            f"{fmt(m['new_water_px'])} piksel di luar air permanen, dengan "
            f"{m['houses_priority']} rumah bersentuhan langsung dengan "
            f"genangan baru dan {m['houses_severe']} rumah pada kontak "
            f"tertinggi, serta terpantau {m['road_segments']} segmen jalan "
            "utama di area tersebut."),
        "rumah_terdeteksi": m["houses_detected"],
        "rumah_terdampak_prioritas": m["houses_priority"],
        "area_air_baru_piksel": m["new_water_px"],
        "prioritas": [
            f"Datangi dan verifikasi {m['houses_severe']} rumah dengan "
            f"kontak tertinggi serta {m['houses_priority']} rumah prioritas "
            "lainnya untuk evakuasi darurat.",
            "Fokuskan pemantauan pada area konsentrasi genangan baru "
            "terbesar hasil segmentasi.",
            f"Cek kondisi dan keteraksesan {m['road_segments']} segmen "
            "jalan utama untuk jalur evakuasi dan distribusi bantuan.",
        ],
        "catatan_ketidakpastian": (
            "Angka berbasis piksel citra ini belum menunjukkan kedalaman "
            "air, jumlah penghuni terdampak, kondisi struktur bangunan, "
            "maupun akses jalan yang sebenarnya di lapangan."),
    }
    return validate_sitrep(sitrep, m)


def generate_sitrep(measurements: dict, api_key: str | None = None,
                    timeout: int = 180, dry_run: bool = False) -> dict:
    """Generate a validated sitrep dict from a measurements dict.

    With dry_run=True no API call is made and a deterministic synthetic
    sitrep (same schema) is returned, for offline smoke tests.
    """
    m = validate_measurements(measurements)
    if dry_run:
        return _synthetic_sitrep(m)
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
                    {"type": "input_text", "text": build_prompt(m)},
                ],
            }
        ],
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
    if isinstance(body.get("output_text"), str):
        text = body["output_text"]
    else:
        texts: list = []
        _collect_text(body, texts)
        text = max(texts, key=len) if texts else ""
    return parse_sitrep(text, m)
