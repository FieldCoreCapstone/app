/**
 * Jest tests for static/js/heatmap.js.
 *
 * Covers: idwInterpolate, valueToColor, renderHeatmapCanvas.
 *
 * IDW and color interpolation are pure math; renderHeatmapCanvas exercises
 * the canvas pipeline. We rely on jest-canvas-mock (from package.json
 * setupFiles) to give jsdom's canvas a usable getContext('2d').
 */

const { loadScript } = require('./_loader');

let scope;

beforeEach(() => {
    scope = loadScript('static/js/heatmap.js');
});

describe('idwInterpolate', () => {
    test('exact sensor location returns that sensor value', () => {
        const points = [
            { x: 0, y: 0, value: 42 },
            { x: 10, y: 10, value: 99 },
        ];
        expect(scope.idwInterpolate(0, 0, points, 2)).toBe(42);
        expect(scope.idwInterpolate(10, 10, points, 2)).toBe(99);
    });

    test('midpoint between equal-value sensors returns same value', () => {
        const points = [
            { x: 0, y: 0, value: 50 },
            { x: 10, y: 0, value: 50 },
        ];
        expect(scope.idwInterpolate(5, 0, points, 2)).toBeCloseTo(50, 6);
    });

    test('midpoint between two distinct sensors is the average', () => {
        const points = [
            { x: 0, y: 0, value: 0 },
            { x: 10, y: 0, value: 100 },
        ];
        // Symmetric distance, IDW power 2 → equal weights → average.
        expect(scope.idwInterpolate(5, 0, points, 2)).toBeCloseTo(50, 6);
    });

    test('result is pulled toward the closer sensor', () => {
        const points = [
            { x: 0, y: 0,  value: 0 },
            { x: 10, y: 0, value: 100 },
        ];
        // Query much closer to the second sensor.
        const v = scope.idwInterpolate(9, 0, points, 2);
        expect(v).toBeGreaterThan(50);
    });
});

describe('valueToColor', () => {
    test('t=0 returns first stop color', () => {
        const c = scope.valueToColor(0, scope.MOISTURE_STOPS);
        expect(c).toEqual({ r: 229, g: 62, b: 62 });
    });

    test('t=1 returns last stop color', () => {
        const c = scope.valueToColor(1, scope.MOISTURE_STOPS);
        expect(c).toEqual({ r: 72, g: 187, b: 120 });
    });

    test('t<0 clamps to first stop', () => {
        const c = scope.valueToColor(-0.5, scope.MOISTURE_STOPS);
        expect(c).toEqual({ r: 229, g: 62, b: 62 });
    });

    test('t>1 clamps to last stop', () => {
        const c = scope.valueToColor(2, scope.MOISTURE_STOPS);
        expect(c).toEqual({ r: 72, g: 187, b: 120 });
    });

    test('temperature stops: t=0.5 returns the mid stop', () => {
        const c = scope.valueToColor(0.5, scope.TEMPERATURE_STOPS);
        expect(c).toEqual({ r: 236, g: 201, b: 75 });
    });
});

describe('renderHeatmapCanvas', () => {
    test('fewer than 2 valid readings returns null', () => {
        const result = scope.renderHeatmapCanvas([], 'moisture');
        expect(result).toBeNull();

        const oneReading = [{ latitude: 0, longitude: 0, moisture: 50 }];
        expect(scope.renderHeatmapCanvas(oneReading, 'moisture')).toBeNull();
    });

    test('readings missing coordinates are filtered out', () => {
        const readings = [
            { latitude: 0, longitude: 0, moisture: 30 },
            { latitude: null, longitude: null, moisture: 50 },
        ];
        // After filtering, only 1 valid reading remains → null.
        expect(scope.renderHeatmapCanvas(readings, 'moisture')).toBeNull();
    });

    test('readings missing the metric are filtered out', () => {
        const readings = [
            { latitude: 0, longitude: 0, moisture: 30 },
            { latitude: 1, longitude: 1, moisture: null },
        ];
        // Only one valid → null.
        expect(scope.renderHeatmapCanvas(readings, 'moisture')).toBeNull();
    });

    test('two+ readings return a result object with required keys', () => {
        const readings = [
            { latitude: 37.4, longitude: -91.5, moisture: 30, temperature: 20 },
            { latitude: 37.5, longitude: -91.4, moisture: 80, temperature: 30 },
        ];
        const result = scope.renderHeatmapCanvas(readings, 'moisture');
        expect(result).not.toBeNull();
        expect(result).toHaveProperty('dataUrl');
        expect(result).toHaveProperty('min');
        expect(result).toHaveProperty('max');
        expect(result).toHaveProperty('bounds');
        expect(result.bounds).toHaveProperty('north');
        expect(result.bounds).toHaveProperty('south');
        expect(result.bounds).toHaveProperty('east');
        expect(result.bounds).toHaveProperty('west');
    });

    test('bounds enclose every input coordinate (with padding)', () => {
        const readings = [
            { latitude: 37.4, longitude: -91.5, moisture: 30 },
            { latitude: 37.5, longitude: -91.4, moisture: 80 },
        ];
        const result = scope.renderHeatmapCanvas(readings, 'moisture');
        expect(result.bounds.south).toBeLessThanOrEqual(37.4);
        expect(result.bounds.north).toBeGreaterThanOrEqual(37.5);
        expect(result.bounds.west).toBeLessThanOrEqual(-91.5);
        expect(result.bounds.east).toBeGreaterThanOrEqual(-91.4);
    });

    test('min and max are coherent', () => {
        const readings = [
            { latitude: 37.4, longitude: -91.5, moisture: 30 },
            { latitude: 37.5, longitude: -91.4, moisture: 80 },
        ];
        const result = scope.renderHeatmapCanvas(readings, 'moisture');
        expect(result.min).toBeLessThanOrEqual(result.max);
    });
});
