"""Which region, above the municipality, contains this place?"""

from src.tasks.templates.common import answer_with, fill_facts, pick_place, within_chain
from src.tasks.world import World


def build(world: World, difficulty: str, rng, level: str | None = None) -> dict:
    level = level or {"easy": "NUTS3", "medium": "NUTS2", "hard": "NUTS1"}[difficulty]
    place = pick_place(world, rng)
    chain, region_id = within_chain(place["place_id"], place["muni_id"], world, level)
    protected = {place["place_id"], *(fact[0] for fact in chain), *(fact[2] for fact in chain)}
    facts = fill_facts(chain, world, rng, difficulty, protected)
    reasoned = answer_with(facts, world)
    if reasoned.contradictions:
        raise RuntimeError(f"spatial task contradicted itself: {reasoned.contradictions[:3]}")
    answer = reasoned.region_at(place["place_id"], level)
    if answer != region_id:
        raise RuntimeError(f"reasoner answered {answer}, chain ends at {region_id}")
    phrase = "borough" if level == "MUNI" else level.replace("NUTS", "NUTS-") + " region"
    return {
        "type": "spatial_inference",
        "difficulty": difficulty,
        "rule_tags": ["within_transitive"],
        "facts": facts,
        "answer_type": "value",
        "answer": answer,
        "question_template": "Which " + phrase + " is {place} within?",
        "slots": {"place": place["place_id"]},
        "focus": place["place_id"],
    }
