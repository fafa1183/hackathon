#!/usr/bin/env python3
"""Run the full SIGAP-Banjir pipeline from a pair of aerial photos.

One command for the whole chain:
  BEFORE + AFTER photos (same location, same frame)
  -> SAM 3.1 segmentation -> water-contact measurement with the
     permanent-water baseline subtracted -> measurements.json +
     overlay.png -> Muse Spark situation report (sitrep.json)

This wraps the existing modules (sigap.sam_client, sigap.exposure_mask,
sigap.sitrep) so a non-programmer can go from raw photos to a report
without chaining the lower-level tools by hand.

Requires MODEL_API_KEY in the environment (SAM 3.1 and the sitrep both
call the Meta Model API). The two photos must show the same location
with the same framing and the same pixel size; the BEFORE photo is the
baseline that keeps rivers and lakes from being counted as flood water.

Example:
    export MODEL_API_KEY=<redacted>
    python tools/olah_foto.py \
        --before foto-sebelum.jpg --after foto-sesudah.jpg \
        --outdir hasil-foto
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def data_url(path: str) -> str:
    """Encode a local image file as a data URL the Model API accepts."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:3] == b"\xff\xd8\xff":  # JPEG
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode()
    from PIL import Image
    buf = io.BytesIO()
    Image.open(io.BytesIO(raw)).convert("RGB").save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Olah pasangan foto udara SIGAP (before/after -> sitrep)")
    ap.add_argument("--before", required=True, help="foto SEBELUM banjir")
    ap.add_argument("--after", required=True, help="foto SESUDAH banjir")
    ap.add_argument("--outdir", default="hasil-foto",
                    help="folder keluaran (default: hasil-foto)")
    ap.add_argument("--lokasi", default=None,
                    help="label lokasi untuk laporan (default: nama file)")
    ap.add_argument("--dry-run", action="store_true",
                    help="sitrep sintetis (segmentasi tetap live)")
    args = ap.parse_args()

    if not os.environ.get("MODEL_API_KEY"):
        print("MODEL_API_KEY belum terpasang di terminal ini.")
        print("Jalankan dulu:  export MODEL_API_KEY=key-kamu")
        return 2
    for p in (args.before, args.after):
        if not os.path.isfile(p):
            print(f"File tidak ditemukan: {p}")
            return 2

    from PIL import Image
    img_after = Image.open(args.after).convert("RGB")
    img_before = Image.open(args.before).convert("RGB")
    if img_after.size != img_before.size:
        print(f"Ukuran foto tidak sama: before {img_before.size} vs "
              f"after {img_after.size}. Pakai pasangan lokasi & bingkai "
              "yang sama.")
        return 2
    W, H = img_after.size
    lokasi = args.lokasi or os.path.splitext(os.path.basename(args.after))[0]

    from sigap.sam_client import segment_image
    from sigap.exposure_mask import build_grid, flood_grid, mask_exposure_summary
    from sigap.sitrep import validate_measurements, generate_sitrep

    url_after, url_before = data_url(args.after), data_url(args.before)
    print("Tahap 1/3: segmentasi SAM 3.1 (live)...")
    houses = segment_image("house", url_after).segments
    print(f"  house: {len(houses)} objek")
    water_after = segment_image("water", url_after).segments
    print(f"  water (sesudah): {len(water_after)} objek")
    roads = segment_image("road", url_after).segments
    print(f"  road: {len(roads)} objek")
    water_before = segment_image("water", url_before).segments
    print(f"  water (sebelum): {len(water_before)} objek")

    print("Tahap 2/3: pengukuran kontak air (air permanen dikurangi)...")
    grid_new = flood_grid(water_after, water_before, W, H, baseline_margin=10)
    grid_after = build_grid(water_after, W, H)
    grid_before = build_grid(water_before, W, H)
    summary = mask_exposure_summary(houses, grid_new, W, H)
    per_house = sorted(
        (h for h in summary["per_house"] if h["water_contact"] > 0),
        key=lambda h: -h["water_contact"])
    measurements = validate_measurements({
        "location": lokasi,
        "image_width": W,
        "image_height": H,
        "houses_detected": summary["houses_total"],
        "new_water_px": int(sum(grid_new)),
        "water_area_after_px": int(sum(grid_after)),
        "water_area_baseline_px": int(sum(grid_before)),
        "priority_houses": [
            {"box": h["box"], "water_contact": h["water_contact"]}
            for h in per_house
        ],
        "road_segments": len(roads),
    })

    os.makedirs(args.outdir, exist_ok=True)
    mpath = os.path.join(args.outdir, "measurements.json")
    with open(mpath, "w") as fh:
        json.dump(measurements, fh, indent=2)

    from PIL import ImageDraw
    overlay = img_after.copy()
    draw = ImageDraw.Draw(overlay)
    for seg in houses:
        color = (0, 200, 0) if (seg.confidence or 0) >= 0.7 else (255, 170, 0)
        draw.rectangle([seg.x1, seg.y1, seg.x2, seg.y2], outline=color, width=2)
    opath = os.path.join(args.outdir, "overlay.png")
    overlay.save(opath)

    print(f"  rumah terdeteksi : {measurements['houses_detected']}")
    print(f"  prioritas (>=10%): {measurements['houses_priority']} "
          f"(terberat >=20%: {measurements['houses_severe']}, "
          f"kontak maks {measurements['max_contact']:.3f})")
    print(f"  air baru         : {measurements['new_water_px']} px")
    print(f"  segmen jalan     : {measurements['road_segments']}")

    print("Tahap 3/3: Muse Spark menulis sitrep...")
    spath = os.path.join(args.outdir, "sitrep.json")
    try:
        sitrep = generate_sitrep(measurements, dry_run=args.dry_run)
        with open(spath, "w") as fh:
            json.dump(sitrep, fh, indent=2, ensure_ascii=False)
        print(f"  sitrep: {sitrep['ringkasan']}")
    except Exception as exc:  # measurements tetap berguna walau Spark gagal
        print(f"  PERINGATAN: sitrep gagal dibuat ({exc}). "
              "measurements.json tetap tersimpan; ulangi tahap ini dengan "
              "tools/run_sitrep.py.")

    print("\nSELESAI. Hasil di " + args.outdir + ":")
    print(f"  - {mpath}")
    print(f"  - {opath}")
    if os.path.isfile(spath):
        print(f"  - {spath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
