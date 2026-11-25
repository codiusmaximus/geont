"""Refresh the static files the explorer fetches.

Writes the map GeoJSON, a task index without fact lists, a manifest, and
one history row per commit. Run from the repo root:

    python explore/build.py
    python explore/build.py --tests "14 passed" --tests-ok
"""

import argparse
import filecmp
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from explore.export import main as export_maps

OUT = Path(__file__).resolve().parent / "data"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _counts() -> dict:
    report = (ROOT / "data" / "processed" / "validation_report.txt").read_text(encoding="utf-8")
    validation = "PASS" if "validation: PASS" in report else "FAIL"
    places = regions = None
    for line in report.splitlines():
        if line.startswith("Places:"):
            places = int(line.split(":", 1)[1].strip())
        if line.startswith("Regions:"):
            regions = int(line.rsplit("total ", 1)[1].rstrip(")"))
    return {"validation": validation, "places": places, "regions": regions}


def _task_index() -> list[dict]:
    rows = []
    folder = ROOT / "tasks" / "real"
    if not folder.exists():
        return rows
    for path in sorted(folder.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        anon_path = ROOT / "tasks" / "anon" / path.name
        question_anon = task["question"]
        if anon_path.exists():
            question_anon = json.loads(anon_path.read_text(encoding="utf-8"))["question"]
        rows.append({
            "task_id": task["task_id"],
            "type": task["type"],
            "difficulty": task.get("preset", task.get("difficulty")),
            "dials": task.get("dials", {}),
            "rule_tags": task["rule_tags"],
            "question": task["question"],
            "question_anon": question_anon,
            "answer_type": task["answer_type"],
            "answer": task["answer"],
            "n_facts": len(task["facts"]),
        })
    return rows


def _write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"{path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


def _check() -> None:
    """Rebuild the map and task index beside the repo and compare bytes.

    The manifest and history carry the commit id, so they are not part of
    this comparison. A commit id cannot be written into a file that is itself
    inside that commit.
    """
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        export_maps(folder)
        (folder / "tasks.json").write_text(
            json.dumps(_task_index(), indent=2) + "\n",
            encoding="utf-8",
        )
        drifted = [
            name
            for name in ("regions.geojson", "places.geojson", "tasks.json")
            if not (OUT / name).exists() or not filecmp.cmp(OUT / name, folder / name, shallow=False)
        ]
    if drifted:
        raise SystemExit(
            "explore/data is stale (" + ", ".join(drifted) + "). Run make explore and commit it before pushing."
        )
    print("explore/data matches the rebuild")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", default="not run")
    parser.add_argument("--tests-ok", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        _check()
        return

    OUT.mkdir(parents=True, exist_ok=True)
    export_maps()
    tasks = _task_index()
    counts = _counts()
    sha = _git("rev-parse", "--short", "HEAD") or "none"
    dirty = bool(_git("status", "--porcelain"))
    manifest = {
        "sha": sha,
        "dirty": dirty,
        "date": date.today().isoformat(),
        "tests": args.tests,
        "tests_ok": args.tests_ok,
        "study_area": "Greater London",
        "tasks": len(tasks),
        **counts,
    }
    _write(OUT / "tasks.json", tasks)
    _write(OUT / "manifest.json", manifest)

    history_path = OUT / "history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    row = {
        "sha": sha + ("-dirty" if dirty else ""),
        "date": manifest["date"],
        "tests": args.tests,
        "tests_ok": args.tests_ok,
        "tasks": len(tasks),
        "places": counts["places"],
        "regions": counts["regions"],
        "validation": counts["validation"],
    }
    if not history or history[-1]["sha"] != row["sha"] or history[-1]["tasks"] != row["tasks"]:
        history.append(row)
    _write(history_path, history)


if __name__ == "__main__":
    main()
