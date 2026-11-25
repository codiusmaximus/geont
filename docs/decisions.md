# Decisions

## 2026-11-25 — Study area is Greater London

The proposal used North West England (NUTS-1 `UKD`). This build uses Greater London (NUTS-1 `UKI`). `config.yaml` is the switch.

The chain is still place → borough → NUTS-3 → NUTS-2 → NUTS-1, so the hard tasks keep a depth of four. There is one NUTS-1 region, so NUTS-1 adjacency is empty. The closed world for later exclusion tasks is this study area.

## 2026-11-25 — Municipalities are London boroughs

`src/data/fetch_gisco.py` reads the GISCO LAU 2021 attribute table (`LAU_RG_01M_2021_4326.csv`). That table has 98,188 units across 34 countries and no `UK` or `GB` code, so zero LAU units fall in Greater London and there is no LAU → NUTS-3 mapping to score. Option 1 in the spec (GISCO LAU) is unavailable. The units are not "wards rather than districts"; for the UK they are missing.

`municipality_source` is `ons_lad`. Boundaries are the ONS Local Authority Districts (December 2021) BGC layer, codes `E09*` (32 boroughs and the City of London). Each borough's parent is the GISCO NUTS-3 polygon that contains the largest share of its area. A parent is rejected when the best share is under 0.5, a second NUTS-3 covers more than 0.2 of the borough, or the second share is at least half the best.

Stored geometries are EPSG:4326. Border distance and shared-boundary length are measured in EPSG:27700. Two regions are adjacent when that shared length is greater than 10 metres, so a corner touch is not adjacency.

`adjacent_to` is stored once, with the lower id as the subject. Symmetry is left to the reasoner.

## 2026-11-25 — Category stand-ins

Overture release `2026-11-18.0` has no `supermarket` category. `grocery_store` and `superstore` map to `Supermarket` only when the name is a large-format chain (Tesco Extra or Superstore, Sainsbury's Superstore, Asda, Morrisons, Aldi, Lidl, Waitrose, Iceland). `college_university` maps to `University` only when the name says university, Imperial College, or the London School of Economics. Whatever the Overture label, a `Hospital` place must contain "hospital" in its name, and names that are a social club, commissioning team, patient panel or charity are dropped. Generic `school` rows must contain "school" or "academy". `college_university` rows that are schools are dropped. Clinic rows must contain "clinic". `train_station` rows must contain "station" or "railway", and names that say tube, DLR, tram, Elizabeth line, locker or tavern are dropped. `gas_station` rows must name a fuel brand or a service or filling station; a petrol station with a shop stays a `PetrolStation`.

Veterinary care, care homes, dental clinics, university housing and tube or light-rail stations are written to `data/processed/borderline.parquet` and are not part of the 300-place sample. The map is `config/category_map.yaml`.

## 2026-11-25 — Difficulty is three dials

The first generator treated easy/medium/hard as one bundle: about 5, 30 or 100 facts, and the extra facts were a random draw from the table. The spec now separates depth, distractor count and order. The pilot presets pin those dials: easy is depth 2, no distractors, logical order; medium is depth 3, 25 distractors, shuffled; hard is depth 4, 100 distractors, shuffled. Distractors are near misses (right category in the wrong region, right region with the wrong category, a chain that stops at the municipality, a similar name, hierarchy facts off the proof). A veterinary clinic may appear as a near miss when the question is about Healthcare. It is `VeterinaryClinic`, under `AnimalServices`, and it is not in the 300-place sample.

Two limits of this study area:

- A category question does not ask for a region, so the depth dial is left unset (`dx` in the task id). Only the distractors and the order change.
- Every top-level category has more than 12 places in Greater London, and a set answer may not be longer than 12. A combined-filter task whose preset asks for depth 4 is generated at the deepest depth that still has 1–12 places. In this build that is depth 3.

Layout (`shuffled` vs `grouped`) and the neighbourhood context are specified and not generated. The one-dial-at-a-time sweep is not generated either. `make tasks` writes the three presets only.
