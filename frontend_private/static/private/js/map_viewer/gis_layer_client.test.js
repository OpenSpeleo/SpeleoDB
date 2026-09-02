import { GISLayerClient } from './gis_layer_client.js';

vi.mock('./utils.js', () => ({ Utils: { getCSRFToken: () => 'csrf-token' } }));

beforeEach(() => {
    globalThis.Urls = {
        'api:v2:gis-layers': () => '/api/v2/gis-layers/',
        'api:v2:gis-layer-detail': id => `/api/v2/gis-layers/${id}/`,
    };
    globalThis.fetch = vi.fn(async () => ({ ok: true, json: async () => [] }));
});

afterEach(() => {
    delete globalThis.Urls;
    delete globalThis.fetch;
});

it('loads accessible layers with their signed display-file URLs', async () => {
    await GISLayerClient.list();
    expect(fetch).toHaveBeenCalledWith(
        '/api/v2/gis-layers/',
        expect.objectContaining({ credentials: 'same-origin' }),
    );
});

it('refreshes one layer through the permission-checked detail endpoint', async () => {
    const controller = new AbortController();
    await GISLayerClient.detail('layer-1', controller.signal);
    expect(fetch).toHaveBeenCalledWith(
        '/api/v2/gis-layers/layer-1/',
        expect.objectContaining({
            credentials: 'same-origin',
            signal: controller.signal,
        }),
    );
});
