"""Point-in-polygon location, border distance, and the stratified sample."""

import random

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


def apply_name_rules(frame: pd.DataFrame, category_map: dict) -> pd.DataFrame:
    """Drop mapped places whose names fail the hand review in the category map."""
    if frame.empty:
        return frame
    keep = pd.Series(True, index=frame.index)
    for column, rules, require in (
        ("source_category", category_map.get("name_include") or {}, True),
        ("subcategory", category_map.get("subcategory_include") or {}, True),
        ("source_category", category_map.get("name_exclude") or {}, False),
        ("subcategory", category_map.get("subcategory_exclude") or {}, False),
    ):
        for key, pattern in rules.items():
            selected = frame[column].eq(key)
            matched = frame["name"].str.contains(pattern, regex=True, na=False)
            keep &= (~selected | matched) if require else ~(selected & matched)
    return frame.loc[keep].copy()


def match_municipalities(
    points: gpd.GeoDataFrame,
    munis: gpd.GeoDataFrame,
    metric_crs: str,
) -> pd.Series:
    """Municipality id for each point, or NA unless the point is inside exactly one."""
    pts = points.to_crs(metric_crs).reset_index(drop=True)
    pts["_pid"] = pts.index
    polys = munis.to_crs(metric_crs)
    joined = gpd.sjoin(
        pts[["_pid", "geometry"]],
        polys[["region_id", "geometry"]],
        how="left",
        predicate="within",
    )
    chosen = {}
    for pid, group in joined.groupby("_pid", sort=True):
        ids = [value for value in group["region_id"].dropna().unique()]
        chosen[int(pid)] = ids[0] if len(ids) == 1 else pd.NA
    return pd.Series(chosen).sort_index()


def border_distances(
    points: gpd.GeoDataFrame,
    munis: gpd.GeoDataFrame,
    muni_ids: pd.Series,
    metric_crs: str,
) -> pd.Series:
    pts = points.to_crs(metric_crs).reset_index(drop=True)
    boundaries = munis.to_crs(metric_crs).set_index("region_id").geometry.boundary
    distances = []
    for pid, muni_id in muni_ids.items():
        if pd.isna(muni_id):
            distances.append(pd.NA)
            continue
        distances.append(float(pts.geometry.iloc[pid].distance(boundaries.loc[muni_id])))
    return pd.Series(distances, index=muni_ids.index)


def dedupe_places(frame: gpd.GeoDataFrame, distance_m: float, metric_crs: str) -> gpd.GeoDataFrame:
    """Keep the highest-confidence copy when the same name sits on top of itself."""
    if frame.empty:
        return frame
    projected = frame.to_crs(metric_crs)
    drop = set()
    grouped = projected.groupby(
        [projected["subcategory"], projected["name"].str.casefold()],
        sort=False,
        dropna=False,
    )
    for _, group in grouped:
        order = group.sort_values(["confidence", "overture_id"], ascending=[False, True])
        kept_geom = []
        for idx, row in order.iterrows():
            if any(row.geometry.distance(other) <= distance_m for other in kept_geom):
                drop.add(idx)
            else:
                kept_geom.append(row.geometry)
    return frame.drop(index=list(drop))


def stratified_sample(frame: pd.DataFrame, sample_size: int, seed: int) -> pd.DataFrame:
    """Take a deterministic stratified sample. Short categories keep every row."""
    if frame.empty:
        return frame
    rng = random.Random(seed)
    groups = {
        category: group.sort_values("overture_id")
        for category, group in frame.groupby("subcategory", sort=True)
    }
    categories = list(groups)
    base = sample_size // len(categories)
    targets = {category: min(len(groups[category]), base) for category in categories}
    shortfall = sample_size - sum(targets.values())
    spare = sorted(
        categories,
        key=lambda category: (-(len(groups[category]) - targets[category]), category),
    )
    for category in spare:
        if shortfall <= 0:
            break
        room = len(groups[category]) - targets[category]
        take = min(room, shortfall)
        targets[category] += take
        shortfall -= take
    picked = []
    for category in categories:
        pool = list(groups[category].index)
        n = targets[category]
        picked.extend(pool if n >= len(pool) else rng.sample(pool, n))
    return frame.loc[picked].copy()


def assign_place_ids(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values("overture_id").copy()
    ordered["place_id"] = [f"P{i:04d}" for i in range(1, len(ordered) + 1)]
    return ordered


def _as_points(table: pd.DataFrame) -> gpd.GeoDataFrame:
    geometry = [Point(lon, lat) for lon, lat in zip(table["lon"], table["lat"])]
    return gpd.GeoDataFrame(table, geometry=geometry, crs="EPSG:4326")


def locate_candidates(raw_places: pd.DataFrame, regions: gpd.GeoDataFrame, config: dict, category_map: dict):
    """Return (kept candidates, borderline places), both still unsampled."""
    munis = regions.loc[regions["level"] == "MUNI", ["region_id", "geometry"]].copy()
    metric = config["metric_crs"]
    buffer_m = config["places"]["border_buffer_m"]
    mapped = raw_places.copy()
    mapped["subcategory"] = mapped["source_category"].map(category_map["map"])
    main = apply_name_rules(mapped.loc[mapped["subcategory"].notna()].copy(), category_map)
    border_keys = category_map["borderline"]
    borderline = mapped.loc[mapped["source_category"].isin(border_keys)].copy()

    def _spatially_filter(table: pd.DataFrame) -> gpd.GeoDataFrame:
        if table.empty:
            return _as_points(table.iloc[0:0])
        points = _as_points(table.reset_index(drop=True))
        muni_ids = match_municipalities(points, munis, metric)
        distances = border_distances(points, munis, muni_ids, metric)
        points["muni_id"] = muni_ids.to_numpy()
        points["border_dist_m"] = distances.to_numpy()
        keep = points["muni_id"].notna() & points["border_dist_m"].ge(buffer_m).fillna(False)
        kept = points.loc[keep].copy()
        return dedupe_places(kept, config["places"]["dedupe_distance_m"], metric)

    candidates = _spatially_filter(main)
    border_points = _spatially_filter(borderline)
    if not border_points.empty:
        notes = category_map["borderline"]
        border_points["official"] = border_points["source_category"].map(
            lambda key: notes[key]["official"]
        )
        border_points["note"] = border_points["source_category"].map(
            lambda key: notes[key]["note"]
        )
    print(f"candidates after border filter: {len(candidates)}")
    print(candidates["subcategory"].value_counts().sort_index().to_string())
    print(f"borderline places kept: {len(border_points)}")
    return candidates, border_points
