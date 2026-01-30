#!/bin/bash
docker run --rm -it \
  --name valhalla_2025 \
  -p 8005:8002 \
  -v /Users/nhiphan/gis/custom_2025:/custom_files \
  -e tile_urls=/custom_files/hcm_2025.osm.pbf \
  -e build_elevation=false \
  ghcr.io/gis-ops/docker-valhalla/valhalla:3.5.1
