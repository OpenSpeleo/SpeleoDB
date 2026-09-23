// Mapbox tiles collapse Multi* geometries into Point/LineString/Polygon. Keep
// the original type on display features so those types remain independently
// selectable. The downloaded GeoJSON and its properties are never mutated.
export const GIS_GEOMETRY_TYPE_PROPERTY = '__speleodb_geometry_type';
export const GEOMETRY_TYPES = Object.freeze([
    'Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'
]);

export function prepareGISLayerGeoJSON(geojson) {
    const features = [];
    const found = new Set();

    function appendGeometry(geometry, feature) {
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

export function gisLayerGeometryFilter(geometryType, enabledTypes) {
    return ['all',
        ['==', ['geometry-type'], geometryType],
        ['in', ['get', GIS_GEOMETRY_TYPE_PROPERTY], ['literal', enabledTypes]]
    ];
}
