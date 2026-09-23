import { GIS_GEOMETRY_TYPE_PROPERTY, gisLayerGeometryFilter, prepareGISLayerGeoJSON } from './gis_layer_geometry.js';

describe('GIS Layer geometry filtering', () => {
    it('requires both the rendered geometry family and an enabled original type', () => {
        expect(gisLayerGeometryFilter('Polygon', ['Point', 'MultiPolygon'])).toEqual([
            'all',
            ['==', ['geometry-type'], 'Polygon'],
            ['in', ['get', '__speleodb_geometry_type'], ['literal', ['Point', 'MultiPolygon']]]
        ]);
    });

    it('keeps an empty enabled-type list as a match-nothing condition', () => {
        expect(gisLayerGeometryFilter('LineString', [])).toEqual([
            'all',
            ['==', ['geometry-type'], 'LineString'],
            ['in', ['get', '__speleodb_geometry_type'], ['literal', []]]
        ]);
    });
});

describe('GIS Layer geometry discovery', () => {
    it('discovers exact types in a stable order and preserves coordinates and metadata', () => {
        const geometryTypes = ['MultiPolygon', 'Polygon', 'MultiLineString', 'LineString', 'MultiPoint', 'Point'];
        const input = {
            type: 'FeatureCollection',
            features: geometryTypes.map((type, id) => ({
                type: 'Feature', id,
                properties: { name: type, extended_data: { owner: 'Park' }, [GIS_GEOMETRY_TYPE_PROPERTY]: 'user value' },
                geometry: { type, coordinates: [] }
            }))
        };
        const original = structuredClone(input);
        const { data, geometryTypes: found } = prepareGISLayerGeoJSON(input);

        expect(found).toEqual(geometryTypes.toReversed());
        expect(input).toEqual(original);
        data.features.forEach((feature, index) => {
            expect(feature.id).toBe(index);
            expect(feature.geometry).toBe(input.features[index].geometry);
            expect(feature.properties).toEqual({
                ...input.features[index].properties,
                [GIS_GEOMETRY_TYPE_PROPERTY]: geometryTypes[index]
            });
        });
    });

    it('exposes nested collection members by type with the original feature metadata', () => {
        const point = { type: 'Point', coordinates: [-80, 25] };
        const line = { type: 'LineString', coordinates: [[-80, 25], [-80, 26]] };
        const input = {
            type: 'Feature', id: 'collection', properties: { name: 'Places and paths' },
            geometry: { type: 'GeometryCollection', geometries: [
                point,
                { type: 'GeometryCollection', geometries: [line, point] }
            ] }
        };
        const { data, geometryTypes } = prepareGISLayerGeoJSON(input);
        expect(geometryTypes).toEqual(['Point', 'LineString']);
        expect(data.features.map(feature => feature.geometry)).toEqual([point, line, point]);
        expect(data.features.every(feature => feature.properties.name === input.properties.name)).toBe(true);
        expect(input.geometry.geometries).toHaveLength(2);
    });

    it('supports a bare geometry and omits null or empty collections', () => {
        expect(prepareGISLayerGeoJSON({ type: 'MultiPoint', coordinates: [[1, 2]] }).geometryTypes).toEqual(['MultiPoint']);
        expect(prepareGISLayerGeoJSON({ type: 'Feature', geometry: null, properties: null }).geometryTypes).toEqual([]);
        expect(prepareGISLayerGeoJSON({ type: 'GeometryCollection', geometries: [] })).toEqual({
            data: { type: 'FeatureCollection', features: [] }, geometryTypes: []
        });
    });
});
