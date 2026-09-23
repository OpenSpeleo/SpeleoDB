import { DEFAULTS } from '../config.js';

/** Thin shared overview strokes with each renderer's existing detail widths. */
export function geoJSONLineWidth(detailWidth, closeWidth = detailWidth, overviewWidthOffset = 0) {
    const render = DEFAULTS.GEOJSON_RENDER;
    return [
        'interpolate', ['linear'], ['zoom'],
        ...render.OVERVIEW_WIDTH_STOPS.flatMap(([zoom, width]) => [zoom, Math.min(width + overviewWidthOffset, detailWidth)]),
        render.DETAIL_ZOOM, detailWidth,
        render.CLOSE_ZOOM, closeWidth,
    ];
}
