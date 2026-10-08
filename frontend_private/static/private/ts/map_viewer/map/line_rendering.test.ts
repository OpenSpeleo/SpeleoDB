import { DEFAULTS } from '../config.ts';
import { geoJSONLineWidth } from './line_rendering.ts';

it('preserves ordered overview stops, detail widths and default close width', () => {
    expect(geoJSONLineWidth(5)).toEqual([
        'interpolate', ['linear'], ['zoom'],
        0, 1, 8, 1, 12, 1.5, 14, 2, 16, 5, 18, 5,
    ]);
    expect(geoJSONLineWidth(5, 6, 2)).toEqual([
        'interpolate', ['linear'], ['zoom'],
        0, 3, 8, 3, 12, 3.5, 14, 4, 16, 5, 18, 6,
    ]);
});

it('caps overview widths at detail width without mutating configuration or sharing arrays', () => {
    const original = structuredClone(DEFAULTS.GEOJSON_RENDER.OVERVIEW_WIDTH_STOPS);
    expect(geoJSONLineWidth(0.5, 1)).toEqual([
        'interpolate', ['linear'], ['zoom'],
        0, 0.5, 8, 0.5, 12, 0.5, 14, 0.5, 16, 0.5, 18, 1,
    ]);
    expect(DEFAULTS.GEOJSON_RENDER.OVERVIEW_WIDTH_STOPS).toEqual(original);
    expect(geoJSONLineWidth(5)).not.toBe(geoJSONLineWidth(5));
});
