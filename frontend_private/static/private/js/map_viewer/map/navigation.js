import { DEFAULTS } from '../config.js';
import { State } from '../state.js';
import { Layers } from './layers.js';

let activeMap = null;

export function configureMapNavigation(map) {
    activeMap = map;
}

export function goToStation(id, lat, lon) {
    if (!activeMap) return;
    activeMap.flyTo({ center: [lon, lat], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
    const station = State.allStations.get(id);
    const surfaceStation = State.allSurfaceStations.get(id);
    if (station) Layers.toggleProjectVisibility(station.project, true);
    else if (surfaceStation) Layers.toggleNetworkVisibility(surfaceStation.network, true);
}

export function goToLandmark(id, lat, lon) {
    if (!activeMap) return;
    activeMap.flyTo({ center: [lon, lat], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
}
