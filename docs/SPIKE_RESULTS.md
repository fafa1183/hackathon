# Spike results — SAM 3.1 on real flood aerial imagery

Run on 27 Oct 2026, before any project code was written, to decide whether
the SIGAP-Banjir concept is technically viable.

## Setup

- API: Meta Model API, `POST https://api.meta.ai/v1/responses`
- Model: `sam-3.1`, one short noun phrase per request
- Image: NOAA NGS post-Harvey aerial, West Houston (960x400, public domain)
- Confidence requested via `metadata.include_confidence = "true"`
- Contract verified against the official docs:
  https://dev.meta.ai/docs/sam/overview ,
  https://dev.meta.ai/docs/sam/segmenting ,
  https://dev.meta.ai/docs/sam/reading-segmentation

Output note: SAM 3.1 does not return a JSON array. Segmentation arrives as
`output_text` lines holding one box record and one mask record per object;
masks are base85 payloads. Usage is billed per image and reported as
`images_processed`.

## Results

| Prompt        | Objects | Confidence    | Latency |
| ------------- | ------- | ------------- | ------- |
| `house`       | 92      | 0.50 - 0.87 (44 at >= 0.70) | 17.2 s |
| `flood water` | 3       | up to 0.73    | 2.0 s   |
| `road`        | 2       | up to 0.64    | 3.5 s   |

- The 92 house boxes were drawn back onto the source image and checked
  visually: they sit on rooftops across the scene, including the houses
  ringing the floodwater. A small number land on similar-looking
  structures (tennis courts, large flat roofs).
- The main `flood water` region covers the flooded bayou through the
  middle of the neighbourhood.
- Box-level proxy: 46-47 of the 92 house boxes overlap a flood-water box.
  This overstates exposure because water boxes are rectangles; the
  production count must intersect the decoded masks instead.

## Verdict

Perception is not the risk in this project. The remaining work is mask
decoding, exposure analytics, the Spark situation-report agent, and the
dashboard — all standard engineering on top of a proven API contract.
