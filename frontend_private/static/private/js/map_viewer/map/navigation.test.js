import { configureMapNavigation, goToStation, goToLandmark } from './navigation.js';
import { Config, DEFAULTS } from '../config.js';
import { State, createDefaultDisplayPreferences } from '../state.js';
import { ProjectPanel } from '../components/project_panel.js';

let map;
beforeEach(() => {
    localStorage.clear();
    State.resetLayerState();
    State.displayPreferences = createDefaultDisplayPreferences();
    State.map = null;
    Config._projects = [
        { id: 'target', name: 'Target', country: 'Mexico' },
        { id: 'selected', name: 'Selected', country: 'Mexico' },
        { id: 'unselected', name: 'Unselected', country: 'Mexico' },
        { id: 'other-country', name: 'Other country', country: 'USA' },
    ];
    Config._networks = [];
    map = { flyTo: vi.fn() };
    configureMapNavigation(map);
});
afterEach(() => {
    Config._projects = null;
    Config._networks = null;
    configureMapNavigation(null);
    localStorage.clear();
    document.body.innerHTML = '';
});

it('reveals only the target project while restoring the country gate and retained sibling selections', () => {
    State.projectLayerStates = new Map([['target', false], ['selected', true], ['unselected', false]]);
    localStorage.setItem(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY, JSON.stringify({ Mexico: false, USA: false }));
    ProjectPanel.revealProject('target');
    expect(State.effectiveProjectVisibility.get('target')).toBe(true);
    expect(State.effectiveProjectVisibility.get('selected')).toBe(true);
    expect(State.effectiveProjectVisibility.get('unselected')).toBe(false);
    expect(State.projectLayerStates.get('unselected')).toBe(false);
    expect(JSON.parse(localStorage.getItem(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY))).toEqual({ USA: false });
});

it('station navigation reveals its station type without showing unrelated station types', () => {
    State.displayPreferences.categories.surveyStations = false;
    State.displayPreferences.stationTypes.biology = false;
    State.displayPreferences.stationTypes.bone = false;
    State.allStations.set('s1', { project: 'target', type: 'biology' });
    goToStation('s1', 20, -87);
    expect(State.displayPreferences.categories.surveyStations).toBe(true);
    expect(State.displayPreferences.stationTypes.biology).toBe(true);
    expect(State.displayPreferences.stationTypes.bone).toBe(false);
    expect(map.flyTo).toHaveBeenCalledWith({ center: [-87, 20], zoom: DEFAULTS.MAP.FLY_TO_ZOOM });
});

it('surface and landmark navigation reveal their categories', () => {
    State.allSurfaceStations.set('s1', { network: 'n1' });
    State.displayPreferences.categories.surfaceStations = false;
    State.displayPreferences.categories.landmarks = false;
    goToStation('s1', 20, -87);
    expect(State.networkLayerStates.get('n1')).toBe(true);
    expect(State.displayPreferences.categories.surfaceStations).toBe(true);
    goToLandmark('l1', 21, -88);
    expect(State.displayPreferences.categories.landmarks).toBe(true);
});
