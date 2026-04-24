# FieldCore API

The Flask application exposes JSON endpoints consumed by the Jinja2/vanilla JS dashboard frontend.

## Base URL

`http://localhost:5001/api`

## Error Responses

All errors return JSON with an `error` field:

```json
{"error": "Description of what went wrong"}
```

Common status codes: `400` (bad input), `404` (not found), `409` (duplicate), `403` (forbidden), `500` (server error).

## Endpoints

### 1. Health Check

- **Endpoint:** `GET /api/health`
- **Response:** `{"status": "ok"}`

### 2. List Nodes

- **Endpoint:** `GET /api/nodes`
- **Response:** Array of node objects with `node_id` (integer), `name`, `latitude`, `longitude`, `installed`, `notes`. The `name` field is always present (auto-derived if not supplied at creation time).

### 3. Create Node

- **Endpoint:** `POST /api/nodes`
- **Body:**

```json
{"node_id": 1, "latitude": 38.94, "longitude": -92.32}
```

- **Validation:**
  - `node_id`: Required. Positive JSON integer (`>= 1`). Stringified integers (`"1"`) are rejected with 400.
  - `name`: Optional. When omitted, defaults to `field_{node_id}` (e.g. `field_1`). 1-100 characters when supplied.
  - `latitude`, `longitude`: Required. Must be valid numbers.
  - `installed` (optional): Date string (e.g., `"2025-12-01"`).
  - `notes` (optional): Free-text string.
- **Response:** Created node object (`201`). The `name` field is always included in the response.
- **Errors:** `400` (missing/invalid fields), `409` (duplicate node_id)

### 4. Get Live Map Data

Returns the latest reading for every registered node.

- **Endpoint:** `GET /api/sensor/latest`
- **Response:** Array of objects with `node_id` (integer), `name`, `latitude`, `longitude`, `temperature`, `moisture`, `battery`, `signal_rssi`, `timestamp`. `moisture` is an integer percent (0-100).

### 5. Get Historical Trends

Returns aggregated data for charts based on a selected time range.

- **Endpoint:** `GET /api/sensor/history`
- **Query Parameters:**
  - `range` (optional, default `7d`): `15m` | `1h` | `12h` | `24h` | `7d` | `1m` | `3m`
  - `node_id` (optional): Filter by specific node. Positive integer (query strings are parsed as integers; `?node_id=abc` returns 400).
- **Response:** Array of objects with `node_id` (integer), `name`, `period`, `avg_temperature`, `avg_moisture`, `avg_battery`, `sample_count`. The `name` field comes from a JOIN with the nodes table so the frontend chart legend can render `field_N` directly.
- **Aggregation:** `15m` and `1h` group by minute; `12h`, `24h`, and `7d` group by hour; `1m` and `3m` group by day.

### 6. Ingest Sensor Reading

Receive a sensor reading from the receiving station or hardware simulator.

- **Endpoint:** `POST /api/sensor/reading`
- **Body:**

```json
{"node_id": 1, "moisture": 62, "temperature": 22.5}
```

- **Optional fields:** `battery` (integer), `signal_rssi` (integer)
- **Validation:** `node_id` must be a positive JSON integer (stringified integers are rejected). `moisture` and `battery` must be integers; `temperature` must be a number. The `node_id` must reference an existing node.
- **Response:** `{"id": 1, "status": "ok"}` (`201`)
- **Errors:** `400` (missing/invalid fields), `404` (unknown node_id)

### 7. Seed Database (Debug Only)

Wipe and repopulate the database with 60 days of test data.

- **Endpoint:** `POST /api/seed`
- **Body:** `{"interval_minutes": 30}` (accepts `15` or `30`)
- **Response:** `{"status": "success", "message": "..."}`
- **Note:** Only available when `FLASK_DEBUG=1`. Returns `403` in production mode.
- **Live reseed:** You can call this while the dashboard is running. The dashboard will pick up the new data on its next auto-refresh (every 3 seconds), or click any range chip in the chart card to refresh the chart immediately.
- **Example:**

```bash
curl -X POST http://localhost:5001/api/seed -H "Content-Type: application/json" -d '{"interval_minutes": 30}'
```
