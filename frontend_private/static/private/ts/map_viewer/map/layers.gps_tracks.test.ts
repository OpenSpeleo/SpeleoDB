import type { RendererLayer, RendererSourceOptions } from '../../../../../../ts-types/domain/renderer.ts';
import type { ViewerMap } from '../../../../../../ts-types/domain/map-state.ts';
import { setBrowserUrl, startApiServer } from '../../../../../../frontend_common/test/api-server.ts';
import { Config } from '../config.ts';
import { State } from '../state.ts';
import { ViewerUpdates } from '../viewer_updates.ts';
import { Layers } from './layers.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
const sources = new Map<string, RendererSourceOptions>();
const layers = new Map<string, RendererLayer>();
const geojson = { type: 'FeatureCollection', features: [] };

beforeAll(async () => {
    originalUrl = window.location.href;
    server = await startApiServer();
});
afterAll(async () => {
    setBrowserUrl(originalUrl);
    await server.close();
});
beforeEach(() => {
    server.reset();
    setBrowserUrl(`${server.origin}/private/map/`);
    server.handle(({ path }) => ({ json: path.startsWith('/api/v2/')
        ? { id: 'track-1', file: `${server.origin}/track.geojson` }
        : geojson }));
    State.resetLayerState();
    State.gpsTrackLayerStates.clear();
    State.gpsTrackLoadingStates.clear();
    State.gpsTrackCache.clear();
    Config._gpsTracks = [{ id: 'track-1' }];
    sources.clear();
    layers.clear();
    // JSDOM has no native map renderer; only source/layer storage is supplied.
    // API transport, preparation, installation and viewer scheduling remain real.
    State.map = {
        getSource: (id: string) => sources.get(id),
        addSource: (id: string, definition: RendererSourceOptions) => sources.set(id, definition),
        removeSource: (id: string) => sources.delete(id),
        getLayer: (id: string) => layers.get(id),
        addLayer(layer: RendererLayer) {
            layers.set(layer.id, layer);
        },
        removeLayer: (id: string) => layers.delete(id),
        moveLayer() {},
        setLayoutProperty(id: string, key: string, value: unknown) {
            Object.assign(layers.get(id)!.layout ??= {}, { [key]: value });
        },
    } as unknown as ViewerMap;
});
afterEach(async () => {
    await ViewerUpdates.whenIdle();
    State.resetLayerState();
    State.map = null;
    Config._gpsTracks = null;
});

it('authorizes a fresh signed URL immediately before the first download', async () => {
    await Layers.toggleGPSTrackVisibility('track-1', true);
    expect(server.requests.map(request => request.path)).toEqual([
        '/api/v2/gps_tracks/track-1/', '/track.geojson',
    ]);
    expect(State.gpsTrackCache.get('track-1')).toEqual(geojson);
    expect(sources.get('gps-track-source-track-1')?.data).toEqual(geojson);
    expect(layers.has('gps-track-line-track-1')).toBe(true);
});

it('never fetches an undefined URL when detail metadata has no file', async () => {
    server.reply({ json: { id: 'track-1' } });
    await Layers.toggleGPSTrackVisibility('track-1', true);
    expect(server.requests.map(request => request.path)).toEqual(['/api/v2/gps_tracks/track-1/']);
    expect(State.gpsTrackLayerStates.get('track-1')).toBe(false);
    expect(State.gpsTrackLoadingStates.get('track-1')).toBe(false);
    expect(State.gpsTrackCache.has('track-1')).toBe(false);
    expect(sources.size).toBe(0);
});
