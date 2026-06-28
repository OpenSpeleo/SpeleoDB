const stateMock = {
    resetLayerState: vi.fn(),
    projectBounds: new Map(),
    allProjectLayers: new Map(),
    effectiveProjectVisibility: new Map(),
    projectDepthDomains: new Map(),
    activeDepthDomain: null
};

const mapCoreMock = {
    init: vi.fn(),
    setupColorModeToggle: vi.fn(),
    setupMapSourceControl: vi.fn()
};

const layersMock = {
    addProjectGeoJSON: vi.fn(),
    reorderLayers: vi.fn()
};

const utilsMock = {
    showNotification: vi.fn()
};

const projectPanelMock = {
    init: vi.fn(),
    refreshList: vi.fn()
};

const depthLegendMock = {
    init: vi.fn()
};

const mapSourcesMock = {
    requiresDataReload: vi.fn(),
};

const configMock = {
    _projects: null,
    get projects() {
        return this._projects || [];
    },
    setPublicProjects(projects) {
        this._projects = projects.map(p => ({
            id: p.id,
            name: p.name,
            color: p.color,
            permissions: 'READ_ONLY',
            geojson_url: p.geojson_url || p.geojson_file,
        }));
    }
};

vi.mock('../../../frontend_private/static/private/js/map_viewer/state.js', () => ({
    State: stateMock
}));

vi.mock('../../../frontend_private/static/private/js/map_viewer/map/core.js', () => ({
    MapCore: mapCoreMock
}));

vi.mock('../../../frontend_private/static/private/js/map_viewer/map/sources.js', () => ({
    MapSources: mapSourcesMock
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

vi.mock('../../../frontend_private/static/private/js/map_viewer/config.js', async () => {
    const actual = await vi.importActual('../../../frontend_private/static/private/js/map_viewer/config.js');
    return { Config: configMock, DEFAULTS: actual.DEFAULTS };
});

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
        const context = window.MAPVIEWER_CONTEXT;
        vi.resetModules();
        const { configureRuntimeContext } = await import('../../../frontend_private/static/private/js/map_viewer/runtime_context.js');
        configureRuntimeContext(context);
        const { initPublicGISViewer } = await import('./gis_view_main.js');
        expect(typeof initPublicGISViewer).toBe('function');
        return initPublicGISViewer;
    }

    beforeEach(() => {
        vi.useFakeTimers();
        vi.clearAllMocks();
        consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => { });
        consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

        const mapSetup = createMapMock();
        mapMock = mapSetup.map;
        mapHandlers = mapSetup.handlers;
        mapCoreMock.init.mockReturnValue(mapMock);
        mapSourcesMock.requiresDataReload.mockReturnValue(true);
        layersMock.addProjectGeoJSON.mockResolvedValue(undefined);

        stateMock.projectBounds = new Map();
        stateMock.allProjectLayers = new Map();
        stateMock.effectiveProjectVisibility = new Map();
        stateMock.projectDepthDomains = new Map();
        stateMock.activeDepthDomain = null;
        configMock._projects = null;

        document.body.innerHTML = `
            <div id="map" style="height: 0;"></div>
            <div id="loading-overlay"></div>
        `;

        window.MAPVIEWER_CONTEXT = {};
        globalThis.fetch = vi.fn();
        globalThis.mapboxgl = { LngLatBounds: MockLngLatBounds };
        globalThis.Urls = new Proxy(
            {},
            {
                get: (_target, prop) =>
                    (...args) =>
                        `/api/${prop}${args.length ? '/' + args.join('/') : ''}`,
            }
        );

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
        delete globalThis.Urls;
    });

    it('shows invalid configuration notification and exits early', async () => {
        window.MAPVIEWER_CONTEXT = { viewMode: 'private', gisToken: null };

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(utilsMock.showNotification).toHaveBeenCalledWith('error', 'Invalid GIS View configuration');
        expect(mapCoreMock.init).not.toHaveBeenCalled();
        expect(depthLegendMock.init).not.toHaveBeenCalled();
    });

    it('initializes with an empty token so tokenless map sources can render', async () => {
        window.MAPVIEWER_CONTEXT = { viewMode: 'public', gisToken: 'abc', mapboxToken: '' };

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(utilsMock.showNotification).not.toHaveBeenCalledWith('error', 'Map configuration missing');
        expect(mapCoreMock.init).toHaveBeenCalledWith('', 'map');
        expect(mapCoreMock.setupMapSourceControl).toHaveBeenCalledWith(mapMock, '');
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
                view_name: 'Public View',
                projects: [
                    { id: 'p1', name: 'Project One', geojson_file: '/g1.geojson' },
                    { id: 'p2', name: 'Project Two', geojson_file: '/g2.geojson' }
                ]
            })
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(stateMock.resetLayerState).toHaveBeenCalledTimes(1);
        expect(mapCoreMock.init).toHaveBeenCalledWith('mapbox-token', 'map');
        expect(mapMock.setMaxZoom).toHaveBeenCalledWith(13);
        expect(depthLegendMock.init).toHaveBeenCalledWith(mapMock);
        expect(mapCoreMock.setupColorModeToggle).toHaveBeenCalledWith(mapMock);
        expect(mapCoreMock.setupMapSourceControl).toHaveBeenCalledWith(mapMock, 'mapbox-token');
        expect(mapHandlers.load).toBeTypeOf('function');

        await mapHandlers.load();

        expect(globalThis.fetch).toHaveBeenCalledWith(Urls['api:v2:gis-ogc:view-geojson']('public-token'));
        expect(configMock._projects).toEqual([
            { id: 'p1', name: 'Project One', color: undefined, permissions: 'READ_ONLY', geojson_url: '/g1.geojson' },
            { id: 'p2', name: 'Project Two', color: undefined, permissions: 'READ_ONLY', geojson_url: '/g2.geojson' }
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

    it('prefetches the GIS View GeoJSON during init, before the map load event', async () => {
        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };

        globalThis.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                view_name: 'Public View',
                projects: [
                    { id: 'p1', name: 'Project One', geojson_file: '/g1.geojson' }
                ]
            })
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        // The view data request is issued during init (concurrently with map
        // init), before the map 'load' event handler runs.
        expect(mapCoreMock.init).toHaveBeenCalledWith('mapbox-token', 'map');
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(globalThis.fetch).toHaveBeenCalledWith(Urls['api:v2:gis-ogc:view-geojson']('public-token'));

        await mapHandlers.load();

        // The load handler consumes the prefetch instead of issuing a 2nd request.
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(layersMock.addProjectGeoJSON).toHaveBeenCalledWith('p1', '/g1.geojson');
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
                view_name: 'Public View',
                projects: [
                    { id: 'p1', name: 'Project One', geojson_file: '/g1.geojson' }
                ]
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

    it('passes color through to Config.setPublicProjects', async () => {
        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',

            mapboxToken: 'mapbox-token',
        };

        globalThis.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                view_name: 'Color View',
                projects: [
                    { id: 'p1', name: 'Red Cave', color: '#e41a1c', geojson_file: '/g1.geojson' },
                ]
            })
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        await mapHandlers.load();

        expect(configMock._projects[0].color).toBe('#e41a1c');
    });

    it('stores no country field — no grouping or country gate in public viewer', async () => {
        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',

            mapboxToken: 'mapbox-token',
        };

        globalThis.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                view_name: 'No Country View',
                projects: [
                    { id: 'p1', name: 'Cave A', geojson_file: '/g1.geojson' },
                ]
            })
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        await mapHandlers.load();

        expect(configMock._projects[0]).not.toHaveProperty('country');
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

    it('retries a failed public prefetch on the next empty-project reload', async () => {
        let sourceChangeHandler;
        const originalWindowAddEventListener = window.addEventListener.bind(window);
        const windowAddEventListenerSpy = vi.spyOn(window, 'addEventListener').mockImplementation((eventName, handler, options) => {
            if (eventName === 'speleo:map-source-changed') {
                sourceChangeHandler = handler;
                return;
            }
            return originalWindowAddEventListener(eventName, handler, options);
        });

        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };

        globalThis.fetch
            .mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error'
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    view_name: 'Recovered Public View',
                    projects: [
                        { id: 'p1', name: 'Recovered Project', geojson_file: '/recovered.geojson' }
                    ]
                })
            });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        windowAddEventListenerSpy.mockRestore();

        await mapHandlers.load();

        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(utilsMock.showNotification).toHaveBeenCalledWith('error', 'Failed to load map data');
        expect(configMock.projects).toEqual([]);
        expect(sourceChangeHandler).toBeTypeOf('function');

        await sourceChangeHandler(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'future-destructive-source', reloadRequired: true }
        }));

        expect(globalThis.fetch).toHaveBeenCalledTimes(2);
        expect(layersMock.addProjectGeoJSON).toHaveBeenCalledWith('p1', '/recovered.geojson');
        expect(configMock._projects).toEqual([
            { id: 'p1', name: 'Recovered Project', color: undefined, permissions: 'READ_ONLY', geojson_url: '/recovered.geojson' }
        ]);
    });

    it('ignores non-destructive public map source changes', async () => {
        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };
        mapSourcesMock.requiresDataReload.mockReturnValue(false);

        globalThis.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                view_name: 'Public View',
                projects: [
                    { id: 'p1', name: 'Project One', geojson_file: '/g1.geojson' }
                ]
            })
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        await mapHandlers.load();

        stateMock.allProjectLayers = new Map([['p1', ['project-layer-p1']]]);
        layersMock.addProjectGeoJSON.mockClear();
        layersMock.reorderLayers.mockClear();
        projectPanelMock.refreshList.mockClear();
        globalThis.fetch.mockClear();

        window.dispatchEvent(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'esri-world-hillshade', reloadRequired: false }
        }));

        await Promise.resolve();

        expect(layersMock.addProjectGeoJSON).not.toHaveBeenCalled();
        expect(layersMock.reorderLayers).not.toHaveBeenCalled();
        expect(projectPanelMock.refreshList).not.toHaveBeenCalled();
        expect(globalThis.fetch).not.toHaveBeenCalled();
        expect(stateMock.allProjectLayers).toEqual(new Map([['p1', ['project-layer-p1']]]));
    });

    it('reloads existing public project layers only when a source event requires it', async () => {
        window.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };

        globalThis.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                view_name: 'Public View',
                projects: [
                    { id: 'p1', name: 'Project One', geojson_file: '/g1.geojson' }
                ]
            })
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        await mapHandlers.load();

        stateMock.allProjectLayers = new Map([['p1', ['project-layer-p1']]]);
        layersMock.addProjectGeoJSON.mockClear();
        layersMock.reorderLayers.mockClear();
        projectPanelMock.refreshList.mockClear();
        globalThis.fetch.mockClear();

        window.dispatchEvent(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'future-destructive-source', reloadRequired: true }
        }));

        await vi.waitFor(() => {
            expect(layersMock.addProjectGeoJSON).toHaveBeenCalledWith('p1', '/g1.geojson');
            expect(layersMock.reorderLayers).toHaveBeenCalled();
        });
        expect(projectPanelMock.refreshList).toHaveBeenCalled();
        expect(globalThis.fetch).not.toHaveBeenCalled();
        expect(stateMock.allProjectLayers.size).toBe(0);
    });
});
