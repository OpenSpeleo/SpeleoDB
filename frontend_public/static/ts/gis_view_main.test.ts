import type { Mock, MockInstance } from 'vitest';
import type { ViewerProject } from '../../../ts-types/domain/map-config.ts';
import type { MapRuntimeContext } from '../../../ts-types/domain/map-runtime.ts';
import type { DisplayPreferences, DepthDomain } from '../../../ts-types/domain/map-display.ts';

interface TestResponse { ok: boolean; status?: number; statusText?: string; json?: () => Promise<unknown> }
const testWindow = window as Window & { MAPVIEWER_CONTEXT?: Partial<Omit<MapRuntimeContext, 'gisToken'>> & { gisToken?: string | null } };
let fetchMock: Mock<(url: string) => Promise<TestResponse>>;
const stateMock = {
    resetLayerState: vi.fn(),
    projectBounds: new Map<string, object>(),
    allProjectLayers: new Map<string, string[]>(),
    effectiveProjectVisibility: new Map<string, boolean>(),
    projectDepthDomains: new Map<string, DepthDomain | null>(),
    displayPreferences: undefined as Partial<DisplayPreferences> | undefined,
    activeDepthDomain: null as DepthDomain | null
};

const mapCoreMock = {
    init: vi.fn(),
    setupColorModeToggle: vi.fn(),
    setupMapSourceControl: vi.fn()
};

const layersMock = {
    applyDisplayPreferences: vi.fn(),
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
    _projects: null as ViewerProject[] | null,
    get projects() {
        return this._projects || [];
    },
    setPublicProjects(projects: (ViewerProject & { geojson_file?: string | null | undefined })[]) {
        this._projects = projects.map(p => ({
            id: p.id,
            name: p.name,
            color: p.color,
            permissions: 'READ_ONLY',
            geojson_url: p.geojson_url || p.geojson_file,
        }));
    }
};

vi.mock('../../../frontend_private/static/private/ts/map_viewer/state.ts', async () => ({
    ...await vi.importActual<typeof import('../../../frontend_private/static/private/ts/map_viewer/state.ts')>('../../../frontend_private/static/private/ts/map_viewer/state.ts'),
    State: stateMock
}));

vi.mock('../../../frontend_private/static/private/ts/map_viewer/map/core.ts', () => ({
    MapCore: mapCoreMock
}));

vi.mock('../../../frontend_private/static/private/ts/map_viewer/map/sources.ts', () => ({
    MapSources: mapSourcesMock
}));

vi.mock('../../../frontend_private/static/private/ts/map_viewer/map/layers.ts', () => ({
    Layers: layersMock
}));

vi.mock('../../../frontend_private/static/private/ts/map_viewer/utils.ts', () => ({
    Utils: utilsMock
}));

vi.mock('../../../frontend_private/static/private/ts/map_viewer/components/project_panel.ts', () => ({
    ProjectPanel: projectPanelMock
}));

vi.mock('../../../frontend_private/static/private/ts/map_viewer/components/depth_legend.ts', () => ({
    DepthLegend: depthLegendMock
}));

vi.mock('../../../frontend_private/static/private/ts/map_viewer/config.ts', async () => {
    const actual = await vi.importActual<typeof import('../../../frontend_private/static/private/ts/map_viewer/config.ts')>('../../../frontend_private/static/private/ts/map_viewer/config.ts');
    return { Config: configMock, DEFAULTS: actual.DEFAULTS };
});

function createMapMock() {
    const handlers: Partial<Record<'load', () => Promise<void>>> = {};
    const map = {
        setMaxZoom: vi.fn(),
        on: vi.fn((eventName: 'load', handler: () => Promise<void>) => {
            handlers[eventName] = handler;
        }),
        fitBounds: vi.fn()
    };
    return { map, handlers };
}

class MockLngLatBounds {
    declare _empty: boolean;
    declare extended: unknown[];
    constructor() {
        this._empty = true;
        this.extended = [];
    }

    extend(value: unknown) {
        this._empty = false;
        this.extended.push(value);
    }

    isEmpty() {
        return this._empty;
    }
}

describe('frontend_public gis_view_main', () => {
    let mapMock: ReturnType<typeof createMapMock>['map'];
    let mapHandlers: ReturnType<typeof createMapMock>['handlers'];
    let domReadyHandler: EventListenerOrEventListenerObject | null;
    let addEventListenerSpy: MockInstance<typeof document.addEventListener>;
    let originalDocumentAddEventListener: typeof document.addEventListener;
    let consoleLogSpy: MockInstance<typeof console.log>;
    let consoleErrorSpy: MockInstance<typeof console.error>;

    async function importModuleAndGetDomReadyHandler() {
        const context = testWindow.MAPVIEWER_CONTEXT;
        vi.resetModules();
        const { configureRuntimeContext } = await import('../../../frontend_private/static/private/ts/map_viewer/runtime_context.ts');
        configureRuntimeContext(context);
        const { initPublicGISViewer } = await import('./gis_view_main.ts');
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

        testWindow.MAPVIEWER_CONTEXT = {};
        fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);
        vi.stubGlobal('__mapRenderer', { LngLatBounds: MockLngLatBounds });
        vi.stubGlobal('Urls', new Proxy(
            {},
            {
                get: (_target, prop) =>
                    (...args: unknown[]) =>
                        `/api/${String(prop)}${args.length ? '/' + args.join('/') : ''}`,
            }
        ));

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
        delete testWindow.MAPVIEWER_CONTEXT;
        vi.unstubAllGlobals();
        Reflect.deleteProperty(document, 'fullscreenElement');
    });

    it.each([
        { width: 1024, height: '830px' },
        { width: 640, height: '850px' },
    ])('sizes the public map for width $width without fullscreen policy', async ({ width, height }) => {
        testWindow.MAPVIEWER_CONTEXT = { viewMode: 'public', gisToken: 'public-token' };
        fetchMock.mockResolvedValue({ ok: true, json: async () => ({ projects: [] }) });
        const element = document.getElementById('map')!;
        vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 50, 800, 400));
        Object.defineProperty(document, 'fullscreenElement', { configurable: true, value: element });
        vi.stubGlobal('innerWidth', width);
        vi.stubGlobal('innerHeight', 900);
        const initialize = await importModuleAndGetDomReadyHandler();
        await initialize();
        expect(element.style.height).toBe(height);
    });

    it('shows invalid configuration notification and exits early', async () => {
        testWindow.MAPVIEWER_CONTEXT = { viewMode: 'private', gisToken: null };

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(utilsMock.showNotification).toHaveBeenCalledWith('error', 'Invalid GIS View configuration');
        expect(mapCoreMock.init).not.toHaveBeenCalled();
        expect(depthLegendMock.init).not.toHaveBeenCalled();
    });

    it('initializes with an empty token so tokenless map sources can render', async () => {
        testWindow.MAPVIEWER_CONTEXT = { viewMode: 'public', gisToken: 'abc', mapboxToken: '' };

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();

        expect(utilsMock.showNotification).not.toHaveBeenCalledWith('error', 'Map configuration missing');
        expect(mapCoreMock.init).toHaveBeenCalledWith('', 'map');
        expect(mapCoreMock.setupMapSourceControl).toHaveBeenCalledWith(mapMock, '');
    });

    it('initializes public viewer, loads projects, and wires shared depth legend', async () => {
        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token',
            allowPreciseZoom: false
        };

        stateMock.projectBounds = new Map([['p1', { any: 'bounds' }]]);
        fetchMock.mockResolvedValue({
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

        await mapHandlers.load!();

        expect(fetchMock).toHaveBeenCalledWith(Urls['api:v2:gis-ogc:view-geojson']('public-token'));
        expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/gis-layers'))).toBe(false);
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

        const overlay = document.getElementById('loading-overlay')!;
        expect(overlay).not.toBeNull();
        expect(overlay.classList.contains('opacity-0')).toBe(true);
        vi.runAllTimers();
        expect(document.getElementById('loading-overlay')!).toBeNull();
    });

    it.each(['depth', 'shot'])('initializes public defaults without reading or changing saved private %s preferences', async mode => {
        testWindow.MAPVIEWER_CONTEXT = { viewMode: 'public', gisToken: 'public-token', mapboxToken: '' };
        fetchMock.mockResolvedValue({ ok: true, json: async () => ({ projects: [] }) });
        const initialize = await importModuleAndGetDomReadyHandler();
        const { DEFAULTS } = await import('../../../frontend_private/static/private/ts/map_viewer/config.ts');
        const { DisplayPreferences } = await import('../../../frontend_private/static/private/ts/map_viewer/display_preferences.ts');
        const storageKey = DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES;
        const previous = localStorage.getItem(storageKey);
        const saved = JSON.stringify({
            version: DEFAULTS.DISPLAY.STORAGE_VERSION,
            colorMode: mode, depthLimitFeet: 125.75, depthUnit: 'm',
            categories: { caveEntrances: false, landmarks: false },
        });
        localStorage.setItem(storageKey, saved);
        stateMock.displayPreferences = { colorMode: mode as DisplayPreferences['colorMode'], depthLimitFeet: 125.75, depthUnit: 'm' };
        const read = vi.spyOn(localStorage, 'getItem');
        const write = vi.spyOn(localStorage, 'setItem');

        try {
            await initialize();

            expect(stateMock.displayPreferences).toMatchObject({
                colorMode: 'project', depthLimitFeet: null, depthUnit: 'ft',
                categories: { caveEntrances: true, landmarks: true },
            });
            expect(depthLegendMock.init).toHaveBeenCalledWith(mapMock);
            window.dispatchEvent(new CustomEvent('speleo:display-preferences-changed', {
                detail: { preferences: stateMock.displayPreferences },
            }));
            expect(read).not.toHaveBeenCalledWith(storageKey);
            expect(write).not.toHaveBeenCalled();
            expect(localStorage.getItem(storageKey)).toBe(saved);
        } finally {
            DisplayPreferences.destroy();
            read.mockRestore();
            write.mockRestore();
            if (previous === null) localStorage.removeItem(storageKey);
            else localStorage.setItem(storageKey, previous);
        }
    });

    it('prefetches the GIS View GeoJSON during init, before the map load event', async () => {
        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };

        fetchMock.mockResolvedValue({
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
        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(fetchMock).toHaveBeenCalledWith(Urls['api:v2:gis-ogc:view-geojson']('public-token'));

        await mapHandlers.load!();

        // The load handler consumes the prefetch instead of issuing a 2nd request.
        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(layersMock.addProjectGeoJSON).toHaveBeenCalledWith('p1', '/g1.geojson');
    });

    it('uses precise zoom limits when allowPreciseZoom is enabled', async () => {
        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',

            mapboxToken: 'mapbox-token',
            allowPreciseZoom: true
        };

        stateMock.projectBounds = new Map([['p1', { any: 'bounds' }]]);
        fetchMock.mockResolvedValue({
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

        await mapHandlers.load!();
        expect(mapMock.fitBounds).toHaveBeenCalledTimes(1);
        expect(mapMock.fitBounds).toHaveBeenCalledWith(
            expect.any(MockLngLatBounds),
            expect.objectContaining({ maxZoom: 16, padding: 50 })
        );
    });

    it('passes color through to Config.setPublicProjects', async () => {
        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',

            mapboxToken: 'mapbox-token',
        };

        fetchMock.mockResolvedValue({
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
        await mapHandlers.load!();

        expect(configMock._projects![0]!.color).toBe('#e41a1c');
    });

    it('stores no country field — no grouping or country gate in public viewer', async () => {
        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',

            mapboxToken: 'mapbox-token',
        };

        fetchMock.mockResolvedValue({
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
        await mapHandlers.load!();

        expect(configMock._projects![0]!).not.toHaveProperty('country');
    });

    it('shows load failure notification when public GIS API call fails', async () => {
        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',

            mapboxToken: 'mapbox-token'
        };

        fetchMock.mockResolvedValue({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error'
        });

        const onDomReady = await importModuleAndGetDomReadyHandler();
        await onDomReady();
        await mapHandlers.load!();

        expect(utilsMock.showNotification).toHaveBeenCalledWith('error', 'Failed to load map data');
        expect(projectPanelMock.init).not.toHaveBeenCalled();
        expect(layersMock.addProjectGeoJSON).not.toHaveBeenCalled();
        expect(layersMock.reorderLayers).not.toHaveBeenCalled();
    });

    it('retries a failed public prefetch on the next empty-project reload', async () => {
        let sourceChangeHandler!: (event: Event) => Promise<void>;
        const originalWindowAddEventListener = window.addEventListener.bind(window);
        const windowAddEventListenerSpy = vi.spyOn(window, 'addEventListener').mockImplementation((eventName, handler, options) => {
            if (eventName === 'speleo:map-source-changed') {
                sourceChangeHandler = handler as (event: Event) => Promise<void>;
                return;
            }
            return originalWindowAddEventListener(eventName, handler, options);
        });

        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };

        fetchMock
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

        await mapHandlers.load!();

        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(utilsMock.showNotification).toHaveBeenCalledWith('error', 'Failed to load map data');
        expect(configMock.projects).toEqual([]);
        expect(sourceChangeHandler).toBeTypeOf('function');

        await sourceChangeHandler(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'future-destructive-source', reloadRequired: true }
        }));

        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(layersMock.addProjectGeoJSON).toHaveBeenCalledWith('p1', '/recovered.geojson');
        expect(configMock._projects).toEqual([
            { id: 'p1', name: 'Recovered Project', color: undefined, permissions: 'READ_ONLY', geojson_url: '/recovered.geojson' }
        ]);
    });

    it('ignores non-destructive public map source changes', async () => {
        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };
        mapSourcesMock.requiresDataReload.mockReturnValue(false);

        fetchMock.mockResolvedValue({
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
        await mapHandlers.load!();

        stateMock.allProjectLayers = new Map([['p1', ['project-layer-p1']]]);
        layersMock.addProjectGeoJSON.mockClear();
        layersMock.reorderLayers.mockClear();
        projectPanelMock.refreshList.mockClear();
        fetchMock.mockClear();

        window.dispatchEvent(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'esri-world-hillshade', reloadRequired: false }
        }));

        await Promise.resolve();

        expect(layersMock.addProjectGeoJSON).not.toHaveBeenCalled();
        expect(layersMock.reorderLayers).not.toHaveBeenCalled();
        expect(projectPanelMock.refreshList).not.toHaveBeenCalled();
        expect(fetchMock).not.toHaveBeenCalled();
        expect(stateMock.allProjectLayers).toEqual(new Map([['p1', ['project-layer-p1']]]));
    });

    it('reloads existing public project layers only when a source event requires it', async () => {
        testWindow.MAPVIEWER_CONTEXT = {
            viewMode: 'public',
            gisToken: 'public-token',
            mapboxToken: 'mapbox-token'
        };

        fetchMock.mockResolvedValue({
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
        await mapHandlers.load!();

        stateMock.allProjectLayers = new Map([['p1', ['project-layer-p1']]]);
        layersMock.addProjectGeoJSON.mockClear();
        layersMock.reorderLayers.mockClear();
        projectPanelMock.refreshList.mockClear();
        fetchMock.mockClear();

        window.dispatchEvent(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'future-destructive-source', reloadRequired: true }
        }));

        await vi.waitFor(() => {
            expect(layersMock.addProjectGeoJSON).toHaveBeenCalledWith('p1', '/g1.geojson');
            expect(layersMock.reorderLayers).toHaveBeenCalled();
        });
        expect(projectPanelMock.refreshList).toHaveBeenCalled();
        expect(fetchMock).not.toHaveBeenCalled();
        expect(stateMock.allProjectLayers.size).toBe(0);
    });
    it('starts prefetch before a missing map element rejects initialization', async () => {
        testWindow.MAPVIEWER_CONTEXT = { viewMode: 'public', gisToken: 'public-token' };
        fetchMock.mockResolvedValue({ ok: true, json: async () => ({ projects: [] }) });
        document.body.innerHTML = '';
        const initialize = await importModuleAndGetDomReadyHandler();
        await expect(initialize()).rejects.toBeInstanceOf(TypeError);
        expect(fetchMock).toHaveBeenCalledOnce();
        expect(depthLegendMock.init).toHaveBeenCalledOnce();
        expect(mapCoreMock.setupMapSourceControl).not.toHaveBeenCalled();
    });

});
