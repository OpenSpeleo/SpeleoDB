import { prepareGeoJSONBounds, prepareProjectGeoJSON } from './preparation.js';
import { computeProjectDepthDomain } from './depth.js';
import { computeGeoJSONBounds } from './geojson.js';

function feature(type, coordinates, properties = {}) {
    return { type: 'Feature', geometry: { type, coordinates }, properties };
}

function collection(features, extra = {}) {
    return { type: 'FeatureCollection', features, ...extra };
}

const immediate = { yieldWork: () => Promise.resolve() };

let restoreClock;
function useIncrementingClock() {
    let clock = 0;
    const descriptor = Object.getOwnPropertyDescriptor(performance, 'now');
    // A plain clock avoids millions of retained mock-call records while sorting
    // the large fixture; only yield behavior is under test here.
    Object.defineProperty(performance, 'now', { configurable: true, value: () => ++clock });
    restoreClock = () => {
        if (descriptor) Object.defineProperty(performance, 'now', descriptor);
        else delete performance.now;
    };
}

afterEach(() => {
    restoreClock?.();
    restoreClock = undefined;
    vi.restoreAllMocks();
});

describe('cooperative project preparation', () => {
    it('preserves source, metadata, domain and line depth semantics', async () => {
        const raw = collection([
            feature('Point', [-88, 20, 17], { section_name: 'a', depth: '20 ft' }),
            feature('Point', [-87, 21, 21], { section_name: 'a', Depth: 40 }),
            feature('LineString', [[-88, 20, 9, 3], [-87, 21, 19]], { section_name: 'a' }),
            feature('LineString', [[-87, 21], [-86, 22]], { depth: -10 }),
            feature('LineString', [[-87, 21], [-86, 22]], { depth_val: 123, depth_norm: 1 }),
        ], { name: 'Survey', custom: { author: 'Sample' } });
        raw.features[2].id = 'line-1';
        const before = structuredClone(raw);
        const result = await prepareProjectGeoJSON(raw, immediate);
        expect(raw).toEqual(before);
        expect(result.data).not.toBe(raw);
        expect(result.data.name).toBe('Survey');
        expect(result.data.custom).toEqual(raw.custom);
        expect(result.data.features[2].id).toBe('line-1');
        expect(result.data.features[2].geometry.coordinates).toEqual([[-88, 20, 0], [-87, 21, 0]]);
        expect(result.data.features[2].properties).toMatchObject({ depth_val: 30, depth_norm: 1 });
        expect(result.data.features[3].properties).toMatchObject({ depth_val: -10, depth_norm: 0 });
        expect(result.data.features[4].properties).toEqual({});
        expect(result.domain).toEqual(computeProjectDepthDomain(raw));
        expect(result.boundsCoordinates).toEqual([[-88, 20], [-86, 22]]);
        expect(result.snapPoints[0]).toEqual({ coordinates: [-88, 20], lineName: 'a', type: 'start', lineIndex: 0 });
        expect(result.snapPoints[1]).toEqual({ coordinates: [-87, 21], lineName: 'a', type: 'end', lineIndex: 1 });
    });

    it.each([[], [feature('LineString', [[0, 0], [1, 1]])]])('does not invent a depth domain', async features => {
        expect((await prepareProjectGeoJSON(collection(features), immediate)).domain).toBeNull();
    });

    it('handles zero depth and point-only sections like the depth utility', async () => {
        const raw = collection([
            feature('Point', [1, 2], { section: 'point-only', depth: 75 }),
            feature('LineString', [[0, 0], [1, 1]], { depth: 0 }),
        ]);
        const result = await prepareProjectGeoJSON(raw, immediate);
        expect(result.domain).toEqual(computeProjectDepthDomain(raw));
        expect(result.data.features[1].properties.depth_norm).toBe(0);
    });

    it('yields within a single 100,000-coordinate line before publishing', async () => {
        useIncrementingClock();
        const yields = vi.fn(() => Promise.resolve());
        const raw = collection([feature('LineString', Array.from({ length: 100_000 }, (_, i) => [i / 1000, 1, 20]))]);
        const result = await prepareProjectGeoJSON(raw, { budgetMs: 1000, yieldWork: yields });
        expect(yields.mock.calls.length).toBeGreaterThan(100);
        expect(result.data.features[0].geometry.coordinates).toHaveLength(100_000);
        expect(result.data.features[0].geometry.coordinates.at(-1)).toEqual([99.999, 1, 0]);
        expect(raw.features[0].geometry.coordinates.at(-1)[2]).toBe(20);
    });

    it('cancels at the next yield without mutating the source or returning partial preparation', async () => {
        const raw = collection([feature('LineString', [[1, 2, 3], [4, 5, 6]])]);
        const before = structuredClone(raw);
        let current = true;
        const work = prepareProjectGeoJSON(raw, {
            budgetMs: 0,
            isCurrent: () => current,
            yieldWork: () => { current = false; return Promise.resolve(); },
        });
        await expect(work).rejects.toMatchObject({ name: 'AbortError' });
        expect(raw).toEqual(before);
        await expect(prepareProjectGeoJSON(raw, { isCurrent: () => false })).rejects.toMatchObject({ name: 'AbortError' });
    });

    it('preserves an authoritative 3D bbox and handles nested coordinate arrays', async () => {
        const raw = collection([feature('MultiPolygon', [[[[1, 2, 3], [4, 5, 6], [1, 2, 3]]]])], { bbox: [172, 18, -20, -65, 72, 0] });
        const result = await prepareProjectGeoJSON(raw, immediate);
        expect(result.boundsCoordinates).toEqual([[172, 18], [295, 72]]);
        expect(result.data.features[0].geometry.coordinates[0][0][1]).toEqual([4, 5, 0]);
    });
});

describe('cooperative bounds', () => {
    it.each([
        { type: 'MultiPoint', coordinates: [[-179, 20], [179, 21], [-67, 22]] },
        { type: 'Point', coordinates: [180, 2] },
        { type: 'GeometryCollection', geometries: [
            { type: 'Point', coordinates: [4, 5] },
            { type: 'GeometryCollection', geometries: [{ type: 'LineString', coordinates: [[6, 7], [8, 9]] }] },
        ] },
        collection([feature('LineString', [[10, 20], [10, 21], [10, 21]])]),
        collection([], { bbox: [172, 18, -65, 72] }),
    ])('matches synchronous wrapped and non-wrapped bounds for %j', async data => {
        class Bounds {
            coordinates = [];
            extend(coordinates) { this.coordinates.push(coordinates); }
        }
        vi.stubGlobal('mapboxgl', { LngLatBounds: Bounds });
        try {
            for (const wrapLongitude of [true, false]) {
                const options = { ...immediate, wrapLongitude };
                expect(await prepareGeoJSONBounds(data, options)).toEqual(computeGeoJSONBounds(data, options).coordinates);
            }
        } finally {
            vi.unstubAllGlobals();
        }
    });

    it('returns null for missing, empty and non-finite coordinates', async () => {
        expect(await prepareGeoJSONBounds(null)).toBeNull();
        expect(await prepareGeoJSONBounds(collection([]))).toBeNull();
        expect(await prepareGeoJSONBounds(feature('Point', [NaN, 2]))).toBeNull();
    });
});

describe('cooperative GIS display preparation', () => {
    it('matches the canonical helper for nested collections without copying coordinates', async () => {
        const { prepareGISLayerGeoJSONAsync } = await import('./preparation.js');
        const { prepareGISLayerGeoJSON } = await import('./gis_layer_geometry.js');
        const raw = collection([{
            type: 'Feature', id: 'multi', properties: { name: 'Imported' },
            geometry: { type: 'GeometryCollection', geometries: [
                { type: 'LineString', coordinates: [[1, 2], [3, 4]] },
                { type: 'GeometryCollection', geometries: [{ type: 'Point', coordinates: [5, 6] }] },
            ] },
        }]);
        const before = structuredClone(raw);
        const prepared = await prepareGISLayerGeoJSONAsync(raw, immediate);
        expect(prepared).toEqual(prepareGISLayerGeoJSON(raw));
        expect(prepared.data.features[0].geometry).toBe(raw.features[0].geometry.geometries[0]);
        expect(raw).toEqual(before);
    });

    it('yields inside a geometry collection and cancels before publication', async () => {
        const { prepareGISLayerGeoJSONAsync } = await import('./preparation.js');
        let current = true;
        await expect(prepareGISLayerGeoJSONAsync({
            type: 'GeometryCollection', geometries: Array.from({ length: 100 }, (_, i) => ({ type: 'Point', coordinates: [i, 0] })),
        }, { budgetMs: 0, isCurrent: () => current, yieldWork: async () => { current = false; } }))
            .rejects.toMatchObject({ name: 'AbortError' });
    });
});

it('shares a preparation slice across simultaneously ready source loads', async () => {
    useIncrementingClock();
    const yieldWork = vi.fn(async () => {});
    const source = collection([feature('Point', [1, 2])]);
    const pending = Array.from({ length: 20 }, () => prepareProjectGeoJSON(source, { budgetMs: 20, yieldWork }));
    // Every load gives the caller a turn before starting CPU work.
    expect(yieldWork).toHaveBeenCalledTimes(20);
    await Promise.all(pending);
    // Small individual inputs must not each get a fresh full task allowance.
    expect(yieldWork.mock.calls.length).toBeGreaterThan(20);
});
