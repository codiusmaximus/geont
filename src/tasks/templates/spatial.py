"""Which region, above the municipality, contains this place?"""

from src.tasks.distractors import assemble
from src.tasks.templates.common import level_at, pick_place, within_chain
from src.tasks.world import World, category_of


def anchor(world: World, rng) -> dict:
    return {"place": pick_place(world, rng)}


def materialise(world: World, base: dict, dials: dict, rng) -> dict:
    place = base["place"]
    depth = int(dials["depth"])
    level = level_at(depth)
    chain, region_id = within_chain(place["place_id"], place["muni_id"], world, level)
    blocked = {fact[0] for fact in chain}
    scope = {
        "focus_id": place["place_id"],
        "focus_name": place["name"],
        "focus_sub": place["subcategory"],
        "focus_top": category_of(place["subcategory"]),
        "focus_muni": place["muni_id"],
        "asked_region": region_id,
        "blocked_within": blocked,
        "forbidden": set(),
    }

    def ok(reasoned) -> bool:
        return not reasoned.contradictions and reasoned.region_at(place["place_id"], level) == region_id

    facts, proof_facts = assemble(world, chain, dials, rng, scope, ok)
    phrase = "borough" if level == "MUNI" else level.replace("NUTS", "NUTS-") + " region"
    return {
        "type": "spatial_inference",
        "rule_tags": ["within_transitive"],
        "facts": facts,
        "proof_facts": proof_facts,
        "answer_type": "value",
        "answer": region_id,
        "question_template": "Which " + phrase + " is {place} within?",
        "slots": {"place": place["place_id"]},
        "dials": dict(dials),
    }
