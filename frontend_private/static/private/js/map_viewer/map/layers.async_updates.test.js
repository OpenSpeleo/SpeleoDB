import { Config } from '../config.js';
import { State, createDefaultDisplayPreferences } from '../state.js';
import { ViewerUpdates } from '../viewer_updates.js';
import { Layers } from './layers.js';
import { API } from '../api.js';
import { Utils } from '../utils.js';
import { beginMapNavigation } from './navigation_intent.js';

function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}

async function apply() {
    await vi.runAllTimersAsync();
    await ViewerUpdates.whenIdle();
}

beforeEach(() => {
    vi.useFakeTimers();
    State.resetLayerState();
    State.displayPreferences = createDefaultDisplayPreferences();
    State.map = {
        getLayer: vi.fn(id => ({ id, type: 'line' })),
        getStyle: vi.fn(() => { throw new Error('A toggle must not serialize the style'); }),
        setLayoutProperty: vi.fn(), setFilter: vi.fn(), setPaintProperty: vi.fn(),
    };
    State.allProjectLayers.set('p', ['project-layer-p']);
    State.projectDepthDomains.set('p', { min: 0, max: 42 });
    Config._projects = [{ id: 'p', color: '#123456' }];
    Config._gpsTracks = [];
    Config._gisLayers = [];
    Config._gisGeometries = [];
    vi.spyOn(Utils, 'showNotification').mockImplementation(() => {});
});

afterEach(async () => {
    Layers.cancelPendingWork();
    await vi.runAllTimersAsync();
    State.map = null;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
});

it('publishes intent immediately, applies only the latest choice, and avoids style serialization', async () => {
    const first = Layers.setCategoryVisibility('caveEntrances', false);
    const final = Layers.setCategoryVisibility('caveEntrances', true);
    expect(State.displayPreferences.categories.caveEntrances).toBe(true);
    expect(State.map.setLayoutProperty).not.toHaveBeenCalled();
    expect(State.map.setFilter).not.toHaveBeenCalled();
    await apply();
    expect(await first).toEqual({ status: 'superseded' });
    expect(await final).toEqual({ status: 'applied' });
    expect(State.map.getStyle).not.toHaveBeenCalled();
    expect(State.displayUpdatePending).toBe(false);
});

it('combines project and color intent before computing the final cached domain', async () => {
    const recompute = vi.spyOn(Layers, 'recomputeActiveDepthDomain');
    Layers.toggleProjectVisibility('p', false);
    Layers.setColorMode('depth');
    Layers.toggleProjectVisibility('p', true);
    expect(State.map.setPaintProperty).not.toHaveBeenCalled();
    await apply();
    expect(recompute).toHaveBeenCalledOnce();
    expect(State.activeDepthDomain).toEqual({ min: 0, max: 42 });
    expect(State.map.setPaintProperty).toHaveBeenCalledOnce();
});

it('deduplicates GPS loads while allowing off/on and prevents obsolete completion rollback', async () => {
    const detail = deferred();
    vi.spyOn(API, 'getGPSTrackDetails').mockReturnValue(detail.promise);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ type: 'FeatureCollection', features: [] }) }));
    const install = vi.spyOn(Layers, 'addGPSTrackLayer').mockImplementation(async () => {
        State.allGPSTrackLayers.set('t', ['gps-track-line-t']);
    });
    const show = vi.spyOn(Layers, 'showGPSTrackLayers');
    const first = Layers.toggleGPSTrackVisibility('t', true);
    const off = Layers.toggleGPSTrackVisibility('t', false);
    const last = Layers.toggleGPSTrackVisibility('t', true);
    expect(State.gpsTrackLayerStates.get('t')).toBe(true);
    expect(API.getGPSTrackDetails).toHaveBeenCalledOnce();
    detail.resolve({ file: '/track' });
    await apply();
    expect(await first).toBe(false);
    expect(await off).toBe(false);
    expect(await last).toBe(true);
    expect(install).toHaveBeenCalledOnce();
    expect(show).toHaveBeenLastCalledWith('t', true);
    expect(State.gpsTrackLoadingStates.get('t')).toBe(false);
});

it('ignores a failed activation after the user has hidden the item', async () => {
    const detail = deferred();
    vi.spyOn(API, 'getGISLayerDetails').mockReturnValue(detail.promise);
    const first = Layers.toggleGISLayerVisibility('g', true);
    const off = Layers.toggleGISLayerVisibility('g', false);
    detail.reject(new Error('obsolete request'));
    await apply();
    expect(await first).toBe(false);
    expect(await off).toBe(true);
    expect(State.gisLayerStates.get('g')).toBe(false);
    expect(Utils.showNotification).not.toHaveBeenCalled();
});

it('does not let late results install into a replacement map or repopulate reset caches', async () => {
    const detail = deferred();
    vi.spyOn(API, 'getGPSTrackDetails').mockReturnValue(detail.promise);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ type: 'FeatureCollection', features: [] }) }));
    const install = vi.spyOn(Layers, 'addGPSTrackLayer');
    const first = Layers.toggleGPSTrackVisibility('t', true);
    State.resetLayerState();
    State.map = { getLayer: vi.fn() };
    detail.resolve({ file: '/track' });
    await apply();
    expect(await first).toBe(false);
    expect(install).not.toHaveBeenCalled();
    expect(State.gpsTrackCache.size).toBe(0);
});

describe.each([
    ['GPS', '_gpsTracks', 'toggleGPSTrackVisibility', 'getGPSTrackDetails', 'addGPSTrackLayer', 'gpsTrackCache', 'gpsTrackLoadingStates', 'allGPSTrackLayers'],
    ['GIS', '_gisLayers', 'toggleGISLayerVisibility', 'getGISLayerDetails', 'addGISLayer', 'gisLayerCache', 'gisLayerLoadingStates', 'allGISLayerLayers'],
])('%s metadata revisions', (_label, metadataKey, toggle, details, install, cache, loading, registry) => {
    let installed;
    beforeEach(() => {
        Config[metadataKey] = [{ id: 'item', modified_date: 'v1' }];
        installed = vi.spyOn(Layers, install).mockImplementation(async () => {
            State[registry].set('item', ['rendered-item']);
        });
        vi.stubGlobal('fetch', vi.fn().mockImplementation(async url => ({
            ok: true, json: async () => ({ type: 'FeatureCollection', features: [], url }),
        })));
    });

    it('finishes a pending display after the list replaces an unchanged metadata object', async () => {
        const detail = deferred();
        vi.spyOn(API, details).mockReturnValue(detail.promise);
        const showing = Layers[toggle]('item', true);
        Config[metadataKey] = [{ id: 'item', modified_date: 'v1', name: 'Refreshed list' }];
        detail.resolve({ file: '/v1' });
        await apply();
        expect(await showing).toBe(true);
        expect(installed).toHaveBeenCalledOnce();
        expect(State[loading].get('item')).toBe(false);
    });

    it.each(['resolve', 'reject'])('reconciles a changed visible revision after the old request %ss', async outcome => {
        const detail = deferred();
        vi.spyOn(API, details).mockReturnValueOnce(detail.promise).mockResolvedValue({ file: '/v2' });
        const showing = Layers[toggle]('item', true);
        Config[metadataKey] = [{ id: 'item', modified_date: 'v2' }];
        detail[outcome](outcome === 'resolve' ? { file: '/v1' } : new Error('obsolete file failed'));
        await apply();
        expect(await showing).toBe(true);
        expect(API[details]).toHaveBeenCalledTimes(2);
        expect(installed).toHaveBeenCalledOnce();
        expect(installed.mock.calls[0][1].url).toBe('/v2');
        expect(State[cache].get('item').url).toBe('/v2');
        expect(State[loading].get('item')).toBe(false);
        expect(Utils.showNotification).not.toHaveBeenCalled();
    });

    it('does not share a stale in-flight download with a newer revision activation', async () => {
        const detail = deferred();
        vi.spyOn(API, details).mockReturnValueOnce(detail.promise).mockResolvedValue({ file: '/v2' });
        const first = Layers[toggle]('item', true);
        const signal = API[details].mock.calls[0][1].signal;
        Config[metadataKey] = [{ id: 'item', modified_date: 'v2' }];
        const latest = Layers[toggle]('item', true);
        expect(signal.aborted).toBe(true);
        await apply();
        detail.resolve({ file: '/v1' });
        await apply();
        expect(await first).toBe(false);
        expect(await latest).toBe(true);
        expect(installed).toHaveBeenCalledOnce();
        expect(State[cache].get('item').url).toBe('/v2');
        expect(State[loading].get('item')).toBe(false);
    });

    it('replaces an already applied old source while retaining unchanged-revision reuse', async () => {
        vi.spyOn(API, details).mockResolvedValueOnce({ file: '/v1' }).mockResolvedValue({ file: '/v2' });
        const first = Layers[toggle]('item', true);
        await apply();
        expect(await first).toBe(true);
        Config[metadataKey] = [{ id: 'item', modified_date: 'v1' }];
        const same = Layers[toggle]('item', true);
        await apply();
        expect(await same).toBe(true);
        expect(installed).toHaveBeenCalledOnce();
        Config[metadataKey] = [{ id: 'item', modified_date: 'v2' }];
        const updated = Layers[toggle]('item', true);
        await apply();
        expect(await updated).toBe(true);
        expect(installed).toHaveBeenCalledTimes(2);
        expect(installed.mock.calls[1][1].url).toBe('/v2');
    });

    it('clears its own loading state when metadata removes the item', async () => {
        const detail = deferred();
        vi.spyOn(API, details).mockReturnValue(detail.promise);
        const showing = Layers[toggle]('item', true);
        Config[metadataKey] = [];
        detail.resolve({ file: '/v1' });
        await apply();
        expect(await showing).toBe(false);
        expect(installed).not.toHaveBeenCalled();
        expect(State[loading].get('item')).toBe(false);
    });
});

it.each(['refreshGISGeometry', 'acceptGISGeometry'])('keeps the latest saved GIS baseline after %s is superseded by hide', async update => {
    const sources = new Map();
    State.map.getSource = id => sources.get(id);
    State.map.addSource = vi.fn((id, source) => sources.set(id, source));
    State.map.removeSource = id => sources.delete(id);
    State.map.removeLayer = vi.fn();
    State.map.addLayer = vi.fn();
    vi.spyOn(Layers, 'reorderLayers').mockImplementation(() => {});
    vi.stubGlobal('mapboxgl', { LngLatBounds: class {
        extend() { return this; }
        isEmpty() { return false; }
    } });
    const original = { id: 'geometry', name: 'Original', revision: 1,
        geojson: { type: 'LineString', coordinates: [[0, 0], [1, 1]] } };
    State.gisGeometryCache.set('geometry', original);
    const first = Layers.toggleGISGeometryVisibility('geometry', true);
    await apply();
    expect(await first).toBe(true);
    const saved = { ...original, revision: 2, name: 'Saved',
        geojson: { type: 'LineString', coordinates: [[2, 2], [3, 3]] } };
    const refreshing = Layers[update](saved);
    const hiding = Layers.toggleGISGeometryVisibility('geometry', false);
    await apply();
    expect(await refreshing).toEqual({ status: 'superseded' });
    expect(await hiding).toBe(true);
    const showing = Layers.toggleGISGeometryVisibility('geometry', true);
    await apply();
    expect(await showing).toBe(true);
    expect(State.map.addSource).toHaveBeenCalledTimes(2);
    expect(sources.get('gis-geometry-source-geometry').data.geometry).toBe(saved.geojson);
});

it.each(['GPS', 'GIS'])('clears obsolete %s bounds when a replacement contains no coordinates', async kind => {
    State.map = { getLayer: () => undefined, getSource: () => undefined, addSource: vi.fn(), addLayer: vi.fn() };
    vi.spyOn(Layers, 'reorderLayers').mockResolvedValue({ status: 'applied' });
    const bounds = kind === 'GPS' ? State.gpsTrackBounds : State.gisLayerBounds;
    bounds.set('empty', { old: true });
    const data = { type: 'FeatureCollection', features: [] };
    if (kind === 'GPS') await Layers.addGPSTrackLayer('empty', data, { prepared: { boundsCoordinates: null } });
    else await Layers.addGISLayer('empty', data, { prepared: { boundsCoordinates: null, data, geometryTypes: [] } });
    expect(bounds.has('empty')).toBe(false);
});

it('detaches navigation listeners and releases the map when cancelling viewer work', () => {
    const map = { on: vi.fn(), off: vi.fn() };
    State.map = map;
    const navigation = beginMapNavigation(map, 'project:p');
    Layers.cancelPendingWork();
    expect(navigation.isCurrent()).toBe(false);
    expect(map.off).toHaveBeenCalledWith('movestart', expect.any(Function));
});
