const mocks = vi.hoisted(() => ({ detail: vi.fn() }));
vi.mock('./gis_layer_client.js', () => ({
    GISLayerClient: {
        detail: mocks.detail,
    },
}));
vi.mock('./lazy_overlay_manager.js', () => ({ LazyOverlayManager: class {} }));
vi.mock('./map/gis_layers.js', () => ({ GISLayerRenderer: {} }));
vi.mock('./utils.js', () => ({ Utils: {} }));
vi.mock('./config.js', () => ({ DEFAULTS: { UI: {} } }));
vi.mock('./map/layers.js', () => ({ Layers: {} }));

import { fetchGISLayerData } from './gis_layers_runtime.js';

it('refreshes authorization and the signed URL immediately before activation', async () => {
    mocks.detail.mockResolvedValue({
        file: 'https://storage.test/layer.geojson?signed=1',
        source_format: 'GEOJSON',
    });
    const signal = new AbortController().signal;

    await expect(fetchGISLayerData({ id: 'layer-1' }, signal)).resolves.toEqual({
        url: 'https://storage.test/layer.geojson?signed=1',
        direct_source: true,
    });
    expect(mocks.detail).toHaveBeenCalledWith('layer-1', signal);
});

it('uses the same contract for converted KML and KMZ', async () => {
    mocks.detail.mockResolvedValue({
        file: 'https://storage.test/data.geojson?signed=1',
        source_format: 'KML',
    });

    await expect(fetchGISLayerData({ id: 'layer-2' })).resolves.toEqual({
        url: 'https://storage.test/data.geojson?signed=1',
        direct_source: false,
    });
});

it('rejects a layer without a display file', async () => {
    mocks.detail.mockResolvedValue({ file: null });
    await expect(fetchGISLayerData({ id: 'layer-3' })).rejects.toThrow('no longer accessible');
});
