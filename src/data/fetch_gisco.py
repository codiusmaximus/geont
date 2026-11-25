"""Download GISCO NUTS 2021 and diagnose LAU coverage of the study area.

GISCO LAU 2021 is an EU/EFTA table. This script counts countries from the
attribute CSV and records whether any UK unit exists to map into the study
area. It does not download LAU polygons when the attribute table already
shows that the UK is absent.
"""

import json

import pandas as pd

from src.data.download import download
from src.settings import ROOT, load_config

GISCO = "https://gisco-services.ec.europa.eu/distribution/v2"


def nuts_url(resolution: str, year: int, level: int) -> str:
    return (
        f"{GISCO}/nuts/geojson/"
        f"NUTS_RG_{resolution}_{year}_4326_LEVL_{level}.geojson"
    )


def lau_csv_url(resolution: str, year: int) -> str:
    return f"{GISCO}/lau/csv/LAU_RG_{resolution}_{year}_4326.csv"


def diagnose_lau(csv_path, nuts1: str) -> dict:
    table = pd.read_csv(csv_path, dtype=str)
    codes = table["CNTR_CODE"].fillna("")
    counts = codes.value_counts().sort_index()
    uk = int(counts.get("UK", 0) + counts.get("GB", 0))
    # LAU_ID is the national code. With no UK rows there is nothing to describe
    # inside the study area, and no LAU → NUTS-3 correspondence to score.
    report = {
        "source": str(csv_path.name),
        "lau_units_total": int(len(table)),
        "countries": {code: int(n) for code, n in counts.items()},
        "uk_or_gb_units": uk,
        "study_area_nuts1": nuts1,
        "study_area_units": 0 if uk == 0 else None,
        "naming_pattern": (
            "no UK LAU units in this GISCO LAU release"
            if uk == 0
            else "UK units present; inspect LAU_ID / LAU_NAME"
        ),
        "nuts3_mapping": (
            "unavailable: the release has no UK units, so none fall in "
            f"{nuts1} and none can be matched to NUTS-3"
            if uk == 0
            else "not assessed"
        ),
        "polygons_downloaded": False,
    }
    return report


def main() -> None:
    config = load_config()
    gisco = config["gisco"]
    year = config["study_area"]["nuts_year"]
    raw = ROOT / "data" / "raw" / "gisco"
    for level in range(4):
        url = nuts_url(gisco["resolution"], year, level)
        download(url, raw / f"NUTS_RG_{gisco['resolution']}_{year}_4326_LEVL_{level}.geojson")
    lau_path = raw / f"LAU_RG_{gisco['resolution']}_{year}_4326.csv"
    download(lau_csv_url(gisco["resolution"], year), lau_path)
    report = diagnose_lau(lau_path, config["study_area"]["nuts1"])
    out = raw / "lau_diagnostic.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "countries"}, indent=2))
    print(f"countries: {len(report['countries'])}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
