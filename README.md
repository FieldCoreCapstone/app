# FieldCore — Field Sensor Dashboard

A web dashboard for monitoring agricultural soil-moisture sensors. Built with Flask and vanilla HTML/CSS/JS, backed by SQLite. Field nodes (Arduino + RFM95W LoRa) report soil moisture, temperature, and battery health to a Raspberry Pi base station, which serves the dashboard.

---

## 👋 If you are Gary McKenzie 

**Start here:** [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md) — explains who did what. The GitHub commit history does **not** accurately reflect contributions, and there are real reasons why. Please read this before evaluating individual contributions.

A few other things worth knowing:

- **The system is real.** It runs on actual hardware: Arduino field nodes in custom waterproof enclosures, talking over LoRa to a Raspberry Pi running this Flask app. There's a lot of work that doesn't show up in code — hardware design, wiring, weatherproofing, field assembly.
- **Test suite:** 214 automated tests pass (`pytest` + `npm test`). See [`tests/README.md`](tests/README.md).
- **Architecture overview:** [`docs/raspberry-pi/ARCHITECTURE.md`](docs/raspberry-pi/ARCHITECTURE.md).
- **API + DB reference:** [`docs/API.md`](docs/API.md), [`docs/DATABASE.md`](docs/DATABASE.md).

---

## Setup

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows

# Install Python dependencies
pip install -r requirements.txt

# (Optional) Install JS dev dependencies for the frontend test suite
npm install
```

## Running

```bash
./start.sh              # debug mode on port 5001
./start.sh --seed       # seed 60 days of data, then start
./start.sh --prod       # production mode (debug off)
./start.sh --help       # all flags
```

Or run directly:

```bash
source venv/bin/activate
python app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

## Seeding Test Data

To populate the database with 60 days of realistic sensor data:

```bash
./start.sh --seed
```

Or via the API (debug mode only):

```bash
curl -X POST http://localhost:5001/api/seed \
  -H "Content-Type: application/json" \
  -d '{"interval_minutes": 30}'
```

## Tests

```bash
pytest                  # 176 Python tests (unit + integration + system)
npm test                # 38 Jest tests for static/js/

pytest -m unit          # subset by layer
pytest -m integration
pytest -m system
```

Manual checklists for the Arduino, the dashboard's UX, and full
sensor-to-screen hardware E2E live in [`tests/manual/`](tests/manual/).

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/nodes` | GET | List all sensor nodes |
| `/api/nodes` | POST | Register a new node |
| `/api/sensor/latest` | GET | Latest reading per node |
| `/api/sensor/history` | GET | Aggregated historical data |
| `/api/sensor/reading` | POST | Ingest a sensor reading |
| `/api/seed` | POST | Reset and seed database (debug only) |

Full reference: [`docs/API.md`](docs/API.md).

## Repo layout

```
prod_project/app/
├── app.py              # Flask entry point + dashboard route
├── backend/            # API blueprints, DB models, scripts
├── pi_software/        # LoRa listener + mock simulator (runs on the Pi)
├── static/, templates/ # dashboard frontend
├── tests/              # pytest + Jest suites + manual checklists
└── docs/               # architecture, API, DB, hardware setup
```
