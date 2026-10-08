import type { ImportedMapResult } from '../../../../../../ts-types/domain/map-import.ts';
import { Config } from '../config.ts';
import { State } from '../state.ts';
import { LandmarkManager } from '../landmarks/manager.ts';
import { Layers } from '../map/layers.ts';
import { fitGISGeometry } from '../map/geometry_camera.ts';
import { GISLayersPanel } from './gis_layers_panel.ts';
import { GPSTracksPanel } from './gps_tracks_panel.ts';
import { GISGeometriesPanel } from './gis_geometries_panel.ts';

/** Refresh only imported categories. Rejection means publication succeeded but refresh failed. */
export async function refreshImportedMapData(result: ImportedMapResult) {
    if (result.kind === 'overlay') {
        await Config.loadGISLayers({ force: true, throwOnError: true });
        if (document.getElementById('gis-layers-panel')) GISLayersPanel.refreshList();
        else GISLayersPanel.init();
    }
    if (result.landmarksCreated! > 0) {
        await LandmarkManager.loadCollections({ throwOnError: true });
        const landmarks = await LandmarkManager.loadAllLandmarks({ throwOnError: true });
        Layers.addLandmarkLayer(landmarks);
        void Layers.reorderLayers();
    }
    if (result.gpsTracksCreated! > 0) {
        await Config.loadGPSTracks({ force: true, throwOnError: true });
        if (document.getElementById('gps-tracks-panel')) GPSTracksPanel.refreshList();
        else GPSTracksPanel.init();
    }
    if (result.kind === 'overlay' || result.gpsTracksCreated! > 0) {
        GISLayersPanel.setupStackListener();
        GISGeometriesPanel.setupStackListener();
    }
}

/** Only an explicit Show on map action changes visibility or the camera. */
export async function showImportedMapData(result: ImportedMapResult) {
    if (!State.map) throw new Error('The map is not ready yet. Please try again.');
    let bounds = result.bounds;
    if (result.kind === 'overlay') {
        const layerId = String(result.layerId);
        const displayed = await Layers.toggleGISLayerVisibility(layerId, true);
        GISLayersPanel.refreshList();
        if (!displayed) throw new Error('The overlay was imported but could not be displayed. Please try again.');
        bounds = State.gisLayerBounds.get(layerId);
    } else if (result.kind === 'places' || result.kind === 'gpx') {
        if (result.gpsTracksCreated! > 0) {
            const trackIds = result.gpsTrackIds || [];
            if (trackIds.length !== result.gpsTracksCreated) {
                throw new Error('The imported GPS tracks could not be identified. Open them from the GPS tracks panel.');
            }
            const displayed = await Promise.all(trackIds.map(async trackId => {
                await Layers.toggleGPSTrackVisibility(trackId, true);
                return Layers.isGPSTrackVisible(trackId);
            }));
            GPSTracksPanel.refreshList();
            if (displayed.some(visible => !visible)) {
                throw new Error('Some imported GPS tracks could not be displayed. Please try again.');
            }
        }
        if (result.landmarksCreated! > 0) Layers.revealCategory('landmarks');
    } else {
        return;
    }
    if (bounds) fitGISGeometry(State.map, bounds);
}
