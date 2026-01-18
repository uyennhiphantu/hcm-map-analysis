import pandas as pd
import folium
from folium import plugins
import numpy as np

# Read data
print("Loading data...")
points_df = pd.read_csv("points.csv")
delta_df = pd.read_csv("matrix_delta.csv")

print(f"Points: {len(points_df)}")
print(f"OD pairs: {len(delta_df)}")

# Merge with point coordinates
delta_df = delta_df.merge(
    points_df[['id', 'lat', 'lon']],
    left_on='src',
    right_on='id',
    how='left'
).rename(columns={'lat': 'src_lat', 'lon': 'src_lon'})

delta_df = delta_df.merge(
    points_df[['id', 'lat', 'lon']],
    left_on='dst',
    right_on='id',
    how='left'
).rename(columns={'lat': 'dst_lat', 'lon': 'dst_lon'})

# Clean data
delta_df = delta_df.dropna(subset=['src_lat', 'src_lon', 'dst_lat', 'dst_lon', 'delta_time_s'])

print(f"Valid OD pairs: {len(delta_df)}")

# Calculate center of map
center_lat = points_df['lat'].mean()
center_lon = points_df['lon'].mean()

# MAP 1: HEAT MAP OF IMPROVEMENTS
print("\n[1/4] Creating improvement heat map...")

m1 = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=11,
    tiles='OpenStreetMap'
)

improvements = delta_df[delta_df['delta_time_s'] < -100].copy()
improvements['weight'] = abs(improvements['delta_time_s'])

heat_data_improvements = []
for _, row in improvements.iterrows():
    heat_data_improvements.append([row['src_lat'], row['src_lon'], row['weight']/100])
    heat_data_improvements.append([row['dst_lat'], row['dst_lon'], row['weight']/100])

if heat_data_improvements:
    plugins.HeatMap(
        heat_data_improvements,
        min_opacity=0.3,
        max_zoom=13,
        radius=15,
        blur=20,
        gradient={0.4: 'blue', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'}
    ).add_to(m1)

for _, point in points_df.iterrows():
    folium.CircleMarker(
        location=[point['lat'], point['lon']],
        radius=3,
        color='black',
        fill=True,
        fillOpacity=0.6,
        popup=f"Point {point['id']}"
    ).add_to(m1)

m1.save('heatmap_improvements.html')
print("✅ Saved: heatmap_improvements.html")

# MAP 2: HEAT MAP OF DEGRADATIONS
print("\n[2/4] Creating degradation heat map...")

m2 = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=11,
    tiles='OpenStreetMap'
)

degradations = delta_df[delta_df['delta_time_s'] > 100].copy()
degradations['weight'] = degradations['delta_time_s']

heat_data_degradations = []
for _, row in degradations.iterrows():
    heat_data_degradations.append([row['src_lat'], row['src_lon'], row['weight']/100])
    heat_data_degradations.append([row['dst_lat'], row['dst_lon'], row['weight']/100])

if heat_data_degradations:
    plugins.HeatMap(
        heat_data_degradations,
        min_opacity=0.3,
        max_zoom=13,
        radius=15,
        blur=20,
        gradient={0.4: 'blue', 0.6: 'purple', 0.8: 'red', 1.0: 'darkred'}
    ).add_to(m2)

for _, point in points_df.iterrows():
    folium.CircleMarker(
        location=[point['lat'], point['lon']],
        radius=3,
        color='black',
        fill=True,
        fillOpacity=0.6,
        popup=f"Point {point['id']}"
    ).add_to(m2)

m2.save('heatmap_degradations.html')
print("✅ Saved: heatmap_degradations.html")

# MAP 3: ALL SIGNIFICANT ROUTES
print("\n[3/4] Creating all significant routes map...")

m3 = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=11,
    tiles='OpenStreetMap'
)

significant = delta_df[abs(delta_df['delta_time_s']) > 200].copy()
print(f"  Significant routes: {len(significant)}")

sig_improve = significant[significant['delta_time_s'] < 0]
sig_degrade = significant[significant['delta_time_s'] > 0]

improve_group = folium.FeatureGroup(name=f'Improvements ({len(sig_improve)} routes)')
for _, row in sig_improve.iterrows():
    folium.PolyLine(
        locations=[[row['src_lat'], row['src_lon']], [row['dst_lat'], row['dst_lon']]],
        color='green',
        weight=2,
        opacity=0.4,
        popup=f"Src: {row['src']} to Dst: {row['dst']}, Faster: {abs(row['delta_time_s']):.0f}s"
    ).add_to(improve_group)
improve_group.add_to(m3)

degrade_group = folium.FeatureGroup(name=f'Degradations ({len(sig_degrade)} routes)')
for _, row in sig_degrade.iterrows():
    folium.PolyLine(
        locations=[[row['src_lat'], row['src_lon']], [row['dst_lat'], row['dst_lon']]],
        color='red',
        weight=2,
        opacity=0.4,
        popup=f"Src: {row['src']} to Dst: {row['dst']}, Slower: {row['delta_time_s']:.0f}s"
    ).add_to(degrade_group)
degrade_group.add_to(m3)

points_group = folium.FeatureGroup(name='All points')
for _, point in points_df.iterrows():
    folium.CircleMarker(
        location=[point['lat'], point['lon']],
        radius=4,
        color='blue',
        fill=True,
        fillOpacity=0.7,
        popup=f"Point {point['id']}"
    ).add_to(points_group)
points_group.add_to(m3)

folium.LayerControl().add_to(m3)
m3.save('map_significant_routes.html')
print("✅ Saved: map_significant_routes.html")

print("\n✅ Done! Open the HTML files to view the maps.")
