"""Write the static GeoJSON the explore map fetches.

Run from the repo root: python explore/export.py
"""

import json
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "data"


def _round_coords(node, digits: int = 5) -> None:
    if isinstance(node, dict):
        for value in node.values():
            _round_coords(value, digits)
    elif isinstance(node, list):
        if node and all(isinstance(item, (int, float)) for item in node):
            for index, item in enumerate(node):
                node[index] = round(float(item), digits)
        else:
            for item in node:
                _round_coords(item, digits)


def _write(frame: gpd.GeoDataFrame, path: Path) -> None:
    payload = json.loads(frame.to_json(drop_id=True))
    _round_coords(payload)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"{path.name}: {len(frame)} features, {path.stat().st_size} bytes")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    regions = gpd.read_parquet(ROOT / "data" / "processed" / "regions.parquet")
    regions = regions.loc[regions["level"] != "NUTS0"].copy()
    metric = regions.to_crs("EPSG:27700")
    metric["geometry"] = metric.geometry.simplify(40).make_valid()
    _write(
        metric.to_crs(4326)[["region_id", "name", "level", "parent_id", "geometry"]],
        OUT / "regions.geojson",
    )

    places = gpd.read_parquet(ROOT / "data" / "processed" / "places.parquet")
    _write(
        places[["place_id", "name", "subcategory", "muni_id", "geometry"]].to_crs(4326),
        OUT / "places.geojson",
    )


if __name__ == "__main__":
    main()
