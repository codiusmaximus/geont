"""Shared fact-chain helpers for the task templates."""

import random

from src.reasoner import Reasoner
from src.tasks.world import World

LEVEL_AT_DEPTH = {1: "MUNI", 2: "NUTS3", 3: "NUTS2", 4: "NUTS1"}
ARTICLE = {
    "Healthcare": "a Healthcare facility",
    "Education": "an Education place",
    "Retail": "a Retail place",
    "Mobility": "a Mobility place",
    "ParcelServices": "a ParcelServices place",
}


def within_chain(place_id: str, muni_id: str, world: World, stop_level: str) -> tuple[list[tuple[str, str, str]], str]:
    """Direct within links from a place up to and including ``stop_level``."""
    facts = [(place_id, "within", muni_id)]
    current = muni_id
    while world.levels[current] != stop_level:
        parent = world.parents[current]
        if parent is None:
            raise RuntimeError(f"{current} has no parent before {stop_level}")
        facts.append((current, "within", parent))
        current = parent
    return facts, current


def level_at(depth: int) -> str:
    return LEVEL_AT_DEPTH[depth]


def region_at_depth(muni_id: str, depth: int, world: World) -> str:
    """Walk up from a municipality to the region at this chain depth."""
    target = level_at(depth)
    current = muni_id
    seen: set[str] = set()
    while current not in seen:
        if world.levels[current] == target:
            return current
        seen.add(current)
        parent = world.parents.get(current)
        if parent is None:
            raise RuntimeError(f"{muni_id} has no {target} ancestor")
        current = parent
    raise RuntimeError(f"cycle walking from {muni_id}")


def answer_with(facts: list[list[str]], world: World) -> Reasoner:
    triples = [tuple(fact) for fact in facts]
    return Reasoner([*triples, *world.ontology_facts], world.levels)


def label(entity_id: str, anonymised: bool, world: World) -> str:
    record = world.entities[entity_id]
    return record["anon"] if anonymised else record["name"]


def render(template: str, slots: dict[str, str], anonymised: bool, world: World) -> str:
    values = {key: label(value, anonymised, world) for key, value in slots.items()}
    return template.format(**values)


def pick_place(world: World, rng: random.Random) -> dict:
    places = list(world.places)
    rng.shuffle(places)
    return places[0]


def level_phrase(level: str) -> str:
    if level == "MUNI":
        return "borough"
    return level.replace("NUTS", "NUTS-") + " region"


def tops() -> list[str]:
    return ["Healthcare", "Education", "Retail", "Mobility", "ParcelServices"]
