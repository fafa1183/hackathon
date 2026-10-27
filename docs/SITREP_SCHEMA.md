# Sitrep JSON schema — the dashboard data contract

`src/sigap/sitrep.py` turns segmentation measurements into a situation
report (sitrep) by asking Muse Spark to reason over the numbers. The
JSON it returns is the contract between the pipeline and the situation
dashboard (`dashboard/sigap_dashboard.html`): **the sample data built
into the dashboard is a placeholder and must be replaced by this output**
for the demo and any real use.

## Input: measurements

A JSON object, typically assembled from `sam_client` +
`exposure_mask` results:

| Key | Type | Meaning |
| --- | --- | --- |
| `houses_detected` | int | houses segmented in the after-flood image |
| `new_water_px` | int | new-water pixel area after baseline (permanent water) subtraction |
| `priority_houses` | list | per-house dicts with at least `water_contact` (0–1), e.g. `mask_exposure_summary`'s `per_house` |
| `road_segments` | int or list | detected road segments (a list is counted) |
| `water_area_after_px`, `water_area_baseline_px` | int, optional | total water areas, after vs before |
| `new_water_notes` | string, optional | where the new water concentrates |
| `location`, `image_width`, `image_height` | optional | scene description for the prompt |

A house is a priority at water contact ≥ 0.10 of its surrounding ring,
severe at ≥ 0.20 — the thresholds the spike reported on.

## Output: sitrep

Exactly these keys; `sigap.sitrep.validate_sitrep` enforces them plus
the types, and rejects a report whose echoed numbers
(`rumah_terdeteksi`, `area_air_baru_piksel`) disagree with the
measurements it was generated from.

| Key | Type | Meaning |
| --- | --- | --- |
| `ringkasan` | string | 2–3 sentence plain-language summary (Bahasa Indonesia) |
| `rumah_terdeteksi` | int | houses detected (echo of the measurement) |
| `rumah_terdampak_prioritas` | int | houses needing first attention |
| `area_air_baru_piksel` | int | new-water area in pixels (echo of the measurement) |
| `prioritas` | list of 1–3 strings | concrete first actions (Bahasa Indonesia) |
| `catatan_ketidakpastian` | string | one sentence on what the numbers cannot yet tell us |

Example (the live spike run, docs/SPIKE_RESULTS.md):

```json
{
  "ringkasan": "Terdeteksi 92 rumah di area permukiman yang dipantau pascabanjir di Houston Barat. ...",
  "rumah_terdeteksi": 92,
  "rumah_terdampak_prioritas": 9,
  "area_air_baru_piksel": 39437,
  "prioritas": ["Datangi dan verifikasi 1 rumah dengan kontak tertinggi ...", "..."],
  "catatan_ketidakpastian": "Angka berbasis piksel citra ini belum menunjukkan kedalaman air, ..."
}
```

## Running it

```bash
export MODEL_API_KEY=...   # Meta Model API key, never commit it
python tools/run_sitrep.py --measurements measurements.json --out sitrep.json

# Offline smoke test (no API call, synthetic sitrep, same schema):
python tools/run_sitrep.py --measurements tests/fixtures/measurements_synthetic.json \
  --out sitrep.json --dry-run
```
