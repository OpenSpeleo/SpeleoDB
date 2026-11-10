import type { BBox, Feature } from 'geojson';
import type { JSONObject } from '../../../../../../ts-types/domain/json.ts';
import type { Coordinate2D, DisplayGeometry, DisplayGeometryType, ViewerFeature, ViewerGeoJSON } from '../../../../../../ts-types/domain/map-geometry.ts';
import { prepareGeoJSONBounds, prepareProjectGeoJSON } from './preparation.ts';
import { computeProjectDepthDomain } from './depth.ts';
import { computeGeoJSONBounds } from './geojson.ts';

function feature<Type extends DisplayGeometryType>(type: Type, coordinates: Extract<DisplayGeometry, { type: Type }>['coordinates'], properties: JSONObject = {}): Feature<Extract<DisplayGeometry, { type: Type }>, JSONObject> {
    return { type: 'Feature', geometry: { type, coordinates } as Extract<DisplayGeometry, { type: Type }>, properties };
}

function collection<const Features extends ViewerFeature[], Extra extends { bbox?: BBox; name?: string; custom?: JSONObject } = Record<never, never>>(features: Features, extra: Extra = {} as Extra) {
    return { type: 'FeatureCollection' as const, features, ...extra };
}

const scheduling = { yieldWork: () => new Promise<void>(resolve => setTimeout(resolve, 0)) };

describe('cooperative project preparation', () => {
    it('returns non-collection inputs by identity without adding a domain or snap points', async () => {
        for (const raw of [null, undefined, { type: 'Point', coordinates: [1, 2] }] satisfies (ViewerGeoJSON | null | undefined)[]) {
            const result = await prepareProjectGeoJSON(raw, scheduling);
            expect(result.data).toBe(raw);
            expect(result.domain).toBeNull();
            expect(result.snapPoints).toEqual([]);
            expect(result.boundsCoordinates).toBeNull();
        }
    });

    it('retains point properties and flat coordinate identity while cloning line properties', async () => {
        const point = feature('Point', [1, 2], { name: 'Point' });
        const line = feature('LineString', [[1, 2], [3, 4]], { depth: 10 });
        const raw = collection([point, line]);
        const result = await prepareProjectGeoJSON(raw, scheduling);
        expect(result.data.features[0].properties).toBe(point.properties);
        expect(result.data.features[0].geometry.coordinates).toBe(point.geometry.coordinates);
        expect(result.data.features[1].properties).not.toBe(line.properties);
        expect(result.data.features[1].geometry.coordinates).not.toBe(line.geometry.coordinates);
        expect(result.data.features[1].geometry.coordinates[0]).toBe(line.geometry.coordinates[0]);
    });

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
        const result = await prepareProjectGeoJSON(raw, scheduling);
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

    it.each([{ features: [] }, { features: [feature('LineString', [[0, 0], [1, 1]])] }])('does not invent a depth domain', async ({ features }) => {
        expect((await prepareProjectGeoJSON(collection(features), scheduling)).domain).toBeNull();
    });

    it('handles zero depth and point-only sections like the depth utility', async () => {
        const raw = collection([
            feature('Point', [1, 2], { section: 'point-only', depth: 75 }),
            feature('LineString', [[0, 0], [1, 1]], { depth: 0 }),
        ]);
        const result = await prepareProjectGeoJSON(raw, scheduling);
        expect(result.domain).toEqual(computeProjectDepthDomain(raw));
        expect(result.data.features[1].properties.depth_norm).toBe(0);
    });

    it('yields within a single line before publishing', async () => {
        const yields = vi.fn(scheduling.yieldWork);
        const raw = collection([feature('LineString', Array.from({ length: 128 }, (_, i) => [i / 1000, 1, 20]))]);
        const result = await prepareProjectGeoJSON(raw, { budgetMs: 0, yieldWork: yields });
        expect(yields.mock.calls.length).toBeGreaterThan(1);
        expect(result.data.features[0].geometry.coordinates).toHaveLength(128);
        expect(result.data.features[0].geometry.coordinates.at(-1)).toEqual([0.127, 1, 0]);
        expect(raw.features[0].geometry.coordinates.at(-1)![2]).toBe(20);
    });

    it('cancels at the next yield without mutating the source or returning partial preparation', async () => {
        const raw = collection([feature('LineString', [[1, 2, 3], [4, 5, 6]])]);
        const before = structuredClone(raw);
        let current = true;
        const work = prepareProjectGeoJSON(raw, {
            budgetMs: 0,
            isCurrent: () => current,
            yieldWork: async () => { await scheduling.yieldWork(); current = false; },
        });
        await expect(work).rejects.toMatchObject({ name: 'AbortError' });
        expect(raw).toEqual(before);
        await expect(prepareProjectGeoJSON(raw, { isCurrent: () => false })).rejects.toMatchObject({ name: 'AbortError' });
    });

    it('preserves an authoritative 3D bbox and handles nested coordinate arrays', async () => {
        const raw = collection([feature('MultiPolygon', [[[[1, 2, 3], [4, 5, 6], [1, 2, 3]]]])], { bbox: [172, 18, -20, -65, 72, 0] });
        const result = await prepareProjectGeoJSON(raw, scheduling);
        expect(result.boundsCoordinates).toEqual([[172, 18], [295, 72]]);
        expect(result.data.features[0].geometry.coordinates[0]![0]![1]).toEqual([4, 5, 0]);
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
    ] satisfies ViewerGeoJSON[])('matches synchronous wrapped and non-wrapped bounds for %j', async data => {
        class Bounds {
            coordinates: Coordinate2D[] = [];
            extend(coordinates: Coordinate2D) { this.coordinates.push(coordinates); return this; }
            isEmpty() { return this.coordinates.length === 0; }
        }
        vi.stubGlobal('__mapRenderer', { LngLatBounds: Bounds });
        try {
            for (const wrapLongitude of [true, false]) {
                const options = { ...scheduling, wrapLongitude };
                expect(await prepareGeoJSONBounds(data, options)).toEqual((computeGeoJSONBounds(data, options) as Bounds).coordinates);
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
        const { prepareGISLayerGeoJSONAsync } = await import('./preparation.ts');
        const { prepareGISLayerGeoJSON } = await import('./gis_layer_geometry.ts');
        const raw = collection([{
            type: 'Feature', id: 'multi', properties: { name: 'Imported' },
            geometry: { type: 'GeometryCollection', geometries: [
                { type: 'LineString', coordinates: [[1, 2], [3, 4]] },
                { type: 'GeometryCollection', geometries: [{ type: 'Point', coordinates: [5, 6] }] },
            ] },
        }]);
        const before = structuredClone(raw);
        const prepared = await prepareGISLayerGeoJSONAsync(raw, scheduling);
        expect(prepared).toEqual(prepareGISLayerGeoJSON(raw));
        expect(prepared.data.features[0]!.geometry).toBe(raw.features[0].geometry.geometries[0]);
        expect(raw).toEqual(before);
    });

    it('yields inside a geometry collection and cancels before publication', async () => {
        const { prepareGISLayerGeoJSONAsync } = await import('./preparation.ts');
        let current = true;
        await expect(prepareGISLayerGeoJSONAsync({
            type: 'GeometryCollection', geometries: Array.from({ length: 100 }, (_, i) => ({ type: 'Point', coordinates: [i, 0] })),
        }, { budgetMs: 0, isCurrent: () => current, yieldWork: async () => { await scheduling.yieldWork(); current = false; } }))
            .rejects.toMatchObject({ name: 'AbortError' });
    });
});

it('yields real event-loop turns across simultaneously ready source loads', async () => {
    const yieldWork = vi.fn(scheduling.yieldWork);
    const source = collection([feature('Point', [1, 2])]);
    const pending = Array.from({ length: 20 }, () => prepareProjectGeoJSON(source, { budgetMs: 0, yieldWork }));
    // Every load gives the caller a turn before starting CPU work.
    expect(yieldWork).toHaveBeenCalledTimes(20);
    await Promise.all(pending);
    // Every preparation continues cooperatively after its initial turn.
    expect(yieldWork.mock.calls.length).toBeGreaterThan(20);
});
