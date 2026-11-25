"""The v1 task set is deterministic and its answers come from the reasoner."""

from src.tasks.generate import build_tasks


def _focus(task: dict) -> str:
    for index in task["proof_facts"]:
        subject, pred, _obj = task["facts"][index]
        if pred in {"within", "is_a"} and subject.startswith("P"):
            return subject
    raise AssertionError(f"no focus place in {task['task_id']}")


def test_tasks_cover_the_v1_grid_and_repeat():
    first, _entities = build_tasks()
    second, _entities = build_tasks()
    assert first == second
    real = [task for task in first if not task["anonymised"]]
    anon = [task for task in first if task["anonymised"]]
    assert len(real) == 4 * 3 * 4
    assert len(anon) == len(real)
    kinds = {task["type"] for task in real}
    assert kinds == {
        "spatial_inference",
        "category_inference",
        "combined_filter",
        "not_determinable",
    }
    for task in real:
        twin = next(item for item in anon if item["task_id"] == task["task_id"])
        assert twin["facts"] == task["facts"]
        assert twin["answer"] == task["answer"]
        assert twin["question"] != task["question"]
        assert "subclass_of" not in {fact[1] for fact in task["facts"]}
        assert task["context_mode"] == "crafted"
        proof = [task["facts"][index] for index in task["proof_facts"]]
        assert task["dials"]["distractors"] == len(task["facts"]) - len(proof)
        if task["dials"]["order"] == "logical":
            assert task["facts"][: len(proof)] == proof
    undetermined = [task for task in real if task["type"] == "not_determinable"]
    assert {task["answer"] for task in undetermined} == {"CANNOT_DETERMINE"}
    sets = [task for task in real if task["answer_type"] == "set"]
    assert sets
    assert all(1 <= len(task["answer"]) <= 12 for task in sets)
    spatial = [task for task in real if task["type"] == "spatial_inference"]
    by_base: dict[str, list] = {}
    for task in spatial:
        by_base.setdefault(task["base_id"], []).append(task)
    for group in by_base.values():
        assert len({_focus(task) for task in group}) == 1
        hard = next(task for task in group if task["preset"] == "hard")
        assert hard["dials"] == {"depth": 4, "distractors": 100, "order": "shuffled"}
    categories = [task for task in real if task["type"] == "category_inference"]
    assert all(task["dials"]["depth"] is None for task in categories)
