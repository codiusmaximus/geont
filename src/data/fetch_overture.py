"""Query one pinned Overture places release for the study-area bbox."""

import re

import duckdb
import geopandas as gpd

from src.settings import ROOT, load_category_map, load_config


def _idents(values: list[str]) -> str:
    for value in values:
        if not re.fullmatch(r"[a-z0-9_]+", value):
            raise ValueError(f"unsafe category id: {value}")
    return ", ".join(f"'{value}'" for value in values)


def study_bbox(config: dict) -> tuple[float, float, float, float]:
    boroughs = ROOT / "data" / "raw" / "ons" / "london_boroughs_2021.geojson"
    if boroughs.exists():
        frame = gpd.read_file(boroughs)
        minx, miny, maxx, maxy = frame.total_bounds
        pad = 0.01
        return (minx - pad, miny - pad, maxx + pad, maxy + pad)
    west, south, east, north = config["study_area"]["bbox"]
    return (west, south, east, north)


def query_places(config: dict, categories: list[str], bbox, dest) -> None:
    release = config["overture_release"]
    west, south, east, north = bbox
    min_confidence = config["places"]["min_confidence"]
    source = (
        f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region = 'us-west-2';")
    sql = f"""
        COPY (
            SELECT
                id AS overture_id,
                names.primary AS name,
                taxonomy.primary AS source_category,
                confidence,
                operating_status,
                ST_X(geometry) AS lon,
                ST_Y(geometry) AS lat
            FROM read_parquet('{source}', filename=true, hive_partitioning=true)
            WHERE bbox.xmin BETWEEN {west} AND {east}
              AND bbox.ymin BETWEEN {south} AND {north}
              AND taxonomy.primary IN ({_idents(categories)})
              AND confidence >= {float(min_confidence)}
              AND (operating_status IS NULL OR operating_status = 'open')
              AND names.primary IS NOT NULL
        ) TO '{dest}' (FORMAT parquet)
    """
    print(f"query {source}")
    print(f"bbox west={west:.4f} south={south:.4f} east={east:.4f} north={north:.4f}")
    con.execute(sql)
    count = con.execute(f"SELECT count(*) FROM read_parquet('{dest}')").fetchone()[0]
    print(f"saved {dest} ({count} places)")


def main() -> None:
    config = load_config()
    category_map = load_category_map()
    categories = sorted(set(category_map["map"]) | set(category_map["borderline"]))
    dest = ROOT / "data" / "raw" / "overture" / "places_london.parquet"
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip {dest}")
        return
    query_places(config, categories, study_bbox(config), dest)


if __name__ == "__main__":
    main()
