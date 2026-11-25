"""The within link the question needs has been removed."""

from src.tasks.templates.common import answer_with, fill_facts, pick_place, within_chain
from src.tasks.world import World

LEVEL_FOR = {"easy": "NUTS3", "medium": "NUTS2", "hard": "NUTS1"}


def build(world: World, difficulty: str, rng) -> dict:
    level = LEVEL_FOR[difficulty]
    place = pick_place(world, rng)
    chain, _region = within_chain(place["place_id"], place["muni_id"], world, level)
    # Drop the last hop, which is what names the asked region.
    kept = chain[:-1]
    removed = chain[-1]
    protected = {place["place_id"], *(fact[0] for fact in chain), *(fact[2] for fact in chain)}
    facts = fill_facts(kept, world, rng, difficulty, protected)
    if list(removed) in facts:
        raise RuntimeError("removed fact was added back as a distractor")
    reasoned = answer_with(facts, world)
    if reasoned.region_at(place["place_id"], level) is not None or reasoned.contradictions:
        raise RuntimeError("not_determinable task still determines a region")
    phrase = level.replace("NUTS", "NUTS-") + " region"
    return {
        "type": "not_determinable",
        "difficulty": difficulty,
        "rule_tags": ["closed_world"],
        "facts": facts,
        "answer_type": "CANNOT_DETERMINE",
        "answer": "CANNOT_DETERMINE",
        "question_template": "Which " + phrase + " is {place} within?",
        "slots": {"place": place["place_id"]},
        "focus": place["place_id"],
    }
