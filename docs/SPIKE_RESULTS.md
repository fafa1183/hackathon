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

## Addendum (same day): masks decoded, two method findings

Mask payloads are decoded with Meta's official Python parser
(`meta_sam_parser.decode_mask_to_raster`); the docs deliberately do not
publish the bit-level format. Decoded rasters are row-major 0/1 with
H rows and W columns, and in all 95 segments checked the raster size
equals the inclusive box size, so a mask maps 1:1 onto its box at
(x1, y1). A rendered composite of the three water masks traces the
visible floodwater exactly. (Development note: an early version of our
parser paired every box with the next record's mask due to an off-by-one
on adjacent tokens; the size-equality check caught it and it is fixed.)

Finding 1 — overlap is the wrong metric. House masks and water masks
are pixel-precise and disjoint (a roof is never water), so mask
intersection counts zero affected houses. Following FloodNet's own
definition, exposure is scored as the water contact fraction in the
ring around each house footprint.

Finding 2 — subtract the baseline. Much of the water in the "after"
photo is a permanent lake that also exists in NOAA's "before" image.
Segmenting water in the before image (54 objects: the lake plus
swimming pools) and subtracting it, dilated by 10 px, leaves 39,437 px
of genuinely new water out of 77,682 px of after-water: the lake's
northern arm expansion and a flooded facility area on the right. On this
particular photo only a handful of houses touch the new water, because
the obvious water body is mostly permanent; the metric and the change
detection, not the raw count, are what this spike needed to prove.
Prompt choice also matters: "flood water" concentrated on the lake,
while plain "water" on the before image returned pools and the lake.

## Verdict

Perception is not the risk in this project. The remaining work is
exposure analytics on FloodNet (where ground truth settles the metric),
the Spark situation-report agent, and the dashboard — all standard
engineering on top of a proven API contract.
