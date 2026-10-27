# SIGAP-Banjir

**Drone flood imagery in, a rescue-ready situation report out.**

SIGAP-Banjir turns aerial photos of a flooded area into decisions for response
teams: how many houses are affected, which roads are cut off, where to send
help first, and a draft situation report a duty officer can act on.

Built for the Meta Global AI Developer Hackathon (Cerebral Valley, 2026),
theme **Push the Frontier**, Indie track, by Fafa Team.

## How it works

1. **See** — [SAM 3.1](https://dev.meta.ai/docs/sam/overview) on the Meta
   Model API segments one concept per request (`house`, `flood water`,
   `road`, ...) in an aerial image and returns a box and a pixel mask for
   every instance, with confidence scores.
2. **Measure** — house footprints are intersected with the flood-water mask
   to count affected homes; road segments overlapped by water are flagged
   as cut off.
3. **Decide** — a Muse Spark agent reasons over the measurements and drafts
   the situation report: affected-house count, cut-off roads, evacuation
   priorities, and a plain-language summary for responders.

## Status

The perception step is already proven. A spike on a public-domain NOAA
aerial photo of West Houston after Hurricane Harvey (960x400) returned:

| Prompt        | Instances | Notes                                   |
| ------------- | --------- | --------------------------------------- |
| `house`       | 92        | confidences 0.50-0.87, boxes verified on rooftops, including the ring of houses around the floodwater |
| `flood water` | 3 regions | main region covers the flooded bayou   |
| `road`        | 2         | main road corridor                     |

Full spike notes: [docs/SPIKE_RESULTS.md](docs/SPIKE_RESULTS.md).
Data sources and licenses: [docs/DATA.md](docs/DATA.md).

## Run the spike

```bash
export MODEL_API_KEY=...   # Meta Model API key, never commit it
python tools/run_spike.py \
  --image-url https://oceanservice.noaa.gov/news/sep17/west-houston-after.jpg \
  --prompts house "flood water" road \
  --outdir out/
```

Outputs per prompt: the raw API response, the segmentation text, a JSON
summary of boxes and confidences, and (with Pillow installed) an overlay
PNG with the detected boxes drawn on the source image.

## Run the sitrep generator

```bash
export MODEL_API_KEY=...   # Meta Model API key, never commit it
python tools/run_sitrep.py --measurements measurements.json --out sitrep.json
```

Add `--dry-run` for an offline smoke test (no API call; a synthetic
sitrep with the same schema). The sitrep JSON is the data contract the
dashboard consumes — schema and a synthetic measurements fixture:
[docs/SITREP_SCHEMA.md](docs/SITREP_SCHEMA.md),
`tests/fixtures/measurements_synthetic.json`.

## Layout

- `src/sigap/sam_client.py` — Meta Model API client for SAM 3.1
  segmentation and the output-text parser.
- `src/sigap/exposure.py` — box-level exposure summary (houses vs water).
- `src/sigap/exposure_mask.py` — mask-level exposure: water-contact
  fraction per house on the baseline-subtracted flood grid.
- `src/sigap/sitrep.py` — Muse Spark situation-report generator
  (measurements in, validated JSON sitrep out).
- `tools/run_spike.py` — command-line spike runner used for the results
  above.
- `tools/run_sitrep.py` — command-line sitrep generator (supports
  `--dry-run` for offline smoke tests).
- `dashboard/` — situation dashboard; consumes the sitrep JSON.
- `docs/` — data sources, licenses, spike results and the sitrep schema.

## Roadmap to submission (freeze: evening of 4 Nov 2026)

- [x] Mask decoding via Meta's official parser, contact-based exposure
      metric, and baseline (before-image) subtraction of permanent water
- [ ] FloodNet subset wired in, scores against its ground-truth labels
- [x] Muse Spark situation-report agent (JSON schema + narrative)
- [ ] Situation dashboard (map overlay + priority panel)
- [ ] Video segmentation pass on a short aerial clip
- [ ] 3-minute demo video and submission package

## License

Code in this repository is MIT (see `LICENSE`). Third-party data keeps its
own licenses; see `docs/DATA.md`.
