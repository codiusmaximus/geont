# Definitions

Types: `NUTS0`, `NUTS1`, `NUTS2`, `NUTS3`, `Municipality`, and the place categories below.

Place categories, each a kind of its group:

- Retail: Supermarket, ConvenienceStore
- Mobility: TrainStation, PetrolStation
- ParcelServices: PostOffice, ParcelShop, ParcelLocker
- Healthcare: Hospital, Clinic, Pharmacy
- Education: School, University
- AnimalServices (borderline, not in the place sample): VeterinaryClinic

Relations:

- `is_a` — a place is an instance of a category.
- `subclass_of` — a category is a kind of a broader category.
- `within` — a place is in a municipality, or a region is in its parent region.
- `adjacent_to` — two regions of the same level share a boundary.

A VeterinaryClinic is an AnimalServices place. It is not a Healthcare facility.

# Rules

1. `within` is transitive.
2. `is_a` inherits upward. A Hospital is a Healthcare facility.
3. Regions at the same level never overlap. Being within two different regions of the same level is a contradiction.
4. `adjacent_to` is symmetric and not transitive.
5. Closed world over the given facts. Anything not stated or derivable is unknown. For exclusion and comparison tasks, the listed places are the complete set.
