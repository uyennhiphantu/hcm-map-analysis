import pandas as pd
import requests
import time
import numpy as np

BASE_2018 = "http://localhost:8004"
BASE_2025 = "http://localhost:8005"

BATCH_SIZE = 40  # Chia thành batch 40x40 = 1600 < 2500
TIMEOUT = 30

def call_matrix_batch(base_url, locations, batch_size=40):
    """Call matrix API in batches to avoid 2500 limit"""
    n = len(locations)
    all_results = []
    
    # Split into batches
    num_batches = (n + batch_size - 1) // batch_size
    
    print(f"  Total points: {n}, splitting into {num_batches}x{num_batches} = {num_batches**2} batches")
    
    for i in range(num_batches):
        src_start = i * batch_size
        src_end = min((i + 1) * batch_size, n)
        sources = locations[src_start:src_end]
        
        for j in range(num_batches):
            dst_start = j * batch_size
            dst_end = min((j + 1) * batch_size, n)
            targets = locations[dst_start:dst_end]
            
            print(f"  Batch [{i+1},{j+1}]: sources {src_start}-{src_end}, targets {dst_start}-{dst_end}")
            
            payload = {
                "sources": sources,
                "targets": targets,
                "costing": "auto"
            }
            
            try:
                resp = requests.post(
                    f"{base_url}/sources_to_targets",
                    json=payload,
                    timeout=TIMEOUT
                )
                resp.raise_for_status()
                data = resp.json()
                
                # Extract results with correct indices
                for src_idx, src_row in enumerate(data.get("sources_to_targets", [])):
                    for dst_idx, cell in enumerate(src_row):
                        global_src = src_start + src_idx
                        global_dst = dst_start + dst_idx
                        
                        all_results.append({
                            'src_idx': global_src,
                            'dst_idx': global_dst,
                            'time': cell.get('time'),
                            'distance': cell.get('distance')
                        })
                        
            except Exception as e:
                print(f"    ERROR in batch [{i+1},{j+1}]: {e}")
                # Fill with None for failed batch
                for si in range(len(sources)):
                    for di in range(len(targets)):
                        all_results.append({
                            'src_idx': src_start + si,
                            'dst_idx': dst_start + di,
                            'time': None,
                            'distance': None
                        })
            
            time.sleep(0.1)  # Small delay between batches
    
    return all_results

def main():
    # Read points
    print("Reading points...")
    points_df = pd.read_csv("points.csv")
    print(f"Loaded {len(points_df)} points")
    
    # Prepare locations
    locations = []
    for _, row in points_df.iterrows():
        locations.append({"lat": row["lat"], "lon": row["lon"]})
    
    # Call matrix for 2018
    print("\nCalling matrix 2018...")
    results_2018 = call_matrix_batch(BASE_2018, locations, BATCH_SIZE)
    
    # Call matrix for 2025
    print("\nCalling matrix 2025...")
    results_2025 = call_matrix_batch(BASE_2025, locations, BATCH_SIZE)
    
    # Convert to DataFrames
    print("\nProcessing results...")
    df_2018 = pd.DataFrame(results_2018)
    df_2025 = pd.DataFrame(results_2025)
    
    # Merge results
    df_merged = df_2018.merge(
        df_2025,
        on=['src_idx', 'dst_idx'],
        suffixes=('_2018', '_2025')
    )
    
    # Map back to point IDs
    df_merged['src'] = df_merged['src_idx'].apply(lambda x: points_df.iloc[x]['id'])
    df_merged['dst'] = df_merged['dst_idx'].apply(lambda x: points_df.iloc[x]['id'])
    
    # Calculate deltas
    df_merged['time_s_2018'] = df_merged['time_2018']
    df_merged['time_s_2025'] = df_merged['time_2025']
    df_merged['distance_km_2018'] = df_merged['distance_2018']
    df_merged['distance_km_2025'] = df_merged['distance_2025']
    
    df_merged['delta_time_s'] = df_merged['time_s_2025'] - df_merged['time_s_2018']
    df_merged['delta_distance_km'] = df_merged['distance_km_2025'] - df_merged['distance_km_2018']
    
    # Select final columns
    final_df = df_merged[[
        'src', 'dst',
        'time_s_2018', 'distance_km_2018',
        'time_s_2025', 'distance_km_2025',
        'delta_time_s', 'delta_distance_km'
    ]]
    
    # Save results
    print("\nSaving results...")
    final_df.to_csv('matrix_2018.csv', index=False)
    print("✅ matrix_2018.csv saved")
    
    final_df.to_csv('matrix_2025.csv', index=False)
    print("✅ matrix_2025.csv saved")
    
    final_df.to_csv('matrix_delta.csv', index=False)
    print("✅ matrix_delta.csv saved")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    null_2018 = final_df['time_s_2018'].isna().sum()
    null_2025 = final_df['time_s_2025'].isna().sum()
    print(f"Total OD pairs: {len(final_df)}")
    print(f"Null routes 2018: {null_2018} ({null_2018*100/len(final_df):.1f}%)")
    print(f"Null routes 2025: {null_2025} ({null_2025*100/len(final_df):.1f}%)")
    
    valid_df = final_df.dropna(subset=['delta_time_s', 'delta_distance_km'])
    if len(valid_df) > 0:
        print(f"\nAverage delta time: {valid_df['delta_time_s'].mean():.1f}s")
        print(f"Average delta distance: {valid_df['delta_distance_km'].mean():.3f}km")
        
        print("\nTop 10 faster in 2025:")
        print(valid_df.nsmallest(10, 'delta_time_s')[['src','dst','time_s_2018','time_s_2025','delta_time_s']])
        
        print("\nTop 10 shorter in 2025:")
        print(valid_df.nsmallest(10, 'delta_distance_km')[['src','dst','distance_km_2018','distance_km_2025','delta_distance_km']])

if __name__ == "__main__":
    main()
