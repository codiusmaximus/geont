"""Load the repo config."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_category_map() -> dict:
    with open(ROOT / "config" / "category_map.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def subcategory_parents(category_map: dict) -> dict[str, str]:
    """Map each subcategory to its top-level category."""
    parents = {}
    for top, subs in category_map["categories"].items():
        for sub in subs:
            parents[sub] = top
    return parents
