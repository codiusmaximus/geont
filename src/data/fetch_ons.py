"""Download ONS December 2021 local-authority polygons for London boroughs."""

import json
import urllib.parse
import urllib.request
from pathlib import Path

from src.settings import ROOT, load_config

SERVICE = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Local_Authority_Districts_December_2021_UK_BGC_2022/FeatureServer/0/query"
)


def fetch_boroughs(code_prefix: str, dest: Path) -> dict:
    features = []
    offset = 0
    while True:
        params = {
            "where": f"LAD21CD LIKE '{code_prefix}%'",
            "outFields": "LAD21CD,LAD21NM",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": 200,
        }
        url = SERVICE + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": "geont-bench/0.1"})
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.load(response)
        if "error" in payload:
            raise RuntimeError(payload["error"])
        batch = payload.get("features", [])
        features.extend(batch)
        if not payload.get("exceededTransferLimit") or not batch:
            break
        offset += len(batch)
    collection = {"type": "FeatureCollection", "features": features}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(collection), encoding="utf-8")
    codes = sorted(feat["properties"]["LAD21CD"] for feat in features)
    return {"count": len(features), "codes": codes, "path": str(dest)}


def main() -> None:
    config = load_config()
    prefix = config["ons_lad"]["code_prefix"]
    dest = ROOT / "data" / "raw" / "ons" / "london_boroughs_2021.geojson"
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip {dest}")
        return
    summary = fetch_boroughs(prefix, dest)
    print(f"boroughs: {summary['count']}")
    print(" ".join(summary["codes"]))
    if prefix == "E09" and summary["count"] != 33:
        raise SystemExit(f"expected 33 London boroughs, got {summary['count']}")


if __name__ == "__main__":
    main()
