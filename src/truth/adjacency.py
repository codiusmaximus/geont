"""Same-level adjacency from shared boundary length."""

import geopandas as gpd
import pandas as pd


def adjacent_pairs(regions: gpd.GeoDataFrame, min_length_m: float, metric_crs: str) -> pd.DataFrame:
    """One row per unordered pair whose shared boundary is longer than min_length_m.

    Corner contact has length 0 and is not adjacency. Pairs are stored once,
    with region_a < region_b. The symmetric triple is a reasoner rule.
    """
    metric = regions.to_crs(metric_crs)
    rows = list(metric.itertuples(index=False))
    records = []
    for i, left in enumerate(rows):
        for right in rows[i + 1 :]:
            if left.level != right.level:
                continue
            shared = left.geometry.boundary.intersection(right.geometry.boundary)
            length = float(shared.length)
            if length <= min_length_m:
                continue
            region_a, region_b = sorted((left.region_id, right.region_id))
            records.append(
                {
                    "region_a": region_a,
                    "region_b": region_b,
                    "level": left.level,
                    "shared_length_m": length,
                }
            )
    frame = pd.DataFrame(
        records,
        columns=["region_a", "region_b", "level", "shared_length_m"],
    )
    return frame.sort_values(["level", "region_a", "region_b"]).reset_index(drop=True)
