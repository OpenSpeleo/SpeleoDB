import { createVectorOverlayLayers } from '@speleodb/map-viewer';
import { DEFAULTS } from '../config.ts';
import { geoJSONLineWidth } from './line_rendering.ts';
import type { GeometryFilter, OverlayLayer, RenderGeometryType, VectorOverlayMap, ViewerGeoJSON } from '../../../../../../ts-types/domain/map-geometry.ts';

// Geometry families in the same order as the fill, outline, line and point IDs.
export const VECTOR_OVERLAY_GEOMETRY_TYPES: readonly RenderGeometryType[] = Object.freeze(['Polygon', 'Polygon', 'LineString', 'Point']);

/** Shared, presentation-only renderer; each owner retains its own data lifecycle. */
export function addVectorOverlay(map: VectorOverlayMap, {
    sourceId, layerIds, data, color,
    fillOpacity = DEFAULTS.GIS_LAYER_RENDER.FILL_OPACITY,
    filterForGeometry = type => ['==', '$type', type]
}: {
    sourceId: string;
    layerIds: readonly [string, string, string, string];
    data: ViewerGeoJSON;
    color: string;
    fillOpacity?: number;
    filterForGeometry?: (type: RenderGeometryType) => GeometryFilter;
}) {
    const [fillLayerId, outlineLayerId, lineLayerId, pointLayerId] = layerIds;
    const render = DEFAULTS.GIS_LAYER_RENDER;
    map.addSource(sourceId, {
        type: 'geojson',
        data: data,
        generateId: true,
        tolerance: DEFAULTS.GEOJSON_RENDER.TOLERANCE
    });
    const layers = createVectorOverlayLayers({
        sourceId,
        layerIds: { fill: fillLayerId, outline: outlineLayerId, line: lineLayerId, point: pointLayerId },
        color, fillOpacity, lineOpacity: render.LINE_OPACITY,
        outlineWidth: geoJSONLineWidth(render.OUTLINE_WIDTH),
        lineWidth: geoJSONLineWidth(render.LINE_WIDTH),
        outlineLayout: {},
        filterForGeometry: filterForGeometry,
        point: {
            radius: ['interpolate', ['linear'], ['zoom'],
                render.POINT_RADIUS_ZOOM_MIN, render.POINT_RADIUS_MIN,
                render.POINT_RADIUS_ZOOM_MAX, render.POINT_RADIUS_MAX],
            strokeColor: render.POINT_STROKE_COLOR, strokeWidth: render.POINT_STROKE_WIDTH,
        },
    });
    for (const layer of layers) {
        layer.layout = { ...layer.layout, visibility: 'visible' };
        // The options above constrain the shared specs to this app's overlay port.
        map.addLayer(layer as OverlayLayer);
    }
}
