/**
 * Jest tests for the helper functions in static/js/main.js.
 *
 * Covers: normalizeMoisture, moistureLevel, moistureBarColor,
 *         normalizeCoords, escapeHtml.
 *
 * main.js declares lots of globals and registers DOM event listeners at
 * the bottom (DOMContentLoaded, setInterval). The sandbox approach in
 * _loader.js isolates each test from those side effects.
 */

const { loadScript } = require('./_loader');

let scope;

beforeEach(() => {
    scope = loadScript('static/js/main.js');
});

describe('normalizeMoisture', () => {
    test('passes through values in range', () => {
        expect(scope.normalizeMoisture(0)).toBe(0);
        expect(scope.normalizeMoisture(50)).toBe(50);
        expect(scope.normalizeMoisture(100)).toBe(100);
    });

    test('clamps high values to 100', () => {
        expect(scope.normalizeMoisture(150)).toBe(100);
        expect(scope.normalizeMoisture(700)).toBe(100);
    });

    test('clamps low values to 0', () => {
        expect(scope.normalizeMoisture(-10)).toBe(0);
    });

    test('null and undefined collapse to 0', () => {
        expect(scope.normalizeMoisture(null)).toBe(0);
        expect(scope.normalizeMoisture(undefined)).toBe(0);
    });

    test('rounds floats', () => {
        expect(scope.normalizeMoisture(49.4)).toBe(49);
        expect(scope.normalizeMoisture(49.6)).toBe(50);
    });
});

describe('moistureLevel', () => {
    test.each([
        [100, 'optimal'],
        [60, 'optimal'],   // boundary
        [59, 'good'],
        [40, 'good'],      // boundary
        [39, 'fair'],
        [20, 'fair'],      // boundary
        [19, 'low'],
        [0, 'low'],
    ])('moistureLevel(%i) -> %s', (pct, expected) => {
        expect(scope.moistureLevel(pct)).toBe(expected);
    });
});

describe('moistureBarColor', () => {
    test('returns the right swatch per band', () => {
        expect(scope.moistureBarColor(80)).toBe('#48BB78'); // optimal: green
        expect(scope.moistureBarColor(50)).toBe('#ECC94B'); // good:    yellow
        expect(scope.moistureBarColor(30)).toBe('#ED8936'); // fair:    orange
        expect(scope.moistureBarColor(10)).toBe('#E53E3E'); // low:     red
    });
});

describe('escapeHtml', () => {
    test('escapes angle brackets', () => {
        expect(scope.escapeHtml('<script>alert(1)</script>'))
            .toBe('&lt;script&gt;alert(1)&lt;/script&gt;');
    });

    test('escapes ampersands', () => {
        expect(scope.escapeHtml('a & b')).toBe('a &amp; b');
    });

    test('empty string returns empty string', () => {
        expect(scope.escapeHtml('')).toBe('');
    });

    test('numeric input is stringified, not thrown', () => {
        expect(() => scope.escapeHtml(123)).not.toThrow();
    });
});

describe('normalizeCoords', () => {
    test('empty array returns empty array', () => {
        expect(scope.normalizeCoords([])).toEqual([]);
    });

    test('two distinct points map to [0.1, 0.9] on each axis', () => {
        const readings = [
            { latitude: 37.4, longitude: -91.5 },
            { latitude: 37.5, longitude: -91.4 },
        ];
        const out = scope.normalizeCoords(readings);
        for (const r of out) {
            expect(r.nx).toBeGreaterThanOrEqual(0.1 - 1e-9);
            expect(r.nx).toBeLessThanOrEqual(0.9 + 1e-9);
            expect(r.ny).toBeGreaterThanOrEqual(0.1 - 1e-9);
            expect(r.ny).toBeLessThanOrEqual(0.9 + 1e-9);
        }
    });

    test('extremes map exactly to padding edges', () => {
        const readings = [
            { latitude: 0,  longitude: 0  },
            { latitude: 10, longitude: 10 },
        ];
        const out = scope.normalizeCoords(readings);
        expect(out[0].nx).toBeCloseTo(0.1, 6);
        expect(out[1].nx).toBeCloseTo(0.9, 6);
    });

    test('single point does not throw (division-by-zero guard)', () => {
        const readings = [{ latitude: 37.4, longitude: -91.5 }];
        expect(() => scope.normalizeCoords(readings)).not.toThrow();
    });

    test('original reading fields are preserved on output', () => {
        const readings = [
            { latitude: 0, longitude: 0, name: 'A', moisture: 50 },
            { latitude: 1, longitude: 1, name: 'B', moisture: 80 },
        ];
        const out = scope.normalizeCoords(readings);
        expect(out[0].name).toBe('A');
        expect(out[1].moisture).toBe(80);
    });
});
