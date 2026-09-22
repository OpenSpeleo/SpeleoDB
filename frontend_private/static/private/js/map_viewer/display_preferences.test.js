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

it.each([
    { depthLimitFeet: null, depthUnit: 'ft' },
    { depthLimitFeet: null, depthUnit: 'm' },
    { depthLimitFeet: 125.75, depthUnit: 'ft' },
    { depthLimitFeet: 100 / DEFAULTS.MEASUREMENT.METERS_PER_FOOT, depthUnit: 'm' },
    { depthLimitFeet: 1e-12, depthUnit: 'ft' },
])('restores the canonical depth limit and display unit: %j', preferences => {
    localStorage.setItem(storageKey, JSON.stringify({
        version: DEFAULTS.DISPLAY.STORAGE_VERSION,
        ...preferences,
    }));

    DisplayPreferences.init({ persist: true });

    expect(State.displayPreferences).toMatchObject(preferences);
    expect(JSON.parse(localStorage.getItem(storageKey))).toMatchObject(preferences);
});

it('adds automatic feet defaults to legacy preferences without discarding their settings', () => {
    localStorage.setItem(storageKey, JSON.stringify({
        version: DEFAULTS.DISPLAY.STORAGE_VERSION,
        colorMode: 'depth',
        categories: { landmarks: false },
    }));

    DisplayPreferences.init({ persist: true });

    const expected = { colorMode: 'depth', depthLimitFeet: null, depthUnit: 'ft' };
    expect(State.displayPreferences).toMatchObject(expected);
    expect(State.displayPreferences.categories.landmarks).toBe(false);
    expect(JSON.parse(localStorage.getItem(storageKey))).toMatchObject(expected);
});

it.each(['0', '-1', '"100"', '"Infinity"', 'true', '[]', '{}', '1e309', '-1e309'])(
    'rejects invalid saved depth limit %s while preserving a valid unit and other settings', value => {
        localStorage.setItem(storageKey, `{"version":${DEFAULTS.DISPLAY.STORAGE_VERSION},"depthLimitFeet":${value},"depthUnit":"m","colorMode":"depth"}`);

        DisplayPreferences.init({ persist: true });

        const expected = { depthLimitFeet: null, depthUnit: 'm', colorMode: 'depth' };
        expect(State.displayPreferences).toMatchObject(expected);
        expect(JSON.parse(localStorage.getItem(storageKey))).toMatchObject(expected);
    },
);

it.each([null, 'meters', 'FT', 25, true, [], {}].map(depthUnit => ({ depthUnit })))(
    'rejects invalid saved depth unit %j without discarding a valid cap', ({ depthUnit }) => {
        localStorage.setItem(storageKey, JSON.stringify({
            version: DEFAULTS.DISPLAY.STORAGE_VERSION,
            depthLimitFeet: 175.25,
            depthUnit,
        }));

        DisplayPreferences.init({ persist: true });

        const expected = { depthLimitFeet: 175.25, depthUnit: 'ft' };
        expect(State.displayPreferences).toMatchObject(expected);
        expect(JSON.parse(localStorage.getItem(storageKey))).toMatchObject(expected);
    },
);

it('persists physical feet independently of the selected unit and retains the unit when cleared', () => {
    const depthLimitFeet = 100 / DEFAULTS.MEASUREMENT.METERS_PER_FOOT;
    DisplayPreferences.init({ persist: true });
    Layers.setDepthLimit(depthLimitFeet, 'm');
    DisplayPreferences.init({ persist: true });
    expect(State.displayPreferences).toMatchObject({ depthLimitFeet, depthUnit: 'm' });

    Layers.setDepthLimit(null, 'm');
    DisplayPreferences.init({ persist: true });

    expect(State.displayPreferences).toMatchObject({ depthLimitFeet: null, depthUnit: 'm' });
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

it.each(['depth', 'shot'])('resets public routes without reading or changing private %s preferences', mode => {
    DisplayPreferences.init({ persist: true });
    Layers.setColorMode(mode);
    Layers.setCategoryVisibility('surveyStations', false);
    Layers.setDepthLimit(125.75, 'm');
    const saved = localStorage.getItem(storageKey);
    const read = vi.spyOn(localStorage, 'getItem');
    const write = vi.spyOn(localStorage, 'setItem');
    DisplayPreferences.init({ persist: false });
    Layers.setCategoryVisibility('landmarks', false);
    expect(State.displayPreferences.colorMode).toBe('project');
    expect(State.displayPreferences.categories.surveyStations).toBe(true);
    expect(State.displayPreferences.depthLimitFeet).toBeNull();
    expect(State.displayPreferences.depthUnit).toBe('ft');
    Layers.setDepthLimit(25, 'ft');
    expect(read).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
    expect(localStorage.getItem(storageKey)).toBe(saved);

    DisplayPreferences.init({ persist: true });
    expect(State.displayPreferences).toMatchObject({ depthLimitFeet: 125.75, depthUnit: 'm' });
});

it('keeps settings usable when browser storage fails and reports the limitation', () => {
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('quota'); });
    DisplayPreferences.init({ persist: true });
    Layers.setCategoryVisibility('landmarks', false);
    Layers.setDepthLimit(125.75, 'm');
    expect(State.landmarksVisible).toBe(false);
    expect(State.displayPreferences).toMatchObject({ depthLimitFeet: 125.75, depthUnit: 'm' });
    expect(DisplayPreferences.storageAvailable).toBe(false);
    DisplayPreferences.reset();
    expect(State.displayPreferences).toEqual(createDefaultDisplayPreferences());
    expect(DisplayPreferences.storageAvailable).toBe(false);
});

it('resets display preferences without clearing selections, data, or unrelated storage', () => {
    DisplayPreferences.init({ persist: true });
    Layers.setCategoryVisibility('surveyStations', false);
    Layers.setStationTypeVisibility('sensor', false);
    Layers.setDepthLimit(125.75, 'm');
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
    expect(JSON.parse(localStorage.getItem(storageKey))).toMatchObject({ depthLimitFeet: null, depthUnit: 'ft' });
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


it('persists shot mode, restores it after layer-state resets, and resets to survey', () => {
    DisplayPreferences.init({ persist: true });
    Layers.setColorMode('shot');
    expect(JSON.parse(localStorage.getItem(storageKey)).colorMode).toBe('shot');
    State.resetLayerState();
    DisplayPreferences.init({ persist: true });
    expect(State.displayPreferences.colorMode).toBe('shot');
    DisplayPreferences.reset();
    expect(State.displayPreferences.colorMode).toBe('project');
    expect(JSON.parse(localStorage.getItem(storageKey)).colorMode).toBe('project');
});
