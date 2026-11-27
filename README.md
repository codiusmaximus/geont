# geo-ontology-bench

Does giving an LLM a geospatial ontology, and refining that ontology's design, improve its reasoning on geographic tasks? This repo builds a controlled experiment to find out: real UK regions and points of interest, independently computed ground truth, a benchmark of inference tasks, and a pipeline that runs the same tasks through several LLMs with and without different ontology versions.

This README is both the **project proposal** and the **build spec**. Sections marked *Spec* define what the code must do.

---

## 1. Research question

Does refining a geospatial ontology's **format**, **structure** and **layering** improve LLM accuracy on geographic reasoning tasks? How does the effect vary across models, and which setup gives the cheapest, most stable and most reproducible results?

## 2. Core idea

- **The ontology defines the vocabulary:**
  - types: `Municipality`, `NUTS3`, `Supermarket`, `Hospital`, …
  - relations: `is_a`, `within`, `adjacent_to`
  - in richer versions, rules about how those relations behave
- **The data fills those fields for every point, storing direct links only:** place → municipality → NUTS-3 → NUTS-2 → NUTS-1. This forces the model to chain relations to answer anything non-trivial.
- **The tasks need chaining.** "Which healthcare facilities are in region R?" requires the `within` chain *and* the `is_a` chain.
- **What varies:** data and questions stay fixed. Only the ontology changes, from none at all up to full rules, in different formats.

## 3. Experimental design

### 3.1 Ontology conditions

| ID | Content | Formats |
|---|---|---|
| `v0` | No ontology: facts only | plain English |
| `v1` | Facts + definitions block (region levels, relation meanings, full category tree) | plain English, Turtle, JSON |
| `v2` | Facts + definitions + rules block. The English block repeats the v1 definitions, then states the rules. | plain English, Turtle, JSON |
| `v2S` *(optional)* | As v2, plus a structure section: the schema path and a lookup procedure | plain English |
| `v2L` *(later)* | As v2, split into layers: vocabulary / rules / instances | plain English |
| `v2M` *(optional)* | As v2, with facts materialised by the reasoner (closure added) | plain English |

**The ontology block is static.** Each version's ontology block (the TBox) is identical for every task: the full vocabulary, the full category tree and, in v2, all the rules. It is never tailored to the question, since choosing what is relevant is part of the reasoning being measured. Only the facts (the ABox) vary per task, and they are identical across v0, v1 and v2.

**v2 rules:**
1. `within` is transitive.
2. `is_a` inherits upward (a Hospital is a HealthcareFacility).
3. Regions at the same level never overlap. Being within two different regions of the same level is a contradiction.
4. `adjacent_to` is symmetric and **not** transitive.
5. Closed world over the given facts. Anything not stated or derivable is unknown. For exclusion and comparison tasks, the listed places are the complete set of places considered.

Note: Turtle/OWL can't natively express rule 3 (spatial disjointness at the same level). In the Turtle rendering it goes in an `rdfs:comment`. Document this as a format limitation.

### 3.2 Delivery approaches

- **A, facts per task (main):** each task carries its own small, deliberately incomplete fact set, plus the ontology for the condition, passed with the question.
- **B, data lake (comparison, after the Dec 9 meeting):** an agent gets a folder of CSV/RDF files, a README or ontology, and tools. Conditions:
  - B0: raw CSVs
  - B1: CSVs + README
  - B2: CSVs + ontology definitions
  - B3: RDF data + ontology + SPARQL
- **C, reasoner ceiling:** our own rule engine answers each task from the same facts. Expected to score 100% at near-zero cost.

**Build A and C now. B is out of scope for v1 of this repo.**

### 3.3 Difficulty dials

Every task starts from a **proof chain**: the minimal set of facts from which the answer is derivable. Difficulty is then set by independent dials:

| Dial | Values | Notes |
|---|---|---|
| `depth` | 1, 2, 3, 4 hops | set by which region level the question targets |
| `distractors` | 0, 25, 100 facts | drawn as described below |
| `order` | `logical`, `shuffled` | |

**Presets for the pilot:**

| Preset | depth | distractors | order |
|---|---|---|---|
| `easy` | 2 | 0 | logical |
| `medium` | 3 | 25 | shuffled |
| `hard` | 4 | 100 | shuffled |

The preset table in the proposal gave depth as a range (1–2, 2–3, 3–4). This build pins one depth per preset so a task is reproducible. For the full run, vary **one dial at a time** with the others fixed, so results show what makes a task hard. That sweep is not generated yet.

**Distractor types.** Near misses, not random noise:

- right category, wrong region
- right region, wrong category
- dead-end chains (a place whose municipality's parent link is missing)
- similar names
- unrelated hierarchy facts

**Answer size** stays similar across all levels (at most 12 items), so harder tasks do not turn into a test of list length.

**Why distractors:** without them, every place mentioned is in the answer, so a model can score perfectly without reasoning. Real use also never supplies a minimal proof. Because distractors mix selecting facts with reasoning over them, always report results at `distractors = 0` (pure reasoning) separately from results with distractors.

A category question has no region target, so the depth dial does not apply to it. See `docs/decisions.md`.

### 3.4 Layout dial

The same facts can be laid out in two ways, to test whether organisation matters as much as rules:

- `shuffled`: one flat, randomised list of sentences.
- `grouped`: facts organised along the ontology's structure, the region hierarchy first, then places grouped by municipality with their type.

The content and number of facts are identical in both layouts. Layout is applied at render time, to v0, v1 and v2 alike. `render.py` is not built yet, so this dial is specified but not generated.

### 3.5 Context mode (optional)

- `crafted` (default): proof chain plus chosen distractors.
- `neighbourhood`: all facts about the target region and its neighbours, with some links removed so dead ends occur naturally. Not built yet.

### 3.6 Hypotheses

| Mechanism | What the ontology adds | Comparison that tests it | Expected to matter most when |
|---|---|---|---|
| Meaning | how relations behave, category membership | v0 → v1 → v2 | deep chains, ambiguous categories, traps |
| Map | schema path and a lookup procedure | v2 vs v2S | many facts, complex questions |
| Organisation | data laid out along the structure | shuffled vs grouped | many facts |
| Access | querying instead of reading | in-prompt vs B / v2M | very many facts |

The main expected result is a set of curves: **accuracy vs each dial, per condition**, showing where the baseline breaks and which mechanism delays that.

### 3.7 Memorisation control

Each task also exists in an **anonymised** variant: places become `F001…`, regions `U001…`, and the type and relation names stay readable. The answer is mapped through the same anonymisation table.

## 4. Data

### 4.1 Region

- **Country:** UK, using GISCO **NUTS 2021**, which still covers the UK.
- **Study area:** **Greater London** (NUTS-1 `UKI`). Configurable in `config.yaml`.

### 4.2 Sources

- **Regions:** Eurostat GISCO (`gisco-services.ec.europa.eu/distribution/v2/`)
  - NUTS 2021 polygons for levels 0–3 (EPSG:4326 or 3035; use 1:1M resolution)
  - LAU polygons plus the LAU → NUTS-3 correspondence
- **Places:** Overture Maps `places` theme, queried with DuckDB from the public S3 parquet, filtered by the study-area bounding box. Pin the Overture release in config.
- **Municipalities:** ONS Local Authority Districts (December 2021), London boroughs. See `docs/decisions.md`.
- **Licences:** keep attribution for GISCO, ONS and Overture in `DATA_LICENSES.md`.

### 4.3 Open item: the municipality level (resolve first)

GISCO's UK LAU units may be electoral wards (thousands of very small units) rather than local authority districts, and GISCO LAU data is not perfectly integrated with NUTS 2021 (a known-issues file ships with the download).

**Spec:** `fetch_gisco.py` must report how many LAU units fall inside the study area, their naming pattern, and how cleanly they map to NUTS-3. Then pick the municipality level:
- **Option 1:** GISCO LAU, if the mapping is clean and the count is manageable.
- **Option 2:** local authority districts (e.g. from ONS), if LAU = wards.

Record the decision in `config.yaml` (`municipality_source`) and in `docs/decisions.md`.

Decision for Greater London: `ons_lad`. GISCO LAU 2021 contains no UK units, so option 1 is unavailable.

### 4.4 Category hierarchy (5 × 2–3)

| Top level | Subcategories |
|---|---|
| `Retail` | `Supermarket`, `ConvenienceStore` |
| `Mobility` | `TrainStation`, `PetrolStation` |
| `ParcelServices` | `PostOffice`, `ParcelShop`, `ParcelLocker` |
| `Healthcare` | `Hospital`, `Clinic`, `Pharmacy` |
| `Education` | `School`, `University` |
| `AnimalServices` *(borderline only)* | `VeterinaryClinic` |

**Spec:** the mapping from Overture category strings to our subcategories lives in `config/category_map.yaml` and is reviewed by hand. Unmapped categories are dropped. A small set of borderline places is kept with an explicit official classification, so the ontology's definitions decide the answer. Veterinary clinics are `AnimalServices`, not `Healthcare`. Borderline classes appear in the v1/v2 category tree and are used mainly as distractors. They are not part of the 300-place sample.

## 5. Data model (*Spec*)

All processed data goes in `data/processed/` as parquet (geometry as GeoParquet).

**`regions`**

| column | type | notes |
|---|---|---|
| `region_id` | str | NUTS code or municipality code |
| `name` | str | |
| `level` | enum | `NUTS0`, `NUTS1`, `NUTS2`, `NUTS3`, `MUNI` |
| `parent_id` | str \| null | direct parent only |
| `geometry` | polygon | |

**`places`**

| column | type | notes |
|---|---|---|
| `place_id` | str | stable id, e.g. `P0001` |
| `name` | str | |
| `subcategory` | str | from §4.4 |
| `source_category` | str | original Overture category |
| `muni_id` | str | from point-in-polygon |
| `lon`, `lat` | float | |
| `border_dist_m` | float | distance to the nearest municipality border |

**`adjacency`:** `region_a`, `region_b`, `level`. Symmetric, stored once with `region_a < region_b`. Only for regions at the same level. Two regions are adjacent if their shared boundary length is > 0; corner-only contact is **not** adjacency.

**`facts`:** the canonical triple store, used for everything downstream.

| column | type |
|---|---|
| `s` | str (entity id) |
| `p` | enum: `is_a`, `within`, `adjacent_to`, `subclass_of` |
| `o` | str (entity id or class name) |

Facts contain **direct links only**:
- place `within` municipality
- region `within` its direct parent
- place `is_a` its subcategory
- subcategory `subclass_of` its top-level category (the ontology layer)

## 6. Ground truth (*Spec*)

Computed by code only. No LLM involved, and independent of the ontology renderings.

1. **Hierarchy:** from NUTS codes (each code's parent is its prefix) plus the municipality → NUTS-3 mapping.
2. **Places:** point-in-polygon against the municipality polygons. Drop places with `border_dist_m < 50` (configurable).
3. **Adjacency:** from the polygons, as defined in §5.
4. **Sampling:** about 300 places, stratified by subcategory, with a fixed seed.

**Validation (`validate.py`), all must pass:**
- every place has exactly one municipality
- every region except NUTS0 has exactly one parent, and the parent is exactly one level up
- no cycles in `within`
- adjacency is symmetric and same-level only
- every place's subcategory is in the hierarchy
- counts per level and per subcategory are printed in a summary report

## 7. Reasoner (`src/reasoner.py`) (*Spec*)

A small forward-chaining engine over triples. It's used to (a) compute each task's expected answer from the given facts and (b) serve as condition C.

- **Inputs:** a list of triples and a set of rules.
- **Rules:** transitive `within`; `is_a` + `subclass_of` inheritance; symmetric `adjacent_to`; same-level disjointness, which flags contradictions.
- **Output:** the closure, plus any contradictions found.
- **Query helpers:** `regions_of(place)`, `is_instance(entity, class)`, `places_in(region, class)`, `adjacent(a, b)`, `count(region, class)`.

**Cross-check:** for full (non-truncated) fact sets, reasoner answers must equal the geometric ground truth. Add a test for this.

## 8. Tasks (*Spec*)

### 8.1 Task types and rule tags

| Type | Example | Answer type | Rule tags |
|---|---|---|---|
| `lookup` | Is P within M? (fact given) | bool | – |
| `spatial_inference` | Which NUTS-2 is P in? | value | `within_transitive` |
| `category_inference` | Is P a Healthcare facility? | bool | `is_a_inheritance` |
| `combined_filter` | List Healthcare places in R | set | `within_transitive`, `is_a_inheritance` |
| `exclusion` | Education places in the country not in R | set | `within_transitive`, `closed_world` |
| `comparison` | Does A have more ParcelServices places than B? | bool | `within_transitive`, `closed_world` |
| `adjacency_category` | Municipalities adjacent to M with at least one TrainStation | set | `adjacency_symmetric`, `within_transitive` |
| `disjointness` | Can P be in both R1 and R2? | bool | `same_level_disjoint` |
| `not_determinable` | Fact needed for the answer is removed | `CANNOT_DETERMINE` | `closed_world` |
| `contradiction` | Fact set contains a same-level double membership | `CONTRADICTION` | `same_level_disjoint` |
| `adjacency_trap` | A~B, B~C: is A~C? (not stated) | `CANNOT_DETERMINE` | `adjacency_not_transitive` |

Set answers have at most 12 items.

**v1 of the repo implements first:** `spatial_inference`, `category_inference`, `combined_filter`, `not_determinable`. The other types follow.

### 8.2 Generation

1. Select a target from the ground truth. The same target is reused for every preset of that base task.
2. Build the **proof chain** at the preset's depth. Mark these facts as `proof_facts`.
3. Add near-miss distractors (§3.3), or build a neighbourhood context (§3.5). The pilot uses `crafted`.
4. Apply `order` (logical or shuffled). Layout (§3.4) is applied later, at render time.
5. Recompute the answer with the reasoner on the final fact set. If a distractor changed the answer, resample up to 10 times.
6. Keep set answers inside 1–12 items. If a depth cannot, use the deepest depth that can and record that depth on the task.

Special types:

- `not_determinable`: remove the last hop of the chain, and check that the reasoner can no longer name the region.
- `contradiction`: inject one conflicting fact. Not generated yet.

The expected answer is **always** computed by the reasoner on the given facts, never copied from the geometry. Generation is deterministic given `seed`.

### 8.3 Task file format (`tasks/<split>/<task_id>.json`)

```json
{
  "task_id": "combined_filter__d3_x100_shuf__0007",
  "base_id": "combined_filter__0007",
  "type": "combined_filter",
  "preset": "hard",
  "dials": {"depth": 3, "distractors": 100, "order": "shuffled"},
  "context_mode": "crafted",
  "rule_tags": ["within_transitive", "is_a_inheritance"],
  "anonymised": false,
  "question": "Which Healthcare places are within Cumbria?",
  "facts": [["P0142", "within", "E06000063"], ["P0142", "is_a", "Hospital"]],
  "proof_facts": [0, 1],
  "answer_type": "set",
  "answer": ["P0142", "P0201"],
  "seed": 42
}
```

`facts` holds ids only. Rendering to names, and anonymisation, happen at prompt time through `entities.json`. The top-level category facts (`Hospital subclass_of Healthcare`) are **not** in the task facts; they belong to the ontology layer (v1/v2). In v0 the model must rely on its own understanding of the category words.

## 9. Ontology rendering (`src/ontology/render.py`) (*Spec*)

`render(task, version, fmt, layout, anonymised) -> str`

- The **ontology block** comes from `ontologies/<version>/` and is the same for every task (§3.1). v0 has no block.
- The **facts block** is always plain English, in the given `layout`. Format does not change it.
  - `shuffled`: the task's stored order.
  - `grouped`: the region hierarchy first, then places grouped by municipality.
  - `"Royal Hospital is a Hospital."`, `"Royal Hospital is within Carlisle."`
- **Turtle and JSON** are the ontology only, and only when that block is present (v1 and v2). Turtle states the vocabulary and `rdfs:subClassOf` lines. JSON states the same content as `{"s", "p", "o"}` triples. v0 has no triples.

Static ontology text (definitions and rules per version and format) lives in `ontologies/<version>/<fmt>.*`. **The fact content must be identical across formats:** add a test that parses each rendering back into triples and compares them.

### 9.1 Prompt template

```
You are given facts about places and regions{ontology_clause}.
Answer using ONLY the information provided. Do not use outside knowledge.
If the answer cannot be derived, answer "CANNOT_DETERMINE".
If the facts contain a contradiction, answer "CONTRADICTION".

{ontology_block}

Facts:
{facts_block}

Question: {question}

Respond with JSON only: {"answer": <bool | string | list of names | "CANNOT_DETERMINE" | "CONTRADICTION">}
```

## 10. Evaluation (*Spec*)

### 10.1 Runner (`src/eval/run.py`)

- Takes a list of models, conditions, formats, task split and `n_runs` from `config.yaml`.
- Provider-agnostic adapter interface `complete(model, prompt, temperature) -> {text, input_tokens, output_tokens, latency_ms}`. Implement Anthropic and OpenAI first; read keys from the environment.
- **Disk cache** keyed by a hash of (model, prompt, temperature, run_index), so re-scoring never re-calls the API.
- Writes `results/raw/<run_id>.jsonl`: one row per (task, model, condition, format, run), with the response text and usage.
- Temperature configurable (default 0.7, so variance across runs is measurable; also support 0).

### 10.2 Scorer (`src/eval/score.py`)

- Parse JSON robustly (strip code fences). An unparseable response scores 0 and is flagged.
- Normalise names (case, whitespace), map back to ids, then score:
  - **bool / value / special tokens:** exact match
  - **set:** precision, recall, F1, and exact match
- Write `results/scores.parquet`.

### 10.3 Metrics and reports (`src/eval/report.py`)

- accuracy by condition × dial value × model (one curve per dial)
- accuracy at `distractors = 0` versus with distractors, reported separately
- shuffled versus grouped layout, per version
- accuracy by rule tag × condition
- correct-abstention rate (`CANNOT_DETERMINE` / `CONTRADICTION`)
- mean tokens and latency per condition
- variance across runs (std of accuracy per cell)
- real vs anonymised gap

**First chart (pilot):** accuracy vs preset (easy/medium/hard), one line per v0/v2 × shuffled/grouped, one model.

## Explore

`index.html` is a static dashboard: the design, the London map, the task list, and the ontology texts. It fetches small JSON indexes from `explore/data`, plus the task and ontology files beside it. GitHub Pages serves it from the root of `main` (folder `/`, not `/docs`), with no build. `.nojekyll` keeps Pages from running Jekyll over those files. `make explore` rewrites the indexes. `make check` runs the tests and rewrites them. The pre-push hook runs the tests and refuses the push when they fail, when `explore/data` is uncommitted, or when the map and task index do not match a fresh rebuild.

## 11. Repo layout

```
geo-ontology-bench/
  README.md
  config.yaml
  config/category_map.yaml
  docs/decisions.md
  DATA_LICENSES.md
  ontologies/
    v1/{en.md, ontology.ttl, ontology.json}
    v2/{en.md, ontology.ttl, ontology.json}
  src/
    data/fetch_gisco.py
    data/fetch_ons.py
    data/fetch_overture.py
    truth/hierarchy.py
    truth/locate_places.py
    truth/adjacency.py
    truth/validate.py
    reasoner.py
    tasks/generate.py
    tasks/templates/*.py
    ontology/render.py
    eval/run.py
    eval/score.py
    eval/report.py
  data/raw/            (gitignored)
  data/processed/
  tasks/
  results/
  tests/
```

**Stack:** Python 3.11+, geopandas, shapely, pyogrio, duckdb, rdflib, pyyaml, pandas, pytest, matplotlib.

## 12. CLI (*Spec*)

```bash
make data        # fetch GISCO + Overture into data/raw
make truth       # build regions, places, adjacency, facts; run validate
make tasks       # generate the pilot presets, real and anonymised
make pilot       # run v0 vs v2-en on one cheap model, small task subset
make run         # full run from config
make report      # scores + charts
make test
```

## 13. config.yaml (initial)

```yaml
seed: 42
study_area:
  nuts1: UKI            # Greater London
  nuts_year: 2021
municipality_source: ons_lad   # gisco_lau | ons_lad
overture_release: "2026-11-18.0"
places:
  sample_size: 300
  border_buffer_m: 50
tasks:
  types: [spatial_inference, category_inference, combined_filter, not_determinable]
  base_tasks_per_type: 4
  presets:
    easy: {depth: 2, distractors: 0, order: logical}
    medium: {depth: 3, distractors: 25, order: shuffled}
    hard: {depth: 4, distractors: 100, order: shuffled}
  answer_size: {min: 1, max: 12}
  context_mode: crafted
  anonymised: true
conditions:
  - {version: v0, format: en}
  - {version: v1, format: en}
  - {version: v2, format: en}
  - {version: v2, format: ttl}
  - {version: v2, format: json}
models: [TBD-small, TBD-mid, TBD-frontier]
n_runs: 3
temperature: 0.7
```

## 14. Milestones

| Date | Milestone | Done when |
|---|---|---|
| Dec 1 | Data + ground truth | `make truth` passes validation; summary report printed; municipality decision recorded |
| Dec 3 | Ontologies + first tasks + README | 4 task types × 3 difficulties generated; renderings round-trip test passes; repo shared |
| Dec 8 | Pilot | v0 vs v2-en on one model; accuracy-vs-difficulty chart |
| Dec 9 | Meeting | design agreed; then full run, remaining task types, approach B |

## 15. Non-goals for v1

- A complete geospatial ontology or GIS agent
- Approach B (data lake), until agreed in the Dec 9 meeting
- Property-graph format and the layered variant (later)
- Fine-tuning or retrieval pipelines

## 16. Related work

- **GISAgentBench** (arXiv 2608.01645): deterministic, output-based scoring of GIS agents; pre-annotated pitfalls; trajectory analysis as a diagnostic. We borrow deterministic scoring and per-task rule tagging, and add repeated runs.
- **NVIDIA Auto Ontology:** an ontology as a semantic layer for text-to-SQL agents; its evaluation compares the same model with and without the ontology. Related work, not a dependency.
