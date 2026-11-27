"""Call one model on a chosen task slice and write the raw log.

The key is read from OPENAI_API_KEY or from a gitignored .env file. It is never
written to the result rows.
"""

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.eval.prompt import load_entities, render_prompt
from src.eval.report import baseline_rows, replace_version, write_format_summary, write_summary
from src.eval.score import score_task
from src.settings import ROOT

SMOKE_TASKS = [
    "spatial_inference__d2_x0_log__0000",
    "category_inference__dx_x0_log__0000",
    "combined_filter__d2_x0_log__0000",
    "not_determinable__d2_x0_log__0000",
]


def complete(model: str, prompt: str, temperature: float) -> dict:
    """OpenAI chat completion. Returns text, token counts, and latency."""
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    payload_bytes = json.dumps(payload).encode()
    key = _api_key()
    delay = 2
    last_error = "OpenAI request failed"
    for attempt in range(6):
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload_bytes,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            last_error = f"OpenAI HTTP {error.code}: {detail}"
            if error.code not in {429, 500, 502, 503} or attempt == 5:
                raise RuntimeError(last_error) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            reason = getattr(error, "reason", error)
            last_error = f"OpenAI connection failed: {reason}"
            if attempt == 5:
                raise RuntimeError(last_error) from None
        print(f"retry {attempt + 1} after {delay}s", flush=True)
        time.sleep(delay)
        delay *= 2
    else:
        raise RuntimeError(last_error)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    usage = body.get("usage", {})
    return {
        "text": body["choices"][0]["message"]["content"],
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "latency_ms": latency_ms,
    }


def run_slice(
    task_ids: list[str],
    versions: list[str],
    model: str = "gpt-4o-mini",
    formats: list[str] | None = None,
    temperature: float = 0,
    n_runs: int = 1,
    split: str = "real",
    summary_path: Path | None = None,
    replace: str | None = None,
) -> tuple[str, list[dict]]:
    formats = formats or ["en"]
    entities = load_entities()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + model.replace("/", "-")
    raw_dir = ROOT / "results" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{run_id}.jsonl"
    rows = []
    with path.open("w", encoding="utf-8") as handle:
        for task_id in task_ids:
            task = json.loads((ROOT / "tasks" / split / f"{task_id}.json").read_text(encoding="utf-8"))
            for version in versions:
                for fmt in formats:
                    prompt = render_prompt(task, version, fmt, entities)
                    for run_index in range(n_runs):
                        cached, result = _cached_complete(model, prompt, temperature, run_index)
                        scored = score_task(task, result["text"], entities)
                        row = {
                            "run_id": run_id,
                            "task_id": task_id,
                            "type": task["type"],
                            "preset": task["preset"],
                            "version": version,
                            "format": fmt,
                            "model": model,
                            "temperature": temperature,
                            "run_index": run_index,
                            "cached": cached,
                            "prompt": prompt,
                            "response": result["text"],
                            "input_tokens": result["input_tokens"],
                            "output_tokens": result["output_tokens"],
                            "latency_ms": result["latency_ms"],
                            "question": task["question"],
                            "gold": task["answer"],
                            **scored,
                        }
                        handle.write(json.dumps(row) + "\n")
                        handle.flush()
                        rows.append(row)
                        mark = "exact" if row["exact"] else "miss"
                        print(
                            f"{task_id}  {version}  {fmt}  {mark}  in={row['input_tokens']} out={row['output_tokens']}",
                            flush=True,
                        )
    published = replace_version(baseline_rows(), rows, replace) if replace else rows
    frame = pd.DataFrame(published)
    for column in ("gold", "predicted"):
        frame[column] = frame[column].map(lambda value: json.dumps(value, ensure_ascii=False))
    scores_name = "scores-format.parquet" if summary_path and summary_path.name != "summary.json" else "scores.parquet"
    frame.to_parquet(ROOT / "results" / scores_name, index=False)
    if summary_path and summary_path.name == "summary-formats.json":
        write_format_summary(rows, summary_path)
    else:
        note = ""
        if replace == "v2":
            note = "v2 English is the v1 definitions plus the five rules."
        write_summary(published, summary_path, note)
    return run_id, rows


def _cached_complete(model: str, prompt: str, temperature: float, run_index: int) -> tuple[bool, dict]:
    key = hashlib.sha256(
        json.dumps({"model": model, "prompt": prompt, "temperature": temperature, "run_index": run_index}, sort_keys=True).encode()
    ).hexdigest()
    path = ROOT / "results" / "cache" / f"{key}.json"
    if path.exists():
        return True, json.loads(path.read_text(encoding="utf-8"))
    result = complete(model, prompt, temperature)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result), encoding="utf-8")
    return False, result


def _api_key() -> str:
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if value:
        return value
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, raw = line.split("=", 1)
            if name.strip() == "OPENAI_API_KEY":
                return raw.strip().strip('"').strip("'")
    raise RuntimeError("OPENAI_API_KEY is not set")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a task slice against one OpenAI model.")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--versions", nargs="+", default=["v0", "v1", "v2"])
    parser.add_argument("--format", nargs="+", default=["en"])
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--n-runs", type=int, default=1)
    parser.add_argument("--tasks", nargs="+", default=SMOKE_TASKS)
    parser.add_argument("--all", action="store_true", help="Every task in the chosen split.")
    parser.add_argument("--split", default="real", choices=["real", "anon"])
    parser.add_argument("--replace-version", default=None, help="Keep the other versions from the English baseline.")
    parser.add_argument("--summary", default="explore/data/summary.json")
    args = parser.parse_args()
    if args.all:
        args.tasks = sorted(path.stem for path in (ROOT / "tasks" / args.split).glob("*.json"))
    summary_path = ROOT / args.summary
    calls = len(args.tasks) * len(args.versions) * len(args.format) * args.n_runs
    print(
        f"{calls} calls  model={args.model}  versions={','.join(args.versions)}  formats={','.join(args.format)}  temperature={args.temperature}",
        flush=True,
    )
    run_id, rows = run_slice(
        args.tasks,
        args.versions,
        args.model,
        args.format,
        args.temperature,
        args.n_runs,
        args.split,
        summary_path,
        args.replace_version,
    )
    exact = sum(row["exact"] for row in rows)
    tokens = sum((row["input_tokens"] or 0) + (row["output_tokens"] or 0) for row in rows)
    print(f"run {run_id}  exact {exact}/{len(rows)}  tokens {tokens}", flush=True)


if __name__ == "__main__":
    main()
