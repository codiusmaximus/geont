# Definitions

Types: `NUTS0`, `NUTS1`, `NUTS2`, `NUTS3`, `Municipality`, and the place categories below.

Place categories, each a kind of its group:

- Retail: Supermarket, ConvenienceStore
- Mobility: TrainStation, PetrolStation
- ParcelServices: PostOffice, ParcelShop, ParcelLocker
- Healthcare: Hospital, Clinic, Pharmacy
- Education: School, University

Relations:

- `is_a` — a place is an instance of a category.
- `subclass_of` — a category is a kind of a broader category.
- `within` — a place is in a municipality, or a region is in its parent region.
- `adjacent_to` — two regions of the same level share a boundary.

No inference rules are stated in this version.
