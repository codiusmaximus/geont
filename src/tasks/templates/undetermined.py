"""The within link the question needs has been removed."""

from src.tasks.distractors import assemble
from src.tasks.templates.common import level_at, pick_place, within_chain
from src.tasks.world import World, category_of


def anchor(world: World, rng) -> dict:
    return {"place": pick_place(world, rng)}


def materialise(world: World, base: dict, dials: dict, rng) -> dict:
    place = base["place"]
    depth = int(dials["depth"])
    level = level_at(depth)
    chain, _region = within_chain(place["place_id"], place["muni_id"], world, level)
    if len(chain) < 2:
        raise RuntimeError("not_determinable needs a chain of at least two hops")
    kept, removed = chain[:-1], chain[-1]
    blocked = {fact[0] for fact in chain} | {removed[0]}
    scope = {
        "focus_id": place["place_id"],
        "focus_name": place["name"],
        "focus_sub": place["subcategory"],
        "focus_top": category_of(place["subcategory"]),
        "focus_muni": place["muni_id"],
        "asked_region": None,
        "blocked_within": blocked,
        "forbidden": {removed},
    }

    def ok(reasoned) -> bool:
        return reasoned.region_at(place["place_id"], level) is None and not reasoned.contradictions

    facts, proof_facts = assemble(world, kept, dials, rng, scope, ok)
    phrase = level.replace("NUTS", "NUTS-") + " region"
    return {
        "type": "not_determinable",
        "rule_tags": ["closed_world"],
        "facts": facts,
        "proof_facts": proof_facts,
        "answer_type": "CANNOT_DETERMINE",
        "answer": "CANNOT_DETERMINE",
        "question_template": "Which " + phrase + " is {place} within?",
        "slots": {"place": place["place_id"]},
        "dials": dict(dials),
    }
