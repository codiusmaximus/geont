"""Direct-link triples. Nothing here is inferred."""

import pandas as pd


def build_facts(
    regions: pd.DataFrame,
    places: pd.DataFrame,
    subcategory_parents: dict[str, str],
    adjacency: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for region in regions.itertuples(index=False):
        if region.parent_id is not None and not pd.isna(region.parent_id):
            rows.append((region.region_id, "within", region.parent_id))
    for place in places.itertuples(index=False):
        rows.append((place.place_id, "within", place.muni_id))
        rows.append((place.place_id, "is_a", place.subcategory))
    for subcategory, top in sorted(subcategory_parents.items()):
        rows.append((subcategory, "subclass_of", top))
    for pair in adjacency.itertuples(index=False):
        rows.append((pair.region_a, "adjacent_to", pair.region_b))
    facts = pd.DataFrame(rows, columns=["s", "p", "o"])
    return facts.sort_values(["s", "p", "o"]).reset_index(drop=True)
