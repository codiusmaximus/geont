"""Build the region hierarchy from GISCO NUTS and ONS boroughs."""

import geopandas as gpd
import pandas as pd

LEVELS = ["NUTS0", "NUTS1", "NUTS2", "NUTS3", "MUNI"]
LEVEL_BY_LENGTH = {2: "NUTS0", 3: "NUTS1", 4: "NUTS2", 5: "NUTS3"}


def parent_nuts_id(nuts_id: str) -> str | None:
    """Direct parent of a UK NUTS code. Each level adds one character."""
    if len(nuts_id) <= 2:
        return None
    return nuts_id[:-1]


def level_from_id(nuts_id: str) -> str:
    try:
        return LEVEL_BY_LENGTH[len(nuts_id)]
    except KeyError as exc:
        raise ValueError(f"not a UK NUTS code: {nuts_id}") from exc


def _name_column(frame: gpd.GeoDataFrame) -> str:
    for column in ("NAME_LATN", "NUTS_NAME", "NAME_ENGL", "NAME"):
        if column in frame.columns:
            return column
    raise KeyError(f"no name column in {list(frame.columns)}")


def load_nuts(raw_dir, config: dict) -> gpd.GeoDataFrame:
    year = config["study_area"]["nuts_year"]
    resolution = config["gisco"]["resolution"]
    nuts0 = config["study_area"]["nuts0"]
    nuts1 = config["study_area"]["nuts1"]
    frames = []
    for level in range(4):
        path = raw_dir / f"NUTS_RG_{resolution}_{year}_4326_LEVL_{level}.geojson"
        frame = gpd.read_file(path)
        frame.columns = [
            column if column.lower() == "geometry" else column.upper()
            for column in frame.columns
        ]
        frame = frame.set_geometry("geometry")
        frames.append(frame)
    nuts = pd.concat(frames, ignore_index=True)
    nuts = gpd.GeoDataFrame(nuts, geometry="geometry", crs=frames[0].crs)
    code = nuts["NUTS_ID"].astype(str)
    keep = (code == nuts0) | code.str.startswith(nuts1)
    nuts = nuts.loc[keep].copy()
    if nuts.empty:
        raise RuntimeError(f"no NUTS units for {nuts0} / {nuts1}")
    name_col = _name_column(nuts)
    nuts["region_id"] = nuts["NUTS_ID"].astype(str)
    nuts["name"] = nuts[name_col].astype(str)
    nuts["level"] = nuts["region_id"].map(level_from_id)
    nuts["parent_id"] = nuts["region_id"].map(parent_nuts_id)
    nuts = nuts[["region_id", "name", "level", "parent_id", "geometry"]]
    nuts = nuts.dissolve(by="region_id", aggfunc="first").reset_index()
    missing_parents = sorted(
        set(nuts["parent_id"].dropna()) - set(nuts["region_id"])
    )
    if missing_parents:
        raise RuntimeError(f"NUTS parents missing from the extract: {missing_parents}")
    return nuts


def load_boroughs(path) -> gpd.GeoDataFrame:
    boroughs = gpd.read_file(path)
    boroughs = boroughs.rename(columns={"LAD21CD": "region_id", "LAD21NM": "name"})
    boroughs["region_id"] = boroughs["region_id"].astype(str)
    boroughs["name"] = boroughs["name"].astype(str)
    boroughs["level"] = "MUNI"
    boroughs = boroughs[["region_id", "name", "level", "geometry"]]
    if boroughs.crs is None:
        boroughs = boroughs.set_crs(4326)
    return boroughs.to_crs(4326)


def assign_nuts3_parents(
    boroughs: gpd.GeoDataFrame,
    nuts3: gpd.GeoDataFrame,
    metric_crs: str,
    min_share: float,
) -> gpd.GeoDataFrame:
    """Parent each borough to the NUTS-3 polygon that covers most of its area."""
    munis = boroughs.to_crs(metric_crs).copy()
    parents = nuts3.to_crs(metric_crs)[["region_id", "geometry"]].rename(
        columns={"region_id": "nuts3_id"}
    ).copy()
    munis["geometry"] = munis.geometry.make_valid()
    parents["geometry"] = parents.geometry.make_valid()
    munis["muni_area"] = munis.geometry.area
    overlay = gpd.overlay(
        munis[["region_id", "muni_area", "geometry"]],
        parents,
        how="intersection",
        keep_geom_type=False,
    )
    if overlay.empty:
        raise RuntimeError("no borough intersects a NUTS-3 polygon")
    overlay["share"] = overlay.geometry.area / overlay["muni_area"]
    overlay = overlay.sort_values(["region_id", "share"], ascending=[True, False])
    best = overlay.drop_duplicates("region_id", keep="first").set_index("region_id")
    second = overlay[overlay.duplicated("region_id", keep="first")]
    second_share = second.groupby("region_id")["share"].max()
    missing = sorted(set(boroughs["region_id"]) - set(best.index))
    if missing:
        raise RuntimeError(f"boroughs with no NUTS-3 overlap: {missing}")
    problems = []
    for region_id, row in best.iterrows():
        runner_up = float(second_share.get(region_id, 0.0))
        ambiguous = row["share"] < 0.5 or runner_up >= row["share"] / 2 or runner_up > 0.2
        if ambiguous:
            problems.append(
                f"{region_id} share={row['share']:.3f} "
                f"second={runner_up:.3f} nuts3={row['nuts3_id']}"
            )
        elif row["share"] < min_share:
            print(
                f"  note: {region_id} coverage {row['share']:.3f} "
                f"is below {min_share} but the next NUTS-3 is only {runner_up:.3f}"
            )
    if problems:
        raise RuntimeError("ambiguous borough → NUTS-3 parent:\n" + "\n".join(problems))
    out = boroughs.copy()
    out["parent_id"] = out["region_id"].map(best["nuts3_id"])
    print("borough → NUTS-3")
    for region_id, row in best.sort_index().iterrows():
        name = boroughs.loc[boroughs["region_id"] == region_id, "name"].iloc[0]
        print(f"  {region_id} {name}: {row['nuts3_id']} ({row['share']:.3f})")
    return out


def build_regions(config: dict, raw_dir, borough_path) -> gpd.GeoDataFrame:
    nuts = load_nuts(raw_dir, config)
    boroughs = load_boroughs(borough_path)
    boroughs = assign_nuts3_parents(
        boroughs,
        nuts.loc[nuts["level"] == "NUTS3"],
        config["metric_crs"],
        config["truth"]["parent_min_share"],
    )
    regions = pd.concat([nuts, boroughs], ignore_index=True)
    regions = gpd.GeoDataFrame(regions, geometry="geometry", crs=nuts.crs)
    regions = regions.sort_values(["level", "region_id"]).reset_index(drop=True)
    return regions[["region_id", "name", "level", "parent_id", "geometry"]]
