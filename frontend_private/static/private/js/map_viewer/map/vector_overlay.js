import { DEFAULTS } from '../config.js';

/** Shared, presentation-only renderer; each owner retains its own data lifecycle. */
export function addVectorOverlay(map, { sourceId, layerIds, data, color, fillOpacity = DEFAULTS.GIS_LAYER_RENDER.FILL_OPACITY }) {
    const [fillLayerId, outlineLayerId, lineLayerId, pointLayerId] = layerIds;
    const render = DEFAULTS.GIS_LAYER_RENDER;
    map.addSource(sourceId, {
        type: 'geojson',
        data: data,
        generateId: true
    });
    map.addLayer({
        id: fillLayerId,
        type: 'fill',
        source: sourceId,
        filter: ['==', '$type', 'Polygon'],
        layout: { visibility: 'visible' },
        paint: { 'fill-color': color, 'fill-opacity': fillOpacity }
    });
    map.addLayer({
        id: outlineLayerId,
        type: 'line',
        source: sourceId,
        filter: ['==', '$type', 'Polygon'],
        layout: { visibility: 'visible' },
        paint: {
            'line-color': color,
            'line-width': render.OUTLINE_WIDTH,
            'line-opacity': render.LINE_OPACITY
        }
    });
    map.addLayer({
        id: lineLayerId,
        type: 'line',
        source: sourceId,
        filter: ['==', '$type', 'LineString'],
        layout: { visibility: 'visible', 'line-join': 'round', 'line-cap': 'round' },
        paint: {
            'line-color': color,
            'line-width': render.LINE_WIDTH,
            'line-opacity': render.LINE_OPACITY
        }
    });
    map.addLayer({
        id: pointLayerId,
        type: 'circle',
        source: sourceId,
        filter: ['==', '$type', 'Point'],
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
