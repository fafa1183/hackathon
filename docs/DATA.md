# Data sources

SIGAP-Banjir is developed and validated on openly licensed aerial flood
imagery. Nothing here is scraped without a license.

## NOAA NGS damage-assessment imagery (primary spike image)

- Post-Hurricane Harvey aerial imagery collected by the U.S. National
  Geodetic Survey, August-September 2017.
- Spike image: West Houston, after the flood —
  https://oceanservice.noaa.gov/news/sep17/west-houston-after.jpg
  (overview page: https://oceanservice.noaa.gov/news/sep17/hurricane-harvey.html)
- License: works of the U.S. federal government, public domain.

## FloodNet (validation set and demo assets)

- Rahnemoonfar et al., "FloodNet: A High Resolution Aerial Imagery Dataset
  for Post Flood Scene Understanding", IEEE Access, 2021.
- 2,343 high-resolution UAS images (DJI Mavic Pro) captured after
  Hurricane Harvey, with pixel-level labels: Building Flooded,
  Building Non-Flooded, Road Flooded, Road Non-Flooded, Water, Tree,
  Vehicle, Pool, Grass. The labels give us ground truth to score
  SAM 3.1 output against.
- Official repository: https://github.com/BinaLab/FloodNet-Supervised_v1.0
- License as stated in the official repository: Community Data License
  Agreement (permissive). The Dataset Ninja mirror states CC BY-SA 4.0.
  When in doubt, the stricter terms win. The paper must be cited when
  the dataset is used.

## Indonesian imagery

Indonesian flood footage for the final demo is still to be sourced
(preferably our own or BPBD-published material with clear permission).
FloodNet and NOAA imagery carry the technical validation either way.
