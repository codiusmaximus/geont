"""Reasoner closure, and agreement with the geometric ground truth."""

import pandas as pd

from src.reasoner import Reasoner
from src.settings import ROOT, load_category_map, subcategory_parents
from src.tasks.world import load_world


def test_within_is_transitive_and_adjacency_is_symmetric():
    reasoned = Reasoner(
        [
            ("P1", "within", "M1"),
            ("M1", "within", "N3"),
            ("N3", "within", "N2"),
            ("M1", "adjacent_to", "M2"),
        ],
        levels={"M1": "MUNI", "M2": "MUNI", "N3": "NUTS3", "N2": "NUTS2"},
    )
    assert reasoned.region_at("P1", "NUTS2") == "N2"
    assert reasoned.adjacent("M2", "M1")
    assert reasoned.contradictions == []


def test_is_a_inherits_through_subclass_of():
    reasoned = Reasoner(
        [
            ("P1", "is_a", "Hospital"),
            ("Hospital", "subclass_of", "Healthcare"),
        ]
    )
    assert reasoned.is_instance("P1", "Healthcare") is True
    assert reasoned.is_instance("P1", "Education") is False
    assert reasoned.is_instance("P2", "Healthcare") is None


def test_same_level_double_membership_is_a_contradiction():
    reasoned = Reasoner(
        [("P1", "within", "A"), ("P1", "within", "B")],
        levels={"A": "NUTS2", "B": "NUTS2"},
    )
    assert reasoned.contradictions == [("P1", "NUTS2", "A", "B")]


def test_full_facts_match_the_geometry():
    world = load_world()
    reasoned = Reasoner([*world.direct_facts, *world.ontology_facts], world.levels)
    assert reasoned.contradictions == []
    parents = subcategory_parents(load_category_map())
    for place in world.places:
        ancestors = []
        cursor = place["muni_id"]
        while cursor is not None:
            ancestors.append(cursor)
            cursor = world.parents[cursor]
        assert reasoned.regions_of(place["place_id"]) == sorted(ancestors)
        assert reasoned.is_instance(place["place_id"], place["subcategory"]) is True
        assert reasoned.is_instance(place["place_id"], parents[place["subcategory"]]) is True
        assert place["place_id"] in reasoned.places_in(place["muni_id"], place["subcategory"])

    adjacency = pd.read_parquet(ROOT / "data" / "processed" / "adjacency.parquet")
    sample = adjacency.head(5)
    for row in sample.itertuples(index=False):
        assert reasoned.adjacent(row.region_a, row.region_b)
        assert reasoned.adjacent(row.region_b, row.region_a)
