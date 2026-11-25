"""List the places of a top-level category inside a region."""

from src.tasks.templates.common import answer_with, fill_facts, within_chain
from src.tasks.world import World, category_of

LEVEL_FOR = {"easy": "MUNI", "medium": "NUTS3", "hard": "NUTS2"}


def _candidates(world: World, level: str) -> list[tuple[str, str, list[str]]]:
    by_region: dict[tuple[str, str], list[str]] = {}
    for place in world.places:
        top = category_of(place["subcategory"])
        region = place["muni_id"]
        while region is not None and world.levels[region] != level:
            region = world.parents[region]
        if region is None:
            continue
        by_region.setdefault((region, top), []).append(place["place_id"])
    found = []
    for (region, top), place_ids in by_region.items():
        if 1 <= len(place_ids) <= 12:
            found.append((region, top, sorted(place_ids)))
    return sorted(found)


def build(world: World, difficulty: str, rng) -> dict:
    level = LEVEL_FOR[difficulty]
    options = _candidates(world, level)
    if not options and level != "MUNI":
        options = _candidates(world, "MUNI")
        level = "MUNI"
    if not options:
        raise RuntimeError(f"no combined-filter target at {difficulty}")
    region_id, top, expected_ids = options[rng.randrange(len(options))]
    required = []
    for place_id in expected_ids:
        place = next(item for item in world.places if item["place_id"] == place_id)
        chain, _ = within_chain(place["place_id"], place["muni_id"], world, world.levels[region_id])
        required.extend(chain)
        required.append((place["place_id"], "is_a", place["subcategory"]))
    protected = {
        place["place_id"]
        for place in world.places
        if category_of(place["subcategory"]) == top
    }
    cursor = region_id
    while cursor is not None:
        protected.add(cursor)
        cursor = world.parents.get(cursor)
    facts = fill_facts(required, world, rng, difficulty, protected)
    reasoned = answer_with(facts, world)
    if reasoned.contradictions:
        raise RuntimeError(f"combined task contradicted itself: {reasoned.contradictions[:3]}")
    answer = reasoned.places_in(region_id, top)
    if answer != expected_ids:
        raise RuntimeError(f"reasoner listed {answer}, geometry listed {expected_ids}")
    return {
        "type": "combined_filter",
        "difficulty": difficulty,
        "rule_tags": ["within_transitive", "is_a_inheritance"],
        "facts": facts,
        "answer_type": "set",
        "answer": answer,
        "question_template": "Which " + top + " places are within {region}?",
        "slots": {"region": region_id},
        "focus": region_id,
    }
