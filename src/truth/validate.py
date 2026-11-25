"""Checks from the ground-truth spec. Prints a summary and returns the errors."""

import pandas as pd

LEVELS = ["NUTS0", "NUTS1", "NUTS2", "NUTS3", "MUNI"]


def _isna(value) -> bool:
    return value is None or pd.isna(value)


def validate(
    regions: pd.DataFrame,
    places: pd.DataFrame,
    adjacency: pd.DataFrame,
    facts: pd.DataFrame,
    subcategory_parents: dict[str, str],
) -> tuple[bool, list[str], str]:
    errors: list[str] = []
    if regions["region_id"].duplicated().any():
        errors.append("duplicate region_id")
    if places["place_id"].duplicated().any():
        errors.append("duplicate place_id")

    level_of = dict(zip(regions["region_id"], regions["level"]))
    parent_of = dict(zip(regions["region_id"], regions["parent_id"]))
    for region_id, level in level_of.items():
        parent = parent_of[region_id]
        if level == "NUTS0":
            if not _isna(parent):
                errors.append(f"{region_id} is NUTS0 and has a parent")
            continue
        if _isna(parent):
            errors.append(f"{region_id} has no parent")
            continue
        if parent not in level_of:
            errors.append(f"{region_id} parent {parent} is missing")
            continue
        if LEVELS.index(level) != LEVELS.index(level_of[parent]) + 1:
            errors.append(
                f"{region_id} ({level}) parent {parent} is {level_of[parent]}, not one level up"
            )

    for start in parent_of:
        cursor = start
        chain = []
        while not _isna(cursor):
            if cursor in chain:
                errors.append(f"cycle in within at {start}")
                break
            chain.append(cursor)
            cursor = parent_of.get(cursor)
            if len(chain) > len(LEVELS) + 1:
                errors.append(f"within chain too long from {start}")
                break

    muni_ids = set(regions.loc[regions["level"] == "MUNI", "region_id"])
    if not places["muni_id"].isin(muni_ids).all():
        bad = sorted(set(places.loc[~places["muni_id"].isin(muni_ids), "muni_id"]))
        errors.append(f"places outside a single municipality: {bad}")
    if places["muni_id"].isna().any():
        errors.append("place with no municipality")

    known_subs = set(subcategory_parents)
    unknown = sorted(set(places["subcategory"]) - known_subs)
    if unknown:
        errors.append(f"subcategories outside the hierarchy: {unknown}")

    if not adjacency.empty:
        if (adjacency["region_a"] >= adjacency["region_b"]).any():
            errors.append("adjacency is not stored with region_a < region_b")
        if adjacency.duplicated(["region_a", "region_b"]).any():
            errors.append("duplicate adjacency pair")
        for pair in adjacency.itertuples(index=False):
            if pair.region_a not in level_of or pair.region_b not in level_of:
                errors.append(f"adjacency endpoint missing: {pair.region_a} {pair.region_b}")
                continue
            if level_of[pair.region_a] != level_of[pair.region_b]:
                errors.append(f"adjacency across levels: {pair.region_a} {pair.region_b}")
            if pair.level != level_of[pair.region_a]:
                errors.append(f"adjacency level mismatch: {pair.region_a} {pair.region_b}")

    within = facts.loc[facts["p"] == "within"]
    if within["s"].duplicated().any():
        errors.append("an entity has more than one within fact")
    within_map = dict(zip(within["s"], within["o"]))
    for region_id, parent in parent_of.items():
        if _isna(parent):
            if region_id in within_map:
                errors.append(f"{region_id} should not have a within fact")
        elif within_map.get(region_id) != parent:
            errors.append(f"within fact for {region_id} does not match its parent")
    for place in places.itertuples(index=False):
        if within_map.get(place.place_id) != place.muni_id:
            errors.append(f"within fact for {place.place_id} does not match its municipality")
        is_a = facts.loc[
            (facts["s"] == place.place_id) & (facts["p"] == "is_a"), "o"
        ]
        if list(is_a) != [place.subcategory]:
            errors.append(f"is_a fact for {place.place_id} does not match its subcategory")

    subclass = facts.loc[facts["p"] == "subclass_of", ["s", "o"]]
    expected = {(sub, top) for sub, top in subcategory_parents.items()}
    actual = set(map(tuple, subclass.to_numpy()))
    if actual != expected:
        errors.append("subclass_of facts do not match the category hierarchy")

    adjacent = set(map(tuple, facts.loc[facts["p"] == "adjacent_to", ["s", "o"]].to_numpy()))
    expected_adj = set(map(tuple, adjacency[["region_a", "region_b"]].to_numpy())) if len(adjacency) else set()
    if adjacent != expected_adj:
        errors.append("adjacent_to facts do not match the adjacency table")
    predicates = set(facts["p"].unique())
    unknown_pred = predicates - {"is_a", "within", "adjacent_to", "subclass_of"}
    if unknown_pred:
        errors.append(f"unknown predicates: {sorted(unknown_pred)}")

    lines = ["Ground truth validation: " + ("PASS" if not errors else "FAIL")]
    counts = regions["level"].value_counts()
    level_bits = ", ".join(f"{level}={int(counts.get(level, 0))}" for level in LEVELS)
    lines.append(f"Regions: {level_bits} (total {len(regions)})")
    lines.append(f"Places: {len(places)}")
    place_counts = places["subcategory"].value_counts()
    for subcategory in sorted(subcategory_parents):
        lines.append(f"  {subcategory}: {int(place_counts.get(subcategory, 0))}")
    if len(adjacency):
        adj_counts = adjacency["level"].value_counts()
        adj_bits = ", ".join(f"{level}={int(adj_counts.get(level, 0))}" for level in LEVELS)
    else:
        adj_bits = "none"
    lines.append(f"Adjacency pairs: {adj_bits}")
    fact_counts = facts["p"].value_counts()
    fact_bits = ", ".join(f"{pred}={int(fact_counts.get(pred, 0))}" for pred in sorted(fact_counts.index))
    lines.append(f"Facts: {fact_bits} (total {len(facts)})")
    if errors:
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in errors)
    summary = "\n".join(lines)
    return not errors, errors, summary
