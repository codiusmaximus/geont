# Definitions

Same types and relations as v1.

# Rules

1. `within` is transitive.
2. `is_a` inherits upward. A Hospital is a Healthcare facility.
3. Regions at the same level never overlap. Being within two different regions of the same level is a contradiction.
4. `adjacent_to` is symmetric and not transitive.
5. Closed world over the given facts. Anything not stated or derivable is unknown. For exclusion and comparison tasks, the listed places are the complete set.

Rule 3 cannot be written as a native OWL axiom. In the Turtle rendering it is an `rdfs:comment`.
