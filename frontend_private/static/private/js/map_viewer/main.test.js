const configMock = {
    loadProjects: vi.fn(),
    loadNetworks: vi.fn(),
    loadGPSTracks: vi.fn(),
    projects: [],
    networks: [],
    gpsTracks: [],
};

const stateMock = {
    resetLayerState: vi.fn(),
    allProjectLayers: new Map(),
    allNetworkLayers: new Map(),
    allStations: new Map(),
    allSurfaceStations: new Map(),
    allLandmarks: new Map(),
    landmarkCollections: new Map(),
    projectDepthDomains: new Map(),
    activeDepthDomain: null,
    projectBounds: new Map(),
    networkBounds: new Map(),
    explorationLeads: new Map(),
    cylinderInstalls: new Map(),
    allGPSTrackLayers: new Map(),
    gpsTrackBounds: new Map(),
    gpsTrackCache: new Map(),
    gpsTrackLayerStates: new Map(),
};

const mapMock = {
    on: vi.fn(),
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
    loadMarkerImages: vi.fn(),
    loadProjectVisibilityPrefs: vi.fn(),
    loadNetworkVisibilityPrefs: vi.fn(),
    reorderLayers: vi.fn(),
    isGPSTrackVisible: vi.fn(),
    toggleGPSTrackVisibility: vi.fn(),
    addGPSTrackLayer: vi.fn(),
    toggleLandmarkVisibility: vi.fn(),
    refreshCylinderInstallsLayer: vi.fn(),
};

const utilsMock = {
    showNotification: vi.fn(),
};

vi.mock('./config.js', async () => {
    const actual = await vi.importActual('./config.js');
    return { Config: configMock, DEFAULTS: actual.DEFAULTS };
});

vi.mock('./state.js', () => ({ State: stateMock }));
vi.mock('./map/core.js', () => ({ MapCore: mapCoreMock }));
vi.mock('./map/sources.js', () => ({ MapSources: mapSourcesMock }));
vi.mock('./map/layers.js', () => ({ Layers: layersMock }));
vi.mock('./map/interactions.js', () => ({ Interactions: { init: vi.fn() } }));
vi.mock('./map/geometry.js', () => ({ Geometry: { getSnapInfo: vi.fn(), setSnapRadius: vi.fn() } }));
vi.mock('./stations/manager.js', () => ({ StationManager: {} }));
vi.mock('./stations/ui.js', () => ({ StationUI: { openManagerModal: vi.fn() } }));
vi.mock('./stations/details.js', () => ({ StationDetails: { openModal: vi.fn() } }));
vi.mock('./stations/tags.js', () => ({ StationTags: { init: vi.fn() } }));
vi.mock('./surface_stations/manager.js', () => ({ SurfaceStationManager: {} }));
vi.mock('./surface_stations/ui.js', () => ({ SurfaceStationUI: { openManagerModal: vi.fn() } }));
vi.mock('./landmarks/manager.js', () => ({ LandmarkManager: {} }));
vi.mock('./landmarks/ui.js', () => ({ LandmarkUI: { openDetailsModal: vi.fn(), openManagerModal: vi.fn() } }));
vi.mock('./exploration_leads/manager.js', () => ({ ExplorationLeadManager: {} }));
vi.mock('./exploration_leads/ui.js', () => ({ ExplorationLeadUI: { showDetailsModal: vi.fn() } }));
vi.mock('./stations/cylinders.js', () => ({ CylinderInstalls: { showCylinderDetails: vi.fn() } }));
vi.mock('./utils.js', () => ({ Utils: utilsMock }));
vi.mock('./components/context_menu.js', () => ({ ContextMenu: {} }));
vi.mock('./components/project_panel.js', () => ({
    ProjectPanel: { init: vi.fn(), refreshVisibilityState: vi.fn() }
}));
vi.mock('./components/gps_tracks_panel.js', () => ({
    GPSTracksPanel: { init: vi.fn(), refreshList: vi.fn() }
}));
vi.mock('./components/depth_legend.js', () => ({ DepthLegend: { init: vi.fn() } }));
vi.mock('./api.js', () => ({
    API: { getAllProjectsGeoJSON: vi.fn(), updateCylinderInstall: vi.fn() }
}));

describe('private map viewer entrypoint', () => {
    let domReadyHandler;
    let documentAddEventListenerSpy;
    let originalDocumentAddEventListener;
    let consoleLogSpy;
    let consoleErrorSpy;

    async function importModuleAndGetDomReadyHandler() {
        vi.resetModules();
        await import('./main.js');
        expect(typeof domReadyHandler).toBe('function');
        return domReadyHandler;
    }

    beforeEach(() => {
        vi.useFakeTimers();
        vi.clearAllMocks();
        consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => { });
        consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

        configMock.loadProjects.mockResolvedValue(undefined);
        configMock.loadNetworks.mockResolvedValue(undefined);
        configMock.loadGPSTracks.mockResolvedValue(undefined);
        mapCoreMock.init.mockReturnValue(mapMock);
        mapSourcesMock.requiresDataReload.mockReturnValue(false);

        stateMock.allProjectLayers = new Map();
        stateMock.allNetworkLayers = new Map();
        stateMock.allStations = new Map();
        stateMock.allSurfaceStations = new Map();
        stateMock.allLandmarks = new Map();
        stateMock.landmarkCollections = new Map();
        stateMock.projectDepthDomains = new Map();
        stateMock.activeDepthDomain = null;
        stateMock.projectBounds = new Map();
        stateMock.networkBounds = new Map();
        stateMock.explorationLeads = new Map();
        stateMock.cylinderInstalls = new Map();
        stateMock.allGPSTrackLayers = new Map();
        stateMock.gpsTrackBounds = new Map();
        stateMock.gpsTrackCache = new Map();
        stateMock.gpsTrackLayerStates = new Map();

        document.body.innerHTML = '<div id="map"></div>';
        window.MAPVIEWER_CONTEXT = { mapboxToken: 'mapbox-token', icons: {} };

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
        document.body.innerHTML = '';
        delete window.MAPVIEWER_CONTEXT;
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
});
