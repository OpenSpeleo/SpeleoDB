import { DEFAULTS } from '../config.js';
import { State } from '../state.js';
import { Layers } from './layers.js';
import { ProjectPanel } from '../components/project_panel.js';

let activeMap = null;

export function configureMapNavigation(map) {
    activeMap = map;
}

export function goToStation(id, lat, lon) {
    if (!activeMap) return;
    const station = State.allStations.get(id);
    const surfaceStation = State.allSurfaceStations.get(id);
    if (station) {
        Layers.revealCategory('surveyStations', { stationType: station.type || 'sensor' });
        ProjectPanel.revealProject(station.project);
    } else if (surfaceStation) {
        Layers.revealCategory('surfaceStations');
        Layers.toggleNetworkVisibility(surfaceStation.network, true);
    }
    activeMap.flyTo({ center: [lon, lat], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
}

export function goToLandmark(id, lat, lon) {
    if (!activeMap) return;
    Layers.revealCategory('landmarks');
    activeMap.flyTo({ center: [lon, lat], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
}
