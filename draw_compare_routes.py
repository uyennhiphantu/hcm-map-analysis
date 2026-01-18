import os
import pandas as pd
import requests
import folium

BASE_2018 = "http://localhost:8004"
BASE_2025 = "http://localhost:8005"

POINTS_CSV = "points.csv"
DELTA_CSV = "matrix_delta.csv"

OUT_HTML = "route_compare_layers.html"
TIMEOUT_SEC = 90

PALETTE = [
    "red", "blue", "green", "orange", "purple",
    "brown", "black", "cadetblue", "darkred", "darkgreen",
    "darkblue", "pink"
]

def decode_polyline(s: str, precision: int = 6):
    """Decode encoded polyline string. Returns list of (lat, lon)."""
    index, lat, lon = 0, 0, 0
    coords = []
    factor = 10 ** precision

    while index < len(s):
        shift = result = 0
        while True:
            b = ord(s[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift = result = 0
        while True:
            b = ord(s[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if (result & 1) else (result >> 1)
        lon += dlon

        coords.append((lat / factor, lon / factor))

    return coords

def get_point(points_df: pd.DataFrame, point_id: int) -> tuple[float, float]:
    row = points_df.loc[points_df["id"] == point_id]
    if row.empty:
        raise ValueError(f"Point id {point_id} not found in points_50.csv")
    return float(row.iloc[0]["lat"]), float(row.iloc[0]["lon"])

def route_coords(base_url: str, A: tuple[float, float], B: tuple[float, float]):
    """
    Robustly fetch route coords from Valhalla /route:
    - GeoJSON shape dict: {"coordinates":[[lon,lat],...]}
    - Polyline shape string: decode
    """
    payload = {
        "locations": [{"lat": A[0], "lon": A[1]}, {"lat": B[0], "lon": B[1]}],
        "costing": "auto",
        "directions_options": {"units": "kilometers"},
        "shape_format": "geojson",
    }
    r = requests.post(f"{base_url}/route", json=payload, timeout=TIMEOUT_SEC)
    r.raise_for_status()
    data = r.json()

    leg = data["trip"]["legs"][0]
    shape = leg.get("shape")

    if isinstance(shape, dict) and "coordinates" in shape:
        coords_lonlat = shape["coordinates"]
        coords_latlon = [(lat, lon) for lon, lat in coords_lonlat]
        return coords_latlon, data["trip"]["summary"]

    if isinstance(shape, str):
        coords_latlon = decode_polyline(shape, precision=6)
        return coords_latlon, data["trip"]["summary"]

    # fallback request without geojson
    payload2 = {
        "locations": [{"lat": A[0], "lon": A[1]}, {"lat": B[0], "lon": B[1]}],
        "costing": "auto",
        "directions_options": {"units": "kilometers"},
    }
    r2 = requests.post(f"{base_url}/route", json=payload2, timeout=TIMEOUT_SEC)
    r2.raise_for_status()
    data2 = r2.json()
    shape2 = data2["trip"]["legs"][0].get("shape")

    if isinstance(shape2, str):
        coords_latlon = decode_polyline(shape2, precision=6)
        return coords_latlon, data2["trip"]["summary"]

    raise RuntimeError(f"Unsupported shape format from {base_url}/route. shape type={type(shape)}")

def safe_num(x):
    return None if pd.isna(x) else float(x)

def main(top_k=10, metric="delta_time_s"):
    points = pd.read_csv(POINTS_CSV)
    delta = pd.read_csv(DELTA_CSV)

    if metric not in delta.columns:
        raise ValueError(f"Metric '{metric}' not found in {DELTA_CSV}")

    # valid for both years + exclude self-loop
    cand = delta.dropna(subset=["time_s_2018","time_s_2025","distance_km_2018","distance_km_2025", metric]).copy()
    cand = cand[cand["src"] != cand["dst"]]

    # choose most "interesting" by abs delta
    cand["abs_metric"] = cand[metric].abs()
    cand = cand.sort_values("abs_metric", ascending=False).head(top_k)

    if cand.empty:
        raise RuntimeError("No valid OD pairs after filtering.")

    # map center based on involved points
    involved_ids = pd.unique(cand[["src","dst"]].values.ravel("K"))
    involved_pts = points[points["id"].isin(involved_ids)]
    center = (float(involved_pts["lat"].mean()), float(involved_pts["lon"].mean()))
    m = folium.Map(location=center, zoom_start=12, control_scale=True)

    # Optional: a base layer showing all points (toggleable)
    all_pts_layer = folium.FeatureGroup(name="All points", show=False)
    for r in points.itertuples(index=False):
        folium.CircleMarker(
            location=(float(r.lat), float(r.lon)),
            radius=2,
            color="#666",
            fill=True,
            fill_opacity=0.6,
            tooltip=f"Point {int(r.id)}"
        ).add_to(all_pts_layer)
    all_pts_layer.add_to(m)

    for i, row in cand.reset_index(drop=True).iterrows():
        src = int(row["src"]); dst = int(row["dst"])
        color = PALETTE[i % len(PALETTE)]

        A = get_point(points, src)
        B = get_point(points, dst)

        abs_metric = float(row["abs_metric"])
        layer_name = f"OD {src}→{dst} |{metric}|={abs_metric:.2f}"
        fg = folium.FeatureGroup(name=layer_name, show=True)

        print(f"[{i+1}/{len(cand)}] {layer_name} color={color}")

        # fetch routes
        try:
            coords14, sum14 = route_coords(BASE_2018, A, B)
        except Exception as e:
            print(f"  ❌ 2018 route failed: {e}")
            continue

        try:
            coords25, sum25 = route_coords(BASE_2025, A, B)
        except Exception as e:
            print(f"  ❌ 2025 route failed: {e}")
            continue

        t14 = safe_num(row["time_s_2018"]); t25 = safe_num(row["time_s_2025"])
        d14 = safe_num(row["distance_km_2018"]); d25 = safe_num(row["distance_km_2025"])
        dt = safe_num(row["delta_time_s"]); dd = safe_num(row["delta_distance_km"])

        popup = (
            f"<b>OD:</b> {src} → {dst}<br>"
            f"<b>2018:</b> {t14:.0f}s, {d14:.3f}km<br>"
            f"<b>2025:</b> {t25:.0f}s, {d25:.3f}km<br>"
            f"<b>Δ:</b> {dt:+.0f}s, {dd:+.3f}km<br><br>"
            f"<b>/route summary</b><br>"
            f"2018: length={sum14.get('length')}, time={sum14.get('time')}<br>"
            f"2025: length={sum25.get('length')}, time={sum25.get('time')}"
        )

        # 2018 solid
        folium.PolyLine(
            coords14,
            weight=5,
            opacity=0.85,
            color=color,
            tooltip=f"2018 {src}->{dst}",
            popup=folium.Popup(popup, max_width=480),
        ).add_to(fg)

        # 2025 dashed
        folium.PolyLine(
            coords25,
            weight=5,
            opacity=0.85,
            color=color,
            dash_array="10,6",
            tooltip=f"2025 {src}->{dst}",
            popup=folium.Popup(popup, max_width=480),
        ).add_to(fg)

        # endpoints
        folium.CircleMarker(A, radius=5, color=color, fill=True, fill_opacity=1.0,
                            tooltip=f"Src {src}").add_to(fg)
        folium.CircleMarker(B, radius=5, color=color, fill=True, fill_opacity=1.0,
                            tooltip=f"Dst {dst}").add_to(fg)

        fg.add_to(m)

    # Checkbox UI
    folium.LayerControl(collapsed=False).add_to(m)

    m.save(OUT_HTML)
    print(f"\n✅ Saved: {OUT_HTML}")
    print("Tip: Use the checkbox control (top-right) to toggle each OD layer.")

if __name__ == "__main__":
    # top_k=5 or 10
    # metric="delta_distance_km" if you want to draw based on distance difference
    main(top_k=10, metric="delta_distance_km")
