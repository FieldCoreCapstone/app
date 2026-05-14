/**
 * Load a production JS file (static/js/*.js) into a fresh sandboxed context
 * with jsdom's `document` / `window` available, so its top-level globals
 * (functions, constants) become accessible without adding module.exports
 * to the production code.
 *
 * Each call returns a sandbox object containing every name the script
 * defined. Use it like:
 *
 *   const { loadScript } = require('./_loader');
 *   let scope;
 *   beforeEach(() => { scope = loadScript('static/js/heatmap.js'); });
 *   test('idwInterpolate on a sensor', () => {
 *     expect(scope.idwInterpolate(0, 0, [{x:0,y:0,value:42}], 2)).toBe(42);
 *   });
 *
 * Using a fresh sandbox per test sidesteps "Identifier X has already been
 * declared" errors that bite `vm.runInThisContext` when scripts use `const`
 * at the top level.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const APP_ROOT = path.resolve(__dirname, '..', '..');

function loadScript(relPath) {
    const abs = path.join(APP_ROOT, relPath);
    let src = fs.readFileSync(abs, 'utf8');

    // vm sandboxes don't expose top-level `const`/`let` bindings to the
    // sandbox object — only `var` and function declarations leak through.
    // Rewrite top-level `const`/`let` (column-0 only) to `var` so test
    // code can read constants like MOISTURE_STOPS as scope.MOISTURE_STOPS.
    // Indented `const`/`let` inside functions are untouched.
    src = src.replace(/^(const|let)\s+/gm, 'var ');

    // Build a sandbox seeded with the jsdom globals that the production
    // script may touch. Jest's jsdom environment puts these on the test's
    // global object; we forward them so script code like
    // `document.createElement('canvas')` works inside the sandbox.
    // Minimal Leaflet stub — main.js builds a MapControlPanel class at load
    // time via L.Control.extend(). We don't exercise that path here.
    const noop = () => {};
    const leafletStub = {
        Control: { extend: () => function Stub() {} },
        DomUtil: { create: () => ({}) },
        DomEvent: { disableClickPropagation: noop, disableScrollPropagation: noop },
        map: () => ({ on: noop, off: noop, addLayer: noop, removeLayer: noop }),
        tileLayer: () => ({ addTo: noop }),
        circleMarker: () => ({ addTo: noop, on: noop, bindPopup: noop }),
        imageOverlay: () => ({ addTo: noop, remove: noop }),
        rectangle: () => ({ addTo: noop, remove: noop }),
        latLngBounds: () => ({ extend: noop }),
    };

    const sandbox = {
        document: global.document,
        window: global.window,
        navigator: global.navigator,
        Math: Math,
        Number: Number,
        String: String,
        Array: Array,
        Object: Object,
        Boolean: Boolean,
        JSON: JSON,
        console: console,
        setTimeout: setTimeout,
        clearTimeout: clearTimeout,
        setInterval: setInterval,
        clearInterval: clearInterval,
        fetch: () => Promise.resolve({ json: () => Promise.resolve([]) }),
        AbortController: global.AbortController,
        L: leafletStub,
        Chart: function ChartStub() { return { destroy: noop, update: noop }; },
    };
    vm.createContext(sandbox);
    vm.runInContext(src, sandbox, { filename: relPath });
    return sandbox;
}

module.exports = { loadScript, APP_ROOT };
