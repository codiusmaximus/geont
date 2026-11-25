"""Unit tests for hierarchy helpers, adjacency, sampling and validation."""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, box

from src.data.fetch_gisco import diagnose_lau
from src.settings import load_category_map, subcategory_parents
from src.truth.adjacency import adjacent_pairs
from src.truth.facts import build_facts
from src.truth.hierarchy import level_from_id, parent_nuts_id
from src.truth.locate_places import (
    apply_name_rules,
    border_distances,
    match_municipalities,
    stratified_sample,
)
from src.truth.validate import validate


def test_nuts_parent_codes():
    assert parent_nuts_id("UK") is None
    assert parent_nuts_id("UKI") == "UK"
    assert parent_nuts_id("UKI3") == "UKI"
    assert parent_nuts_id("UKI31") == "UKI3"
    assert level_from_id("UKI31") == "NUTS3"
    assert level_from_id("UK") == "NUTS0"


def test_category_map_covers_the_hierarchy():
    category_map = load_category_map()
    parents = subcategory_parents(category_map)
    assert set(parents) == {
        "Supermarket",
        "ConvenienceStore",
        "TrainStation",
        "PetrolStation",
        "PostOffice",
        "ParcelShop",
        "ParcelLocker",
        "Hospital",
        "Clinic",
        "Pharmacy",
        "School",
        "University",
    }
    assert set(category_map["map"].values()) <= set(parents)
    for entry in category_map["borderline"].values():
        assert entry["official"] == "excluded"


def test_adjacency_ignores_corner_contact():
    frame = gpd.GeoDataFrame(
        {
            "region_id": ["A", "B", "C"],
            "level": ["MUNI", "MUNI", "MUNI"],
            "geometry": [
                box(0, 0, 100, 100),
                box(100, 0, 200, 100),
                box(100, 100, 200, 200),
            ],
        },
        crs="EPSG:27700",
    )
    pairs = adjacent_pairs(frame, min_length_m=10, metric_crs="EPSG:27700")
    found = set(zip(pairs["region_a"], pairs["region_b"]))
    # A shares an edge with B. A meets C only at a corner. B shares an edge with C.
    assert found == {("A", "B"), ("B", "C")}


def test_point_inside_one_municipality_and_border_distance():
    munis = gpd.GeoDataFrame(
        {"region_id": ["M1", "M2"], "geometry": [box(0, 0, 1000, 1000), box(2000, 0, 3000, 1000)]},
        crs="EPSG:27700",
    )
    points = gpd.GeoDataFrame(
        {
            "overture_id": ["inside", "edge", "overlap"],
            "geometry": [Point(500, 500), Point(10, 500), Point(5000, 500)],
        },
        crs="EPSG:27700",
    )
    matched = match_municipalities(points, munis, "EPSG:27700")
    distances = border_distances(points, munis, matched, "EPSG:27700")
    assert list(matched.iloc[:2]) == ["M1", "M1"]
    assert pd.isna(matched.iloc[2])
    assert distances.iloc[0] == 500
    assert distances.iloc[1] == 10
    assert pd.isna(distances.iloc[2])


def test_name_rules_keep_a_hospital_and_drop_a_surgery():
    category_map = load_category_map()
    frame = pd.DataFrame(
        {
            "name": ["Guy's Hospital", "Havergal Surgery", "Tesco Extra", "Tesco Express"],
            "source_category": ["hospital", "hospital", "grocery_store", "grocery_store"],
            "subcategory": ["Hospital", "Hospital", "Supermarket", "Supermarket"],
        }
    )
    kept = apply_name_rules(frame, category_map)
    assert list(kept["name"]) == ["Guy's Hospital", "Tesco Extra"]


def test_stratified_sample_is_deterministic_and_fills_shortfall():
    frame = pd.DataFrame(
        {
            "overture_id": [f"o{i:02d}" for i in range(12)],
            "subcategory": ["Hospital"] * 2 + ["School"] * 10,
        }
    )
    first = stratified_sample(frame, sample_size=6, seed=42)
    second = stratified_sample(frame, sample_size=6, seed=42)
    assert first["overture_id"].tolist() == second["overture_id"].tolist()
    assert len(first) == 6
    assert (first["subcategory"] == "Hospital").sum() == 2
    assert (first["subcategory"] == "School").sum() == 4


def _mini():
    regions = pd.DataFrame(
        [
            {"region_id": "UK", "name": "United Kingdom", "level": "NUTS0", "parent_id": None},
            {"region_id": "UKI", "name": "London", "level": "NUTS1", "parent_id": "UK"},
            {"region_id": "UKI3", "name": "Inner London - West", "level": "NUTS2", "parent_id": "UKI"},
            {"region_id": "UKI31", "name": "Camden and City of London", "level": "NUTS3", "parent_id": "UKI3"},
            {"region_id": "E09000001", "name": "City of London", "level": "MUNI", "parent_id": "UKI31"},
            {"region_id": "E09000007", "name": "Camden", "level": "MUNI", "parent_id": "UKI31"},
        ]
    )
    places = pd.DataFrame(
        [
            {
                "place_id": "P0001",
                "name": "A Hospital",
                "subcategory": "Hospital",
                "source_category": "hospital",
                "muni_id": "E09000001",
            },
            {
                "place_id": "P0002",
                "name": "A School",
                "subcategory": "School",
                "source_category": "school",
                "muni_id": "E09000007",
            },
        ]
    )
    adjacency = pd.DataFrame(
        [{"region_a": "E09000001", "region_b": "E09000007", "level": "MUNI"}]
    )
    parents = {"Hospital": "Healthcare", "School": "Education"}
    facts = build_facts(regions, places, parents, adjacency)
    return regions, places, adjacency, facts, parents


def test_validation_passes_on_direct_links():
    regions, places, adjacency, facts, parents = _mini()
    ok, errors, summary = validate(regions, places, adjacency, facts, parents)
    assert ok, summary
    assert "Places: 2" in summary
    assert "Hospital: 1" in summary


def test_validation_rejects_a_place_outside_its_municipality():
    regions, places, adjacency, facts, parents = _mini()
    places = places.copy()
    places.loc[places["place_id"] == "P0001", "muni_id"] = "UKI"
    ok, errors, _summary = validate(regions, places, adjacency, facts, parents)
    assert not ok
    assert errors


def test_lau_diagnostic_reports_no_uk_units(tmp_path):
    csv_path = tmp_path / "lau.csv"
    csv_path.write_text(
        "GISCO_ID,CNTR_CODE,LAU_ID,LAU_NAME\n"
        "FR_1,FR,1,Paris\n"
        "DE_2,DE,2,Berlin\n",
        encoding="utf-8",
    )
    report = diagnose_lau(csv_path, "UKI")
    assert report["uk_or_gb_units"] == 0
    assert report["study_area_units"] == 0
    assert "no UK" in report["naming_pattern"]
