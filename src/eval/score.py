"""Score one model answer against the gold answer stored on the task."""

import json
import re


def parse_answer(text: str):
    """Return the answer field, or None when the response is not JSON."""
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and "answer" in data:
        return data["answer"]
    return data


def score_task(task: dict, text: str, entities: dict) -> dict:
    """Exact match for bools, tokens, and values. Sets also get precision, recall, and F1."""
    predicted = parse_answer(text)
    if predicted is None:
        return {"parsed": False, "exact": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "predicted": None}
    gold = task["answer"]
    kind = task["answer_type"]
    mentioned = _mentioned(task)
    if kind == "set":
        return _score_set(gold, predicted, entities, mentioned)
    if kind == "bool":
        exact = int(_as_bool(predicted) is bool(gold))
        return {"parsed": True, "exact": exact, "precision": None, "recall": None, "f1": None, "predicted": predicted}
    resolved = _resolve(predicted, entities, mentioned)
    if kind in {"CANNOT_DETERMINE", "CONTRADICTION"} or gold in {"CANNOT_DETERMINE", "CONTRADICTION"}:
        exact = int(str(predicted).strip() == str(gold))
    else:
        exact = int(resolved == gold or str(predicted).strip() == str(gold))
    return {"parsed": True, "exact": exact, "precision": None, "recall": None, "f1": None, "predicted": predicted}


def _score_set(gold: list, predicted, entities: dict, mentioned: set[str]) -> dict:
    if isinstance(predicted, str):
        predicted = [predicted]
    if not isinstance(predicted, list):
        return {"parsed": True, "exact": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "predicted": predicted}
    gold_ids = set(gold)
    pred_ids = set()
    for value in predicted:
        resolved = _resolve(value, entities, mentioned)
        pred_ids.add(resolved if resolved else f"unresolved:{value}")
    overlap = gold_ids & pred_ids
    precision = len(overlap) / len(pred_ids) if pred_ids else 0.0
    recall = len(overlap) / len(gold_ids) if gold_ids else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "parsed": True,
        "exact": int(pred_ids == gold_ids),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "predicted": predicted,
    }


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().casefold() in {"true", "false"}:
        return value.strip().casefold() == "true"
    return None


def _mentioned(task: dict) -> set[str]:
    ids = set()
    for subject, _relation, obj in task["facts"]:
        ids.add(subject)
        ids.add(obj)
    return ids


def _resolve(value, entities: dict, mentioned: set[str] | None = None) -> str | None:
    """Map a name or an id back to an entity id. A repeated name must be unique on the sheet."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    if text in entities:
        return text
    folded = text.casefold()
    hits = [
        entity_id
        for entity_id, record in entities.items()
        if record.get("name", "").casefold() == folded or record.get("anon", "").casefold() == folded
    ]
    if mentioned:
        on_sheet = [entity_id for entity_id in hits if entity_id in mentioned]
        if len(on_sheet) == 1:
            return on_sheet[0]
    if len(hits) == 1:
        return hits[0]
    return None
