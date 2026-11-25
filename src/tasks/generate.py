"""Generate the v1 tasks, real and anonymised, at every difficulty."""

import json
import random
from pathlib import Path

from src.settings import ROOT, load_config
from src.tasks.templates import category, combined, spatial, undetermined
from src.tasks.templates.common import render
from src.tasks.world import load_world

BUILDERS = {
    "spatial_inference": spatial.build,
    "category_inference": category.build,
    "combined_filter": combined.build,
    "not_determinable": undetermined.build,
}


def build_tasks(config: dict | None = None) -> tuple[list[dict], dict]:
    config = config or load_config()
    world = load_world()
    seed = int(config["seed"])
    tasks = []
    for task_type in config["tasks"]["types"]:
        builder = BUILDERS[task_type]
        for difficulty in config["tasks"]["difficulties"]:
            count = int(config["tasks"]["per_type_per_difficulty"])
            for index in range(count):
                rng = random.Random(f"{seed}:{task_type}:{difficulty}:{index}")
                draft = builder(world, difficulty, rng)
                task_id = f"{task_type}__{difficulty}__{index:04d}"
                for anonymised in (False, True):
                    tasks.append({
                        "task_id": task_id,
                        "type": draft["type"],
                        "difficulty": draft["difficulty"],
                        "rule_tags": draft["rule_tags"],
                        "anonymised": anonymised,
                        "question": render(draft["question_template"], draft["slots"], anonymised, world),
                        "facts": draft["facts"],
                        "answer_type": draft["answer_type"],
                        "answer": draft["answer"],
                        "seed": seed,
                    })
    return tasks, world.entities


def write_tasks(tasks: list[dict], entities: dict, root: Path | None = None) -> Path:
    root = root or (ROOT / "tasks")
    for task in tasks:
        folder = root / ("anon" if task["anonymised"] else "real")
        folder.mkdir(parents=True, exist_ok=True)
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
