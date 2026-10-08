import { DEFAULTS } from '../config.ts';
import { addVectorOverlay } from './vector_overlay.ts';
import type { GeometryFilter, OverlayLayer, OverlaySource, RenderGeometryType, VectorOverlayMap, ViewerGeoJSON } from '../../../../../../ts-types/domain/map-geometry.ts';

it('installs the original source once before fill, outline, line and point layers', () => {
    const calls: (['source', string, OverlaySource] | ['layer', OverlayLayer])[] = [];
    const map = {
        addSource: vi.fn((...args: Parameters<VectorOverlayMap['addSource']>) => { calls.push(['source', ...args]); }),
        addLayer: vi.fn((layer: OverlayLayer) => { calls.push(['layer', layer]); }),
    };
    const data: ViewerGeoJSON = { type: 'FeatureCollection', features: [] };
    const layerIds = ['fill', 'outline', 'line', 'point'] as const;
    expect(addVectorOverlay(map, { sourceId: 'source', layerIds, data, color: '#123456' })).toBeUndefined();
    expect(calls[0]![0]).toBe('source');
    expect(map.addSource).toHaveBeenCalledExactlyOnceWith('source', {
        type: 'geojson', data, generateId: true, tolerance: DEFAULTS.GEOJSON_RENDER.TOLERANCE,
    });
    expect(map.addSource.mock.calls[0]![1].data).toBe(data);
    expect(map.addLayer.mock.calls.map(([layer]) => [layer.id, layer.type, layer.filter])).toEqual([
        ['fill', 'fill', ['==', '$type', 'Polygon']],
        ['outline', 'line', ['==', '$type', 'Polygon']],
        ['line', 'line', ['==', '$type', 'LineString']],
        ['point', 'circle', ['==', '$type', 'Point']],
    ]);
    expect(layerIds).toEqual(['fill', 'outline', 'line', 'point']);
});

it('forwards per-layer filters and explicit zero opacity without altering their identity', () => {
    const map = { addSource: vi.fn<VectorOverlayMap['addSource']>(), addLayer: vi.fn<VectorOverlayMap['addLayer']>() };
    const filters: GeometryFilter[] = [];
    const filterForGeometry = vi.fn((type: RenderGeometryType) => {
        const filter: GeometryFilter = ['==', 'family', type];
        filters.push(filter);
        return filter;
    });
    addVectorOverlay(map, {
        sourceId: 'source', layerIds: ['fill', 'outline', 'line', 'point'],
        data: { type: 'FeatureCollection', features: [] }, color: '#123456',
        fillOpacity: 0, filterForGeometry,
    });
    expect(filterForGeometry.mock.calls.map(([type]) => type)).toEqual(['Polygon', 'Polygon', 'LineString', 'Point']);
    map.addLayer.mock.calls.forEach(([layer], index) => {
        expect(layer.filter).toBe(filters[index]);
    });
    const first = map.addLayer.mock.calls[0]![0];
    expect(first.type).toBe('fill');
    expect((first as Extract<OverlayLayer, { type: 'fill' }>).paint['fill-opacity']).toBe(0);
});
