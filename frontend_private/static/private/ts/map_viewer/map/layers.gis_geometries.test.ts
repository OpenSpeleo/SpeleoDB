import { geometryFixture } from '../../../../../../frontend_common/test/api-fixtures.ts';
import type { GISGeometry } from '@speleodb/api';
import type { RendererLayer, RendererSourceOptions } from '../../../../../../ts-types/domain/renderer.ts';
import type { ViewerMap } from '../../../../../../ts-types/domain/map-state.ts';
import { Config, DEFAULTS } from '../config.ts';
import { State } from '../state.ts';
import { setBrowserUrl, startApiServer } from '../../../../../../frontend_common/test/api-server.ts';
import type { ApiTestReply } from '../../../../../../frontend_common/test/api-server.ts';
import { LngLatBounds } from 'maplibre-gl';
import { ViewerUpdates } from '../viewer_updates.ts';
import { Layers } from './layers.ts';


function record(overrides: Partial<GISGeometry> = {}): GISGeometry {
    return { ...geometryFixture(), id: 'g1', name: 'Boundary', color: '#123456', can_write: true, revision: 1,
        geojson: { type: 'LineString', coordinates: [[-87, 20], [-87.001, 20.001]] }, ...overrides };
}

function createMap() {
    const layers = new Map<string, RendererLayer>();
    const sources = new Map<string, RendererSourceOptions>();
    return {
        getStyle: () => ({ layers: [...layers.values()] }),
        getLayer: (id: string) => layers.get(id),
        getSource: (id: string) => sources.get(id),
        addSource: vi.fn((id: string, source: RendererSourceOptions) => sources.set(id, source)),
        addLayer: vi.fn((layer: RendererLayer) => layers.set(layer.id, layer)),
        removeLayer: vi.fn((id: string) => layers.delete(id)),
        removeSource: vi.fn((id: string) => sources.delete(id)),
        setLayoutProperty: vi.fn(), moveLayer: vi.fn<(id: string) => void>(), fitBounds: vi.fn(),
    };
}
let map: ReturnType<typeof createMap>;
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; server = await startApiServer(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

beforeEach(() => {
    server.reset();
    setBrowserUrl(`${server.origin}/private/map/`);
    // GPU source/layer methods are the only unavailable renderer boundary.
    vi.stubGlobal('__mapRenderer', { LngLatBounds });
    State.resetLayerState();
    Config._gisGeometries = null;
    map = createMap();
    State.map = map as unknown as ViewerMap;
    server.reply({ json: record() });
});
afterEach(async () => { await ViewerUpdates.whenIdle(); State.resetLayerState(); State.map = null; Config._gisGeometries = null; Config.gisGeometriesError = false; vi.unstubAllGlobals(); });

it('starts hidden and loads metadata without fetching coordinates', async () => {
    server.reply({ json: [geometryFixture()] });
    await Config.loadGISGeometries();
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
    expect(server.requests.map(request => request.path)).toEqual(['/api/v2/gis-geometries/']);
    expect(map.addSource).not.toHaveBeenCalled();
});

it('loads once on show, caches and toggles without moving the camera', async () => {
    await Layers.toggleGISGeometryVisibility('g1', true);
    await Layers.toggleGISGeometryVisibility('g1', false);
    await Layers.toggleGISGeometryVisibility('g1', true);
    expect(server.requests.filter(request => request.path === '/api/v2/gis-geometries/g1/')).toHaveLength(1);
    expect(map.addSource).toHaveBeenCalledTimes(1);
    expect(map.fitBounds).not.toHaveBeenCalled();
    expect(Config.getGISGeometryById('g1')).not.toHaveProperty('geojson');
    expect(State.gisGeometryCache.get('g1')!.geojson).toEqual(record().geojson);
    const line = map.addLayer.mock.calls.map(([layer]) => layer)
        .find(layer => layer.type === 'line' && (layer.filter as unknown[])[2] === 'LineString');
    expect(map.addSource.mock.calls[0]![1].tolerance).toBe(0);
    expect(line!.paint!['line-width']).toEqual(['interpolate', ['linear'], ['zoom'],
        0, 1, 8, 1, 12, 1.5, 14, 2, 16, 2.5, 18, 2.5]);
    expect(line!.paint!['line-color']).toBe(record().color);
});

it('retains locally saved metadata when a metadata retry fails', async () => {

    Config.upsertGISGeometry(record({ name: 'Saved while offline' }));
    Config.gisGeometriesError = true;
    server.reply({ status: 503, json: { detail: 'offline' } });
    await Config.loadGISGeometries();
    expect(Config.getGISGeometryById('g1')!.name).toBe('Saved while offline');
    expect(Config.gisGeometriesError).toBe(true);
});

it('merges a delayed metadata retry with saves without retaining unrelated deleted rows', async () => {
    Config.upsertGISGeometry(record());
    Config.upsertGISGeometry(record({ id: 'removed' }));
    Config.gisGeometriesError = true;
    let resolve!: (records: GISGeometry[]) => void;
    const response = new Promise<GISGeometry[]>(done => { resolve = done; });
    server.handle(async () => ({ json: await response }));
    const retry = Config.loadGISGeometries();
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    Config.upsertGISGeometry(record({ name: 'Newer save', revision: 2 }));
    Config.upsertGISGeometry(record({ id: 'new', name: 'Created during retry' }));
    resolve([record()]);
    await retry;
    expect(Config.getGISGeometryById('g1')!.name).toBe('Newer save');
    expect(Config.getGISGeometryById('new')!.name).toBe('Created during retry');
    expect(Config.getGISGeometryById('removed')).toBeNull();
    expect(Config.gisGeometries).toHaveLength(2);
    expect(Config.gisGeometriesError).toBe(false);
});

it('accepts a newer server revision and updated permissions during metadata retry', async () => {
    Config.upsertGISGeometry(record());
    Config.gisGeometriesError = true;
    server.reply({ json: [record({ name: 'Remote edit', revision: 2, can_write: false })] });
    await Config.loadGISGeometries();
    expect(Config.getGISGeometryById('g1')!.name).toBe('Remote edit');
    expect(Config.hasGISGeometryAccess('g1', 'write')).toBe(false);
    expect(Config.getGISGeometryById('g1')).not.toHaveProperty('geojson');
});

it('does not show a delayed load after it was hidden', async () => {
    let resolve!: (record: GISGeometry) => void;
    const response = new Promise<GISGeometry>(done => { resolve = done; });
    server.handle(async () => ({ json: await response }));
    const showing = Layers.toggleGISGeometryVisibility('g1', true);
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    await Layers.toggleGISGeometryVisibility('g1', false);
    resolve(record());
    await showing;
    expect(map.addSource).not.toHaveBeenCalled();
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
});

it('shares a pending request between concurrent show operations', async () => {
    await Promise.all([Layers.toggleGISGeometryVisibility('g1', true), Layers.toggleGISGeometryVisibility('g1', true)]);
    expect(server.requests.filter(request => request.path === '/api/v2/gis-geometries/g1/')).toHaveLength(1);
    expect(map.addSource).toHaveBeenCalledTimes(1);
});

it('hides the saved source during a draft and reveals the accepted save', async () => {
    await Layers.toggleGISGeometryVisibility('g1', true);
    State.gisGeometryEditingId = 'g1';
    Layers.showGISGeometryLayers('g1', true);
    expect(map.setLayoutProperty).toHaveBeenLastCalledWith('gis-geometry-g1-point', 'visibility', 'none');
    void Layers.acceptGISGeometry(record({ name: 'Changed', revision: 2 }));
    State.gisGeometryEditingId = null;
    Layers.showGISGeometryLayers('g1', Layers.isGISGeometryVisible('g1'));
    expect(Config.getGISGeometryById('g1')!.name).toBe('Changed');
    expect(map.setLayoutProperty).toHaveBeenLastCalledWith('gis-geometry-g1-point', 'visibility', 'visible');
});

it('rebuilds cached overlays after a style reset', async () => {
    await Layers.toggleGISGeometryVisibility('g1', true);
    State.allGISGeometryLayers.clear();
    await Layers.toggleGISGeometryVisibility('g1', true);
    expect(server.requests.filter(request => request.path === '/api/v2/gis-geometries/g1/')).toHaveLength(1);
    expect(map.addSource).toHaveBeenCalledTimes(2);
});

it('does not let an older pending detail response replace a saved revision', async () => {
    let resolve!: (record: GISGeometry) => void;
    const response = new Promise<GISGeometry>(done => { resolve = done; });
    server.handle(async () => ({ json: await response }));
    const showing = Layers.toggleGISGeometryVisibility('g1', true);
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    void Layers.acceptGISGeometry(record({ name: 'Saved', revision: 2 }));
    resolve(record());
    await showing;
    expect(State.gisGeometryCache.get('g1')!.revision).toBe(2);
    expect(Config.getGISGeometryById('g1')!.name).toBe('Saved');
});

it('refreshes a collaborator change as the revert baseline without revealing hidden geometry', async () => {
    const refreshing = Layers.refreshGISGeometry(record({ name: 'Collaborator edit', revision: 2 }));
    expect(State.gisGeometryCache.get('g1')!.revision).toBe(2);
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
    expect(map.setLayoutProperty).not.toHaveBeenCalled();
    await refreshing;
    expect(map.setLayoutProperty).toHaveBeenLastCalledWith('gis-geometry-g1-point', 'visibility', 'none');
});

it.each(['acceptGISGeometry', 'refreshGISGeometry'] as const)('ignores a stale request failure after %s supplies the record', async replaceRecord => {
    let finish!: (reply: ApiTestReply) => void;
    const response = new Promise<ApiTestReply>(resolve => { finish = resolve; });
    server.handle(() => response);
    const showing = Layers.toggleGISGeometryVisibility('g1', true);
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    const replacing = Layers[replaceRecord](record({ name: 'Newer saved baseline', revision: 2 }));
    finish({ status: 503, json: { detail: 'The older request failed' } });
    expect(await showing).toBe(true);
    expect(Layers.isGISGeometryVisible('g1')).toBe(true);
    expect(State.gisGeometryCache.get('g1')!.revision).toBe(2);
    await replacing;
    expect(map.setLayoutProperty).toHaveBeenLastCalledWith('gis-geometry-g1-point', 'visibility', 'visible');
    expect(State.gisGeometryLoading.size).toBe(0);
});

it('preserves an explicit hide after saving when an older request fails', async () => {
    let finish!: (reply: ApiTestReply) => void;
    const response = new Promise<ApiTestReply>(resolve => { finish = resolve; });
    server.handle(() => response);
    const showing = Layers.toggleGISGeometryVisibility('g1', true);
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    void Layers.acceptGISGeometry(record({ revision: 2 }));
    await Layers.toggleGISGeometryVisibility('g1', false);
    finish({ status: 503, json: { detail: 'The older request failed' } });
    expect(await showing).toBe(false);
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
    expect(map.addSource).not.toHaveBeenCalled();
});

it('hides existing rendered layers when an ordinary show attempt fails', async () => {

    await Layers.toggleGISGeometryVisibility('g1', true);
    State.gisGeometryCache.delete('g1');
    server.reply({ status: 503, json: { detail: 'offline' } });
    expect(await Layers.toggleGISGeometryVisibility('g1', true)).toBe(false);
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
    expect(map.setLayoutProperty).toHaveBeenLastCalledWith('gis-geometry-g1-point', 'visibility', 'none');
});

it('fails closed on missing access and releases loading state', async () => {

    server.reply({ status: 503, json: { detail: 'revoked' } });
    expect(await Layers.toggleGISGeometryVisibility('g1', true)).toBe(false);
    expect(State.gisGeometryLoading.size).toBe(0);
    expect(State.gisGeometryStates.get('g1')).toBe(false);
});

it('centralizes read/write/delete capabilities and forgets session visibility on reset', async () => {
    Config.upsertGISGeometry(record({ can_write: false, can_delete: false }));
    expect(Config.getScopedAccess('gis_geometry', 'g1')).toEqual({ read: true, write: false, delete: false });
    expect(Config.hasGISGeometryAccess('absent', 'read')).toBe(false);
    State.gisGeometryStates.set('g1', true);
    State.resetLayerState();
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
});

it('restores measurement order above saved overlays and below editor handles', async () => {
    const measurementIds = DEFAULTS.MEASUREMENT.LAYER_ROLES.map(role => `${DEFAULTS.MEASUREMENT.LAYER_PREFIX}${role}`);
    for (const id of [...measurementIds].reverse()) map.addLayer({ id, type: 'line' });
    map.addLayer({ type: 'line', id: 'landmarks-layer' });
    map.addLayer({ type: 'line', id: 'gis-geometry-draft-vertices' });
    await Layers.reorderLayers();
    const moved = map.moveLayer.mock.calls.map(([id]) => id);
    expect(moved.slice(-(measurementIds.length + 1))).toEqual([
        ...measurementIds, 'gis-geometry-draft-vertices',
    ]);
});


it('gates labels independently and keeps anchors out of metadata and lazy coordinate requests', async () => {
    State.displayPreferences.geometryLabelsVisible = true;
    const saved = record({ alias: 'Approach', description: 'Long detail text' });
    server.reply({ json: saved });
    await Layers.toggleGISGeometryVisibility('g1', true);
    const labelId = 'gis-geometry-g1-label';
    expect(map.getLayer(labelId)?.layout?.['text-field']).toEqual(['get', 'alias']);
    expect(map.getSource('gis-geometry-label-source-g1')?.data).toMatchObject({
        type: 'Feature', geometry: { type: 'Point' }, properties: { alias: 'Approach' },
    });
    expect(Config.getGISGeometryById('g1')).not.toHaveProperty('description');
    await Layers.setGeometryLabelsVisible(false);
    expect(map.setLayoutProperty).toHaveBeenCalledWith(labelId, 'visibility', 'none');
    await Layers.setGeometryLabelsVisible(true);
    expect(map.setLayoutProperty).toHaveBeenLastCalledWith(labelId, 'visibility', 'visible');
    State.gisGeometryEditingId = 'g1';
    Layers.showGISGeometryLayers('g1', true);
    expect(map.setLayoutProperty).toHaveBeenLastCalledWith(labelId, 'visibility', 'none');
    expect(server.requests.filter(request => request.path === '/api/v2/gis-geometries/g1/')).toHaveLength(1);
    State.gisGeometryEditingId = null;
    await Layers.acceptGISGeometry({ ...saved, alias: '', revision: 2 });
    expect(map.getLayer(labelId)).toBeUndefined();
    expect(map.getSource('gis-geometry-label-source-g1')).toBeUndefined();
});
