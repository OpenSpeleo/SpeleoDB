import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerNavigationMap } from '../../../../../../ts-types/domain/map-runtime.ts';
import { DEFAULTS } from '../config.ts';
import { State } from '../state.ts';
import { Layers } from './layers.ts';
import { ProjectPanel } from '../components/project_panel.ts';
import { beginMapNavigation, resetMapNavigation } from './navigation_intent.ts';

let activeMap: ViewerNavigationMap | null = null;

export function configureMapNavigation(map: ViewerNavigationMap | null) {
    activeMap = map;
    resetMapNavigation(map);
}

export async function goToStation(id: EntityId, lat: number, lon: number) {
    if (!activeMap) return;
    const map = activeMap;
    const station = State.allStations.get(id);
    const surfaceStation = State.allSurfaceStations.get(id);
    const navigation = beginMapNavigation(map, station ? `project:${station.project}`
        : surfaceStation ? `network:${surfaceStation.network}` : `station:${id}`);
    if (station) {
        Layers.revealCategory('surveyStations', { stationType: (station.type || 'sensor') as import('../../../../../../ts-types/domain/map-display.ts').DisplayStationType });
        ProjectPanel.revealProject(station.project!);
    } else if (surfaceStation) {
        Layers.revealCategory('surfaceStations');
        void Layers.toggleNetworkVisibility(surfaceStation.network!, true);
    }
    await Layers.whenDisplayApplied();
    if (navigation.isCurrent() && activeMap === map) {
        map.flyTo({ center: [lon, lat], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
    }
}

export async function goToLandmark(id: EntityId, lat: number, lon: number) {
    if (!activeMap) return;
    const map = activeMap;
    const navigation = beginMapNavigation(map, `landmark:${id}`);
    Layers.revealCategory('landmarks');
    await Layers.whenDisplayApplied();
    if (navigation.isCurrent() && activeMap === map) {
        map.flyTo({ center: [lon, lat], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
    }
}
