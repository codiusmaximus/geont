"""Build processed regions, places, adjacency and facts, then validate."""

import sys

import geopandas as gpd
import pandas as pd

from src.settings import ROOT, load_category_map, load_config, subcategory_parents
from src.truth.adjacency import adjacent_pairs
from src.truth.facts import build_facts
from src.truth.hierarchy import build_regions
from src.truth.locate_places import assign_place_ids, locate_candidates, stratified_sample
from src.truth.validate import validate


def _write_places(frame: gpd.GeoDataFrame, path) -> None:
    columns = [
        "place_id",
        "name",
        "subcategory",
        "source_category",
        "muni_id",
        "lon",
        "lat",
        "border_dist_m",
        "overture_id",
        "geometry",
    ]
    out = frame.copy()
    if out.crs is None or out.crs.to_epsg() != 4326:
        out = out.to_crs(4326)
    out["lon"] = out.geometry.x
    out["lat"] = out.geometry.y
    out[columns].to_parquet(path, index=False)


def main() -> None:
    config = load_config()
    if config["municipality_source"] != "ons_lad":
        raise SystemExit(
            "municipality_source is not ons_lad. GISCO LAU 2021 has no UK units; "
            "see docs/decisions.md."
        )
    category_map = load_category_map()
    parents = subcategory_parents(category_map)
    raw = ROOT / "data" / "raw"
    regions = build_regions(
        config,
        raw / "gisco",
        raw / "ons" / "london_boroughs_2021.geojson",
    )
    raw_places = pd.read_parquet(raw / "overture" / "places_london.parquet")
    print(f"raw overture rows: {len(raw_places)}")
    candidates, borderline = locate_candidates(raw_places, regions, config, category_map)
    sampled = stratified_sample(
        candidates,
        config["places"]["sample_size"],
        config["seed"],
    )
    places = assign_place_ids(sampled)
    print(f"sampled places: {len(places)} (target {config['places']['sample_size']})")
    if places.empty:
        raise SystemExit("no places left after the border filter and sample")
    adjacency = adjacent_pairs(
        regions,
        config["truth"]["adjacency_min_length_m"],
        config["metric_crs"],
    )
    facts = build_facts(regions, places, parents, adjacency)
    processed = ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    regions.to_parquet(processed / "regions.parquet", index=False)
    _write_places(places, processed / "places.parquet")
    adjacency.to_parquet(processed / "adjacency.parquet", index=False)
    facts.to_parquet(processed / "facts.parquet", index=False)
    border_cols = [
        "name",
        "source_category",
        "official",
        "note",
        "muni_id",
        "lon",
        "lat",
        "overture_id",
    ]
    if len(borderline):
        border_out = borderline.to_crs(4326) if borderline.crs.to_epsg() != 4326 else borderline
        border_out = border_out.copy()
        border_out["lon"] = border_out.geometry.x
        border_out["lat"] = border_out.geometry.y
        border_out[border_cols].to_parquet(processed / "borderline.parquet", index=False)
    else:
        pd.DataFrame(columns=border_cols).to_parquet(processed / "borderline.parquet", index=False)

    ok, _errors, summary = validate(regions, places, adjacency, facts, parents)
    report_path = processed / "validation_report.txt"
    report_path.write_text(summary + "\n", encoding="utf-8")
    print(summary)
    print(f"wrote {report_path}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
