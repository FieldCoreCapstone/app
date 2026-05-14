# FieldCore Tests

How to run, what's where, and how this maps to the Testing Plan.

## Quick start

From `prod_project/app/`:

```bash
# Python: 176 tests across unit / integration / system layers
pytest

# Frontend: 38 Jest tests for static/js/heatmap.js and static/js/main.js helpers
npm install        # first time only
npm test
```

That's the whole automated suite — **214 tests, runs in a few seconds**.

## Run by layer

```bash
pytest -m unit          # fast, isolated tests of a single function or module
pytest -m integration   # CSV→DB, API→DB→API, seed→dashboard
pytest -m system        # start.sh, env vars, full smoke test
```

## Layout

```
prod_project/app/
├── tests/
│   ├── test_api.py              # legacy: Flask API tests (kept in place)
│   ├── ui_tests.py              # legacy: dashboard HTML rendering tests
│   ├── conftest.py              # Flask test client backed by tmp_path DB
│   ├── unit/
│   │   ├── db/                  # backend/models/database.py + seed_db
│   │   └── processing/          # app.py helpers (normalize, classify)
│   ├── integration/             # cross-layer roundtrips
│   ├── system/                  # start.sh, env vars, smoke
│   ├── frontend/                # Jest tests for static/js/
│   │   ├── _loader.js           # vm-based loader for prod JS globals
│   │   ├── helpers.test.js
│   │   └── heatmap.test.js
│   └── manual/                  # checklists for what can't be automated
│       ├── ARDUINO_TESTS.md
│       ├── DASHBOARD_USABILITY.md
│       └── HARDWARE_E2E.md
├── pi_software/tests/           # services/reading_processor, mock_simulator
└── pyproject.toml               # pytest markers + import mode config
```

## Manual checklists

The Arduino, the dashboard's user-facing usability, and the full
sensor→dashboard hardware path are tested by hand. Open the relevant
file under `tests/manual/`, fill in the checkboxes as you go, and
commit the result with the tester's name.

