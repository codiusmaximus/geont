"""List the places of a top-level category inside a region."""

from src.tasks.distractors import assemble, top_of
from src.tasks.templates.common import level_at, region_at_depth, within_chain
from src.tasks.world import World


def _members(world: World, place: dict, depth: int) -> tuple[str, list[dict]]:
    region_id = region_at_depth(place["muni_id"], depth, world)
    top = top_of(place["subcategory"])
    members = [
        other
        for other in world.places
        if top_of(other["subcategory"]) == top and region_at_depth(other["muni_id"], depth, world) == region_id
    ]
    return region_id, sorted(members, key=lambda item: item["place_id"])


def _fits(world: World, place: dict, depth: int, limits: dict) -> bool:
    _region, members = _members(world, place, depth)
    return limits["min"] <= len(members) <= limits["max"]


def anchor(world: World, rng, limits: dict | None = None) -> dict:
    limits = limits or {"min": 1, "max": 12}
    places = list(world.places)
    rng.shuffle(places)
    for place in places:
        if _fits(world, place, 2, limits) and _fits(world, place, 3, limits):
            return {"place": place}
    raise RuntimeError("no combined-filter place fits the answer-size limit")


def materialise(world: World, base: dict, dials: dict, rng, limits: dict | None = None) -> dict:
    limits = limits or {"min": 1, "max": 12}
    place = base["place"]
    dials = dict(dials)
    depth = int(dials["depth"])
    while depth > 1 and not _fits(world, place, depth, limits):
        depth -= 1
    dials["depth"] = depth
    if not _fits(world, place, depth, limits):
        raise RuntimeError(f"combined filter cannot keep the answer size at depth {depth}")
    region_id, members = _members(world, place, depth)
    top = top_of(place["subcategory"])
    level = level_at(depth)
    required: list[tuple[str, str, str]] = []
    for member in members:
        chain, _region = within_chain(member["place_id"], member["muni_id"], world, level)
        required.extend(chain)
        required.append((member["place_id"], "is_a", member["subcategory"]))
    blocked = {fact[0] for fact in required}
    scope = {
        "focus_id": place["place_id"],
        "focus_name": place["name"],
        "focus_sub": place["subcategory"],
        "focus_top": top,
        "focus_muni": place["muni_id"],
        "asked_region": region_id,
        "blocked_within": blocked,
        "forbidden": set(),
    }
    expected = [member["place_id"] for member in members]

    def ok(reasoned) -> bool:
        return not reasoned.contradictions and reasoned.places_in(region_id, top) == expected

    facts, proof_facts = assemble(world, required, dials, rng, scope, ok)
    return {
        "type": "combined_filter",
        "rule_tags": ["within_transitive", "is_a_inheritance"],
        "facts": facts,
        "proof_facts": proof_facts,
        "answer_type": "set",
        "answer": expected,
        "question_template": "Which " + top + " places are within {region}?",
        "slots": {"region": region_id},
        "dials": dials,
    }
