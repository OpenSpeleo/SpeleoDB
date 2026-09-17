import { refreshImportedMapData, showImportedMapData } from './map_import_navigation.js';
import { Config } from '../config.js';
import { State } from '../state.js';
import { LandmarkManager } from '../landmarks/manager.js';
import { Layers } from '../map/layers.js';
import { fitGISGeometry } from '../map/geometry_camera.js';
import { GISLayersPanel } from './gis_layers_panel.js';
import { GPSTracksPanel } from './gps_tracks_panel.js';

vi.mock('../config.js', () => ({ Config: { loadGISLayers: vi.fn(), loadGPSTracks: vi.fn() } }));
vi.mock('../state.js', () => ({ State: { map: {}, gisLayerBounds: new Map() } }));
vi.mock('../landmarks/manager.js', () => ({ LandmarkManager: { loadCollections: vi.fn(), loadAllLandmarks: vi.fn() } }));
vi.mock('../map/layers.js', () => ({ Layers: {
    addLandmarkLayer: vi.fn(), reorderLayers: vi.fn(), revealCategory: vi.fn(), toggleGISLayerVisibility: vi.fn(),
    toggleGPSTrackVisibility: vi.fn(), isGPSTrackVisible: vi.fn(),
} }));
vi.mock('../map/geometry_camera.js', () => ({ fitGISGeometry: vi.fn() }));
vi.mock('./gis_layers_panel.js', () => ({ GISLayersPanel: { refreshList: vi.fn(), init: vi.fn(), setupStackListener: vi.fn() } }));
vi.mock('./gps_tracks_panel.js', () => ({ GPSTracksPanel: { refreshList: vi.fn(), init: vi.fn() } }));
vi.mock('./gis_geometries_panel.js', () => ({ GISGeometriesPanel: { setupStackListener: vi.fn() } }));

describe('imported map data navigation', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        document.body.replaceChildren();
        State.map = {};
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
        Config.loadGISLayers.mockRejectedValue(new Error('Offline'));
        await expect(refreshImportedMapData({ kind: 'overlay' })).rejects.toThrow('Offline');
        expect(GISLayersPanel.init).not.toHaveBeenCalled();
    });

    it('reloads only landmarks after place creation without changing their visibility', async () => {
        const geojson = { type: 'FeatureCollection', features: [] };
        LandmarkManager.loadAllLandmarks.mockResolvedValue(geojson);
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
        const bounds = [-80, 20, -79, 21];
        State.gisLayerBounds.set('new', bounds);
        Layers.toggleGISLayerVisibility.mockResolvedValue(true);
        await showImportedMapData({ kind: 'overlay', layerId: 'new' });
        expect(Layers.toggleGISLayerVisibility).toHaveBeenCalledExactlyOnceWith('new', true);
        expect(fitGISGeometry).toHaveBeenCalledWith(State.map, bounds);
    });

    it('keeps display failure separate from import success and does not move the map', async () => {
        Layers.toggleGISLayerVisibility.mockResolvedValue(false);
        await expect(showImportedMapData({ kind: 'overlay', layerId: 'new' })).rejects.toThrow('could not be displayed');
        expect(fitGISGeometry).not.toHaveBeenCalled();
    });

    it('explicitly reveals landmarks and frames only newly created locations', async () => {
        const bounds = [-80, 20, -79, 21];
        await showImportedMapData({ kind: 'places', landmarksCreated: 2, bounds });
        expect(Layers.revealCategory).toHaveBeenCalledWith('landmarks');
        expect(fitGISGeometry).toHaveBeenCalledWith(State.map, bounds);
    });

    it('shows the imported GPX tracks and landmarks together without revealing other tracks', async () => {
        const bounds = [-80, 20, -79, 21];
        Layers.isGPSTrackVisible.mockReturnValue(true);
        await showImportedMapData({ kind: 'gpx', gpsTracksCreated: 2,
            gpsTrackIds: ['new-1', 'new-2'], landmarksCreated: 1, bounds });
        expect(Layers.toggleGPSTrackVisibility.mock.calls).toEqual([['new-1', true], ['new-2', true]]);
        expect(GPSTracksPanel.refreshList).toHaveBeenCalledOnce();
        expect(Layers.revealCategory).toHaveBeenCalledWith('landmarks');
        expect(fitGISGeometry).toHaveBeenCalledExactlyOnceWith(State.map, bounds);
    });

    it('supports a GPX creating only new landmarks', async () => {
        const bounds = [-80, 20, -80, 20];
        await showImportedMapData({ kind: 'gpx', gpsTracksCreated: 0, landmarksCreated: 1, bounds });
        expect(Layers.toggleGPSTrackVisibility).not.toHaveBeenCalled();
        expect(Layers.revealCategory).toHaveBeenCalledWith('landmarks');
        expect(fitGISGeometry).toHaveBeenCalledWith(State.map, bounds);
    });

    it('does not zoom when an imported GPX track fails to load', async () => {
        Layers.isGPSTrackVisible.mockReturnValue(false);
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
