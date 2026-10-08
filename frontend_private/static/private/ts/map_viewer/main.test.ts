import type { Mock, MockInstance } from 'vitest';
import type { MapRuntimeContext } from '../../../../../ts-types/domain/map-runtime.ts';
const testWindow = window as Window & { MAPVIEWER_CONTEXT?: Partial<MapRuntimeContext> };
const configMock = {
    loadProjects: vi.fn(),
    loadNetworks: vi.fn(),
    loadGPSTracks: vi.fn(),
    loadGISLayers: vi.fn(),
    loadGISGeometries: vi.fn(),
    filterProjectsByGeoJSON: vi.fn(),
    projects: [],
    networks: [],
    gpsTracks: [],
    gisLayers: [],
    gisGeometries: [],
};

const stateMock = {
    resetLayerState: vi.fn(),
    allProjectLayers: new Map<string, string[]>(),
    allNetworkLayers: new Map<string, unknown>(),
    allStations: new Map<string, unknown>(),
    allSurfaceStations: new Map<string, unknown>(),
    allLandmarks: new Map<string, unknown>(),
    landmarkCollections: new Map<string, unknown>(),
    projectDepthDomains: new Map<string, unknown>(),
    activeDepthDomain: null,
    projectBounds: new Map<string, unknown>(),
    networkBounds: new Map<string, unknown>(),
    explorationLeads: new Map<string, unknown>(),
    cylinderInstalls: new Map<string, unknown>(),
    allGPSTrackLayers: new Map<string, unknown>(),
    gpsTrackBounds: new Map<string, unknown>(),
    gpsTrackCache: new Map<string, unknown>(),
    gpsTrackLayerStates: new Map<string, unknown>(),
    allGISLayerLayers: new Map<string, unknown>(),
    gisLayerBounds: new Map<string, unknown>(),
    gisLayerCache: new Map<string, unknown>(),
    gisLayerStates: new Map<string, unknown>(),
    gisLayerClickableLayerIds: new Set<string>(),
};

const mapMock = {
    on: vi.fn<(name: string, handler: () => Promise<void>) => void>(),
    addControl: vi.fn(),
    flyTo: vi.fn(),
    resize: vi.fn(),
};

const mapCoreMock = {
    init: vi.fn(),
    setupColorModeToggle: vi.fn(),
    setupMapSourceControl: vi.fn(),
};

const mapSourcesMock = {
    requiresDataReload: vi.fn(),
};

const layersMock = {
    applyDisplayPreferences: vi.fn(),
    loadMarkerImages: vi.fn(),
    loadProjectVisibilityPrefs: vi.fn(),
    loadNetworkVisibilityPrefs: vi.fn(),
    reorderLayers: vi.fn(),
    isGPSTrackVisible: vi.fn(),
    toggleGPSTrackVisibility: vi.fn(),
    addGPSTrackLayer: vi.fn(),
    isGISLayerVisible: vi.fn(),
    toggleGISLayerVisibility: vi.fn(),
    openGISFeaturePopup: vi.fn(),
    toggleLandmarkVisibility: vi.fn(),
    refreshCylinderInstallsLayer: vi.fn(),
};

const utilsMock = {
    showNotification: vi.fn(),
};

const apiMock = {
    getAllProjectsGeoJSON: vi.fn(),
    updateCylinderInstall: vi.fn(),
};

vi.mock('./config.ts', async () => {
    const actual = await vi.importActual<typeof import('./config.ts')>('./config.ts');
    return { Config: configMock, DEFAULTS: actual.DEFAULTS };
});

vi.mock('./state.ts', async () => ({
    ...await vi.importActual<typeof import('./state.ts')>('./state.ts'),
    State: stateMock,
}));
vi.mock('./map/core.ts', () => ({ MapCore: mapCoreMock }));
vi.mock('./map/sources.ts', () => ({ MapSources: mapSourcesMock }));
vi.mock('./map/layers.ts', () => ({ Layers: layersMock }));
vi.mock('./map/interactions.ts', () => ({ Interactions: { init: vi.fn(), cancelPendingDrag: vi.fn() } }));
vi.mock('./map/geometry.ts', () => ({ Geometry: { getSnapInfo: vi.fn(), setSnapRadius: vi.fn() } }));
vi.mock('./stations/manager.ts', () => ({ StationManager: {} }));
vi.mock('./stations/ui.ts', () => ({ StationUI: { openManagerModal: vi.fn() } }));
vi.mock('./stations/details.ts', () => ({
    StationDetails: { openModal: vi.fn() },
    configureStationManagerNavigation: vi.fn(),
    returnToStationManager: vi.fn(),
}));
vi.mock('./stations/tags.ts', () => ({ StationTags: { init: vi.fn() } }));
vi.mock('./surface_stations/manager.ts', () => ({ SurfaceStationManager: {} }));
vi.mock('./surface_stations/ui.ts', () => ({ SurfaceStationUI: { openManagerModal: vi.fn() } }));
vi.mock('./landmarks/manager.ts', () => ({ LandmarkManager: {} }));
vi.mock('./landmarks/ui.ts', () => ({ LandmarkUI: { openDetailsModal: vi.fn(), openManagerModal: vi.fn() } }));
vi.mock('./exploration_leads/manager.ts', () => ({ ExplorationLeadManager: {} }));
vi.mock('./exploration_leads/ui.ts', () => ({ ExplorationLeadUI: { showDetailsModal: vi.fn() } }));
vi.mock('./stations/cylinders.ts', () => ({ CylinderInstalls: { showCylinderDetails: vi.fn() } }));
vi.mock('./stations/sensors.ts', () => ({ StationSensors: {} }));
vi.mock('./action_dispatcher.ts', () => ({ initMapActionDispatcher: vi.fn() }));
vi.mock('./map/navigation.ts', () => ({ configureMapNavigation: vi.fn() }));
vi.mock('./utils.ts', () => ({ Utils: utilsMock }));
vi.mock('./components/context_menu.ts', () => ({ ContextMenu: {} }));
vi.mock('./components/project_panel.ts', () => ({
    ProjectPanel: { init: vi.fn(), refreshVisibilityState: vi.fn() }
}));
vi.mock('./components/gps_tracks_panel.ts', () => ({
    GPSTracksPanel: { init: vi.fn(), refreshList: vi.fn() }
}));
vi.mock('./components/gis_layers_panel.ts', () => ({
    GISLayersPanel: { init: vi.fn(), refreshList: vi.fn() }
}));
vi.mock('./components/gis_geometries_panel.ts', () => ({
    GISGeometriesPanel: { init: vi.fn(), refreshList: vi.fn(), setupStackListener: vi.fn(), setExpanded: vi.fn() },
}));
vi.mock('./geometry_editor/editor.ts', () => ({
    GeometryEditor: { init: vi.fn(), restoreLayers: vi.fn(), isActive: vi.fn(() => false), isOpening: vi.fn(() => false), create: vi.fn(async () => true) },
}));
vi.mock('./components/depth_legend.ts', () => ({ DepthLegend: { init: vi.fn() } }));
vi.mock('./api.ts', () => ({ API: apiMock }));

describe('private map viewer entrypoint', () => {
    let domReadyHandler: EventListenerOrEventListenerObject | null;
    let documentAddEventListenerSpy: MockInstance<typeof document.addEventListener>;
    let originalDocumentAddEventListener: typeof document.addEventListener;
    let consoleLogSpy: MockInstance<typeof console.log>;
    let consoleErrorSpy: MockInstance<typeof console.error>;

    async function importModuleAndGetDomReadyHandler() {
        const context = testWindow.MAPVIEWER_CONTEXT;
        vi.resetModules();
        const { configureRuntimeContext } = await import('./runtime_context.ts');
        configureRuntimeContext(context);
        const { initPrivateMapViewer } = await import('./main.ts');
        expect(typeof initPrivateMapViewer).toBe('function');
        return initPrivateMapViewer;
    }

    beforeEach(() => {
        vi.useFakeTimers();
        vi.clearAllMocks();
        consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => { });
        consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

        configMock.loadProjects.mockResolvedValue(undefined);
        configMock.loadNetworks.mockResolvedValue(undefined);
        configMock.loadGPSTracks.mockResolvedValue(undefined);
        configMock.loadGISLayers.mockResolvedValue(undefined);
        configMock.loadGISGeometries.mockResolvedValue(undefined);
        mapCoreMock.init.mockReturnValue(mapMock);
        mapSourcesMock.requiresDataReload.mockReturnValue(false);
        apiMock.getAllProjectsGeoJSON.mockResolvedValue([]);

        stateMock.allProjectLayers = new Map<string, string[]>();
        stateMock.allNetworkLayers = new Map<string, unknown>();
        stateMock.allStations = new Map<string, unknown>();
        stateMock.allSurfaceStations = new Map<string, unknown>();
        stateMock.allLandmarks = new Map<string, unknown>();
        stateMock.landmarkCollections = new Map<string, unknown>();
        stateMock.projectDepthDomains = new Map<string, unknown>();
        stateMock.activeDepthDomain = null;
        stateMock.projectBounds = new Map<string, unknown>();
        stateMock.networkBounds = new Map<string, unknown>();
        stateMock.explorationLeads = new Map<string, unknown>();
        stateMock.cylinderInstalls = new Map<string, unknown>();
        stateMock.allGPSTrackLayers = new Map<string, unknown>();
        stateMock.gpsTrackBounds = new Map<string, unknown>();
        stateMock.gpsTrackCache = new Map<string, unknown>();
        stateMock.gpsTrackLayerStates = new Map<string, unknown>();
        stateMock.allGISLayerLayers = new Map<string, unknown>();
        stateMock.gisLayerBounds = new Map<string, unknown>();
        stateMock.gisLayerCache = new Map<string, unknown>();
        stateMock.gisLayerStates = new Map<string, unknown>();
        stateMock.gisLayerClickableLayerIds = new Set<string>();

        document.body.innerHTML = '<div id="map"></div>';
        testWindow.MAPVIEWER_CONTEXT = { mapboxToken: 'mapbox-token', icons: {} };

        domReadyHandler = null;
        originalDocumentAddEventListener = document.addEventListener.bind(document);
        documentAddEventListenerSpy = vi.spyOn(document, 'addEventListener').mockImplementation((eventName, handler, options) => {
            if (eventName === 'DOMContentLoaded') {
                domReadyHandler = handler;
                return;
            }
            return originalDocumentAddEventListener(eventName, handler, options);
        });
    });

    afterEach(() => {
        documentAddEventListenerSpy.mockRestore();
        consoleLogSpy.mockRestore();
        consoleErrorSpy.mockRestore();
        vi.useRealTimers();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        Reflect.deleteProperty(document, 'fullscreenElement');
        document.body.innerHTML = '';
        delete testWindow.MAPVIEWER_CONTEXT;
    });

    it.each([
        { width: 1024, fullscreen: false, height: '830px' },
        { width: 640, fullscreen: false, height: '850px' },
        { width: 1024, fullscreen: true, height: '850px' },
    ])('sizes the private map for $width/fullscreen=$fullscreen', async ({ width, fullscreen, height }) => {
        document.body.innerHTML = '<div id="map-viewer-shell"><div id="map"></div></div>';
        const element = document.getElementById('map')!;
        vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 50, 800, 400));
        Object.defineProperty(document, 'fullscreenElement', { configurable: true, value: fullscreen ? document.getElementById('map-viewer-shell') : null });
        vi.stubGlobal('innerWidth', width);
        vi.stubGlobal('innerHeight', 900);
        const initialize = await importModuleAndGetDomReadyHandler();
        await initialize();
        expect(element.style.height).toBe(height);
    });

    it('does not reload private map data for non-destructive map source changes', async () => {
        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        stateMock.allProjectLayers = new Map([['p1', ['project-layer-p1']]]);
        layersMock.loadMarkerImages.mockClear();

        const event = new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'esri-world-hillshade', reloadRequired: false }
        });
        window.dispatchEvent(event);
        await Promise.resolve();

        expect(mapSourcesMock.requiresDataReload).toHaveBeenCalledWith(event);
        expect(layersMock.loadMarkerImages).not.toHaveBeenCalled();
        expect(utilsMock.showNotification).not.toHaveBeenCalledWith('success', 'Map source updated');
        expect(stateMock.allProjectLayers).toEqual(new Map([['p1', ['project-layer-p1']]]));
    });

    it('clears clickable GIS layer registration before a destructive style rebuild', async () => {
        mapSourcesMock.requiresDataReload.mockReturnValue(true);
        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        stateMock.gisLayerClickableLayerIds.add('gis-layer-layer-1-point');

        window.dispatchEvent(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'mapbox-satellite', reloadRequired: true }
        }));

        await vi.waitFor(() => expect(stateMock.gisLayerClickableLayerIds.size).toBe(0));
    });

    it('initializes the map without waiting for startup config to resolve', async () => {
        // Keep projects pending forever: a sequential `await` chain would block
        // here and never initialize the map or start the other loads.
        configMock.loadProjects.mockReturnValue(new Promise(() => { }));

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(mapCoreMock.init).toHaveBeenCalledWith('mapbox-token', 'map', { fullscreenContainer: null });
        expect(mapCoreMock.setupMapSourceControl).toHaveBeenCalledWith(mapMock, 'mapbox-token');
        expect(mapMock.addControl).toHaveBeenCalledWith(expect.objectContaining({
            onAdd: expect.any(Function) as unknown, onRemove: expect.any(Function) as unknown,
            activate: expect.any(Function) as unknown, deactivate: expect.any(Function) as unknown,
        }), 'top-right');
        expect(mapMock.addControl.mock.invocationCallOrder[0])
            .toBeGreaterThan(mapCoreMock.setupMapSourceControl.mock.invocationCallOrder[0]!);
    });

    it('kicks off project, network, GPS track, and private GIS Layer loads in parallel', async () => {
        // Projects hangs; networks/gpsTracks must still be invoked, proving the
        // three loads are started concurrently rather than awaited one-by-one.
        configMock.loadProjects.mockReturnValue(new Promise(() => { }));

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(configMock.loadProjects).toHaveBeenCalledTimes(1);
        expect(configMock.loadNetworks).toHaveBeenCalledTimes(1);
        expect(configMock.loadGPSTracks).toHaveBeenCalledTimes(1);
        expect(configMock.loadGISLayers).toHaveBeenCalledTimes(1);
    });

    it('prefetches the all-projects GeoJSON metadata once and consumes it during initial load', async () => {
        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(apiMock.getAllProjectsGeoJSON).toHaveBeenCalledTimes(1);

        const loadHandler = mapMock.on.mock.calls.find(([eventName]) => eventName === 'load')?.[1];
        expect(loadHandler).toBeTypeOf('function');

        await loadHandler!();

        expect(apiMock.getAllProjectsGeoJSON).toHaveBeenCalledTimes(1);
    });

    it('opens geometry creation from the top bar after the map is ready', async () => {
        document.body.insertAdjacentHTML('beforeend', '<button id="create-geometry-btn">Create Geometry</button>');
        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        await mapMock.on.mock.calls.find(([name]) => name === 'load')![1]();
        const { GeometryEditor } = await import('./geometry_editor/editor.ts') as unknown as { GeometryEditor: { create: Mock<() => Promise<boolean>> } };
        const { GISGeometriesPanel } = await import('./components/gis_geometries_panel.ts') as unknown as { GISGeometriesPanel: { setExpanded: Mock<(value: boolean) => void> } };
        document.getElementById('create-geometry-btn')!.click();
        await Promise.resolve();
        expect(vi.mocked(GeometryEditor.create)).toHaveBeenCalledOnce();
        expect(vi.mocked(GISGeometriesPanel.setExpanded)).toHaveBeenCalledWith(false);
    });
});
