"""Near-miss distractors. Not a random draw from the fact table.

The five kinds are the ones in the spec: right category in the wrong region,
right region with the wrong category, a chain that stops at the municipality,
a similar name, and hierarchy facts that are not on the proof.
"""

import random
import re

import pandas as pd

from src.reasoner import Reasoner
from src.settings import ROOT, load_category_map, subcategory_parents
from src.tasks.world import World

_TOPS: dict[str, str] | None = None
_VETS: list[dict] | None = None
_STOP = {"london", "street", "road", "limited", "store", "station", "school"}


def top_of(subcategory: str) -> str:
    global _TOPS
    if _TOPS is None:
        _TOPS = subcategory_parents(load_category_map())
    return _TOPS[subcategory]


def veterinary_places() -> list[dict]:
    """A fixed slice of veterinary clinics, used only as Healthcare near misses."""
    global _VETS
    if _VETS is not None:
        return _VETS
    path = ROOT / "data" / "processed" / "borderline.parquet"
    rows: list[dict] = []
    if path.exists():
        frame = pd.read_parquet(path)
        picked = frame[frame["source_category"].isin(["veterinarian", "veterinary_care"])]
        picked = picked.sort_values("name").head(40)
        for index, row in enumerate(picked.itertuples(index=False), start=1):
            rows.append({
                "place_id": f"V{index:04d}",
                "name": str(row.name),
                "muni_id": str(row.muni_id),
                "anon": f"V{index:03d}",
            })
    _VETS = rows
    return rows


def register_veterinary(world: World) -> None:
    for place in veterinary_places():
        world.entities.setdefault(place["place_id"], {
            "name": place["name"],
            "anon": place["anon"],
            "kind": "place",
        })
        world.names.setdefault(place["place_id"], place["name"])


def _tokens(name: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{4,}", name.casefold()) if token not in _STOP}


def _inside(world: World, muni_id: str, region_id: str | None) -> bool:
    if region_id is None:
        return False
    current: str | None = muni_id
    seen: set[str] = set()
    while current and current not in seen:
        if current == region_id:
            return True
        seen.add(current)
        current = world.parents.get(current)
    return False


def _pools(world: World, scope: dict) -> dict[str, list[tuple[str, str, str]]]:
    focus = scope["focus_id"]
    focus_top = scope["focus_top"]
    asked = scope["asked_region"]
    blocked = scope["blocked_within"]
    names = _tokens(scope["focus_name"])
    right_category: list[tuple[str, str, str]] = []
    right_region: list[tuple[str, str, str]] = []
    dead: list[tuple[str, str, str]] = []
    similar: list[tuple[str, str, str]] = []
    hierarchy: list[tuple[str, str, str]] = []

    for place in world.places:
        if place["place_id"] == focus:
            continue
        top = top_of(place["subcategory"])
        inside = _inside(world, place["muni_id"], asked)
        if top == focus_top and not inside:
            right_category.append((place["place_id"], "is_a", place["subcategory"]))
        if inside and top != focus_top:
            right_region.append((place["place_id"], "is_a", place["subcategory"]))
            if place["muni_id"] not in blocked:
                right_region.append((place["place_id"], "within", place["muni_id"]))
        if not inside and top != focus_top and place["muni_id"] not in blocked:
            dead.append((place["place_id"], "within", place["muni_id"]))
        if names and (_tokens(place["name"]) & names):
            similar.append((place["place_id"], "is_a", place["subcategory"]))

    if focus_top == "Healthcare":
        for vet in veterinary_places():
            right_category.append((vet["place_id"], "is_a", "VeterinaryClinic"))

    place_ids = {place["place_id"] for place in world.places}
    for subject, pred, obj in world.direct_facts:
        if pred == "adjacent_to":
            hierarchy.append((subject, pred, obj))
        elif pred == "within" and subject not in place_ids and subject not in blocked:
            hierarchy.append((subject, pred, obj))

    return {
        "right_category_wrong_region": right_category,
        "right_region_wrong_category": right_region,
        "dead_end": dead,
        "similar_name": similar,
        "unrelated_hierarchy": hierarchy,
    }


def sample(world: World, scope: dict, count: int, rng: random.Random) -> list[tuple[str, str, str]]:
    """Draw up to ``count`` near misses, round-robin across the five kinds."""
    if count <= 0:
        return []
    pools = _pools(world, scope)
    forbidden = set(scope["forbidden"])
    for facts in pools.values():
        rng.shuffle(facts)
    chosen: list[tuple[str, str, str]] = []
    seen = set(forbidden)
    dead_munis: set[str] = set()
    cursors = {name: 0 for name in pools}
    while len(chosen) < count:
        progressed = False
        for name, facts in pools.items():
            while cursors[name] < len(facts):
                fact = facts[cursors[name]]
                cursors[name] += 1
                if fact in seen or fact[1] == "subclass_of":
                    continue
                if name == "unrelated_hierarchy" and fact[1] == "within" and fact[0] in dead_munis:
                    continue
                chosen.append(fact)
                seen.add(fact)
                if name == "dead_end":
                    dead_munis.add(fact[2])
                progressed = True
                break
            if len(chosen) >= count:
                break
        if not progressed:
            break
    return chosen


def assemble(world: World, proof: list[tuple[str, str, str]], dials: dict, rng: random.Random, scope: dict, ok) -> tuple[list[list[str]], list[int]]:
    """Add distractors and refuse a draw that changes the reasoner's answer."""
    proof = list(dict.fromkeys(proof))
    scope = {**scope, "forbidden": set(scope["forbidden"]) | set(proof)}
    count = int(dials["distractors"])
    for _attempt in range(10):
        local = random.Random(rng.randrange(2**31))
        extra = sample(world, scope, count, local)
        facts = list(proof) + extra
        if dials["order"] == "shuffled":
            local.shuffle(facts)
        reasoned = Reasoner([*facts, *world.ontology_facts], world.levels)
        if ok(reasoned):
            proof_set = set(proof)
            indexes = [index for index, fact in enumerate(facts) if fact in proof_set]
            return [[subject, pred, obj] for subject, pred, obj in facts], indexes
    raise RuntimeError(f"distractors kept changing the answer for {scope['focus_id']}")
