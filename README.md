# FieldCore UI — Field Sensor Dashboard

A web-based dashboard for monitoring agricultural field sensor nodes. Displays real-time sensor data including soil moisture levels, battery status, and temperature readings across a visual field map.

Built with Flask and vanilla HTML/CSS/JS.

## Setup

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
source venv/bin/activate
python app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

## Seeding Test Data

To populate the database with 60 days of realistic sensor data:

```bash
FLASK_DEBUG=1 python -c "from backend.scripts.seed_db import seed_db; seed_db()"
```

Or via the API (debug mode only):

```bash
curl -X POST http://localhost:5001/api/seed -H "Content-Type: application/json" -d '{"interval_minutes": 30}'
```

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
