"""Is this place a member of a top-level category?"""

from src.tasks.templates.common import ARTICLE, answer_with, fill_facts, pick_place, tops
from src.tasks.world import World, category_of


def build(world: World, difficulty: str, rng) -> dict:
    place = pick_place(world, rng)
    true_top = category_of(place["subcategory"])
    others = [top for top in tops() if top != true_top]
    asked = true_top if rng.randrange(2) == 0 else rng.choice(others)
    required = [(place["place_id"], "is_a", place["subcategory"])]
    facts = fill_facts(required, world, rng, difficulty, {place["place_id"]})
    reasoned = answer_with(facts, world)
    verdict = reasoned.is_instance(place["place_id"], asked)
    if verdict is None:
        raise RuntimeError(f"category of {place['place_id']} was not derivable")
    return {
        "type": "category_inference",
        "difficulty": difficulty,
        "rule_tags": ["is_a_inheritance"],
        "facts": facts,
        "answer_type": "bool",
        "answer": verdict,
        "question_template": "Is {place} " + ARTICLE[asked] + "?",
        "slots": {"place": place["place_id"]},
        "focus": place["place_id"],
    }
