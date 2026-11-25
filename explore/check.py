"""Run the tests, refresh the explorer, and refuse a push if either drifted.

    python explore/check.py          # test, rebuild, report
    python explore/check.py --strict # also fail when explore/data is uncommitted
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pytest() -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    text = (result.stdout + result.stderr).strip()
    summary = next((line for line in reversed(text.splitlines()) if "passed" in line or "failed" in line), text[-80:])
    print(text, flush=True)
    return result.returncode == 0, summary


def _uncommitted() -> str:
    diff = subprocess.run(
        ["git", "diff", "--", "explore/data"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "explore/data"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return (diff.stdout + untracked.stdout).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.strict and _uncommitted():
        raise SystemExit("explore/data changed. Commit it before pushing.")
    ok, summary = _pytest()
    if not ok:
        if not args.strict:
            subprocess.run(
                [sys.executable, "explore/build.py", "--tests", summary],
                cwd=ROOT,
                check=True,
            )
        raise SystemExit("tests failed")
    if args.strict:
        subprocess.run([sys.executable, "explore/build.py", "--check"], cwd=ROOT, check=True)
        return
    subprocess.run(
        [sys.executable, "explore/build.py", "--tests", summary, "--tests-ok"],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
