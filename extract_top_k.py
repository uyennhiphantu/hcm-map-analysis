#!/usr/bin/env python3
"""
Extract top k routes with the largest difference in a specified metric,
and include the return route for each item.
"""

import argparse
import pandas as pd
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract top k routes with largest metric differences, including return routes."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="matrix_delta.csv",
        help="Input CSV file (default: matrix_delta.csv)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="top_k_routes.csv",
        help="Output CSV file (default: top_k_routes.csv)",
    )
    parser.add_argument(
        "--metric",
        type=str,
        choices=["delta_distance_km", "delta_time_s"],
        required=True,
        help="Metric to sort by (delta_distance_km or delta_time_s)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of top routes to extract (default: 10)",
    )
    parser.add_argument(
        "--ascending",
        action="store_true",
        help="Sort in ascending order (default: descending by absolute value)",
    )
    parser.add_argument(
        "--by-absolute",
        action="store_true",
        default=True,
        help="Sort by absolute value of the metric (default: True)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Read input CSV
    try:
        df = pd.read_csv(args.input)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    # Validate required columns
    required_cols = ["src", "dst", args.metric]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns in input file: {missing_cols}", file=sys.stderr)
        sys.exit(1)

    # Drop rows with NaN in the metric column
    df_valid = df.dropna(subset=[args.metric]).copy()

    # Sort by the metric
    if args.by_absolute:
        df_valid["_abs_metric"] = df_valid[args.metric].abs()
        df_sorted = df_valid.sort_values("_abs_metric", ascending=args.ascending)
        df_sorted = df_sorted.drop(columns=["_abs_metric"])
    else:
        df_sorted = df_valid.sort_values(args.metric, ascending=args.ascending)

    # Get top k routes
    top_k = df_sorted.head(args.top_k).copy()

    # Create a lookup dictionary for finding return routes
    # Key: (src, dst), Value: row data
    route_lookup = {(row["src"], row["dst"]): row for _, row in df.iterrows()}

    # Build result with original routes and their return routes
    result_rows = []
    for _, row in top_k.iterrows():
        src, dst = row["src"], row["dst"]

        # Add original route
        original_row = row.to_dict()
        original_row["route_type"] = "original"
        result_rows.append(original_row)

        # Find and add return route (dst -> src)
        return_key = (dst, src)
        if return_key in route_lookup:
            return_row = route_lookup[return_key].to_dict()
            return_row["route_type"] = "return"
            result_rows.append(return_row)
        else:
            # Return route not found, add a placeholder
            return_row = {col: None for col in df.columns}
            return_row["src"] = dst
            return_row["dst"] = src
            return_row["route_type"] = "return (not found)"
            result_rows.append(return_row)

    # Create result dataframe
    result_df = pd.DataFrame(result_rows)

    # Reorder columns to have route_type first, then src, dst, then the rest
    cols = ["route_type", "src", "dst"] + [
        c for c in result_df.columns if c not in ["route_type", "src", "dst"]
    ]
    result_df = result_df[cols]

    # Save to output file
    result_df.to_csv(args.output, index=False)
    print(f"Extracted {args.top_k} routes (with return routes) to '{args.output}'")
    print(f"Total rows in output: {len(result_df)}")

    # Print summary
    print(f"\nTop {args.top_k} routes by {args.metric}:")
    print("-" * 60)
    for i, (_, row) in enumerate(top_k.iterrows(), 1):
        print(f"{i}. src={row['src']:.0f} -> dst={row['dst']:.0f}: {args.metric}={row[args.metric]:.4f}")


if __name__ == "__main__":
    main()
