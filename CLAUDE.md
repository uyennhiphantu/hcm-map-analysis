# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Motivation & Goals

**Career:** Building mapping and spatial analysis skills to prepare for roles at companies like Grab (ride-hailing/logistics platform in Vietnam).

**Personal:** Passion for maps and geography - using spatial data to help people navigate, solve real-world problems, and discover meaningful patterns.

**Approach:** This is a personal project - prioritize fast iteration and quick results over enterprise-level code standards. Keep token usage efficient.

## Project Overview

GIS routing comparison project analyzing road network evolution in Ho Chi Minh City by comparing historical OSM snapshots (2018 vs 2025) using Valhalla routing engine.

## Current Scope

**Geographic Focus:** Districts 1, 2, 3 - Ho Chi Minh City
```
BBOX: 106.665, 10.762 → 106.760, 10.820
```

**Routing Mode:** Car-only (`costing: auto`)
- Includes: motorway, trunk, primary, secondary, tertiary, residential, service roads
- Excludes: footway, pedestrian, cycleway, steps, paths

## Architecture

```
config.py          # Central configuration (bbox, endpoints, costing)
    ↓
generate_points.py # Create random points snapped to road network → points.csv
    ↓
run_matrix_and_delta.py # Query both Valhalla instances → matrix_*.csv
    ↓
draw_*.py          # Visualize routes with Folium → *.html
analysis.py        # Print statistics
```

## Key Commands

```bash
# Generate 50 points in Districts 1,2,3 (uses config.py bounding box)
python generate_points.py
python generate_points.py --n 100

# Run OD matrix comparison (requires Docker instances running)
python run_matrix_and_delta.py

# Visualize top routes with BIDIRECTIONAL comparison (A→B and B→A)
python draw_compare_routes.py --top-k 10 --metric delta_time_s
python draw_compare_routes.py --top-k 10 --metric delta_distance_km

# Single-direction visualization
python draw_map.py

# Analysis
python analysis.py
```

## Bidirectional Visualization

`draw_compare_routes.py` shows both forward (A→B) and return (B→A) routes to highlight one-way street asymmetries:

- **Thick lines**: Forward route (A→B)
- **Thin lines**: Return route (B→A)
- **Solid**: 2018 route
- **Dashed**: 2025 route
- **⚠️ ASYMMETRY**: Flagged when |Δtime| > 60s or |Δdist| > 0.3km between forward/return

## Docker Instances

| Year | Port | Container | OSM File |
|------|------|-----------|----------|
| 2018 | 8004 | valhalla_2018 | custom_2018/hcm_2018.osm.pbf |
| 2025 | 8005 | valhalla_2025 | custom_2025/hcm_2025.osm.pbf |

```bash
# Start instances
./run_2018.sh
./run_2025.sh

# Check status
curl -s http://localhost:8004/status | head
curl -s http://localhost:8005/status | head
```

## OSM Extraction

To re-extract OSM data for the narrowed scope:
```bash
osmium extract -b 106.665,10.762,106.760,10.820 vietnam-180101.osm.pbf -o custom_2018/hcm_2018.osm.pbf
osmium extract -b 106.665,10.762,106.760,10.820 vietnam-251201.osm.pbf -o custom_2025/hcm_2025.osm.pbf
```

## Data Schema

**points.csv:** `id, lat, lon, snap_m`

**matrix_delta.csv:** `src, dst, time_s_2018, distance_km_2018, time_s_2025, distance_km_2025, delta_time_s, delta_distance_km, pct_time, pct_distance`

## Key Insight

Positive delta doesn't mean "slower" - it often means 2025 routing is more realistic due to complete road network data. 2018 OSM had sparse coverage leading to unrealistic short routes.
