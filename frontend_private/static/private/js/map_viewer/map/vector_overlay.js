import { DEFAULTS } from '../config.js';
import { geoJSONLineWidth } from './line_rendering.js';

// Geometry families in the same order as the fill, outline, line and point IDs.
export const VECTOR_OVERLAY_GEOMETRY_TYPES = Object.freeze(['Polygon', 'Polygon', 'LineString', 'Point']);

/** Shared, presentation-only renderer; each owner retains its own data lifecycle. */
export function addVectorOverlay(map, {
    sourceId, layerIds, data, color,
    fillOpacity = DEFAULTS.GIS_LAYER_RENDER.FILL_OPACITY,
    filterForGeometry = type => ['==', '$type', type]
}) {
    const [fillLayerId, outlineLayerId, lineLayerId, pointLayerId] = layerIds;
    const filters = VECTOR_OVERLAY_GEOMETRY_TYPES.map(filterForGeometry);
    const render = DEFAULTS.GIS_LAYER_RENDER;
    map.addSource(sourceId, {
        type: 'geojson',
        data: data,
        generateId: true,
        tolerance: DEFAULTS.GEOJSON_RENDER.TOLERANCE
    });
    map.addLayer({
        id: fillLayerId,
        type: 'fill',
        source: sourceId,
        filter: filters[0],
        layout: { visibility: 'visible' },
        paint: { 'fill-color': color, 'fill-opacity': fillOpacity }
    });
    map.addLayer({
        id: outlineLayerId,
        type: 'line',
        source: sourceId,
        filter: filters[1],
        layout: { visibility: 'visible' },
        paint: {
            'line-color': color,
            'line-width': geoJSONLineWidth(render.OUTLINE_WIDTH),
            'line-opacity': render.LINE_OPACITY
        }
    });
    map.addLayer({
        id: lineLayerId,
        type: 'line',
        source: sourceId,
        filter: filters[2],
        layout: { visibility: 'visible', 'line-join': 'round', 'line-cap': 'round' },
        paint: {
            'line-color': color,
            'line-width': geoJSONLineWidth(render.LINE_WIDTH),
            'line-opacity': render.LINE_OPACITY
        }
    });
    map.addLayer({
        id: pointLayerId,
        type: 'circle',
        source: sourceId,
        filter: filters[3],
        layout: { visibility: 'visible' },
        paint: {
            'circle-color': color,
            'circle-radius': [
                'interpolate', ['linear'], ['zoom'],
                render.POINT_RADIUS_ZOOM_MIN, render.POINT_RADIUS_MIN,
                render.POINT_RADIUS_ZOOM_MAX, render.POINT_RADIUS_MAX
            ],
            'circle-stroke-color': render.POINT_STROKE_COLOR,
            'circle-stroke-width': render.POINT_STROKE_WIDTH
        }
    });
}
