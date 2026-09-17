import { Config } from '../config.js';
import { State } from '../state.js';
import { API } from '../api.js';
import { Layers } from './layers.js';

vi.mock('../api.js', () => ({ API: { getGISGeometryDetails: vi.fn(), getGISGeometries: vi.fn() } }));
vi.mock('./geojson.js', () => ({ computeGeoJSONBounds: () => ({ isEmpty: () => false }) }));

function record(overrides = {}) {
    return { id: 'g1', name: 'Boundary', color: '#123456', can_write: true, revision: 1,
        geojson: { type: 'LineString', coordinates: [[-87, 20], [-87.001, 20.001]] }, ...overrides };
}

beforeEach(() => {
    State.resetLayerState();
    Config._gisGeometries = null;
    const layers = new Map();
    const sources = new Map();
    State.map = {
        getStyle: () => ({ layers: [...layers.values()] }),
        getLayer: id => layers.get(id),
        getSource: id => sources.get(id),
        addSource: vi.fn((id, source) => sources.set(id, source)),
        addLayer: vi.fn(layer => layers.set(layer.id, layer)),
        removeLayer: vi.fn(id => layers.delete(id)),
        removeSource: vi.fn(id => sources.delete(id)),
        setLayoutProperty: vi.fn(), moveLayer: vi.fn(), fitBounds: vi.fn(),
    };
    API.getGISGeometryDetails.mockReset().mockResolvedValue(record());
});
afterEach(() => { State.resetLayerState(); State.map = null; Config._gisGeometries = null; Config.gisGeometriesError = false; vi.restoreAllMocks(); });

it('starts hidden and loads metadata without fetching coordinates', async () => {
    API.getGISGeometries.mockResolvedValue([{ id: 'g1', name: 'Boundary', can_write: true }]);
    await Config.loadGISGeometries();
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
    expect(API.getGISGeometryDetails).not.toHaveBeenCalled();
    expect(State.map.addSource).not.toHaveBeenCalled();
});

it('loads once on show, caches and toggles without moving the camera', async () => {
    await Layers.toggleGISGeometryVisibility('g1', true);
    await Layers.toggleGISGeometryVisibility('g1', false);
    await Layers.toggleGISGeometryVisibility('g1', true);
    expect(API.getGISGeometryDetails).toHaveBeenCalledTimes(1);
    expect(State.map.addSource).toHaveBeenCalledTimes(1);
    expect(State.map.fitBounds).not.toHaveBeenCalled();
    expect(Config.getGISGeometryById('g1').geojson).toBeUndefined();
    expect(State.gisGeometryCache.get('g1').geojson).toEqual(record().geojson);
});

it('retries failed metadata loading even after locally saving a geometry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    API.getGISGeometries.mockRejectedValueOnce(new Error('offline'));
    expect(await Config.loadGISGeometries()).toEqual([]);
    expect(Config.gisGeometriesError).toBe(true);
    Config.upsertGISGeometry(record());
    API.getGISGeometries.mockResolvedValueOnce([record(), record({ id: 'g2' })]);
    expect(await Config.loadGISGeometries()).toHaveLength(2);
    expect(Config.gisGeometriesError).toBe(false);
});

it('retains locally saved metadata when a metadata retry fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    Config.upsertGISGeometry(record({ name: 'Saved while offline' }));
    Config.gisGeometriesError = true;
    API.getGISGeometries.mockRejectedValueOnce(new Error('offline'));
    await Config.loadGISGeometries();
    expect(Config.getGISGeometryById('g1').name).toBe('Saved while offline');
    expect(Config.gisGeometriesError).toBe(true);
});

it('merges a delayed metadata retry with saves without retaining unrelated deleted rows', async () => {
    Config.upsertGISGeometry(record());
    Config.upsertGISGeometry(record({ id: 'removed' }));
    Config.gisGeometriesError = true;
    let resolve;
    API.getGISGeometries.mockReturnValueOnce(new Promise(done => { resolve = done; }));
    const retry = Config.loadGISGeometries();
    Config.upsertGISGeometry(record({ name: 'Newer save', revision: 2 }));
    Config.upsertGISGeometry(record({ id: 'new', name: 'Created during retry' }));
    resolve([record()]);
    await retry;
    expect(Config.getGISGeometryById('g1').name).toBe('Newer save');
    expect(Config.getGISGeometryById('new').name).toBe('Created during retry');
    expect(Config.getGISGeometryById('removed')).toBeNull();
    expect(Config.gisGeometries).toHaveLength(2);
    expect(Config.gisGeometriesError).toBe(false);
});

it('accepts a newer server revision and updated permissions during metadata retry', async () => {
    Config.upsertGISGeometry(record());
    Config.gisGeometriesError = true;
    API.getGISGeometries.mockResolvedValueOnce([record({ name: 'Remote edit', revision: 2, can_write: false })]);
    await Config.loadGISGeometries();
    expect(Config.getGISGeometryById('g1').name).toBe('Remote edit');
    expect(Config.hasGISGeometryAccess('g1', 'write')).toBe(false);
    expect(Config.getGISGeometryById('g1').geojson).toBeUndefined();
});

it('does not show a delayed load after it was hidden', async () => {
    let resolve;
    API.getGISGeometryDetails.mockReturnValue(new Promise(done => { resolve = done; }));
    const showing = Layers.toggleGISGeometryVisibility('g1', true);
    await Layers.toggleGISGeometryVisibility('g1', false);
    resolve(record());
    await showing;
    expect(State.map.addSource).not.toHaveBeenCalled();
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
});

it('shares a pending request between concurrent show operations', async () => {
    await Promise.all([Layers.toggleGISGeometryVisibility('g1', true), Layers.toggleGISGeometryVisibility('g1', true)]);
    expect(API.getGISGeometryDetails).toHaveBeenCalledTimes(1);
    expect(State.map.addSource).toHaveBeenCalledTimes(1);
});

it('hides the saved source during a draft and reveals the accepted save', async () => {
    await Layers.toggleGISGeometryVisibility('g1', true);
    State.gisGeometryEditingId = 'g1';
    Layers.showGISGeometryLayers('g1', true);
    expect(State.map.setLayoutProperty).toHaveBeenLastCalledWith('gis-geometry-g1-point', 'visibility', 'none');
    Layers.acceptGISGeometry(record({ name: 'Changed', revision: 2 }));
    State.gisGeometryEditingId = null;
    Layers.showGISGeometryLayers('g1', Layers.isGISGeometryVisible('g1'));
    expect(Config.getGISGeometryById('g1').name).toBe('Changed');
    expect(State.map.setLayoutProperty).toHaveBeenLastCalledWith('gis-geometry-g1-point', 'visibility', 'visible');
});

it('rebuilds cached overlays after a style reset', async () => {
    await Layers.toggleGISGeometryVisibility('g1', true);
    State.allGISGeometryLayers.clear();
    await Layers.toggleGISGeometryVisibility('g1', true);
    expect(API.getGISGeometryDetails).toHaveBeenCalledTimes(1);
    expect(State.map.addSource).toHaveBeenCalledTimes(2);
});

it('does not let an older pending detail response replace a saved revision', async () => {
    let resolve;
    API.getGISGeometryDetails.mockReturnValue(new Promise(done => { resolve = done; }));
    const showing = Layers.toggleGISGeometryVisibility('g1', true);
    Layers.acceptGISGeometry(record({ name: 'Saved', revision: 2 }));
    resolve(record());
    await showing;
    expect(State.gisGeometryCache.get('g1').revision).toBe(2);
    expect(Config.getGISGeometryById('g1').name).toBe('Saved');
});

it('refreshes a collaborator change as the revert baseline without revealing hidden geometry', () => {
    Layers.refreshGISGeometry(record({ name: 'Collaborator edit', revision: 2 }));
    expect(State.gisGeometryCache.get('g1').revision).toBe(2);
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
    expect(State.map.setLayoutProperty).toHaveBeenLastCalledWith('gis-geometry-g1-point', 'visibility', 'none');
});

it('fails closed on missing access and permits retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    API.getGISGeometryDetails.mockRejectedValueOnce(new Error('revoked'));
    expect(await Layers.toggleGISGeometryVisibility('g1', true)).toBe(false);
    expect(State.gisGeometryLoading.size).toBe(0);
    expect(State.gisGeometryStates.get('g1')).toBe(false);
    expect(await Layers.toggleGISGeometryVisibility('g1', true)).toBe(true);
});

it('centralizes read/write/delete capabilities and forgets session visibility on reset', () => {
    Config.upsertGISGeometry(record({ can_write: false, can_delete: false }));
    expect(Config.getScopedAccess('gis_geometry', 'g1')).toEqual({ read: true, write: false, delete: false });
    expect(Config.hasGISGeometryAccess('absent', 'read')).toBe(false);
    State.gisGeometryStates.set('g1', true);
    State.resetLayerState();
    expect(Layers.isGISGeometryVisible('g1')).toBe(false);
});
