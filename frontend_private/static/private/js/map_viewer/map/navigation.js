import { DEFAULTS } from '../config.js';
import { State } from '../state.js';
import { Layers } from './layers.js';
import { ProjectPanel } from '../components/project_panel.js';
import { beginMapNavigation, resetMapNavigation } from './navigation_intent.js';

let activeMap = null;

export function configureMapNavigation(map) {
    activeMap = map;
    resetMapNavigation(map);
}

export async function goToStation(id, lat, lon) {
    if (!activeMap) return;
    const map = activeMap;
    const station = State.allStations.get(id);
    const surfaceStation = State.allSurfaceStations.get(id);
    const navigation = beginMapNavigation(map, station ? `project:${station.project}`
        : surfaceStation ? `network:${surfaceStation.network}` : `station:${id}`);
    if (station) {
        Layers.revealCategory('surveyStations', { stationType: station.type || 'sensor' });
        ProjectPanel.revealProject(station.project);
    } else if (surfaceStation) {
        Layers.revealCategory('surfaceStations');
        Layers.toggleNetworkVisibility(surfaceStation.network, true);
    }
    await Layers.whenDisplayApplied();
    if (navigation.isCurrent() && activeMap === map) {
        map.flyTo({ center: [lon, lat], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
    }
}

export async function goToLandmark(id, lat, lon) {
    if (!activeMap) return;
    const map = activeMap;
    const navigation = beginMapNavigation(map, `landmark:${id}`);
    Layers.revealCategory('landmarks');
    await Layers.whenDisplayApplied();
    if (navigation.isCurrent() && activeMap === map) {
        map.flyTo({ center: [lon, lat], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
    }
}
