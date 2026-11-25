"""Forward-chaining over direct place and region triples.

The closure adds transitive ``within``, ``is_a`` inheritance through
``subclass_of``, and symmetric ``adjacent_to``. Same-level ``within``
links are contradictions when a ``levels`` map is supplied.
"""

from collections import defaultdict
from itertools import combinations


Triple = tuple[str, str, str]


class Reasoner:
    def __init__(self, triples, levels: dict[str, str] | None = None):
        self.facts: set[Triple] = {(str(s), str(p), str(o)) for s, p, o in triples}
        self.levels = dict(levels or {})
        self.contradictions: list[tuple[str, str, str, str]] = []
        self._close()
        self._disjoint()

    def _add(self, triple: Triple) -> bool:
        if triple in self.facts:
            return False
        self.facts.add(triple)
        return True

    def _close(self) -> None:
        changed = True
        while changed:
            changed = False
            changed |= self._transitive_within()
            changed |= self._inherit()
            changed |= self._symmetric_adjacent()

    def _transitive_within(self) -> bool:
        links = [(s, o) for s, p, o in self.facts if p == "within"]
        parents: dict[str, set[str]] = defaultdict(set)
        children: dict[str, set[str]] = defaultdict(set)
        for subject, obj in links:
            parents[subject].add(obj)
            children[obj].add(subject)
        added = False
        for mid, mid_parents in list(parents.items()):
            for child in children.get(mid, ()):
                for parent in mid_parents:
                    added |= self._add((child, "within", parent))
        return added

    def _inherit(self) -> bool:
        subclass = {s: o for s, p, o in self.facts if p == "subclass_of"}
        added = False
        for subject, obj in [(s, o) for s, p, o in self.facts if p == "is_a"]:
            parent = subclass.get(obj)
            if parent is not None:
                added |= self._add((subject, "is_a", parent))
        return added

    def _symmetric_adjacent(self) -> bool:
        added = False
        for subject, obj in [(s, o) for s, p, o in self.facts if p == "adjacent_to"]:
            added |= self._add((obj, "adjacent_to", subject))
        return added

    def _disjoint(self) -> None:
        if not self.levels:
            return
        within: dict[str, set[str]] = defaultdict(set)
        for subject, pred, obj in self.facts:
            if pred == "within" and obj in self.levels:
                within[subject].add(obj)
        found = []
        for entity, regions in within.items():
            by_level: dict[str, list[str]] = defaultdict(list)
            for region in regions:
                by_level[self.levels[region]].append(region)
            for level, ids in by_level.items():
                if len(ids) < 2:
                    continue
                for left, right in combinations(sorted(ids), 2):
                    found.append((entity, level, left, right))
        self.contradictions = sorted(found)

    def regions_of(self, place: str) -> list[str]:
        return sorted(obj for subject, pred, obj in self.facts if subject == place and pred == "within")

    def region_at(self, place: str, level: str) -> str | None:
        hits = [region for region in self.regions_of(place) if self.levels.get(region) == level]
        if len(hits) == 1:
            return hits[0]
        return None

    def is_instance(self, entity: str, cls: str) -> bool | None:
        """True or False when the entity has a type. None when it has none."""
        types = [obj for subject, pred, obj in self.facts if subject == entity and pred == "is_a"]
        if cls in types:
            return True
        if types:
            return False
        return None

    def places_in(self, region: str, cls: str) -> list[str]:
        found = []
        for subject, pred, obj in self.facts:
            if pred == "within" and obj == region and self.is_instance(subject, cls) is True:
                found.append(subject)
        return sorted(set(found))

    def adjacent(self, left: str, right: str) -> bool:
        return (left, "adjacent_to", right) in self.facts

    def count(self, region: str, cls: str) -> int:
        return len(self.places_in(region, cls))
