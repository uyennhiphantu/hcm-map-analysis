import pandas as pd
import requests

from config import (
    VALHALLA_2018, VALHALLA_2025, COSTING,
    POINTS_CSV, MATRIX_2018_CSV, MATRIX_2025_CSV, MATRIX_DELTA_CSV,
    MATRIX_TIMEOUT
)

BASE_2018 = VALHALLA_2018
BASE_2025 = VALHALLA_2025
TIMEOUT_SEC = MATRIX_TIMEOUT


def _post(base_url: str, path: str, payload: dict):
    url = f"{base_url}{path}"
    r = requests.post(url, json=payload, timeout=TIMEOUT_SEC)
    if r.status_code == 404:
        return None, r
    if not r.ok:
        print("\n=== VALHALLA ERROR ===")
        print("URL:", url)
        print("HTTP:", r.status_code)
        print("Response:", r.text[:2000])
        print("Payload sizes: sources =", len(payload.get("sources", [])),
              "targets =", len(payload.get("targets", [])))
        if payload.get("sources"):
            print("Sample source[0]:", payload["sources"][0])
        if payload.get("targets"):
            print("Sample target[0]:", payload["targets"][0])
        print("=== END ERROR ===\n")

    r.raise_for_status()
    return r.json(), r


def call_matrix(base_url: str, locs: list[dict]) -> list:
    payload_stt = {
        "sources": locs,
        "targets": locs,
        "costing": COSTING,
    }

    data, resp = _post(base_url, "/sources_to_targets", payload_stt)
    if data is None:
        payload_matrix = {
            "sources": locs,
            "targets": locs,
            "costing": COSTING,
            "action": "sources_to_targets",
        }
        data, resp = _post(base_url, "/matrix", payload_matrix)

    if data is None:
        raise RuntimeError(
            f"Matrix endpoint not found on {base_url}. "
            f"Tried /sources_to_targets and /matrix. Last status={resp.status_code}"
        )

    if isinstance(data, dict) and "sources_to_targets" in data:
        return data["sources_to_targets"]

    if isinstance(data, list):
        return data

    raise RuntimeError(f"Unexpected matrix response shape from {base_url}: {type(data)} keys={list(data.keys()) if isinstance(data, dict) else ''}")


def matrix_to_long(m: list, year: int) -> pd.DataFrame:
    rows = []
    n = len(m)
    for i in range(n):
        for j in range(len(m[i])):
            cell = m[i][j]
            rows.append({
                "src": i + 1,
                "dst": j + 1,
                "time_s": None if cell is None else cell.get("time"),
                "distance_km": None if cell is None else cell.get("distance"),
                "year": year,
            })
    return pd.DataFrame(rows)


def main():
    pts = pd.read_csv(POINTS_CSV)
    locs = [{"lat": float(r.lat), "lon": float(r.lon)} for r in pts.itertuples(index=False)]

    print(f"Loaded {len(locs)} points from {POINTS_CSV}")
    print(f"Bounding box coverage check: lat=[{pts['lat'].min():.4f}, {pts['lat'].max():.4f}], lon=[{pts['lon'].min():.4f}, {pts['lon'].max():.4f}]")

    print("\nCalling matrix 2018...")
    m2018 = call_matrix(BASE_2018, locs)
    df2018 = matrix_to_long(m2018, 2018)
    df2018.to_csv(MATRIX_2018_CSV, index=False)
    print(f"✅ {MATRIX_2018_CSV} saved")

    print("\nCalling matrix 2025...")
    m2025 = call_matrix(BASE_2025, locs)
    df2025 = matrix_to_long(m2025, 2025)
    df2025.to_csv(MATRIX_2025_CSV, index=False)
    print(f"✅ {MATRIX_2025_CSV} saved")

    df = df2018.merge(
        df2025[["src", "dst", "time_s", "distance_km"]],
        on=["src", "dst"],
        suffixes=("_2018", "_2025")
    )

    df["delta_time_s"] = df["time_s_2025"] - df["time_s_2018"]
    df["delta_distance_km"] = df["distance_km_2025"] - df["distance_km_2018"]
    df["pct_time"] = (df["delta_time_s"] / df["time_s_2018"]) * 100
    df["pct_distance"] = (df["delta_distance_km"] / df["distance_km_2018"]) * 100

    df.to_csv(MATRIX_DELTA_CSV, index=False)
    print(f"✅ {MATRIX_DELTA_CSV} saved")

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total OD pairs: {len(df)}")
    print(f"Null cells 2018: {df['time_s_2018'].isna().sum()}")
    print(f"Null cells 2025: {df['time_s_2025'].isna().sum()}")

    best_time = df.dropna(subset=["delta_time_s"]).sort_values("delta_time_s").head(10)
    best_dist = df.dropna(subset=["delta_distance_km"]).sort_values("delta_distance_km").head(10)

    print("\nTop 10 FASTER in 2025 (most negative delta_time_s):")
    print(best_time[["src", "dst", "time_s_2018", "time_s_2025", "delta_time_s"]].to_string(index=False))

    print("\nTop 10 SHORTER in 2025 (most negative delta_distance_km):")
    print(best_dist[["src", "dst", "distance_km_2018", "distance_km_2025", "delta_distance_km"]].to_string(index=False))


if __name__ == "__main__":
    main()
