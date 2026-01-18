import pandas as pd

path = "/Users/nhiphan/gis/matrix_delta.csv"
df = pd.read_csv(path)

summary = {
    "rows": len(df),
    "null_2018_time": int(df["time_s_2018"].isna().sum()),
    "null_2025_time": int(df["time_s_2025"].isna().sum()),
    "avg_delta_time_s": df["delta_time_s"].dropna().mean(),
    "avg_delta_distance_km": df["delta_distance_km"].dropna().mean(),
    "median_delta_time_s": df["delta_time_s"].dropna().median(),
    "median_delta_distance_km": df["delta_distance_km"].dropna().median(),
}

top_faster = (
    df.dropna(subset=["delta_time_s"])
      .sort_values("delta_time_s")
      .head(10)[["src","dst","time_s_2018","time_s_2025","delta_time_s"]]
)

top_slower = (
    df.dropna(subset=["delta_time_s"])
      .sort_values("delta_time_s", ascending=False)
      .head(10)[["src","dst","time_s_2018","time_s_2025","delta_time_s"]]
)

print("="*60)
print("SUMMARY STATISTICS")
print("="*60)
for key, value in summary.items():
    print(f"{key}: {value}")
print()

print("="*60)
print("TOP 10 FASTER ROUTES IN 2025 (negative delta = faster)")
print("="*60)
print(top_faster.to_string(index=False))
print()

print("="*60)
print("TOP 10 SLOWER ROUTES IN 2025 (positive delta = slower)")
print("="*60)
print(top_slower.to_string(index=False))
