import { computeGeoJSONBounds } from './geojson.ts';
import type { Coordinate2D, MapboxGlobal, ViewerGeoJSON } from '../../../../../../ts-types/domain/map-geometry.ts';

class LngLatBoundsMock {
    declare coordinates: Coordinate2D[];
    constructor() { this.coordinates = []; }
    extend(coordinates: Coordinate2D) { this.coordinates.push(coordinates); return this; }
    isEmpty() { return this.coordinates.length === 0; }
}

beforeEach(() => {
    globalThis.mapboxgl = { LngLatBounds: LngLatBoundsMock } as unknown as MapboxGlobal;
});

afterEach(() => {
    delete (globalThis as { mapboxgl?: MapboxGlobal }).mapboxgl;
});

it('uses an existing GeoJSON bbox', () => {
    const bounds = computeGeoJSONBounds({
        type: 'FeatureCollection',
        bbox: [-88, 20, -87, 21],
        features: [],
    });

    expect((bounds as LngLatBoundsMock).coordinates).toEqual([[-88, 20], [-87, 21]]);
});

it('unwraps an existing bbox that crosses the antimeridian', () => {
    const bounds = computeGeoJSONBounds({
        type: 'FeatureCollection',
        bbox: [172, 18, -65, 72],
        features: [],
    });

    expect((bounds as LngLatBoundsMock).coordinates).toEqual([[172, 18], [295, 72]]);
});

it('computes bounds across nested geometry collections', () => {
    const bounds = computeGeoJSONBounds({
        type: 'FeatureCollection',
        features: [{
            type: 'Feature',
            properties: {},
            geometry: {
                type: 'GeometryCollection',
                geometries: [
                    { type: 'Point', coordinates: [-88, 20] },
                    { type: 'LineString', coordinates: [[-87.5, 20.5], [-87, 21]] },
                ],
            },
        }],
    });

    expect((bounds as LngLatBoundsMock).coordinates).toEqual([[-88, 20], [-87, 21]]);
});

it('uses the smallest bbox for geometry crossing the antimeridian', () => {
    const bounds = computeGeoJSONBounds({
        type: 'MultiPoint',
        coordinates: [[-179, 20], [179, 21], [-67, 22]],
    });

    expect((bounds as LngLatBoundsMock).coordinates).toEqual([[179, 20], [293, 22]]);
});

it('preserves the full extent of non-wrapping authoring geometry', () => {
    const bounds = computeGeoJSONBounds({
        type: 'LineString',
        coordinates: [[-170, 0], [0, 0], [170, 0]],
    }, { wrapLongitude: false });

    expect((bounds as LngLatBoundsMock).coordinates).toEqual([[-170, 0], [170, 0]]);
});

it('ignores empty, null and nonfinite coordinates without adding a fallback extent', () => {
    expect(computeGeoJSONBounds(null).isEmpty()).toBe(true);
    expect(computeGeoJSONBounds({ type: 'Point', coordinates: [NaN, 1] }).isEmpty()).toBe(true);
    expect(computeGeoJSONBounds({ type: 'Point', coordinates: [1] }).isEmpty()).toBe(true);
    expect(computeGeoJSONBounds({ type: 'GeometryCollection', geometries: [] }).isEmpty()).toBe(true);
});

it('retains the existing malformed collection failure instead of silently dropping invalid features', () => {
    expect(() => computeGeoJSONBounds({ type: 'FeatureCollection', features: [null] } as unknown as ViewerGeoJSON)).toThrow(TypeError);
});
