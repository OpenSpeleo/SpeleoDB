import { Config, DEFAULTS } from '../config.js';
import { State, createDefaultDisplayPreferences } from '../state.js';
import { Layers } from './layers.js';
import { Colors } from './colors.js';
import { Geometry } from './geometry.js';

vi.mock('./geojson.js', () => ({ computeGeoJSONBounds: () => ({ isEmpty: () => false }) }));

function point(id, properties = {}) {
    return { type: 'Feature', id, geometry: { type: 'Point', coordinates: [-87, 20] }, properties };
}

function collection(features) { return { type: 'FeatureCollection', features }; }

function surveyCollection() {
    return collection([
        point('entrance', { name: 'Cave entrance' }),
        {
            type: 'Feature',
            properties: { section_name: 'Passage', depth: 100 },
            geometry: { type: 'LineString', coordinates: [[-87, 20], [-87.1, 20.1]] },
        },
    ]);
}

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

function widthAtZoom(expression, zoom) {
    expect(expression.slice(0, 3)).toEqual(['interpolate', ['linear'], ['zoom']]);
    const stops = expression.slice(3);
    if (zoom <= stops[0]) return stops[1];
    for (let index = 2; index < stops.length; index += 2) {
        if (zoom <= stops[index]) {
            const fraction = (zoom - stops[index - 2]) / (stops[index] - stops[index - 2]);
            return stops[index - 1] + fraction * (stops[index + 1] - stops[index - 1]);
        }
    }
    return stops.at(-1);
}

beforeEach(() => {
    State.resetLayerState();
    State.displayPreferences = createDefaultDisplayPreferences();
    State.map = createMap();
    Config._projects = [{ id: 'p1', name: 'Survey', color: '#123456' }];
    Colors.resetColorMap();
    localStorage.clear();
});

afterEach(() => {
    State.map = null;
    State.displayPreferences = createDefaultDisplayPreferences();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
});

it('keeps survey lines enabled at country scale with thin continuous overview strokes', async () => {
    const data = surveyCollection();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => data }));
    await Layers.addProjectGeoJSON('p1', '/survey.geojson');

    const source = State.map.getSource('project-geojson-p1');
    const layer = State.map.getLayer('project-layer-p1');
    expect(source.tolerance).toBe(0);
    expect(source.data.features[1].geometry).toEqual(data.features[1].geometry);
    expect(layer).toMatchObject({
        type: 'line',
        filter: ['==', '$type', 'LineString'],
        minzoom: 0,
        paint: { 'line-color': '#123456', 'line-opacity': 1 },
    });
    for (const [zoom, width] of [[0, 1], [5, 1], [7.99, 1], [8, 1], [10, 1.25], [11.5, 1.4375], [12, 1.5], [14, 2], [16, 5], [17, 5.5], [18, 6], [20, 6]]) {
        expect(widthAtZoom(layer.paint['line-width'], zoom)).toBeCloseTo(width);
    }
});

it('keeps GPS tracks visible at overview zooms without changing track geometry, color or dash pattern', async () => {
    const data = surveyCollection();
    vi.spyOn(Colors, 'getGPSTrackColor').mockReturnValue('#abcdef');
    await Layers.addGPSTrackLayer('t1', data);
    const source = State.map.getSource('gps-track-source-t1');
    const layer = State.map.getLayer('gps-track-line-t1');
    expect(source).toMatchObject({ tolerance: 0, data });
    expect(layer).toMatchObject({
        minzoom: 0,
        filter: ['==', '$type', 'LineString'],
        paint: { 'line-color': '#abcdef', 'line-dasharray': [0.1, 1.5] },
    });
    for (const [zoom, width] of [[5, 1], [8, 1], [11.5, 1.4375], [14, 2], [16, 6], [17, 6.5], [18, 7]]) {
        expect(widthAtZoom(layer.paint['line-width'], zoom)).toBeCloseTo(width);
    }
    Layers.showGPSTrackLayers('t1', false);
    expect(visibility(layer.id)).toBe('none');
    Layers.showGPSTrackLayers('t1', true);
    expect(visibility(layer.id)).toBe('visible');
    await Layers.addGPSTrackLayer('t1', data);
    expect(State.map.getSource('gps-track-source-t1').tolerance).toBe(0);
    expect(State.map.getLayer(layer.id).paint).toEqual(layer.paint);
});

it.each(['project', 'depth', 'shot'])('preserves overview rendering and visibility through refresh and style rebuild in %s mode', async mode => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => surveyCollection() }));
    Layers.setColorMode(mode);
    Layers.applyProjectVisibility('p1', false);
    await Layers.addProjectGeoJSON('p1', '/survey.geojson');
    const source = State.map.getSource('project-geojson-p1');
    const originalLayer = State.map.getLayer('project-layer-p1');
    const originalWidth = structuredClone(originalLayer.paint['line-width']);
    const expectedColor = Colors.getSurveyPaint('p1', mode, State.activeDepthDomain);

    await Layers.addProjectGeoJSON('p1', '/refreshed.geojson');
    expect(source.setData).toHaveBeenCalledOnce();
    expect(State.map.addSource).toHaveBeenCalledOnce();
    expect(State.map.getLayer('project-layer-p1')).toBe(originalLayer);
    expect(visibility('project-layer-p1')).toBe('none');

    // A base-style replacement discards map sources/layers, not display preferences.
    State.map = createMap();
    State.allProjectLayers = new Map();
    await Layers.addProjectGeoJSON('p1', '/rebuilt.geojson');
    expect(State.map.getSource('project-geojson-p1').tolerance).toBe(0);
    expect(State.map.getLayer('project-layer-p1')).toMatchObject({
        minzoom: 0,
        layout: { visibility: 'none' },
        paint: { 'line-width': originalWidth, 'line-color': expectedColor },
    });
    Layers.applyProjectVisibility('p1', true);
    Layers.setCategoryVisibility('caveEntrances', false);
    expect(visibility('project-layer-p1')).toBe('visible');
    expect(visibility('project-points-p1')).toBe('none');
    Layers.toggleProjectVisibility('p1', false);
    expect(visibility('project-layer-p1')).toBe('none');
    expect(State.displayPreferences.colorMode).toBe(mode);
});

it('shows cave entrances by default and composes their category with project and country gates', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => surveyCollection() }));
    Config._projects.push({ id: 'p2', name: 'Hidden country', color: '#abcdef' });
    Layers.applyProjectVisibility('p2', false);
    await Layers.addProjectGeoJSON('p1', '/p1.geojson');
    await Layers.addProjectGeoJSON('p2', '/p2.geojson');
    expect(visibility('project-points-p1')).toBe('visible');
    expect(visibility('project-points-p2')).toBe('none');
    expect(State.map.getLayer('project-points-p1')).toMatchObject({
        filter: ['==', '$type', 'Point'],
        minzoom: DEFAULTS.ZOOM_LEVELS.PROJECT_ENTRY_SYMBOL,
        layout: { 'text-field': '★' },
    });

    Layers.setCategoryVisibility('caveEntrances', false);
    expect(visibility('project-points-p1')).toBe('none');
    expect(visibility('project-layer-p1')).toBe('visible');
    expect(visibility('project-labels-p1')).toBe('visible');
    Layers.toggleProjectVisibility('p1', false);
    Layers.toggleProjectVisibility('p1', true);
    Layers.applyProjectVisibility('p2', true);
    expect(visibility('project-points-p1')).toBe('none');
    expect(visibility('project-points-p2')).toBe('none');
    expect(visibility('project-layer-p2')).toBe('visible');

    Layers.toggleProjectVisibility('p1', false);
    Layers.applyProjectVisibility('p2', false);
    Layers.setCategoryVisibility('caveEntrances', true);
    expect(visibility('project-points-p1')).toBe('none');
    expect(visibility('project-points-p2')).toBe('none');
    expect(State.projectLayerStates.get('p1')).toBe(false);
    expect(State.projectLayerStates.get('p2')).toBeUndefined();
    Layers.toggleProjectVisibility('p1', true);
    expect(visibility('project-points-p1')).toBe('visible');
});

it('honors hidden entrances through an in-flight load, source refresh, and layer reconstruction', async () => {
    let resolveResponse;
    vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { resolveResponse = resolve; })));
    const pending = Layers.addProjectGeoJSON('p1', '/pending.geojson');
    Layers.setCategoryVisibility('caveEntrances', false);
    resolveResponse({ ok: true, json: async () => surveyCollection() });
    await pending;
    expect(visibility('project-points-p1')).toBe('none');
    expect(visibility('project-layer-p1')).toBe('visible');

    const source = State.map.getSource('project-geojson-p1');
    fetch.mockResolvedValue({ ok: true, json: async () => surveyCollection() });
    await Layers.addProjectGeoJSON('p1', '/refreshed.geojson');
    expect(source.setData).toHaveBeenCalledOnce();
    expect(visibility('project-points-p1')).toBe('none');

    State.resetLayerState();
    State.map = createMap();
    await Layers.addProjectGeoJSON('p1', '/rebuilt.geojson');
    expect(visibility('project-points-p1')).toBe('none');
    expect(visibility('project-labels-p1')).toBe('visible');
});

it('changes entrance visibility without data work, depth-domain changes, camera movement, or unrelated preferences', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => surveyCollection() }));
    await Layers.addProjectGeoJSON('p1', '/survey.geojson');
    Layers.setColorMode('depth');
    Layers.setDepthLimit(50, 'ft');
    const domain = State.activeDepthDomain;
    const projectDomain = State.projectDepthDomains.get('p1');
    const source = State.map.getSource('project-geojson-p1');
    const cache = vi.spyOn(Geometry, 'cacheLineFeatures');
    const recompute = vi.spyOn(Layers, 'recomputeActiveDepthDomain');
    fetch.mockClear();
    State.map.addSource.mockClear();
    State.map.setPaintProperty.mockClear();

    Layers.setCategoryVisibility('caveEntrances', false);
    Layers.setCategoryVisibility('caveEntrances', true);

    expect(fetch).not.toHaveBeenCalled();
    expect(cache).not.toHaveBeenCalled();
    expect(recompute).not.toHaveBeenCalled();
    expect(source.setData).not.toHaveBeenCalled();
    expect(State.map.addSource).not.toHaveBeenCalled();
    expect(State.map.setPaintProperty).not.toHaveBeenCalled();
    expect(State.map.fitBounds).not.toHaveBeenCalled();
    expect(State.map.flyTo).not.toHaveBeenCalled();
    expect(State.map.setStyle).not.toHaveBeenCalled();
    expect(State.activeDepthDomain).toBe(domain);
    expect(State.projectDepthDomains.get('p1')).toBe(projectDomain);
    expect(State.displayPreferences).toMatchObject({
        colorMode: 'depth', depthLimitFeet: 50, depthUnit: 'ft',
        categories: { caveEntrances: true, surveyStations: true },
    });
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


it('changes all survey modes using paint only, with each project fallback and no unrelated layer changes', () => {
    const map = State.map;
    Config._projects.push({ id: 'p2', color: '#abcdef' });
    for (const id of ['p1', 'p2']) {
        map.addLayer({ id: `project-layer-${id}`, type: 'line' });
        map.addLayer({ id: `project-points-${id}`, type: 'symbol' });
        State.allProjectLayers.set(id, [`project-layer-${id}`, `project-points-${id}`]);
        State.projectDepthDomains.set(id, { min: 0, max: 100 });
    }
    map.addLayer({ id: 'gps-track', type: 'line' });
    map.addLayer({ id: 'gis-outline', type: 'line' });
    vi.stubGlobal('fetch', vi.fn());
    const cache = vi.spyOn(Geometry, 'cacheLineFeatures');
    for (const mode of ['depth', 'shot', 'project', 'shot']) {
        map.setPaintProperty.mockClear();
        Layers.setColorMode(mode);
        expect(map.setPaintProperty).toHaveBeenCalledTimes(2);
        for (const id of ['p1', 'p2']) {
            expect(map.setPaintProperty).toHaveBeenCalledWith(
                `project-layer-${id}`, 'line-color', Colors.getSurveyPaint(id, mode, { min: 0, max: 100 }),
            );
        }
    }
    expect(map.setPaintProperty).toHaveBeenCalledWith('project-layer-p1', 'line-color', ['to-color', ['get', 'color'], '#123456']);
    expect(map.setPaintProperty).toHaveBeenCalledWith('project-layer-p2', 'line-color', ['to-color', ['get', 'color'], '#abcdef']);
    expect(fetch).not.toHaveBeenCalled();
    expect(cache).not.toHaveBeenCalled();
    expect(map.addSource).not.toHaveBeenCalled();
    expect(map.fitBounds).not.toHaveBeenCalled();
    expect(map.flyTo).not.toHaveBeenCalled();
    expect(map.setStyle).not.toHaveBeenCalled();
});

it('preserves shot properties through late loading, data refresh, and layer reconstruction', async () => {
    const properties = [
        { color: '#12ab34', depth: 20 },
        { color: 'rgba(50,100,150,0.5)', depth: 40 },
        {},
        { color: 'not-a-color' },
    ];
    const data = collection(properties.map((props, index) => ({
        type: 'Feature', id: index, properties: props,
        geometry: { type: 'LineString', coordinates: [[-87, 20, -20], [-87.1, 20.1, -40]] },
    })));
    let resolveResponse;
    vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { resolveResponse = resolve; })));
    const pending = Layers.addProjectGeoJSON('p1', '/survey.geojson');
    Layers.setColorMode('shot');
    resolveResponse({ ok: true, json: async () => data });
    await pending;
    const expression = ['to-color', ['get', 'color'], '#123456'];
    expect(State.map.getLayer('project-layer-p1').paint['line-color']).toEqual(expression);
    const source = State.map.getSource('project-geojson-p1');
    expect(source.data.features.map(feature => feature.properties.color)).toEqual(properties.map(props => props.color));
    const entrancePaint = State.map.getLayer('project-points-p1').paint;
    expect(entrancePaint['text-color']).toBe('#F5E027');
    fetch.mockResolvedValue({ ok: true, json: async () => data });
    await Layers.addProjectGeoJSON('p1', '/refreshed.geojson');
    expect(source.setData).toHaveBeenCalledOnce();
    expect(source.setData.mock.calls[0][0].features[1].properties.color).toBe('rgba(50,100,150,0.5)');
    State.resetLayerState();
    State.map = createMap();
    await Layers.addProjectGeoJSON('p1', '/rebuilt.geojson');
    Layers.applyDisplayPreferences();
    expect(State.map.getLayer('project-layer-p1').paint['line-color']).toEqual(expression);
    expect(State.map.setPaintProperty).toHaveBeenCalledWith('project-layer-p1', 'line-color', expression);
    expect(State.map.getLayer('project-points-p1').paint).toEqual(entrancePaint);
});

it('ignores invalid color modes without changing preferences, paint, or events', () => {
    Layers.setColorMode('shot');
    const changed = vi.fn();
    window.addEventListener('speleo:color-mode-changed', changed);
    State.map.setPaintProperty.mockClear();
    try {
        for (const mode of [null, undefined, 'invalid', {}, 1]) Layers.setColorMode(mode);
        expect(State.displayPreferences.colorMode).toBe('shot');
        expect(State.map.setPaintProperty).not.toHaveBeenCalled();
        expect(changed).not.toHaveBeenCalled();
    } finally {
        window.removeEventListener('speleo:color-mode-changed', changed);
    }
});
