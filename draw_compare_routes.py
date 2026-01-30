import os
import pandas as pd
import requests
import folium

from config import (
    VALHALLA_2018, VALHALLA_2025, COSTING,
    POINTS_CSV, MATRIX_DELTA_CSV, ROUTE_TIMEOUT
)

BASE_2018 = VALHALLA_2018
BASE_2025 = VALHALLA_2025
DELTA_CSV = MATRIX_DELTA_CSV
OUT_HTML = "route_compare_layers.html"
TIMEOUT_SEC = ROUTE_TIMEOUT

# Color scheme for bidirectional comparison
COLOR_FORWARD = "#2563eb"  # Blue for Forward (A→B)
COLOR_RETURN = "#dc2626"   # Red for Return (B→A)

def decode_polyline(s, precision=6):
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

def get_point(points_df, point_id):
    row = points_df.loc[points_df["id"] == point_id]
    if row.empty:
        raise ValueError(f"Point {point_id} not found")
    return float(row.iloc[0]["lat"]), float(row.iloc[0]["lon"])

def get_delta_row(delta_df, src, dst):
    """Get delta row for specific OD pair (for return route lookup)."""
    row = delta_df[(delta_df["src"] == src) & (delta_df["dst"] == dst)]
    return row.iloc[0] if not row.empty else None


def route_coords(base_url, A, B):
    payload = {
        "locations": [{"lat": A[0], "lon": A[1]}, {"lat": B[0], "lon": B[1]}],
        "costing": COSTING,
        "shape_format": "geojson",
    }
    try:
        r = requests.post(f"{base_url}/route", json=payload, timeout=TIMEOUT_SEC)
        r.raise_for_status()
        data = r.json()
        leg = data["trip"]["legs"][0]
        shape = leg.get("shape")
        
        if isinstance(shape, dict) and "coordinates" in shape:
            coords = [(lat, lon) for lon, lat in shape["coordinates"]]
            return coords, data["trip"]["summary"]
        if isinstance(shape, str):
            coords = decode_polyline(shape, 6)
            return coords, data["trip"]["summary"]
    except:
        return None, None

def main(top_k=10, metric="delta_distance_km"):
    points = pd.read_csv(POINTS_CSV)
    delta = pd.read_csv(DELTA_CSV)
    
    cand = delta.dropna(subset=["time_s_2018", "time_s_2025"]).copy()
    cand = cand[cand["src"] != cand["dst"]]
    cand["abs_metric"] = cand[metric].abs()
    cand = cand.sort_values("abs_metric", ascending=False).head(top_k)
    
    center = (float(points["lat"].mean()), float(points["lon"].mean()))
    m = folium.Map(location=center, zoom_start=14, control_scale=True)  # zoom=14 for Districts 1,2,3
    
    for i, row in cand.reset_index(drop=True).iterrows():
        src = int(row["src"])
        dst = int(row["dst"])

        try:
            A = get_point(points, src)
            B = get_point(points, dst)
        except ValueError as e:
            print(f"[{i+1}/{top_k}] ✗ {e}")
            continue

        abs_metric = float(row["abs_metric"])
        layer_name = f"OD {src}↔{dst} |{metric}|={abs_metric:.2f}"
        fg = folium.FeatureGroup(name=layer_name, show=True)

        # Forward route (src → dst) - BLUE
        coords18_fwd, sum18_fwd = route_coords(BASE_2018, A, B)
        coords25_fwd, sum25_fwd = route_coords(BASE_2025, A, B)

        if not coords18_fwd or not coords25_fwd:
            print(f"[{i+1}/{top_k}] ✗ Failed {src}→{dst}")
            continue

        popup_fwd = f"""
        <b style="color:{COLOR_FORWARD}">▶ FORWARD: {src} → {dst}</b><br>
        <b>2018:</b> {row['time_s_2018']:.0f}s, {row['distance_km_2018']:.3f}km<br>
        <b>2025:</b> {row['time_s_2025']:.0f}s, {row['distance_km_2025']:.3f}km<br>
        <b>Δ:</b> {row['delta_time_s']:+.0f}s, {row['delta_distance_km']:+.3f}km<br><br>
        <b>Valhalla /route:</b><br>
        2018: {sum18_fwd.get('length'):.2f}km, {sum18_fwd.get('time'):.0f}s<br>
        2025: {sum25_fwd.get('length'):.2f}km, {sum25_fwd.get('time'):.0f}s
        """

        # Forward 2018 - Blue Solid
        folium.PolyLine(coords18_fwd, weight=5, opacity=0.9, color=COLOR_FORWARD,
                       tooltip=f"▶ FWD 2018: {src}→{dst}",
                       popup=folium.Popup(popup_fwd, max_width=400)).add_to(fg)

        # Forward 2025 - Blue Dashed
        folium.PolyLine(coords25_fwd, weight=5, opacity=0.9, color=COLOR_FORWARD,
                       dash_array="12,8", tooltip=f"▶ FWD 2025: {src}→{dst}",
                       popup=folium.Popup(popup_fwd, max_width=400)).add_to(fg)

        # Markers: Green for Source, Orange for Destination
        folium.Marker(A, icon=folium.Icon(color="green", icon="play"),
                     tooltip=f"SRC: Point {src}").add_to(fg)
        folium.Marker(B, icon=folium.Icon(color="orange", icon="stop"),
                     tooltip=f"DST: Point {dst}").add_to(fg)
        
        # Return route (dst → src) - RED color, lookup actual B→A data
        coords18_ret, sum18_ret = route_coords(BASE_2018, B, A)
        coords25_ret, sum25_ret = route_coords(BASE_2025, B, A)
        ret_row = get_delta_row(delta, dst, src)

        if coords18_ret and coords25_ret and ret_row is not None:
            # Calculate asymmetry between forward and return
            fwd_time_25 = row['time_s_2025']
            ret_time_25 = ret_row['time_s_2025']
            fwd_dist_25 = row['distance_km_2025']
            ret_dist_25 = ret_row['distance_km_2025']

            time_asym = ret_time_25 - fwd_time_25 if pd.notna(ret_time_25) and pd.notna(fwd_time_25) else 0
            dist_asym = ret_dist_25 - fwd_dist_25 if pd.notna(ret_dist_25) and pd.notna(fwd_dist_25) else 0

            asym_note = ""
            if abs(time_asym) > 60 or abs(dist_asym) > 0.3:
                asym_note = f"<br><b style='color:#dc2626'>⚠️ ASYMMETRY vs Forward: Δt={time_asym:+.0f}s, Δd={dist_asym:+.2f}km</b>"

            popup_ret = f"""
            <b style="color:{COLOR_RETURN}">◀ RETURN: {dst} → {src}</b><br>
            <b>2018:</b> {ret_row['time_s_2018']:.0f}s, {ret_row['distance_km_2018']:.3f}km<br>
            <b>2025:</b> {ret_row['time_s_2025']:.0f}s, {ret_row['distance_km_2025']:.3f}km<br>
            <b>Δ:</b> {ret_row['delta_time_s']:+.0f}s, {ret_row['delta_distance_km']:+.3f}km<br>
            {asym_note}<br>
            <b>Valhalla /route:</b><br>
            2018: {sum18_ret.get('length'):.2f}km, {sum18_ret.get('time'):.0f}s<br>
            2025: {sum25_ret.get('length'):.2f}km, {sum25_ret.get('time'):.0f}s
            """

            # Return 2018 - Red Solid
            folium.PolyLine(coords18_ret, weight=5, opacity=0.9, color=COLOR_RETURN,
                           tooltip=f"◀ RET 2018: {dst}→{src}",
                           popup=folium.Popup(popup_ret, max_width=400)).add_to(fg)

            # Return 2025 - Red Dashed
            folium.PolyLine(coords25_ret, weight=5, opacity=0.9, color=COLOR_RETURN,
                           dash_array="12,8", tooltip=f"◀ RET 2025: {dst}→{src}",
                           popup=folium.Popup(popup_ret, max_width=400)).add_to(fg)

            if abs(time_asym) > 60 or abs(dist_asym) > 0.3:
                print(f"      ⚠️  Asymmetry: Δtime={time_asym:+.0f}s, Δdist={dist_asym:+.2f}km")
        
        fg.add_to(m)
        print(f"[{i+1}/{top_k}] OD {src}↔{dst} |{metric}|={abs_metric:.2f} (fwd: {row['time_s_2025']:.0f}s)")
    
    all_pts = folium.FeatureGroup(name="All points", show=False)
    for r in points.itertuples(index=False):
        folium.CircleMarker((float(r.lat), float(r.lon)), radius=2, 
                          color="#666", fill=True).add_to(all_pts)
    all_pts.add_to(m)
    
    # Add legend - Color-coded bidirectional
    legend_html = f"""
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 9999;
                background: white; padding: 12px 16px; border: 2px solid #333;
                border-radius: 8px; font-size: 13px; font-family: sans-serif;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
        <b style="font-size:14px">Route Legend</b><br><br>
        <span style="color:{COLOR_FORWARD}">━━━</span> <b>Blue Solid</b>: Forward (A→B) 2018<br>
        <span style="color:{COLOR_FORWARD}">╌╌╌</span> <b>Blue Dashed</b>: Forward (A→B) 2025<br>
        <span style="color:{COLOR_RETURN}">━━━</span> <b>Red Solid</b>: Return (B→A) 2018<br>
        <span style="color:{COLOR_RETURN}">╌╌╌</span> <b>Red Dashed</b>: Return (B→A) 2025<br>
        <hr style="margin:8px 0">
        <span style="color:green">▶</span> Source &nbsp;
        <span style="color:orange">■</span> Destination<br>
        <span style="color:#dc2626">⚠️</span> = One-way street asymmetry
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(OUT_HTML)
    print(f"\n✅ Saved: {OUT_HTML}")
    print("   Legend: Thick=Forward, Thin=Return | Solid=2018, Dashed=2025")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metric", default="delta_distance_km")
    args = parser.parse_args()
    main(args.top_k, args.metric)
