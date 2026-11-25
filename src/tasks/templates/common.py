"""Shared fact-chain helpers for the task templates."""

import random

from src.reasoner import Reasoner
from src.tasks.world import World

FACT_TARGET = {"easy": 5, "medium": 30, "hard": 100}
SPATIAL_LEVEL = {"easy": "NUTS3", "medium": "NUTS2", "hard": "NUTS1"}
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


def fill_facts(required: list[tuple[str, str, str]], world: World, rng: random.Random, difficulty: str, protected: set[str]) -> list[list[str]]:
    """Pad with distractors that do not add within-links for the protected entities."""
    chosen = list(dict.fromkeys(required))
    target = FACT_TARGET[difficulty]
    if difficulty != "easy" and len(chosen) < target:
        pool = [
            fact for fact in world.direct_facts
            if fact not in chosen and fact[0] not in protected
        ]
        rng.shuffle(pool)
        for fact in pool:
            if len(chosen) >= target:
                break
            chosen.append(fact)
    if difficulty != "easy":
        rng.shuffle(chosen)
    return [[subject, pred, obj] for subject, pred, obj in chosen]


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
