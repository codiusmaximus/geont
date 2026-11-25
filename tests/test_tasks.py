"""The v1 task set is deterministic and its answers come from the reasoner."""

from src.tasks.generate import build_tasks


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
    undetermined = [task for task in real if task["type"] == "not_determinable"]
    assert undetermined
    assert {task["answer"] for task in undetermined} == {"CANNOT_DETERMINE"}
    sets = [task for task in real if task["answer_type"] == "set"]
    assert sets
    assert all(1 <= len(task["answer"]) <= 12 for task in sets)
