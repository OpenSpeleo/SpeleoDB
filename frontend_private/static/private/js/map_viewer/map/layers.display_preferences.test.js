import { Config, DEFAULTS } from '../config.js';
import { State, createDefaultDisplayPreferences } from '../state.js';
import { Layers } from './layers.js';

vi.mock('./geojson.js', () => ({ computeGeoJSONBounds: () => ({ isEmpty: () => false }) }));

function point(id, properties = {}) {
    return { type: 'Feature', id, geometry: { type: 'Point', coordinates: [-87, 20] }, properties };
}

function collection(features) { return { type: 'FeatureCollection', features }; }

function createMap() {
    const layers = new Map();
    const sources = new Map();
    return {
        getStyle: () => ({ layers: [...layers.values()] }),
        getLayer: id => layers.get(id),
        getSource: id => sources.get(id),
        addLayer: vi.fn(layer => layers.set(layer.id, layer)),
        removeLayer: id => layers.delete(id),
        addSource: vi.fn((id, source) => sources.set(id, { ...source, _data: source.data, setData: vi.fn() })),
        removeSource: id => sources.delete(id),
        hasImage: () => true,
        setLayoutProperty: vi.fn((id, key, value) => {
            const layer = layers.get(id);
            layer.layout = { ...layer.layout, [key]: value };
        }),
        setFilter: vi.fn((id, filter) => { layers.get(id).filter = filter; }),
        setPaintProperty: vi.fn(),
        moveLayer: vi.fn(), fitBounds: vi.fn(), flyTo: vi.fn(), setStyle: vi.fn(),
    };
}

function visibility(id) { return State.map.getLayer(id)?.layout?.visibility; }

beforeEach(() => {
    State.resetLayerState();
    State.displayPreferences = createDefaultDisplayPreferences();
    State.map = createMap();
    Config._projects = [{ id: 'p1', name: 'Survey', color: '#123456' }];
    localStorage.clear();
});

afterEach(() => {
    State.map = null;
    State.displayPreferences = createDefaultDisplayPreferences();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
});

it('composes station and subtype gates with project and country visibility while preserving survey linework', () => {
    const map = State.map;
    map.addLayer({ id: 'project-layer-p1', type: 'line' });
    State.allProjectLayers.set('p1', ['project-layer-p1']);
    Layers.addSubSurfaceStationLayer('p1', collection([
        point('sensor'), point('legacy', { type: null }), point('bio', { type: 'biology' }),
    ]));
    Layers.setStationTypeVisibility('biology', false);
    expect(visibility('project-layer-p1')).toBe('visible');
    expect(visibility('stations-p1-circles')).toBe('visible');
    expect(visibility('stations-p1-biology-icons')).toBe('none');
    expect(map.getLayer('stations-p1-labels').filter).toEqual([
        'in', ['coalesce', ['get', 'type'], 'sensor'], ['literal', ['sensor', 'bone', 'artifact', 'geology']],
    ]);
    expect(map.getLayer('stations-p1-circles').filter).toEqual([
        'any', ['!', ['has', 'type']], ['==', ['get', 'type'], null], ['==', ['get', 'type'], 'sensor'],
    ]);
    Layers.applyProjectVisibility('p1', false);
    Layers.setCategoryVisibility('surveyStations', false);
    Layers.setCategoryVisibility('surveyStations', true);
    expect(visibility('stations-p1-circles')).toBe('none');
    Layers.applyProjectVisibility('p1', true);
    expect(visibility('stations-p1-circles')).toBe('visible');
    expect(visibility('stations-p1-biology-icons')).toBe('none');
    expect(visibility('project-layer-p1')).toBe('visible');
    Layers.setCategoryVisibility('surveyStations', false);
    expect(visibility('stations-p1-circles')).toBe('none');
    expect(visibility('project-layer-p1')).toBe('visible');
});

it.each(DEFAULTS.DISPLAY.STATION_TYPES)('honors $id before creation and after station refresh', ({ id, layerSuffix }) => {
    Layers.setStationTypeVisibility(id, false);
    const data = collection([point('station', { type: id })]);
    Layers.addSubSurfaceStationLayer('p1', data);
    Layers.addSubSurfaceStationLayer('p1', data);
    expect(visibility(`stations-p1-${layerSuffix}`)).toBe('none');
    expect(State.map.getLayer('stations-p1-labels').filter[2][1]).not.toContain(id);
});

it('composes surface station preferences with network selection on refresh', () => {
    Layers.setCategoryVisibility('surfaceStations', false);
    Layers.addSurfaceStationLayer('n1', collection([point('surface')]));
    Layers.toggleNetworkVisibility('n1', true);
    expect(visibility('surface-stations-n1')).toBe('none');
    Layers.setCategoryVisibility('surfaceStations', true);
    expect(visibility('surface-stations-n1')).toBe('visible');
    Layers.toggleNetworkVisibility('n1', false);
    Layers.addSurfaceStationLayer('n1', collection([point('surface')]));
    expect(visibility('surface-stations-n1-labels')).toBe('none');
});

it('keeps landmarks, leads and cylinders gated through creation and project changes', () => {
    for (const category of ['landmarks', 'explorationLeads', 'cylinders']) Layers.setCategoryVisibility(category, false);
    Layers.addLandmarkLayer(collection([point('landmark')]));
    Layers.addExplorationLeadMarker('lead', [-87, 20], 'Survey', '', 'p1');
    Layers.addCylinderInstallsLayer(collection([point('cylinder', { project_id: 'p1' })]));
    Layers.applyProjectVisibility('p1', false);
    Layers.applyProjectVisibility('p1', true);
    for (const id of ['landmarks-layer', 'landmarks-labels', 'exploration-leads-layer', 'cylinder-installs-layer', 'cylinder-installs-labels']) {
        expect(visibility(id)).toBe('none');
    }
    Layers.setCategoryVisibility('explorationLeads', true);
    expect(visibility('exploration-leads-layer')).toBe('visible');
    expect(State.map.getLayer('exploration-leads-layer').filter).toEqual(Layers.getProjectScopedMarkerFilter());
});

it('changes every category without fetching, moving the map, rebuilding data, or resetting the style', () => {
    vi.stubGlobal('fetch', vi.fn());
    for (const { id } of DEFAULTS.DISPLAY.CATEGORIES) {
        Layers.setCategoryVisibility(id, false);
        Layers.setCategoryVisibility(id, true);
    }
    expect(fetch).not.toHaveBeenCalled();
    expect(State.map.addSource).not.toHaveBeenCalled();
    expect(State.map.fitBounds).not.toHaveBeenCalled();
    expect(State.map.flyTo).not.toHaveBeenCalled();
    expect(State.map.setStyle).not.toHaveBeenCalled();
    expect(State.gpsTrackLayerStates.size).toBe(0);
    expect(State.gisLayerStates.size).toBe(0);
    expect(State.gisGeometryStates.size).toBe(0);
});

it('reveals only the requested category and station subtype', () => {
    Layers.setCategoryVisibility('surveyStations', false);
    Layers.setCategoryVisibility('landmarks', false);
    Layers.setStationTypeVisibility('biology', false);
    Layers.setStationTypeVisibility('sensor', false);
    Layers.revealCategory('surveyStations', { stationType: 'biology' });
    expect(State.displayPreferences.categories.surveyStations).toBe(true);
    expect(State.displayPreferences.categories.landmarks).toBe(false);
    expect(State.displayPreferences.stationTypes.biology).toBe(true);
    expect(State.displayPreferences.stationTypes.sensor).toBe(false);
    Layers.revealCategory('surveyStations', { stationType: undefined });
    expect(State.displayPreferences.stationTypes.sensor).toBe(true);
});

it('emits color and preference changes once, sharing legacy accessors without rescanning features', () => {
    const colorChanged = vi.fn();
    const preferencesChanged = vi.fn();
    window.addEventListener('speleo:color-mode-changed', colorChanged);
    window.addEventListener('speleo:display-preferences-changed', preferencesChanged);
    State.projectDepthDomains.set('p1', { min: 0, max: 100 });
    Layers.setColorMode('depth');
    expect(colorChanged).toHaveBeenCalledTimes(1);
    expect(preferencesChanged).toHaveBeenCalledTimes(1);
    expect(Layers.colorMode).toBe(State.displayPreferences.colorMode);
    Layers.setCategoryVisibility('surveyStations', false);
    expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
    State.landmarksVisible = false;
    expect(State.displayPreferences.categories.landmarks).toBe(false);
    window.removeEventListener('speleo:color-mode-changed', colorChanged);
    window.removeEventListener('speleo:display-preferences-changed', preferencesChanged);
});
