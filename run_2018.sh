#!/bin/bash
docker run --rm -it \
  --name valhalla_2018 \
  -p 8004:8002 \
  -v /Users/nhiphan/gis/custom_2018:/custom_files \
  -e tile_urls=/custom_files/hcm_2018.osm.pbf \
  -e build_elevation=false \
  ghcr.io/gis-ops/docker-valhalla/valhalla:3.5.1
