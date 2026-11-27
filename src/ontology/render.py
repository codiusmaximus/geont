"""Render one task as a prompt in English, Turtle, or JSON.

The facts are English sentences in every format. Subject, predicate, and object
belong to the ontology block, and only v1 and v2 have one. v0 is facts only.
"""

import json
from pathlib import Path

from src.settings import ROOT

ONTOLOGY_FILES = {"en": "en.md", "json": "ontology.json", "ttl": "ontology.ttl"}


def load_entities(path: Path | None = None) -> dict:
    path = path or ROOT / "tasks" / "entities.json"
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def render_prompt(task: dict, version: str, fmt: str = "en", entities: dict | None = None) -> str:
    """Build the section 9.1 prompt. Facts stay in the order stored on the task."""
    entities = entities if entities is not None else load_entities()
    anonymised = bool(task.get("anonymised"))
    facts = render_facts(task, fmt, entities, anonymised)
    if version == "v0":
        clause = ""
        block = ""
    else:
        clause = " and an ontology"
        block = _ontology_text(version, fmt).strip() + "\n\n"
    question = task["question_anon"] if anonymised and task.get("question_anon") else task["question"]
    return (
        f"You are given facts about places and regions{clause}.\n"
        "Answer using ONLY the information provided. Do not use outside knowledge.\n"
        'If the answer cannot be derived, answer "CANNOT_DETERMINE".\n'
        'If the facts contain a contradiction, answer "CONTRADICTION".\n'
        "\n"
        f"{block}"
        "Facts:\n"
        f"{facts}\n"
        "\n"
        f"Question: {question}\n"
        "\n"
        'Respond with JSON only: {"answer": <bool | string | list of names | "CANNOT_DETERMINE" | "CONTRADICTION">}\n'
    )


def render_facts(task: dict, fmt: str, entities: dict, anonymised: bool = False) -> str:
    if fmt not in ONTOLOGY_FILES:
        raise ValueError(f"unknown format {fmt}")
    return "\n".join(fact_line(fact, entities, anonymised) for fact in task["facts"])


def fact_line(fact: list[str], entities: dict, anonymised: bool = False) -> str:
    subject, relation, obj = fact
    left = _name(subject, entities, anonymised)
    right = _name(obj, entities, anonymised)
    if relation == "within":
        return f"{left} is within {right}."
    if relation == "is_a":
        return f"{left} is a {right}."
    if relation == "adjacent_to":
        return f"{left} is adjacent to {right}."
    return f"{left} {relation} {right}."


def parse_facts(prompt: str, fmt: str, entities: dict, task: dict) -> list[tuple[str, str, str]]:
    """Read the English facts block back into the task's id triples."""
    if fmt not in ONTOLOGY_FILES:
        raise ValueError(f"unknown format {fmt}")
    block = prompt.split("Facts:\n", 1)[1].split("\n\nQuestion:", 1)[0]
    mentioned = {item for fact in task["facts"] for item in (fact[0], fact[2])}
    return [_parse_english(line, entities, mentioned) for line in block.splitlines() if line.strip()]


def _parse_english(line: str, entities: dict, mentioned: set[str]) -> tuple[str, str, str]:
    text = line.strip().removesuffix(".")
    for marker, relation in ((" is within ", "within"), (" is adjacent to ", "adjacent_to"), (" is a ", "is_a")):
        if marker in text:
            left, right = text.split(marker, 1)
            return (_resolve(left, entities, mentioned), relation, _resolve(right, entities, mentioned))
    raise ValueError(f"cannot parse fact: {line}")


def _name(entity_id: str, entities: dict, anonymised: bool) -> str:
    record = entities.get(entity_id)
    if not record:
        return entity_id
    return record["anon"] if anonymised else record["name"]


def _resolve(text: str, entities: dict, mentioned: set[str]) -> str:
    cleaned = " ".join(text.strip().split())
    if cleaned in entities:
        return cleaned
    folded = cleaned.casefold()
    hits = [
        entity_id
        for entity_id, record in entities.items()
        if record.get("name", "").casefold() == folded or record.get("anon", "").casefold() == folded
    ]
    on_sheet = [entity_id for entity_id in hits if entity_id in mentioned]
    if len(on_sheet) == 1:
        return on_sheet[0]
    if len(hits) == 1:
        return hits[0]
    return cleaned


def _ontology_text(version: str, fmt: str) -> str:
    path = ROOT / "ontologies" / version / ONTOLOGY_FILES[fmt]
    return path.read_text(encoding="utf-8")
