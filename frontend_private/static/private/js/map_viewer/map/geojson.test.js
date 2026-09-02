import { computeGeoJSONBounds } from './geojson.js';

class LngLatBoundsMock {
    constructor() { this.coordinates = []; }
    extend(coordinates) { this.coordinates.push(coordinates); return this; }
    isEmpty() { return this.coordinates.length === 0; }
}

beforeEach(() => {
    globalThis.mapboxgl = { LngLatBounds: LngLatBoundsMock };
});

afterEach(() => {
    delete globalThis.mapboxgl;
});

it('uses an existing GeoJSON bbox', () => {
    const bounds = computeGeoJSONBounds({
        type: 'FeatureCollection',
        bbox: [-88, 20, -87, 21],
        features: [],
    });

    expect(bounds.coordinates).toEqual([[-88, 20], [-87, 21]]);
});

it('unwraps an existing bbox that crosses the antimeridian', () => {
    const bounds = computeGeoJSONBounds({
        type: 'FeatureCollection',
        bbox: [172, 18, -65, 72],
        features: [],
    });

    expect(bounds.coordinates).toEqual([[172, 18], [295, 72]]);
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

    expect(bounds.coordinates).toEqual([[-88, 20], [-87, 21]]);
});

it('uses the smallest bbox for geometry crossing the antimeridian', () => {
    const bounds = computeGeoJSONBounds({
        type: 'MultiPoint',
        coordinates: [[-179, 20], [179, 21], [-67, 22]],
    });

    expect(bounds.coordinates).toEqual([[179, 20], [293, 22]]);
});
