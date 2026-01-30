import random, math, time
import argparse
import pandas as pd
import requests

from config import (
    MIN_LON, MIN_LAT, MAX_LON, MAX_LAT,
    VALHALLA_2025, LOCATE_TIMEOUT, POINTS_DATA_CSV
)

VALHALLA_LOCATE_URL = f"{VALHALLA_2025}/locate"

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def locate(lat, lon, timeout=LOCATE_TIMEOUT):
    payload = {"locations": [{"lat": lat, "lon": lon}]}
    r = requests.post(VALHALLA_LOCATE_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _unwrap_locate_response(resp):
    """
    Handle both:
      - dict: {"locations":[...]}
      - list: [...]
    Return first location dict or None
    """
    if isinstance(resp, dict):
        locs = resp.get("locations")
        if isinstance(locs, list) and len(locs) > 0:
            return locs[0]
        # sometimes resp itself is the location dict
        if "edges" in resp:
            return resp
        return None

    if isinstance(resp, list):
        return resp[0] if len(resp) > 0 and isinstance(resp[0], dict) else None

    return None

def pick_snapped_point(resp):
    """
    Extract snapped (correlated/projected) lat/lon from locate response.
    Return (lat, lon) or None.
    """
    loc0 = _unwrap_locate_response(resp)
    if not loc0:
        return None

    edges = loc0.get("edges") or []
    if not edges:
        return None

    e0 = edges[0]

    # Common fields across Valhalla builds:
    # - correlated_lat/correlated_lon
    # - projected: {lat, lon}
    slat = e0.get("correlated_lat")
    slon = e0.get("correlated_lon")

    if slat is None or slon is None:
        proj = e0.get("projected") or {}
        slat = proj.get("lat")
        slon = proj.get("lon")

    if slat is None or slon is None:
        return None

    return float(slat), float(slon)

def main(n=50, min_lon=MIN_LON, min_lat=MIN_LAT, max_lon=MAX_LON, max_lat=MAX_LAT, seed=42, max_snap_m=40, max_tries=8000, sleep_s=0.01):
    random.seed(seed)
    accepted = []
    tries = 0

    while len(accepted) < n and tries < max_tries:
        tries += 1

        lat = random.uniform(min_lat, max_lat)
        lon = random.uniform(min_lon, max_lon)

        try:
            resp = locate(lat, lon)
        except Exception:
            time.sleep(0.1)
            continue

        snapped = pick_snapped_point(resp)
        if not snapped:
            continue

        slat, slon = snapped
        d = haversine_m(lat, lon, slat, slon)

        if d <= max_snap_m:
            accepted.append({
                "id": len(accepted) + 1,
                "lat": slat,
                "lon": slon,
                "snap_m": round(d, 2)
            })

        time.sleep(sleep_s)

    if len(accepted) < n:
        raise RuntimeError(
            f"We can just only create {len(accepted)}/{n} points after {tries} attempts. "
            f"Try increasing max_tries or max_snap_m."
        )

    df = pd.DataFrame(accepted)
    df.to_csv(POINTS_DATA_CSV, index=False)
    print(f"✅ {POINTS_DATA_CSV} generated")
    print(df["snap_m"].describe())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate snapped points for this region")
    parser.add_argument("--n", type=int, default=50, help="Number of points to generate (default: 50)")
    parser.add_argument("--min-lon", type=float, default=MIN_LON, help=f"Minimum longitude (default: {MIN_LON})")
    parser.add_argument("--min-lat", type=float, default=MIN_LAT, help=f"Minimum latitude (default: {MIN_LAT})")
    parser.add_argument("--max-lon", type=float, default=MAX_LON, help=f"Maximum longitude (default: {MAX_LON})")
    parser.add_argument("--max-lat", type=float, default=MAX_LAT, help=f"Maximum latitude (default: {MAX_LAT})")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--max-snap-m", type=float, default=40, help="Maximum snap distance in meters (default: 40)")
    parser.add_argument("--max-tries", type=int, default=8000, help="Maximum attempts to generate points (default: 8000)")
    
    args = parser.parse_args()
    
    main(
        n=args.n,
        min_lon=args.min_lon,
        min_lat=args.min_lat,
        max_lon=args.max_lon,
        max_lat=args.max_lat,
        seed=args.seed,
        max_snap_m=args.max_snap_m,
        max_tries=args.max_tries
    )
