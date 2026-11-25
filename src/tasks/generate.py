"""Generate the v1 tasks, real and anonymised, for each pilot preset."""

import json
import random
from pathlib import Path

from src.settings import ROOT, load_config
from src.tasks.distractors import register_veterinary
from src.tasks.templates import category, combined, spatial, undetermined
from src.tasks.templates.common import render
from src.tasks.world import load_world

BUILDERS = {
    "spatial_inference": spatial,
    "category_inference": category,
    "combined_filter": combined,
    "not_determinable": undetermined,
}

PRESETS = {
    "easy": {"depth": 2, "distractors": 0, "order": "logical"},
    "medium": {"depth": 3, "distractors": 25, "order": "shuffled"},
    "hard": {"depth": 4, "distractors": 100, "order": "shuffled"},
}


def _presets(config: dict) -> dict[str, dict]:
    raw = config["tasks"].get("presets", PRESETS)
    if isinstance(raw, list):
        return {name: PRESETS[name] for name in raw}
    return {name: dict(value) for name, value in raw.items()}


def _token(dials: dict) -> str:
    depth = dials["depth"]
    depth_token = "dx" if depth is None else f"d{depth}"
    order = "shuf" if dials["order"] == "shuffled" else "log"
    return f"{depth_token}_x{dials['distractors']}_{order}"


def build_tasks(config: dict | None = None) -> tuple[list[dict], dict]:
    config = config or load_config()
    world = load_world()
    register_veterinary(world)
    seed = int(config["seed"])
    presets = _presets(config)
    count = int(config["tasks"].get("base_tasks_per_type", config["tasks"].get("per_type_per_difficulty", 4)))
    context_mode = config["tasks"].get("context_mode", "crafted")
    tasks = []
    for task_type in config["tasks"]["types"]:
        builder = BUILDERS[task_type]
        for index in range(count):
            base_rng = random.Random(f"{seed}:{task_type}:{index}")
            base = builder.anchor(world, base_rng)
            base_id = f"{task_type}__{index:04d}"
            for preset, dials in presets.items():
                variant_rng = random.Random(f"{seed}:{task_type}:{index}:{preset}")
                draft = builder.materialise(world, base, dict(dials), variant_rng)
                task_id = f"{task_type}__{_token(draft['dials'])}__{index:04d}"
                for anonymised in (False, True):
                    tasks.append({
                        "task_id": task_id,
                        "base_id": base_id,
                        "type": draft["type"],
                        "preset": preset,
                        "dials": draft["dials"],
                        "context_mode": context_mode,
                        "rule_tags": draft["rule_tags"],
                        "anonymised": anonymised,
                        "question": render(draft["question_template"], draft["slots"], anonymised, world),
                        "facts": draft["facts"],
                        "proof_facts": draft["proof_facts"],
                        "answer_type": draft["answer_type"],
                        "answer": draft["answer"],
                        "seed": seed,
                    })
    return tasks, world.entities


def write_tasks(tasks: list[dict], entities: dict, root: Path | None = None) -> Path:
    root = root or (ROOT / "tasks")
    for name in ("real", "anon"):
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True)
        for path in folder.glob("*.json"):
            path.unlink()
    for task in tasks:
        folder = root / ("anon" if task["anonymised"] else "real")
        path = folder / f"{task['task_id']}.json"
        path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    entity_path = root / "entities.json"
    entity_path.write_text(json.dumps(entities, indent=2) + "\n", encoding="utf-8")
    return root


def main() -> None:
    tasks, entities = build_tasks()
    root = write_tasks(tasks, entities)
    real = sum(1 for task in tasks if not task["anonymised"])
    print(f"wrote {real} tasks x 2 variants in {root}")


if __name__ == "__main__":
    main()
