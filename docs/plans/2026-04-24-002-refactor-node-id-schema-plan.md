---
title: "refactor: Switch nodes to integer id + derived field_{id} name"
type: refactor
status: completed
date: 2026-04-24
---

# refactor: Switch nodes to integer id + derived field_{id} name

## Overview

Simplify node identity. Today `nodes.node_id` is a `TEXT` primary key with mixed shapes (`"1"` from the Arduino, `"FIELD_01"`, `"BARN_13"` from the seed). The refactor makes the column an explicit integer (`nodes.id INTEGER PRIMARY KEY`) and turns the human-readable label into a derived default (`name = f"field_{id}"`). No UI for renaming, no prefix column, no groups.

Strategy is **wipe-and-reseed** — no migration of existing DB data. The Arduino wire format doesn't change (it already sends an integer in CSV position 0).

## Problem Frame

Mixed ID shapes created real friction during the graph view cleanup: the Arduino sends `1`, the seed inserts `FIELD_01`, the tests depend on `TEST_01`, and the FK between tables is typed `TEXT` to tolerate all of them. Every time a new node joins the system we invent a string convention by hand. The operator wants a bounded "thing that just works": pure integer identity, auto-named in the `field_N` pattern, no UI surface to manage it.

## Requirements Trace

- **R1.** `nodes` table: the PK is `id INTEGER PRIMARY KEY` (rowid alias, explicit at insert, no AUTOINCREMENT). `name TEXT NOT NULL` is a required but non-key column. `latitude / longitude / installed / notes` retained. The old `node_id TEXT PRIMARY KEY` column is gone.
- **R2.** `readings.node_id` is an `INTEGER` foreign key to `nodes(id)`. Column keeps its `node_id` name (it describes the relationship, not the node's own PK).
- **R3.** When a node is created without an explicit `name`, the backend derives `name = f"field_{id}"`.
- **R4.** Arduino wire format is unchanged — CSV field 0 is still the node's integer ID.
- **R5.** The reading processor parses CSV field 0 as an integer; non-integer values raise `ValueError` at ingest.
- **R6.** `POST /api/nodes` and `POST /api/sensor/reading` accept and validate `node_id` as a positive integer.
- **R7.** Seed script and mock simulator produce 14 nodes numbered `1..14` with names `field_1..field_14` (coordinates preserved from the current seed so map positions stay familiar). The Arduino node keeps `id = 1`.
- **R8.** The dashboard's sensor table displays the node's `name` (not its `id`), so the operator sees `field_1`, `field_2`, … instead of raw integers.
- **R9.** Wipe-and-reseed is acceptable — no migration preservation of existing data.
- **R10.** `/api/sensor/latest` and `/api/sensor/history` keep `node_id` as the JSON field name for the node's identity (wire format unchanged), so the frontend does not need to rename property accessors. Only the backend columns change.
- **R11.** Tests (API, UI, pi_software) all pass after the refactor.
- **R12.** All documentation reflects the new `node_id: integer` contract — `docs/API.md`, `docs/DATABASE.md`, `docs/raspberry-pi/ARCHITECTURE.md`, and `docs/raspberry-pi/SETUP.md`. Grep for `FIELD_01 / Node-00 / TEST_01` across `docs/` returns zero hits after the refactor.

## Scope Boundaries

- No UI for renaming nodes.
- No `prefix` column, no groups, no zones.
- No auto-creation of nodes on first reading from an unknown ID — if a LoRa packet arrives for an unseeded integer, the FK insert into `readings` fails (or the row is orphaned) just like today. Auto-registration is deferred as a follow-up.
- No frontend JSON-field rename on the reads path — the dashboard reads `r.node_id` and will continue to. Only internal SQL columns change.
- Frontend display does change: the sensor table cell switches from `r.node_id` to `r.name` (so operators see `field_1`), and the chart legend picks up the `name` field from the history response. `r.node_id` stays in the JSON wire shape.
- No changes to the Chart.js controls themselves (range chips, metric toggle), the range set, the map heatmap, or the LoRa listener framing. (The listener's `process_reading` call path is touched only for integer parsing; the radio framing is untouched.)
- No autoincrement. IDs are explicit at insert time.
- `node_id` query string on `GET /api/sensor/history?node_id=X` is validated as a positive integer (same rule as POST bodies). Non-numeric values return 400.
- POST bodies accept `node_id` as a JSON integer only. Stringified integers (`"1"`) are rejected with 400. Keeping the rule sharp avoids a silent type-coercion path the tests would have to double-cover.

## Context & Research

### Relevant Code and Patterns

- `backend/scripts/init_db.py` — authoritative `SCHEMA` constant; `init_db()` called on first app boot.
- `backend/models/database.py` — `create_node`, `insert_reading`, `get_latest_readings`, `get_history` (SQL that references `nodes.node_id` needs updating).
- `backend/routes/nodes.py` — POST validates `node_id` against a regex; that regex needs replacing with an integer check. `_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,50}$")` is the current contract.
- `backend/routes/sensors.py` — `POST /api/sensor/reading` validates `node_id` before insert.
- `backend/scripts/seed_db.py` — hand-written list of 14 `(node_id, name, lat, lon, installed, notes)` tuples plus per-node moisture/temperature config.
- `pi_software/services/reading_processor.py` — parses CSV, calls `insert_reading`. Field 0 is parsed via `parts[0].strip()` with no type coercion.
- `pi_software/services/mock_simulator.py` — `MOCK_NODES` list of tuples, each with a string `node_id` in position 0.
- `pi_software/services/db.py` — raw SQL insert path used by `reading_processor`. `insert_reading` and `node_exists` take a `node_id` parameter but don't enforce its type.
- `pi_software/tests/conftest.py` — inlines its own `SCHEMA` string (separate from `backend/scripts/init_db.py`) and seeds `TEST_01`, `FIELD_01`, `"1"`. Needs to mirror the new schema.
- `tests/conftest.py` — calls `init_db()` directly, so the backend test fixture gets the new schema automatically. Tests that seed nodes do so via `POST /api/nodes` or not at all.
- `tests/test_api.py` — `_add_node(client)` helper POSTs a `"Node-001"` string ID; every test using it needs a new integer ID.
- `tests/ui_tests.py` — uses string `"Node-001"`/`"Node-H"` in POSTs and asserts them in rendered HTML.
- `app.py` — `index()` view reads `get_latest_readings()` and builds both a `nodes` list for the map (`{"id": r["node_id"], …}`) and a `table_data` list for the sensor table. The sensor table renders `row.node_id` today; switching to `row.name` gives operators `field_1` instead of `1`.
- `templates/index.html:55` — `<td class="node-id">{{ row.node_id }}</td>`. One-line change.
- `static/js/main.js` — ~15 references to `r.node_id`. With integers in JSON these continue to work as dict keys (JS object keys coerce numbers to strings) and as Chart.js dataset labels.

### Institutional Learnings

- None — `docs/solutions/` still doesn't exist in this repo.

### External References

- Not consulted. SQLite `INTEGER PRIMARY KEY` (alias for rowid) behavior is stable and well-documented; no framework choices to research.

## Key Technical Decisions

- **`INTEGER PRIMARY KEY`, no AUTOINCREMENT.** The caller provides the id on insert. The Arduino's hardware-configured ID drives the value; the operator can also assign ids when registering nodes manually. Using `AUTOINCREMENT` would create impedance — the DB would want to pick an id while the hardware has its own.
- **Name default lives in the application layer, not in the DDL.** SQLite `DEFAULT` expressions can't reference the inserted row's `id`. `create_node(id, name=None, …)` derives `name = name or f"field_{id}"`. `seed_db.py` also writes explicit names (keeps the seed data self-documenting).
- **Wipe-and-reseed is the migration.** No `ALTER TABLE`, no `INSERT INTO … SELECT …` dance. `init_db` creates fresh tables; `seed_db` repopulates with integer IDs. On the Pi, the operator runs `python -m backend.scripts.seed_db` after pulling.
- **`readings.node_id` keeps its name.** Changing it to `readings.id` would be actively misleading — the readings table already has its own `id` (autoincrement PK for each reading). The FK column describes *which node the reading belongs to*; `node_id` is exactly right.
- **JSON wire field stays `node_id`.** DB column is `id` per the user's request, but the HTTP responses alias back (`SELECT id AS node_id …`). Every `SELECT` against `nodes` uses explicit projection — no `SELECT *` anywhere in the model. This is load-bearing: `SELECT *` would leak the raw `id` field and break the frontend.
- **Name surfaces everywhere the user looks.** Sensor table cell, table column header, map popups, and chart legend all switch to `name` ("field_1"). The JSON key is still `node_id` for programmatic consumers; humans see `field_1`.
- **`get_history` gains a nodes JOIN.** Adds a `name` field per response row so the chart legend can render `field_N` without an extra round trip. One extra column projection; join cost is trivial since the nodes table is ≤14 rows.
- **Integer validation is positive-only.** `node_id ≥ 1`. Zero and negatives are rejected at the route layer. This matches the Arduino's firmware convention (starts numbering at 1).

## Open Questions

### Resolved During Planning

- **Autoincrement vs explicit PK?** Explicit. See Key Decisions.
- **Where does the name default live?** `create_node()`. See Key Decisions.
- **What about the `name` column in the route POST?** Optional — if caller supplies it, use it; otherwise derive. `name` is removed from the route's `required` list.
- **Does the JSON wire shape change?** `node_id` stays as the JSON field name. `get_history` gains a `name` field per row (new key, additive). No renames.
- **Does the sensor table display change?** Yes — both the SSR template cell and the JS `updateTable` rebuild switch to `row.name` / `r.name`. Column header renames from `Node ID` to `Node`.
- **Does the chart change?** Legend labels switch to `field_N` (dataset label pulls from the new `name` field in the history response). Numeric sort applied so order is 1, 2, 3, …, 14 not 1, 10, 11, …, 2.
- **Does the seed keep 14 nodes?** Yes. Node 1 = Arduino, nodes 2-13 = mock sim targets, node 14 = spare.
- **Does the Arduino firmware need changes?** No.
- **Should POST accept stringified integers?** No. Route rejects `"1"` as 400 (JSON integers only). Query params still accept numeric strings (query strings are always strings by HTTP spec).

### Deferred to Implementation

- **Exact regex or validation style** for the integer check in the route handlers (regex vs `int()` with try/except vs positive-int-specific check). Implementer picks whichever matches the rest of `nodes.py`'s style.
- **Whether `create_node` should also accept `id=None` and auto-assign.** For now it requires an explicit id — matches the Arduino model. If seeded data or manual registration ever wants auto-ids, a small follow-up adds `AUTOINCREMENT` or `MAX(id)+1`.
- **Coordinate default for future auto-registration** (when/if we add it) — not implemented in this plan.

## Implementation Units

- [ ] **Unit 1: Schema + test fixtures (foundation)**

**Goal:** Update the authoritative `SCHEMA` in `backend/scripts/init_db.py` and the mirrored fixture schema in `pi_software/tests/conftest.py` to integer node IDs. Also update `pi_software/tests/conftest.py`'s seeded INSERTs so the test DB carries valid integer-keyed rows.

**Requirements:** R1, R2, R9

**Dependencies:** None — can land first.

**Files:**
- Modify: `backend/scripts/init_db.py`
- Modify: `pi_software/tests/conftest.py`

**Approach:**
- `backend/scripts/init_db.py` SCHEMA: change `node_id TEXT PRIMARY KEY` to `id INTEGER PRIMARY KEY`. Change `readings.node_id` to `INTEGER NOT NULL`. FK changes to `FOREIGN KEY (node_id) REFERENCES nodes(id)`. Keep `idx_readings_node_time` index — column name unchanged.
- `pi_software/tests/conftest.py`: mirror the same schema changes. Rewrite the fixture INSERTs to seed three integer-keyed nodes with `(id, name, latitude, longitude)` columns: `(1, "field_1", 37.42, -91.56)`, `(2, "field_2", 37.42, -91.56)`, `(3, "field_3", 37.42, -91.56)`. These are raw SQL INSERTs — no dependency on `backend.models.database.create_node`. After Unit 1 alone, the pi_software test suite's schema is valid but assertions still reference string IDs; those are fixed in Unit 3.

**Patterns to follow:**
- `INTEGER PRIMARY KEY` without `AUTOINCREMENT`, matching the rowid-alias pattern common across SQLite-backed Python apps.
- Keep whitespace, comment style, and column ordering consistent with the existing block.

**Test scenarios:**
- Test expectation: none — pure DDL change, covered indirectly by downstream units' test suites executing against the new schema.

**Verification:**
- `python -c "from backend.scripts.init_db import init_db; init_db('/tmp/_smoke.db')"` creates the DB without error and `sqlite3 /tmp/_smoke.db '.schema nodes'` shows `id INTEGER PRIMARY KEY`.

---

- [ ] **Unit 2: Backend models + routes + API tests**

**Goal:** Update `backend/models/database.py` queries to read from `nodes.id` (with `AS node_id` in outputs so the JSON wire shape is preserved), add the `field_{id}` name default in `create_node`, tighten POST validation to positive integers, and rewrite the API tests that touch node IDs.

**Requirements:** R3, R6, R8, R10, R11

**Dependencies:** Unit 1 (schema must exist).

**Files:**
- Modify: `backend/models/database.py`
- Modify: `backend/routes/nodes.py`
- Modify: `backend/routes/sensors.py`
- Modify: `app.py`
- Modify: `tests/test_api.py`

**Approach:**
- `backend/models/database.py` — every query that touches `nodes` must use explicit projection with `id AS node_id` (no `SELECT *`):
  - `get_all_nodes`: `SELECT id AS node_id, name, latitude, longitude, installed, notes FROM nodes ORDER BY id`.
  - `get_node(node_id)`: `SELECT id AS node_id, name, latitude, longitude, installed, notes FROM nodes WHERE id = ?`.
  - `create_node(node_id, latitude, longitude, name=None, installed=None, notes=None, db_path=None)` — **note the parameter order**: `latitude` and `longitude` come before `name` because `name` has a default and Python forbids non-default parameters after defaulted ones. All route callers pass by keyword (`create_node(node_id=..., latitude=..., longitude=..., name=...)`) so the reorder is safe. Body: derive `name = name or f"field_{node_id}"`, INSERT into `(id, name, latitude, longitude, installed, notes)`, then re-read the row with the same aliased SELECT used elsewhere.
  - `insert_reading(node_id, …)`: unchanged signature (the FK column stays named `node_id`).
  - `get_latest_readings`: `SELECT n.id AS node_id, n.name, n.latitude, n.longitude, r.temperature, r.moisture, r.battery, r.signal_rssi, r.timestamp FROM nodes n LEFT JOIN readings r ON r.node_id = n.id AND r.id = (…) ORDER BY n.id`.
  - `get_history`: **JOIN nodes to surface the name** so the chart legend can render `field_N`. New SQL shape:
    ```
    SELECT r.node_id,
           n.name,
           {group_expr} AS period,
           ROUND(AVG(r.temperature), 1) AS avg_temperature,
           ROUND(AVG(r.moisture), 0)    AS avg_moisture,
           ROUND(AVG(r.battery), 0)     AS avg_battery,
           COUNT(*)                    AS sample_count
    FROM readings r
    LEFT JOIN nodes n ON n.id = r.node_id
    WHERE r.timestamp >= {since_expr} [AND r.node_id = ?]
    GROUP BY r.node_id, n.name, period
    ORDER BY r.node_id, period
    ```
    Response row gains a `"name"` field alongside `"node_id"`. Frontend will use it as the chart dataset label (see Unit 4).
- `backend/routes/nodes.py`:
  - Remove `"name"` from the `required = [...]` list so nameless POSTs aren't rejected at the route. New required set: `["node_id", "latitude", "longitude"]`.
  - Replace `_NODE_ID_RE` with inline integer validation: `try: node_id = int(data["node_id"]); except (ValueError, TypeError): return 400`. After coercion check `node_id >= 1` or return 400. **Reject stringified integers** — only JSON integers are accepted. If `isinstance(data["node_id"], bool) or not isinstance(data["node_id"], int)`, return 400. This is two conditions, not a helper.
  - `add_node` extracts `name` only if present; validates length when present; passes through to `create_node` otherwise.
  - Duplicate-node branch unchanged — `UNIQUE constraint` on `id` still fires.
- `backend/routes/sensors.py`:
  - `ingest_reading`: same inline integer validation for the POST body's `node_id`.
  - `history` route (`GET /api/sensor/history`): when `request.args.get("node_id")` is present, coerce via `int()` with try/except; reject non-numeric and non-positive values with 400. Query strings are always strings, so this path DOES accept a numeric string like `"1"` (different rule from POST bodies — CLI/query-param consumers expect stringification). Pass the integer to `get_history`.
  - The existing `get_node(data["node_id"])` check now receives an integer; `database.py::get_node` queries `WHERE id = ?`.
- `app.py`:
  - `index()` reads from `get_latest_readings()` which exposes `node_id` as the JSON alias. The sensor `table_data` dict gains `"name": r["name"]` so the template can render it. **All `app.py` changes live in Unit 2** — Unit 4 does not re-edit this file.
- `tests/test_api.py`:
  - `_add_node(client)` helper uses an integer ID (`"node_id": 1`) — body is a JSON integer, not a string.
  - Every test that hard-codes a string node_id (`"Node-001"`, `"NORTH_01"`, etc.) switches to integers.
  - Add `test_create_node_defaults_name_to_field_id`: POST without `name`, assert `body["name"] == "field_<id>"`.
  - Add `test_create_node_rejects_non_integer_id`: POST with `"node_id": "abc"` → 400; with `"node_id": 0` → 400; with `"node_id": -1` → 400.
  - Add `test_create_node_rejects_stringified_integer`: POST with `"node_id": "1"` → 400 (sharp rule for POST bodies).
  - Add `test_history_filter_rejects_non_integer_node_id`: `GET /api/sensor/history?range=24h&node_id=abc` → 400.
  - Update `test_history_filter_by_node`: `node_id=1` in query string; assert returned rows match.
  - Keep `test_history_*` tests structurally intact — only the hard-coded ID values change from `"Node-001"` to `1`.

**Patterns to follow:**
- Validation returns `jsonify({"error": "..."}), 400` consistent with the rest of `nodes.py`.
- SQL projection aliasing (`SELECT id AS node_id`) keeps the wire contract.
- `_add_node(client)` test helper pattern stays — single-line integer swap.

**Test scenarios:**
- *Happy path* — `POST /api/nodes` with `{"node_id": 7, "latitude": 37.4, "longitude": -91.5}` (no name): response has `201`, body includes `"name": "field_7"`, `"node_id": 7`.
- *Happy path* — `POST /api/nodes` with an explicit name keeps the explicit name.
- *Happy path* — `POST /api/sensor/reading` with `{"node_id": 1, "moisture": 60, "temperature": 22.5}` after a node with `id=1` exists returns 201.
- *Edge case* — `POST /api/nodes` with `node_id: 0` returns 400.
- *Edge case* — `POST /api/nodes` with `node_id: "1"` (string form of integer) — acceptable or rejected? Implementer decides; document the choice in the helper. Recommended: accept numeric strings, reject non-numeric strings.
- *Error path* — `POST /api/nodes` with `node_id: "abc"` returns 400 with a clear error.
- *Error path* — `POST /api/nodes` with a duplicate integer id returns 409 (existing behavior).
- *Happy path* — `GET /api/nodes` after inserting three nodes returns them ordered by `id`.
- *Integration* — `GET /api/sensor/latest` after inserting a reading for node `id=1` returns a JSON list where the row has `"node_id": 1, "name": "field_1", "moisture": ...`.
- *Integration* — `GET /api/sensor/history?range=7d` after seeding returns rows with `"node_id": <integer>` (the JSON field retains its name even though the DB column is `nodes.id`).

**Verification:**
- `pytest tests/test_api.py -v` passes end-to-end, including the new cases.
- Manually: start the Flask app against a fresh DB, `curl -X POST /api/nodes -d '{"node_id":1,"latitude":0,"longitude":0}'` returns `name: "field_1"`.

---

- [ ] **Unit 3: Seed + pi_software + their tests**

**Goal:** Propagate the integer-id contract into the seed script, the LoRa/mock ingestion path, and the `pi_software/tests` suite.

**Requirements:** R4, R5, R7, R11

**Dependencies:** Units 1 and 2 (schema and models must be in place).

**Files:**
- Modify: `backend/scripts/seed_db.py`
- Modify: `pi_software/services/reading_processor.py`
- Modify: `pi_software/services/mock_simulator.py`
- Modify: `pi_software/services/db.py`
- Modify: `pi_software/tests/test_reading_processor.py`
- Modify: `pi_software/tests/test_mock_simulator.py`

**Approach:**
- `backend/scripts/seed_db.py`:
  - Fix the header docstring to say `14 nodes` (currently says `13`).
  - Replace the `nodes` list with 14 tuples: `(id, name, latitude, longitude, installed, notes)` where `id ∈ 1..14` and `name = f"field_{id}"`. Coordinates lift straight from the current list so map positions stay stable. The "Arduino Field Node" note moves to node `id=1`'s `notes` field.
  - `node_configs` dict keys become integers (`1..14`). The readings loop iterates the integer keys.
  - The INSERT statement targets `(id, name, latitude, longitude, installed, notes)` instead of `(node_id, …)`.
- `pi_software/services/reading_processor.py`:
  - `node_id = parts[0].strip()` becomes `int(parts[0].strip())` inside a try/except that re-raises as `ValueError(f"Invalid node_id: {parts[0]!r}")`.
  - Positive-integer check after parsing: reject `<= 0`.
  - Update the module docstring example from `"e.g. '1' or 'FIELD_01'"` to `"positive integer matching the node's DB id"`.
  - The return dict's `"node_id"` field now carries an int.
- `pi_software/services/mock_simulator.py`:
  - **Reserve `id=1` for the real Arduino node.** `MOCK_NODES` tuples use integer ids `2..13` (12 nodes) in position 0 — e.g. `(2, 64, 7, 0.0, 5100)`. This mirrors the seed's nodes 2-13 so the mock feeds registered nodes without colliding with the hardware.
  - `generate_reading` unpacks `node_id` as an int; `csv_string = f"{node_id},{moisture}.00,{temp:.2f},{vcc_mv}"` renders correctly.
- `pi_software/services/db.py`:
  - `node_exists(node_id, …)` SQL changes from `SELECT 1 FROM nodes WHERE node_id = ?` to `SELECT 1 FROM nodes WHERE id = ?` — the column was renamed in Unit 1.
  - `insert_reading(node_id, …)` keeps its SQL unchanged (it inserts into `readings.node_id`, which retains its name).
  - The latent `DEFAULT_DB_PATH` bug (points at stale `cap-proj/app/backend/sensors.db`) is **out of scope** — flagged as a follow-up.
- `pi_software/tests/test_reading_processor.py` (enumerate every touched line):
  - `test_valid_csv` line 37: `assert result["node_id"] == "1"` → `== 1`.
  - `test_whitespace_in_csv` line 79: `assert result["node_id"] == "1"` → `== 1`.
  - `test_reading_in_database` line 53: query `WHERE node_id = '1'` → `WHERE node_id = 1` (SQLite coerces either way but the integer form reads correctly).
  - **Delete `test_legacy_string_node_id_still_works`** (line 45) — string IDs are no longer supported.
  - Update any test that seeds a FIELD_01 node in `pi_software/tests/conftest.py`-driven fixtures to reference integer `2` (matches conftest's seeded rows).
  - Add a negative test: `process_reading("abc,45.5,22.5,5100", …)` raises `ValueError` containing "Invalid node_id".
  - Add a negative test: `process_reading("0,45.5,22.5,5100", …)` raises `ValueError` (positive-int rule).
  - Keep the empty-node-id test; its assertion text updates to match the new error message.
- `pi_software/tests/test_mock_simulator.py`:
  - `test_node_id_matches`: `csv_string.startswith(f"{config[0]},")` — works identically for int or str (`f"{2}" == "2"`), but the tuple's first element is now an int.
  - `test_twelve_distinct_nodes`: asserts 12 unique integers.
  - `test_csv_parses_through_process_reading`: replace the hand-built config `("TEST_01", 50, 5, 0, 5100)` with `(2, 50, 5, 0, 5100)` (reserving 1 for Arduino). Assert `result["node_id"] == 2`. Conftest must have node id=2 seeded (see Unit 1).
- `pi_software/tests/conftest.py` (touched in Unit 1): seeded nodes use ids `1, 2, 3` with names `field_1, field_2, field_3`. Node 1 covers Arduino-shaped tests; node 2 covers the mock-simulator integration test.

**Patterns to follow:**
- `mock_simulator.MOCK_NODES` tuple order is preserved; only the first element's type changes.
- Logger format strings (`%s` for node_id) continue to work with integers in CPython.
- The seed's `--interval` CLI flag and 60-day window are unchanged.

**Test scenarios:**
- *Happy path* — `process_reading("1,45.50,22.20,5161", rssi=-67, db_path=test_db)` returns `{"node_id": 1, ...}`.
- *Happy path* — mock simulator's `generate_reading((1, 50, 5, 0, 5100), time.time())` produces a CSV starting with `"1,"`.
- *Error path* — `process_reading("abc,45.5,22.5,5100", ...)` raises `ValueError` with "Invalid node_id" in the message.
- *Error path* — `process_reading("0,45.5,22.5,5100", ...)` raises `ValueError` (positive-int only).
- *Error path* — `process_reading(",45.5,22.5,5100", ...)` raises `ValueError` (empty field).
- *Integration* — running `seed_db.seed_db(interval_minutes=30, db_path=<tmp>)` on a fresh DB followed by `SELECT COUNT(*) FROM nodes` returns 14; `SELECT id, name FROM nodes ORDER BY id` returns `(1, 'field_1'), (2, 'field_2'), …`.

**Verification:**
- `pytest pi_software/tests/ -v` passes.
- `python -m backend.scripts.seed_db --interval 30` against a fresh DB logs `Seeding complete!` and the resulting `sqlite3` query shows integer IDs + `field_N` names.

---

- [ ] **Unit 4: Frontend display + UI tests + docs**

**Goal:** Make the dashboard render the node's `name` (operators see `field_1`) in both the server-side initial paint AND the live 3-second refresh, pick up the name in chart legend, fix UI tests referencing string IDs, and update all doc files that enumerate the old string-id surface.

**Requirements:** R8, R11, R12

**Dependencies:** Units 1-3 (backend + seed + pi must speak integers).

**Files:**
- Modify: `templates/index.html`
- Modify: `static/js/main.js`
- Modify: `tests/ui_tests.py`
- Modify: `docs/API.md`
- Modify: `docs/DATABASE.md`
- Modify: `docs/raspberry-pi/ARCHITECTURE.md`
- Modify: `docs/raspberry-pi/SETUP.md`

*(Note: `app.py` is touched by Unit 2 only — the `table_data` dict already gains `"name"` there. This unit relies on that change.)*

**Approach:**
- `templates/index.html`:
  - Line 55 cell: `{{ row.node_id }}` → `{{ row.name }}`.
  - Column header: `Node ID` → `Node` (the cell now shows a name, not a bare id; the header should match).
- `static/js/main.js` — three required changes; the plan's earlier "no changes" claim was wrong:
  1. **`updateTable` (around line 260-263)**: the client-side rebuilt table must read `r.name` (with `r.node_id` as fallback). Change `const safeNodeId = escapeHtml(r.node_id || '');` to a pair — `const safeName = escapeHtml(r.name || r.node_id || '');` for the cell content, `const safeNodeId = escapeHtml(r.node_id || '');` for the row id and scrollToNode anchor. Without this, the server-rendered `field_1` gets overwritten with `1` after the first 3-second refresh.
  2. **`renderChart` `Object.keys(byNode).sort()` (around line 303)**: change to numeric sort: `Object.keys(byNode).sort((a, b) => Number(a) - Number(b))`. Without this, nodes 1-14 render in lexicographic order (1, 10, 11, 12, 13, 14, 2, 3, ...), scrambling legend order and line colors.
  3. **`renderChart` dataset labels**: the chart now gets a `row.name` from the history API (Unit 2 added the JOIN). Build a `nodeName` map from the history data (`nodeNames[row.node_id] = row.name`) inside the grouping loop, then use `label: nodeNames[nodeId] || nodeId` in each dataset. Legend shows `field_1, field_2, ...` instead of `1, 2, ...`.
  4. **`updateLeafletMarkers` `currentIds` Set (around line 509)**: coerce to string — `const currentIds = new Set(readings.map(r => String(r.node_id)));`. Without this, `Object.keys(leafletMarkers)` yields `"1"` but the Set holds integer `1`, so the existence check fails every tick and every marker is deleted + recreated every 3 seconds (visible flicker, and `knownNodeIds` never stabilises).
  5. **Row-id / scrollToNode coupling**: keep `row-${r.node_id}` as the DOM id and the `scrollToNode('${nodeId}')` argument. Only the visible cell content changes to `name`. No changes needed to `buildPopupContent`.
- `tests/ui_tests.py`:
  - Every POST that supplies a string `node_id` (`"Node-001"`, `"Node-H"`, etc.) switches to an integer.
  - Assertions that look for `"Node-001" in _html(resp)` switch to `"field_1" in _html(resp)`.
  - `test_multiple_nodes_appear_in_table`: seed three integer-keyed nodes via `POST /api/nodes` **without supplying `name`** so the derivation is exercised end-to-end; assert `"field_1"`, `"field_2"`, `"field_3"` appear in the rendered HTML.
  - Add `test_node_column_header_is_node`: assert `"<th>Node</th>"` (or equivalent) is present in the rendered header.
- `docs/API.md`:
  - Under `GET /api/nodes` / `GET /api/sensor/latest` / `GET /api/sensor/history`: document `node_id` as integer; note that `name` is always present in responses (auto-derived if not supplied at creation).
  - Under `POST /api/nodes`: body shape becomes `{"node_id": <int>, "latitude": <float>, "longitude": <float>, "name": <optional str>}`. Explicitly document that omitting `name` yields `"field_{id}"` and that the `name` response field is always populated. **Stringified integers are rejected.**
  - Under `POST /api/sensor/reading`: body's `node_id` is a JSON integer.
  - Under `GET /api/sensor/history`: note the new `name` field in each row of the response (from the nodes JOIN).
  - Fix the stale line 55 moisture note (currently claims raw capacitance 0-700) to say integer percent 0-100 — pre-existing drift, cheap to clean up while we're in the file.
  - Example `curl` payloads updated.
- `docs/DATABASE.md`:
  - Update the `nodes` schema table: `node_id TEXT` → `id INTEGER`. Example value changes from `NORTH_01` to `1`.
  - Update the `readings` schema table: FK description points at `nodes(id)`.
- `docs/raspberry-pi/ARCHITECTURE.md`:
  - CSV example `FIELD_01,450,22.5,8.7` → `1,65,22.5,5161` (matches current Arduino output shape too).
  - Packet field table: `node_id | string | ... | FIELD_01` → `node_id | integer | ... | 1`.
  - Any "real hardware node (FIELD_01)" prose → "real hardware node (id=1, name field_1)".
- `docs/raspberry-pi/SETUP.md`:
  - "13 nodes (FIELD_01 is the real hardware node, the rest are mock)" → "14 seeded nodes numbered 1-14 with names field_1 through field_14; node 1 is the real Arduino, nodes 2-13 feed from the mock simulator, node 14 is a spare demo node."

**Patterns to follow:**
- Template already uses `{{ row.name }}` elsewhere — consistent approach.
- API.md request-body / error-message conventions retained.

**Test scenarios:**
- *Integration* — `GET /` after seeding the DB shows `field_1` through `field_14` in the sensor table body. Column header is `Node`.
- *Integration* — `POST /api/nodes {"node_id": 99, "latitude": 0, "longitude": 0}` (no name) followed by `GET /` renders `field_99` in the table body — end-to-end name derivation via the API path.
- *Integration* — `test_multiple_nodes_appear_in_table` creates three nodes via POST without names and asserts all three derived names appear in the rendered HTML.
- *Browser* — open the dashboard, wait 6 seconds, confirm the sensor table still shows `field_N` (not `N`) after multiple 3-second refreshes. This exercises the `updateTable` fix specifically.
- *Browser* — confirm chart legend shows `field_1, field_2, field_3, …` in numeric order (not lexicographic).
- *Browser* — Canvas/Map toggle, heatmap, and chart chips continue to work.

**Verification:**
- `pytest tests/ -v` — all green.
- `grep -rn 'FIELD_01\|Node-00\|TEST_01' tests/ docs/` returns zero hits after the refactor (excluding the plan and brainstorm docs).
- Browser-verified locally against a freshly seeded DB: sensor table shows `field_1 / field_2 / …`, map popups show `field_N`, chart legend shows `field_N` in numeric order.

## System-Wide Impact

- **Interaction graph:** Three writers touch `nodes` — `create_node` via `POST /api/nodes`, seed_db's direct INSERT, and (indirectly) any `INSERT` added for future auto-registration. All three now agree on the integer id format.
- **Error propagation:** `process_reading` raises `ValueError` on malformed node_ids. The LoRa listener's existing catch-and-log pattern (`logger.exception` wrappers) absorbs it the same way it absorbs any other malformed packet. The HTTP routes return `400` for bad integer input.
- **State lifecycle risks:** Wipe-and-reseed is atomic within `seed_db.py`'s transaction. No partial-write risk beyond what exists today.
- **API surface parity:** HTTP response shape unchanged — `node_id` stays as the JSON key for the node's identity. Internal SQL column is `nodes.id`, but this is invisible to external callers.
- **Integration coverage:** Unit tests (API layer) and the pi_software tests together exercise the integer-id path end-to-end. The browser verification step in Unit 4 covers the display change.
- **Unchanged invariants:**
  - Chart.js `/api/sensor/history` row shape (`node_id, period, avg_*, sample_count`).
  - Time-range set (`15m/1h/12h/24h/7d/1m/3m`) and default (`7d`) from the graph view cleanup.
  - Map/heatmap/Canvas/Map toggle behavior.
  - Arduino firmware and LoRa framing.
  - `REFRESH_MS = 3000`.
  - `readings.id` (the reading's own PK) stays an autoincrement integer.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Existing dev DBs on the Pi have string IDs; `git pull` + `systemctl restart` alone would leave stale data and schema mismatch | Rollout sequence above documents `stop fieldcore-lora → seed_db → restart`. Two-command cost. |
| Wipe-and-reseed destroys real Arduino readings collected to date | User-approved. Optional CSV backup step added to the rollout sequence for anyone who wants the pre-refactor data for the capstone report. |
| LoRa packet arrives during the reseed window, hits the FK between DELETE and INSERT of node 1 | `systemctl stop fieldcore-lora` before `seed_db` eliminates the window. If skipped, listener's `logger.exception` wrapper absorbs the IntegrityError. |
| `pi_software/services/db.py` `DEFAULT_DB_PATH` has a latent stale-path bug (points at dead `cap-proj/` tree) | Out of scope. Works on the Pi because systemd sets `FIELDCORE_DB`. Flagged as a follow-up. |
| Frontend assumes `r.node_id` is serialisable as-is; on an integer the value renders as `1` in any `{{ row.node_id }}` spot we missed | Unit 4 enumerates every touched renderer: template cell, JS `updateTable`, JS `renderChart` legend, and Leaflet markers. No other `node_id` display sites remain after the sweep. |
| JS `Object.keys()` + `Set.has()` mismatch between string and integer node_ids | Explicit `String(r.node_id)` coercion wherever the value is used as an object key or Set member (see Unit 4, `updateLeafletMarkers`). |
| Chart legend sorts `Object.keys().sort()` lexicographically so `10` comes before `2` | Unit 4 switches to `sort((a, b) => Number(a) - Number(b))`. |
| Mock simulator id collides with Arduino id=1 | MOCK_NODES uses ids 2-13; id=1 is reserved for hardware. |
| The new positive-integer validation could reject an Arduino firmware that accidentally sends `0` | Arduino's `readings_send.ino` hardcodes `nodeID = 1`. Doc the positive-int expectation in the reading_processor docstring. |

## Documentation / Operational Notes

- **Pi rollout sequence (ordering matters):**
  1. `ssh wex@fieldcorepi1.local`
  2. Optional — back up existing real Arduino readings before the wipe: `sqlite3 ~/app/backend/sensors.db ".mode csv" ".output ~/readings_backup_$(date +%F).csv" "SELECT * FROM readings WHERE node_id = '1'"` (single quotes around `'1'` for today's TEXT schema; run before the git pull).
  3. `sudo systemctl stop fieldcore-lora` — stops the Arduino ingest so no packet hits the DB during reseed.
  4. `cd ~/app && git pull`
  5. `python -m backend.scripts.seed_db` — wipes nodes + readings, inserts integer-keyed seed.
  6. `sudo systemctl restart fieldcore-web fieldcore-lora`
- No migration script — `seed_db.py` IS the migration.
- Docs fanout (Unit 4 covers all of these): `docs/API.md`, `docs/DATABASE.md`, `docs/raspberry-pi/ARCHITECTURE.md`, `docs/raspberry-pi/SETUP.md`. Verification grep broadened to `grep -rn 'FIELD_01\|Node-00\|TEST_01' tests/ docs/`.
- No monitoring changes.
- No feature flag. Single-node kiosk.

## Sources & References

- User conversation on 2026-04-24 establishing the scope and wipe-and-reseed strategy (no separate brainstorm doc).
- Related code: listed in Context & Research.
- Related PRs: [#11 — graph view cleanup](https://github.com/FieldCoreCapstone/app/pull/11) for the prior refactor that touched many of the same files.
- Prior plan (completed): `docs/plans/2026-04-24-001-refactor-graph-view-cleanup-plan.md`.
