"""Turn a raw run log into the summary the metrics page reads."""

import json
from pathlib import Path

from src.eval.prompt import load_entities
from src.settings import ROOT


def summarize(rows: list[dict], entities: dict) -> dict:
    versions = list(dict.fromkeys(row["version"] for row in rows))
    by_version = [_rate(version, [row for row in rows if row["version"] == version]) for version in versions]
    presets = [name for name in ("easy", "medium", "hard") if any(row.get("preset") == name for row in rows)]
    by_preset = []
    for preset in presets:
        by_preset.append({
            "preset": preset,
            "versions": [
                _rate(version, [row for row in rows if row.get("preset") == preset and row["version"] == version])
                for version in versions
            ],
        })
    types = list(dict.fromkeys(row["type"] for row in rows))
    by_type = []
    for task_type in types:
        by_type.append({
            "type": task_type,
            "versions": [
                _rate(version, [row for row in rows if row["type"] == task_type and row["version"] == version])
                for version in versions
            ],
        })
    tasks = []
    seen = []
    for row in rows:
        if row["task_id"] not in seen:
            seen.append(row["task_id"])
    for task_id in seen:
        chosen = [row for row in rows if row["task_id"] == task_id]
        first = chosen[0]
        tasks.append({
            "task_id": task_id,
            "type": first["type"],
            "question": first.get("question") or _question(task_id),
            "gold": _label(first["gold"], entities),
            "cells": [
                {"version": row["version"], "exact": bool(row["exact"]), "answer": _label(row["predicted"], entities)}
                for row in chosen
            ],
        })
    tokens = sum((row.get("input_tokens") or 0) + (row.get("output_tokens") or 0) for row in rows)
    first = rows[0]
    return {
        "run_id": first["run_id"],
        "when": _when(first["run_id"]),
        "model": first["model"],
        "temperature": first["temperature"],
        "format": first["format"],
        "split": "real",
        "versions": versions,
        "tokens": tokens,
        "scope": _scope(rows),
        "by_version": by_version,
        "by_preset": by_preset,
        "by_type": by_type,
        "tasks": tasks,
    }


def _rate(version: str, chosen: list[dict]) -> dict:
    exact = sum(int(row["exact"]) for row in chosen)
    return {
        "version": version,
        "exact": exact,
        "n": len(chosen),
        "accuracy": exact / len(chosen) if chosen else 0,
    }


def write_summary(rows: list[dict], path: Path | None = None, note: str = "") -> Path:
    summary = summarize(rows, load_entities())
    if note:
        summary["note"] = note
    path = path or ROOT / "explore" / "data" / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path


def baseline_rows() -> list[dict]:
    """The longest finished English log that still has v0 and v1."""
    best: list[dict] = []
    for path in sorted((ROOT / "results" / "raw").glob("*.jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        versions = {row["version"] for row in rows}
        if {"v0", "v1"} <= versions and len(rows) > len(best):
            best = rows
    if not best:
        raise FileNotFoundError("no English baseline log with v0 and v1")
    return best


def replace_version(baseline: list[dict], new_rows: list[dict], version: str) -> list[dict]:
    kept = [row for row in baseline if row["version"] != version]
    return kept + new_rows


def summarize_formats(rows: list[dict]) -> dict:
    versions = [name for name in ("v1", "v2") if any(row["version"] == name for row in rows)]
    formats = [name for name in ("ttl", "json") if any(row["format"] == name for row in rows)]
    first = rows[0]
    return {
        "experiment": "format",
        "run_id": first["run_id"],
        "when": _when(first["run_id"]),
        "model": first["model"],
        "temperature": first["temperature"],
        "versions": versions,
        "formats": formats,
        "tokens": sum((row.get("input_tokens") or 0) + (row.get("output_tokens") or 0) for row in rows),
        "scope": (
            f"{len({row['task_id'] for row in rows})} real tasks. "
            "v1 and v2 in Turtle and JSON. Separate from the English run."
        ),
        "cells": _format_cells(rows, versions, formats),
        "by_preset": [
            {
                "preset": preset,
                "cells": _format_cells(
                    [row for row in rows if row.get("preset") == preset], versions, formats
                ),
            }
            for preset in ("easy", "medium", "hard")
            if any(row.get("preset") == preset for row in rows)
        ],
        "by_type": [
            {
                "type": task_type,
                "cells": _format_cells(
                    [row for row in rows if row["type"] == task_type], versions, formats
                ),
            }
            for task_type in dict.fromkeys(row["type"] for row in rows)
        ],
    }


def write_format_summary(rows: list[dict], path: Path | None = None) -> Path:
    path = path or ROOT / "explore" / "data" / "summary-formats.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summarize_formats(rows), indent=2) + "\n", encoding="utf-8")
    return path


def _format_cells(rows: list[dict], versions: list[str], formats: list[str]) -> list[dict]:
    cells = []
    for version in versions:
        for fmt in formats:
            chosen = [row for row in rows if row["version"] == version and row["format"] == fmt]
            exact = sum(int(row["exact"]) for row in chosen)
            cells.append({
                "version": version,
                "format": fmt,
                "exact": exact,
                "n": len(chosen),
                "accuracy": exact / len(chosen) if chosen else 0,
            })
    return cells


def latest_rows() -> list[dict]:
    files = sorted((ROOT / "results" / "raw").glob("*.jsonl"))
    if not files:
        raise FileNotFoundError("no results/raw log")
    return [json.loads(line) for line in files[-1].read_text(encoding="utf-8").splitlines() if line.strip()]


def _question(task_id: str) -> str:
    path = ROOT / "tasks" / "real" / f"{task_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))["question"]


def _label(value, entities: dict) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_label(item, entities) for item in value)
    if isinstance(value, str):
        record = entities.get(value)
        return record["name"] if record else value
    if value is None:
        return ""
    return str(value)


def _when(run_id: str) -> str:
    stamp = run_id.split("-", 1)[0]
    if len(stamp) < 8 or not stamp[:8].isdigit():
        return run_id
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{int(stamp[6:8])} {months[int(stamp[4:6]) - 1]} {stamp[:4]}"


def _scope(rows: list[dict]) -> str:
    presets = [name for name in ("easy", "medium", "hard") if any(row.get("preset") == name for row in rows)]
    n_tasks = len({row["task_id"] for row in rows})
    preset = ", ".join(presets) if presets else "easy"
    return (
        f"{n_tasks} real tasks ({preset}). English only, one run. "
        "Anonymised twins, Turtle, and JSON are not in this run."
    )


if __name__ == "__main__":
    written = write_summary(latest_rows())
    print(written)
