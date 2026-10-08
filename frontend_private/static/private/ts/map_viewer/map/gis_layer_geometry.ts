// Mapbox tiles collapse Multi* geometries into Point/LineString/Polygon. Keep
// the original type on display features so those types remain independently
// selectable. The downloaded GeoJSON and its properties are never mutated.
export const GIS_GEOMETRY_TYPE_PROPERTY = '__speleodb_geometry_type';
export const GEOMETRY_TYPES: readonly DisplayGeometryType[] = Object.freeze([
    'Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'
]);

export function prepareGISLayerGeoJSON(geojson: ViewerGeoJSON | null | undefined): {
    data: FeatureCollection<DisplayGeometry, JSONObject>;
    geometryTypes: DisplayGeometryType[];
} {
    const features: FeatureCollection<DisplayGeometry, JSONObject>['features'] = [];
    const found = new Set<DisplayGeometryType>();

    function appendGeometry(geometry: Geometry | null | undefined, feature?: ViewerFeature): void {
        if (!geometry) return;
        if (geometry.type === 'GeometryCollection') {
            for (const child of geometry.geometries || []) appendGeometry(child, feature);
        } else if (GEOMETRY_TYPES.includes(geometry.type)) {
            found.add(geometry.type);
            features.push({
                ...feature,
                type: 'Feature',
                properties: { ...feature?.properties, [GIS_GEOMETRY_TYPE_PROPERTY]: geometry.type },
                geometry
            });
        }
    }

    if (geojson?.type === 'FeatureCollection') {
        for (const feature of geojson.features || []) appendGeometry(feature.geometry, feature);
    } else if (geojson?.type === 'Feature') {
        appendGeometry(geojson.geometry, geojson);
    } else {
        appendGeometry(geojson);
    }

    return {
        data: { type: 'FeatureCollection', features },
        geometryTypes: GEOMETRY_TYPES.filter(type => found.has(type))
    };
}

export function gisLayerGeometryFilter(geometryType: RenderGeometryType, enabledTypes: DisplayGeometryType[]): GeometryFilter {
    return ['all',
        ['==', ['geometry-type'], geometryType],
        ['in', ['get', GIS_GEOMETRY_TYPE_PROPERTY], ['literal', enabledTypes]]
    ];
}
import type { FeatureCollection, Geometry } from 'geojson';
import type { JSONObject } from '../../../../../../ts-types/domain/json.ts';
import type { DisplayGeometry, DisplayGeometryType, GeometryFilter, RenderGeometryType, ViewerFeature, ViewerGeoJSON } from '../../../../../../ts-types/domain/map-geometry.ts';
