/* ── FieldCore Heatmap — IDW Interpolation Engine ──────────────────────── */

/* ── Color stop definitions ──────────────────────────────────────────── */
const MOISTURE_STOPS = [
    { pos: 0.00, r: 229, g: 62,  b: 62  },  // #E53E3E red (low/dry)
    { pos: 0.35, r: 237, g: 137, b: 54  },  // #ED8936 orange (fair)
    { pos: 0.55, r: 236, g: 201, b: 75  },  // #ECC94B yellow (good)
    { pos: 1.00, r: 72,  g: 187, b: 120 },  // #48BB78 green (optimal)
];

const TEMPERATURE_STOPS = [
    { pos: 0.00, r: 66,  g: 153, b: 225 },  // #4299E1 blue (cold)
    { pos: 0.50, r: 236, g: 201, b: 75  },  // #ECC94B yellow (mild)
    { pos: 1.00, r: 229, g: 62,  b: 62  },  // #E53E3E red (hot)
];

const HEATMAP_GRID_SIZE = 100;
const HEATMAP_PADDING = 0.18;
const HEATMAP_MIN_EXTENT = 0.001; // ~100m in degrees
const IDW_POWER = 2;
const HEATMAP_OPACITY = 0.55;

// Absolute normalization ranges
const MOISTURE_RANGE = { min: 0, max: 100 };       // percentage
const TEMPERATURE_RANGE = { min: -10, max: 45 };   // Celsius

/**
 * IDW interpolation at a single point.
 * @param {number} x - x coordinate of the query point
 * @param {number} y - y coordinate of the query point
 * @param {Array<{x: number, y: number, value: number}>} points - data points
 * @param {number} power - IDW power parameter (default 2)
 * @returns {number} interpolated value
 */
function idwInterpolate(x, y, points, power) {
    let numerator = 0;
    let denominator = 0;

    for (const p of points) {
        const dx = x - p.x;
        const dy = y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 1e-10) return p.value; // exactly on a sensor

        const w = 1 / Math.pow(dist, power);
        numerator += w * p.value;
        denominator += w;
    }

    return numerator / denominator;
}

/**
 * Piecewise linear RGB interpolation through color stops.
 * @param {number} t - normalized value 0..1
 * @param {Array<{pos: number, r: number, g: number, b: number}>} stops
 * @returns {{r: number, g: number, b: number}}
 */
function valueToColor(t, stops) {
    t = Math.max(0, Math.min(1, t));

    for (let i = 0; i < stops.length - 1; i++) {
        if (t <= stops[i + 1].pos) {
            const range = stops[i + 1].pos - stops[i].pos;
            const local = (t - stops[i].pos) / range;
            return {
                r: Math.round(stops[i].r + local * (stops[i + 1].r - stops[i].r)),
                g: Math.round(stops[i].g + local * (stops[i + 1].g - stops[i].g)),
                b: Math.round(stops[i].b + local * (stops[i + 1].b - stops[i].b)),
            };
        }
    }

    const last = stops[stops.length - 1];
    return { r: last.r, g: last.g, b: last.b };
}

/**
 * Render an IDW heatmap to an offscreen canvas.
 * Uses absolute normalization so colors match marker semantics.
 *
 * @param {Array} readings - sensor readings from /api/sensor/latest
 * @param {string} metric - 'moisture' or 'temperature'
 * @param {number} [gridSize=100] - grid resolution
 * @returns {{dataUrl: string, min: number, max: number, bounds: {south: number, west: number, north: number, east: number}}|null}
 */
function renderHeatmapCanvas(readings, metric, gridSize) {
    gridSize = gridSize || HEATMAP_GRID_SIZE;

    // Filter readings with valid coordinates and metric values
    const valid = readings.filter(r => {
        if (r.latitude == null || r.longitude == null) return false;
        if (metric === 'moisture') return r.moisture != null;
        return r.temperature != null;
    });

    if (valid.length < 2) return null; // need at least 2 points for meaningful interpolation

    // Extract metric values and normalize moisture to percentage
    const points = valid.map(r => ({
        x: r.latitude,
        y: r.longitude,
        value: metric === 'moisture'
            ? Math.max(0, Math.min(100, Math.round((r.moisture / 700) * 100)))
            : r.temperature,
    }));

    // Compute actual data range for legend
    const values = points.map(p => p.value);
    const dataMin = Math.min(...values);
    const dataMax = Math.max(...values);

    // Compute padded bounding box
    const lats = points.map(p => p.x);
    const lngs = points.map(p => p.y);
    const latMin = Math.min(...lats);
    const latMax = Math.max(...lats);
    const lngMin = Math.min(...lngs);
    const lngMax = Math.max(...lngs);

    const latExtent = Math.max(latMax - latMin, HEATMAP_MIN_EXTENT);
    const lngExtent = Math.max(lngMax - lngMin, HEATMAP_MIN_EXTENT);
    const latPad = latExtent * HEATMAP_PADDING;
    const lngPad = lngExtent * HEATMAP_PADDING;

    const bounds = {
        south: latMin - latPad,
        north: latMax + latPad,
        west:  lngMin - lngPad,
        east:  lngMax + lngPad,
    };

    // Absolute normalization range for color mapping
    const absRange = metric === 'moisture' ? MOISTURE_RANGE : TEMPERATURE_RANGE;
    const stops = metric === 'moisture' ? MOISTURE_STOPS : TEMPERATURE_STOPS;

    // Create offscreen canvas
    const canvas = document.createElement('canvas');
    canvas.width = gridSize;
    canvas.height = gridSize;
    const ctx = canvas.getContext('2d');
    const imageData = ctx.createImageData(gridSize, gridSize);
    const data = imageData.data;

    const totalLat = bounds.north - bounds.south;
    const totalLng = bounds.east - bounds.west;

    for (let row = 0; row < gridSize; row++) {
        for (let col = 0; col < gridSize; col++) {
            // Map grid cell to geographic coordinates
            // Row 0 = north (top), row N = south (bottom)
            const lat = bounds.north - (row / (gridSize - 1)) * totalLat;
            const lng = bounds.west + (col / (gridSize - 1)) * totalLng;

            const val = idwInterpolate(lat, lng, points, IDW_POWER);

            // Normalize to 0..1 using absolute range
            const t = Math.max(0, Math.min(1,
                (val - absRange.min) / (absRange.max - absRange.min)
            ));

            const color = valueToColor(t, stops);

            const idx = (row * gridSize + col) * 4;
            data[idx]     = color.r;
            data[idx + 1] = color.g;
            data[idx + 2] = color.b;
            data[idx + 3] = 255;
        }
    }

    ctx.putImageData(imageData, 0, 0);

    return {
        dataUrl: canvas.toDataURL(),
        min: dataMin,
        max: dataMax,
        bounds: bounds,
    };
}
