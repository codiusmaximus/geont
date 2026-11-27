"""Prompt wording and scoring. No network calls."""

import json

from src.eval.prompt import render_prompt
from src.eval.report import summarize
from src.eval.score import score_task
from src.ontology.render import parse_facts
from src.settings import ROOT


def _task(name: str) -> dict:
    path = ROOT / "tasks" / "real" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _entities() -> dict:
    return json.loads((ROOT / "tasks" / "entities.json").read_text(encoding="utf-8"))


def test_v0_has_no_ontology_and_v2_has_the_rules():
    task = _task("spatial_inference__d2_x0_log__0000")
    entities = _entities()
    v0 = render_prompt(task, "v0", "en", entities)
    v2 = render_prompt(task, "v2", "en", entities)
    assert "and an ontology" not in v0.split("Facts:")[0]
    assert "transitive" not in v0
    assert "and an ontology" in v2
    assert "`within` is transitive." in v2
    assert "Supermarket, ConvenienceStore" in v2.split("Facts:", 1)[0]
    assert "Same types and relations as v1" not in v2
    assert v0.split("Facts:", 1)[1] == v2.split("Facts:", 1)[1]
    assert "Post Office-Lea Bridge Road 333 is within" in v0
    assert "Redbridge and Waltham Forest" in v0


def test_scores_names_bools_and_abstention():
    entities = _entities()
    spatial = _task("spatial_inference__d2_x0_log__0000")
    named = score_task(spatial, '{"answer": "Redbridge and Waltham Forest"}', entities)
    assert named["exact"] == 1
    wrong = score_task(spatial, '{"answer": "Enfield"}', entities)
    assert wrong["exact"] == 0
    category = _task("category_inference__dx_x0_log__0000")
    assert score_task(category, '{"answer": false}', entities)["exact"] == 1
    missing = _task("not_determinable__d2_x0_log__0000")
    assert score_task(missing, '{"answer": "CANNOT_DETERMINE"}', entities)["exact"] == 1
    assert score_task(missing, "not json", entities)["parsed"] is False
    combined = _task("combined_filter__d2_x0_log__0000")
    names = [entities[item]["name"] for item in combined["answer"]]
    scored = score_task(combined, json.dumps({"answer": names}), entities)
    assert scored["exact"] == 1
    assert scored["f1"] == 1


def test_summary_counts_exact_by_version():
    rows = [
        {"run_id": "20261127T153611Z-gpt-4o-mini", "task_id": "a", "type": "spatial_inference", "preset": "easy", "version": "v0", "format": "en", "model": "gpt-4o-mini", "temperature": 0, "question": "Where?", "gold": "UKI53", "predicted": "CANNOT_DETERMINE", "exact": 0, "input_tokens": 10, "output_tokens": 2},
        {"run_id": "20261127T153611Z-gpt-4o-mini", "task_id": "a", "type": "spatial_inference", "preset": "easy", "version": "v1", "format": "en", "model": "gpt-4o-mini", "temperature": 0, "question": "Where?", "gold": "UKI53", "predicted": "Redbridge and Waltham Forest", "exact": 1, "input_tokens": 20, "output_tokens": 4},
    ]
    summary = summarize(rows, {"UKI53": {"name": "Redbridge and Waltham Forest", "anon": "U019"}})
    assert summary["when"] == "27 Nov 2026"
    assert summary["by_version"][0]["exact"] == 0
    assert summary["by_version"][1]["accuracy"] == 1
    assert summary["tasks"][0]["gold"] == "Redbridge and Waltham Forest"
    assert summary["tokens"] == 36


def test_facts_stay_sentences_and_spo_is_the_ontology():
    task = _task("combined_filter__d2_x0_log__0000")
    entities = _entities()
    expected = [tuple(fact) for fact in task["facts"]]
    english = render_prompt(task, "v2", "en", entities)
    facts = english.split("Facts:", 1)[1]
    for fmt in ("en", "json", "ttl"):
        prompt = render_prompt(task, "v2", fmt, entities)
        assert prompt.split("Facts:", 1)[1] == facts
        assert parse_facts(prompt, fmt, entities, task) == expected
        assert '"s":' not in prompt.split("Facts:", 1)[1]
    v0 = render_prompt(task, "v0", "json", entities)
    assert '"s":' not in v0
    v1 = render_prompt(task, "v1", "json", entities).split("Facts:", 1)[0]
    v2 = render_prompt(task, "v2", "json", entities).split("Facts:", 1)[0]
    assert '"s": "Supermarket"' in v1
    assert "TransitiveProperty" not in v1
    assert '"s": "within"' in v2 and "TransitiveProperty" in v2
    assert "owl:TransitiveProperty" in render_prompt(task, "v2", "ttl", entities).split("Facts:", 1)[0]
