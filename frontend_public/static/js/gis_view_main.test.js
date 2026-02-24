const stateMock = {
    init: vi.fn(),
    projectBounds: new Map()
};

const mapCoreMock = {
    init: vi.fn(),
    setupColorModeToggle: vi.fn()
};

const layersMock = {
    addProjectGeoJSON: vi.fn(),
    reorderLayers: vi.fn()
};

const utilsMock = {
    showNotification: vi.fn()
};

const projectPanelMock = {
    init: vi.fn()
};

const depthLegendMock = {
    init: vi.fn()
};

const configMock = {
    _projects: null,
    get projects() {
        return this._projects || [];
    }
};

vi.mock('../../../frontend_private/static/private/js/map_viewer/state.js', () => ({
    State: stateMock
}));

vi.mock('../../../frontend_private/static/private/js/map_viewer/map/core.js', () => ({
    MapCore: mapCoreMock
}));

vi.mock('../../../frontend_private/static/private/js/map_viewer/map/layers.js', () => ({
    Layers: layersMock
}));

vi.mock('../../../frontend_private/static/private/js/map_viewer/utils.js', () => ({
    Utils: utilsMock
}));

vi.mock('../../../frontend_private/static/private/js/map_viewer/components/project_panel.js', () => ({
    ProjectPanel: projectPanelMock
}));

vi.mock('../../../frontend_private/static/private/js/map_viewer/components/depth_legend.js', () => ({
    DepthLegend: depthLegendMock
}));

vi.mock('../../../frontend_private/static/private/js/map_viewer/config.js', () => ({
    Config: configMock
}));

function createMapMock() {
    const handlers = {};
    const map = {
        setMaxZoom: vi.fn(),
        on: vi.fn((eventName, handler) => {
            handlers[eventName] = handler;
        }),
        fitBounds: vi.fn()
    };
    return { map, handlers };
}

class MockLngLatBounds {
    constructor() {
        this._empty = true;
        this.extended = [];
    }

    extend(value) {
        this._empty = false;
        this.extended.push(value);
    }

    isEmpty() {
        return this._empty;
    }
}

describe('frontend_public gis_view_main', () => {
    let mapMock;
    let mapHandlers;
    let domReadyHandler;
    let addEventListenerSpy;
    let originalDocumentAddEventListener;
    let consoleLogSpy;
    let consoleErrorSpy;

    async function importModuleAndGetDomReadyHandler() {
        vi.resetModules();
        await import('./gis_view_main.js');
        expect(typeof domReadyHandler).toBe('function');
        return domReadyHandler;
    }

    beforeEach(() => {
        vi.useFakeTimers();
        vi.clearAllMocks();
        consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
        consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

        const mapSetup = createMapMock();
        mapMock = mapSetup.map;
        mapHandlers = mapSetup.handlers;
        mapCoreMock.init.mockReturnValue(mapMock);
        layersMock.addProjectGeoJSON.mockResolvedValue(undefined);

        stateMock.projectBounds = new Map();
        configMock._projects = null;

        document.body.innerHTML = `
            <div id="map" style="height: 0;"></div>
            <div id="loading-overlay"></div>
        `;

        window.MAPVIEWER_CONTEXT = {};
        globalThis.fetch = vi.fn();
        globalThis.mapboxgl = { LngLatBounds: MockLngLatBounds };

        domReadyHandler = null;
        originalDocumentAddEventListener = document.addEventListener.bind(document);
        addEventListenerSpy = vi.spyOn(document, 'addEventListener').mockImplementation((eventName, handler, options) => {
            if (eventName === 'DOMContentLoaded') {
                domReadyHandler = handler;
                return;
            }
            return originalDocumentAddEventListener(eventName, handler, options);
        });
    });

    afterEach(() => {
        addEventListenerSpy.mockRestore();
        consoleLogSpy.mockRestore();
        consoleErrorSpy.mockRestore();
        vi.useRealTimers();
        vi.restoreAllMocks();
        document.body.innerHTML = '';
        delete window.MAPVIEWER_CONTEXT;
        delete globalThis.mapboxgl;
        delete globalThis.fetch;
    });

    it('shows invalid configuration notification and exits early', async () => {
        window.MAPVIEWER_CONTEXT = { viewMode: 'private', gisToken: null };

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(utilsMock.showNotification).toHaveBeenCalledWith('error', 'Invalid GIS View configuration');
        expect(mapCoreMock.init).not.toHaveBeenCalled();
        expect(depthLegendMock.init).not.toHaveBeenCalled();
    });

    it('shows map configuration notification when token is missing', async () => {
        window.MAPVIEWER_CONTEXT = { viewMode: 'public', gisToken: 'abc', mapboxToken: '' };

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(utilsMock.showNotification).toHaveBeenCalledWith('error', 'Map configuration missing');
        expect(mapCoreMock.init).not.toHaveBeenCalled();
    });

    it('initializes public viewer, loads projects, and wires shared depth legend', async () => {
        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token',
            allowPreciseZoom: false
        };

        stateMock.projectBounds = new Map([['p1', { any: 'bounds' }]]);
        globalThis.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    view_name: 'Public View',
                    projects: [
                        { id: 'p1', name: 'Project One', geojson_file: '/g1.geojson' },
                        { id: 'p2', name: 'Project Two', geojson_file: '/g2.geojson' }
                    ]
                }
            })
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(stateMock.init).toHaveBeenCalledTimes(1);
        expect(mapCoreMock.init).toHaveBeenCalledWith('mapbox-token', 'map');
        expect(mapMock.setMaxZoom).toHaveBeenCalledWith(13);
        expect(depthLegendMock.init).toHaveBeenCalledWith(mapMock);
        expect(mapCoreMock.setupColorModeToggle).toHaveBeenCalledWith(mapMock);
        expect(mapHandlers.load).toBeTypeOf('function');

        await mapHandlers.load();

        expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/gis-ogc/view/public-token/geojson');
        expect(configMock._projects).toEqual([
            { id: 'p1', name: 'Project One', permissions: 'READ_ONLY', geojson_url: '/g1.geojson' },
            { id: 'p2', name: 'Project Two', permissions: 'READ_ONLY', geojson_url: '/g2.geojson' }
        ]);
        expect(projectPanelMock.init).toHaveBeenCalledTimes(1);
        expect(layersMock.addProjectGeoJSON).toHaveBeenCalledTimes(2);
        expect(layersMock.addProjectGeoJSON).toHaveBeenNthCalledWith(1, 'p1', '/g1.geojson');
        expect(layersMock.addProjectGeoJSON).toHaveBeenNthCalledWith(2, 'p2', '/g2.geojson');
        expect(layersMock.reorderLayers).toHaveBeenCalledTimes(1);
        expect(mapMock.fitBounds).toHaveBeenCalledTimes(1);

        const overlay = document.getElementById('loading-overlay');
        expect(overlay).not.toBeNull();
        expect(overlay.classList.contains('opacity-0')).toBe(true);
        vi.runAllTimers();
        expect(document.getElementById('loading-overlay')).toBeNull();
    });

    it('uses precise zoom limits when allowPreciseZoom is enabled', async () => {
        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token',
            allowPreciseZoom: true
        };

        stateMock.projectBounds = new Map([['p1', { any: 'bounds' }]]);
        globalThis.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    view_name: 'Public View',
                    projects: [
                        { id: 'p1', name: 'Project One', geojson_file: '/g1.geojson' }
                    ]
                }
            })
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        expect(mapMock.setMaxZoom).toHaveBeenCalledWith(22);

        await mapHandlers.load();
        expect(mapMock.fitBounds).toHaveBeenCalledTimes(1);
        expect(mapMock.fitBounds).toHaveBeenCalledWith(
            expect.any(MockLngLatBounds),
            expect.objectContaining({ maxZoom: 16, padding: 50 })
        );
    });

    it('shows load failure notification when public GIS API call fails', async () => {
        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };

        globalThis.fetch.mockResolvedValue({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error'
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        await mapHandlers.load();

        expect(utilsMock.showNotification).toHaveBeenCalledWith('error', 'Failed to load map data');
        expect(projectPanelMock.init).not.toHaveBeenCalled();
        expect(layersMock.addProjectGeoJSON).not.toHaveBeenCalled();
        expect(layersMock.reorderLayers).not.toHaveBeenCalled();
    });
});

