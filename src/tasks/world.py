"""Load processed ground truth for task generation."""

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd

from src.settings import ROOT, load_category_map, subcategory_parents

LEVELS = ["NUTS0", "NUTS1", "NUTS2", "NUTS3", "MUNI"]


@dataclass
class World:
    places: list[dict]
    regions: list[dict]
    levels: dict[str, str]
    parents: dict[str, str | None]
    names: dict[str, str]
    direct_facts: list[tuple[str, str, str]]
    ontology_facts: list[tuple[str, str, str]]
    entities: dict[str, dict]


def _clean_parent(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def load_world() -> World:
    regions_frame = gpd.read_parquet(ROOT / "data" / "processed" / "regions.parquet")
    places_frame = gpd.read_parquet(ROOT / "data" / "processed" / "places.parquet")
    facts_frame = pd.read_parquet(ROOT / "data" / "processed" / "facts.parquet")
    regions = [
        {
            "region_id": str(row.region_id),
            "name": str(row.name),
            "level": str(row.level),
            "parent_id": _clean_parent(row.parent_id),
        }
        for row in regions_frame.itertuples(index=False)
    ]
    places = [
        {
            "place_id": str(row.place_id),
            "name": str(row.name),
            "subcategory": str(row.subcategory),
            "muni_id": str(row.muni_id),
        }
        for row in places_frame.itertuples(index=False)
    ]
    triples = [(str(row.s), str(row.p), str(row.o)) for row in facts_frame.itertuples(index=False)]
    ontology = [triple for triple in triples if triple[1] == "subclass_of"]
    direct = [triple for triple in triples if triple[1] != "subclass_of"]
    names = {place["place_id"]: place["name"] for place in places}
    names.update({region["region_id"]: region["name"] for region in regions})
    entities = {}
    for index, place in enumerate(sorted(places, key=lambda item: item["place_id"]), start=1):
        entities[place["place_id"]] = {"name": place["name"], "anon": f"F{index:03d}", "kind": "place"}
    ordered_regions = sorted(regions, key=lambda item: (LEVELS.index(item["level"]), item["region_id"]))
    for index, region in enumerate(ordered_regions, start=1):
        entities[region["region_id"]] = {"name": region["name"], "anon": f"U{index:03d}", "kind": "region"}
    return World(
        places=places,
        regions=regions,
        levels={region["region_id"]: region["level"] for region in regions},
        parents={region["region_id"]: region["parent_id"] for region in regions},
        names=names,
        direct_facts=direct,
        ontology_facts=ontology,
        entities=entities,
    )


def category_of(subcategory: str) -> str:
    return subcategory_parents(load_category_map())[subcategory]
