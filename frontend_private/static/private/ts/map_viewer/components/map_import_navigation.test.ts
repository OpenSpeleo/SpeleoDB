import type { ModuleMock } from '../../../../../../ts-types/testing/vitest/mocks.ts';
import type { ImportedMapResult } from '../../../../../../ts-types/domain/map-import.ts';
import type { FlatBounds } from '../../../../../../ts-types/domain/map-geometry.ts';
import type { LandmarkFeatureCollection } from '../../../../../../ts-types/domain/map-entities.ts';
import { refreshImportedMapData, showImportedMapData as showImported } from './map_import_navigation.ts';
import { Config as importedConfig } from '../config.ts';
import { State } from '../state.ts';
import { LandmarkManager as importedLandmarkManager } from '../landmarks/manager.ts';
import { Layers as importedLayers } from '../map/layers.ts';
import { fitGISGeometry } from '../map/geometry_camera.ts';
import { GISLayersPanel as importedGISLayersPanel } from './gis_layers_panel.ts';
import { GPSTracksPanel as importedGPSTracksPanel } from './gps_tracks_panel.ts';

vi.mock('../config.ts', () => ({ Config: { loadGISLayers: vi.fn(), loadGPSTracks: vi.fn() } }));
vi.mock('../state.ts', () => ({ State: { map: {}, gisLayerBounds: new Map() } }));
vi.mock('../landmarks/manager.ts', () => ({ LandmarkManager: { loadCollections: vi.fn(), loadAllLandmarks: vi.fn() } }));
vi.mock('../map/layers.ts', () => ({ Layers: {
    addLandmarkLayer: vi.fn(), reorderLayers: vi.fn(), revealCategory: vi.fn(), toggleGISLayerVisibility: vi.fn(),
    toggleGPSTrackVisibility: vi.fn(), isGPSTrackVisible: vi.fn(),
} }));
vi.mock('../map/geometry_camera.ts', () => ({ fitGISGeometry: vi.fn() }));
vi.mock('./gis_layers_panel.ts', () => ({ GISLayersPanel: { refreshList: vi.fn(), init: vi.fn(), setupStackListener: vi.fn() } }));
vi.mock('./gps_tracks_panel.ts', () => ({ GPSTracksPanel: { refreshList: vi.fn(), init: vi.fn() } }));
vi.mock('./gis_geometries_panel.ts', () => ({ GISGeometriesPanel: { setupStackListener: vi.fn() } }));

describe('imported map data navigation', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        document.body.replaceChildren();
        State.map = {} as NonNullable<typeof State.map>;
        State.gisLayerBounds.clear();
    });

    it.each([true, false])('refreshes the overlay panel (already present: %s) without revealing or moving', async present => {
        if (present) document.body.innerHTML = '<div id="gis-layers-panel"></div>';
        await refreshImportedMapData({ kind: 'overlay', layerId: 'new' });
        expect(Config.loadGISLayers).toHaveBeenCalledWith({ force: true, throwOnError: true });
        expect(present ? GISLayersPanel.refreshList : GISLayersPanel.init).toHaveBeenCalledOnce();
        expect(Config.loadGPSTracks).not.toHaveBeenCalled();
        expect(LandmarkManager.loadAllLandmarks).not.toHaveBeenCalled();
        expect(Layers.toggleGISLayerVisibility).not.toHaveBeenCalled();
        expect(fitGISGeometry).not.toHaveBeenCalled();
    });

    it('propagates refresh failure and does not initialize a panel from stale data', async () => {
        vi.mocked(Config.loadGISLayers).mockRejectedValue(new Error('Offline'));
        await expect(refreshImportedMapData({ kind: 'overlay' })).rejects.toThrow('Offline');
        expect(GISLayersPanel.init).not.toHaveBeenCalled();
    });

    it('reloads only landmarks after place creation without changing their visibility', async () => {
        const geojson: LandmarkFeatureCollection = { type: 'FeatureCollection', features: [] };
        vi.mocked(LandmarkManager.loadAllLandmarks).mockResolvedValue(geojson);
        await refreshImportedMapData({ kind: 'places', landmarksCreated: 2 });
        expect(LandmarkManager.loadCollections).toHaveBeenCalledWith({ throwOnError: true });
        expect(Layers.addLandmarkLayer).toHaveBeenCalledWith(geojson);
        expect(Layers.revealCategory).not.toHaveBeenCalled();
        expect(Config.loadGISLayers).not.toHaveBeenCalled();
    });

    it('does not reload for an all-duplicate place import', async () => {
        await refreshImportedMapData({ kind: 'places', landmarksCreated: 0 });
        expect(LandmarkManager.loadCollections).not.toHaveBeenCalled();
    });

    it('refreshes both GPX outputs while leaving existing track visibility and caches intact', async () => {
        await refreshImportedMapData({ kind: 'gpx', landmarksCreated: 1, gpsTracksCreated: 1 });
        expect(Config.loadGPSTracks).toHaveBeenCalledWith({ force: true, throwOnError: true });
        expect(GPSTracksPanel.init).toHaveBeenCalledOnce();
        expect(Layers.addLandmarkLayer).toHaveBeenCalledOnce();
        expect(fitGISGeometry).not.toHaveBeenCalled();
    });

    it('shows only the requested new overlay and uses its loaded bounds', async () => {
        const bounds: FlatBounds = [-80, 20, -79, 21];
        State.gisLayerBounds.set('new', bounds);
        vi.mocked(Layers.toggleGISLayerVisibility).mockResolvedValue(true);
        await showImportedMapData({ kind: 'overlay', layerId: 'new' });
        expect(Layers.toggleGISLayerVisibility).toHaveBeenCalledExactlyOnceWith('new', true);
        expect(fitGISGeometry).toHaveBeenCalledWith(State.map, bounds);
    });

    it('keeps display failure separate from import success and does not move the map', async () => {
        vi.mocked(Layers.toggleGISLayerVisibility).mockResolvedValue(false);
        await expect(showImportedMapData({ kind: 'overlay', layerId: 'new' })).rejects.toThrow('could not be displayed');
        expect(fitGISGeometry).not.toHaveBeenCalled();
    });

    it('explicitly reveals landmarks and frames only newly created locations', async () => {
        const bounds: FlatBounds = [-80, 20, -79, 21];
        await showImportedMapData({ kind: 'places', landmarksCreated: 2, bounds });
        expect(Layers.revealCategory).toHaveBeenCalledWith('landmarks');
        expect(fitGISGeometry).toHaveBeenCalledWith(State.map, bounds);
    });

    it('shows the imported GPX tracks and landmarks together without revealing other tracks', async () => {
        const bounds: FlatBounds = [-80, 20, -79, 21];
        vi.mocked(Layers.isGPSTrackVisible).mockReturnValue(true);
        await showImportedMapData({ kind: 'gpx', gpsTracksCreated: 2,
            gpsTrackIds: ['new-1', 'new-2'], landmarksCreated: 1, bounds });
        expect(vi.mocked(Layers.toggleGPSTrackVisibility).mock.calls).toEqual([['new-1', true], ['new-2', true]]);
        expect(GPSTracksPanel.refreshList).toHaveBeenCalledOnce();
        expect(Layers.revealCategory).toHaveBeenCalledWith('landmarks');
        expect(fitGISGeometry).toHaveBeenCalledExactlyOnceWith(State.map, bounds);
    });

    it('supports a GPX creating only new landmarks', async () => {
        const bounds: FlatBounds = [-80, 20, -80, 20];
        await showImportedMapData({ kind: 'gpx', gpsTracksCreated: 0, landmarksCreated: 1, bounds });
        expect(Layers.toggleGPSTrackVisibility).not.toHaveBeenCalled();
        expect(Layers.revealCategory).toHaveBeenCalledWith('landmarks');
        expect(fitGISGeometry).toHaveBeenCalledWith(State.map, bounds);
    });

    it('does not zoom when an imported GPX track fails to load', async () => {
        vi.mocked(Layers.isGPSTrackVisible).mockReturnValue(false);
        await expect(showImportedMapData({ kind: 'gpx', gpsTracksCreated: 1,
            gpsTrackIds: ['new'], bounds: [-80, 20, -79, 21] })).rejects.toThrow('could not be displayed');
        expect(GPSTracksPanel.refreshList).toHaveBeenCalledOnce();
        expect(fitGISGeometry).not.toHaveBeenCalled();
    });

    it('does not guess track identities when an import response omits them', async () => {
        await expect(showImportedMapData({ kind: 'gpx', gpsTracksCreated: 1 })).rejects.toThrow('could not be identified');
        expect(Layers.toggleGPSTrackVisibility).not.toHaveBeenCalled();
        expect(fitGISGeometry).not.toHaveBeenCalled();
    });
});

it('rejects even an unknown result before dispatch when the map is absent', async () => {
    State.map = null;
    await expect(showImportedMapData({ kind: 'unknown' })).rejects.toThrow('The map is not ready yet. Please try again.');
});
it('resolves unknown categories without changing the camera', async () => {
    State.map = {} as NonNullable<typeof State.map>;
    vi.clearAllMocks();
    await expect(showImportedMapData({ kind: 'unknown', bounds: [0, 0, 1, 1] })).resolves.toBeUndefined();
    expect(fitGISGeometry).not.toHaveBeenCalled();
});
it('waits for track activation before deciding whether to reveal landmarks', async () => {
    State.map = {} as NonNullable<typeof State.map>;
    vi.clearAllMocks();
    let finish!: (value: boolean) => void;
    vi.mocked(Layers.toggleGPSTrackVisibility).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    vi.mocked(Layers.isGPSTrackVisible).mockReturnValue(true);
    const pending = showImportedMapData({ kind: 'gpx', gpsTracksCreated: 1, gpsTrackIds: ['one'], landmarksCreated: 1 });
    expect(Layers.revealCategory).not.toHaveBeenCalled();
    finish(true);
    await pending;
    expect(Layers.revealCategory).toHaveBeenCalledWith('landmarks');
});

function showImportedMapData(result: unknown) { return showImported(result as ImportedMapResult); }

const Config = importedConfig as unknown as ModuleMock<typeof importedConfig>;

const LandmarkManager = importedLandmarkManager as unknown as ModuleMock<typeof importedLandmarkManager>;

const Layers = importedLayers as unknown as ModuleMock<typeof importedLayers>;

const GISLayersPanel = importedGISLayersPanel as unknown as ModuleMock<typeof importedGISLayersPanel>;

const GPSTracksPanel = importedGPSTracksPanel as unknown as ModuleMock<typeof importedGPSTracksPanel>;
