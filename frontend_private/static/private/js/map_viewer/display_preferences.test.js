import { DEFAULTS } from './config.js';
import { DisplayPreferences } from './display_preferences.js';
import { Layers } from './map/layers.js';
import { State, createDefaultDisplayPreferences } from './state.js';

const storageKey = DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES;

beforeEach(() => {
    State.resetLayerState();
    State.map = null;
    State.displayPreferences = createDefaultDisplayPreferences();
    localStorage.clear();
});

afterEach(() => {
    DisplayPreferences.destroy();
    vi.restoreAllMocks();
});

it('restores only valid known preferences and saves instant changes in the private viewer', () => {
    localStorage.setItem(storageKey, JSON.stringify({
        version: DEFAULTS.DISPLAY.STORAGE_VERSION,
        colorMode: 'depth',
        categories: { landmarks: false, surveyStations: 'false', unknown: false },
        stationTypes: { biology: false, sensor: null },
    }));
    DisplayPreferences.init({ persist: true });
    expect(State.displayPreferences.colorMode).toBe('depth');
    expect(State.displayPreferences.categories.landmarks).toBe(false);
    expect(State.displayPreferences.categories.surveyStations).toBe(true);
    expect(State.displayPreferences.categories).not.toHaveProperty('unknown');
    expect(State.displayPreferences.stationTypes.biology).toBe(false);
    expect(State.displayPreferences.stationTypes.sensor).toBe(true);
    Layers.setCategoryVisibility('surfaceStations', false);
    expect(JSON.parse(localStorage.getItem(storageKey)).categories.surfaceStations).toBe(false);
});

it('discards retired linework and overlay gates saved by an earlier settings layout', () => {
    const retired = { surveyLinework: false, gpsTracks: false, gisLayers: false, gisGeometries: false };
    localStorage.setItem(storageKey, JSON.stringify({
        version: DEFAULTS.DISPLAY.STORAGE_VERSION,
        categories: { ...retired, landmarks: false },
    }));
    DisplayPreferences.init({ persist: true });
    expect(State.displayPreferences.categories.landmarks).toBe(false);
    for (const id of Object.keys(retired)) {
        expect(State.displayPreferences.categories).not.toHaveProperty(id);
        expect(JSON.parse(localStorage.getItem(storageKey)).categories).not.toHaveProperty(id);
    }
});

it.each(['not JSON', 'null', '[]', '{"version":999,"colorMode":"depth"}'])('uses defaults for invalid or unsupported saved data: %s', stored => {
    localStorage.setItem(storageKey, stored);
    DisplayPreferences.init({ persist: true });
    expect(State.displayPreferences).toEqual(createDefaultDisplayPreferences());
    expect(DisplayPreferences.storageAvailable).toBe(true);
});

it('resets public routes without reading, replacing, or persisting private browser preferences', () => {
    DisplayPreferences.init({ persist: true });
    Layers.setColorMode('depth');
    Layers.setCategoryVisibility('surveyStations', false);
    const saved = localStorage.getItem(storageKey);
    const read = vi.spyOn(localStorage, 'getItem');
    const write = vi.spyOn(localStorage, 'setItem');
    DisplayPreferences.init({ persist: false });
    Layers.setCategoryVisibility('landmarks', false);
    expect(State.displayPreferences.colorMode).toBe('project');
    expect(State.displayPreferences.categories.surveyStations).toBe(true);
    expect(read).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
    expect(localStorage.getItem(storageKey)).toBe(saved);
});

it('keeps settings usable when browser storage fails and reports the limitation', () => {
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('quota'); });
    DisplayPreferences.init({ persist: true });
    Layers.setCategoryVisibility('landmarks', false);
    expect(State.landmarksVisible).toBe(false);
    expect(DisplayPreferences.storageAvailable).toBe(false);
});

it('resets display preferences without clearing selections, data, or unrelated storage', () => {
    DisplayPreferences.init({ persist: true });
    Layers.setCategoryVisibility('surveyStations', false);
    Layers.setStationTypeVisibility('sensor', false);
    State.projectLayerStates.set('project', false);
    State.networkLayerStates.set('network', false);
    State.gpsTrackLayerStates.set('track', true);
    State.gpsTrackCache.set('track', { type: 'FeatureCollection', features: [] });
    localStorage.setItem(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY, '{"Mexico":false}');
    localStorage.setItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE, 'esri-satellite');
    DisplayPreferences.reset();
    expect(State.displayPreferences).toEqual(createDefaultDisplayPreferences());
    expect(State.projectLayerStates.get('project')).toBe(false);
    expect(State.networkLayerStates.get('network')).toBe(false);
    expect(State.gpsTrackLayerStates.get('track')).toBe(true);
    expect(State.gpsTrackCache.has('track')).toBe(true);
    expect(localStorage.getItem(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY)).toBe('{"Mexico":false}');
    expect(localStorage.getItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE)).toBe('esri-satellite');
    expect(JSON.parse(localStorage.getItem(storageKey)).stationTypes.sensor).toBe(true);
});

it('keeps one persistence listener after repeated initialization and removes it on destroy', () => {
    DisplayPreferences.init({ persist: true });
    DisplayPreferences.init({ persist: true });
    const write = vi.spyOn(localStorage, 'setItem');
    Layers.setCategoryVisibility('landmarks', false);
    expect(write).toHaveBeenCalledTimes(1);
    DisplayPreferences.destroy();
    Layers.setCategoryVisibility('landmarks', true);
    expect(write).toHaveBeenCalledTimes(1);
});
