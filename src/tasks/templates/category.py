"""Is this place a member of a top-level category?"""

from src.tasks.distractors import assemble
from src.tasks.templates.common import ARTICLE, answer_with, pick_place, tops
from src.tasks.world import World, category_of


def anchor(world: World, rng) -> dict:
    place = pick_place(world, rng)
    true_top = category_of(place["subcategory"])
    others = [top for top in tops() if top != true_top]
    asked = true_top if rng.randrange(2) == 0 else rng.choice(others)
    return {"place": place, "asked": asked}


def materialise(world: World, base: dict, dials: dict, rng) -> dict:
    place = base["place"]
    asked = base["asked"]
    dials = {**dials, "depth": None}
    proof = [(place["place_id"], "is_a", place["subcategory"])]
    scope = {
        "focus_id": place["place_id"],
        "focus_name": place["name"],
        "focus_sub": place["subcategory"],
        "focus_top": category_of(place["subcategory"]),
        "focus_muni": place["muni_id"],
        "asked_region": None,
        "blocked_within": {place["place_id"]},
        "forbidden": set(),
    }

    expected = answer_with([list(fact) for fact in proof], world).is_instance(place["place_id"], asked)
    if expected is None:
        raise RuntimeError(f"category of {place['place_id']} was not derivable")

    def ok(reasoned) -> bool:
        return not reasoned.contradictions and reasoned.is_instance(place["place_id"], asked) is expected

    facts, proof_facts = assemble(world, proof, dials, rng, scope, ok)
    verdict = expected
    return {
        "type": "category_inference",
        "rule_tags": ["is_a_inheritance"],
        "facts": facts,
        "proof_facts": proof_facts,
        "answer_type": "bool",
        "answer": verdict,
        "question_template": "Is {place} " + ARTICLE[asked] + "?",
        "slots": {"place": place["place_id"]},
        "dials": dials,
    }
