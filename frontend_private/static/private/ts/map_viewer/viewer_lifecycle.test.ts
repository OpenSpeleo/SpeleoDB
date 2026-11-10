import { runtimeClosure } from '../../../../../frontend_common/test/runtime-import-graph.ts';
import path from 'node:path';
import { State } from './state.ts';
import { clearRenderedSurveyState, createMapHeightUpdater, registerViewerDataLifecycle } from './viewer_lifecycle.ts';


describe('read-only viewer lifecycle', () => {
    it('runs load and source callbacks only when their native events arrive', async () => {
        let loadCalls = 0;
        let sourceCalls = 0;
        let mapLoad!: () => Promise<void>;
        const load = async () => { loadCalls += 1; };
        const sourceChange = async () => { sourceCalls += 1; };
        registerViewerDataLifecycle({ on(_event, callback) { mapLoad = callback; } }, { load, sourceChange });
        try {
            expect(loadCalls).toBe(0);
            expect(sourceCalls).toBe(0);
            await mapLoad();
            window.dispatchEvent(new CustomEvent('speleo:map-source-changed'));
            expect(loadCalls).toBe(1);
            expect(sourceCalls).toBe(1);
        } finally {
            window.removeEventListener('speleo:map-source-changed', sourceChange as unknown as EventListener);
        }
    });

    afterEach(() => {
        State.resetLayerState();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        document.body.innerHTML = '';
    });

    it('replaces rendered survey containers while retaining preferences, cached data, and private state', () => {
        State.effectiveProjectVisibility.set('1', true);
        State.allProjectLayers.set('1', ['project-layer-1']);
        State.projectDepthDomains.set('1', { min: 0, max: 10 });
        State.activeDepthDomain = { min: 0, max: 10 };
        const before = { ...State };
        clearRenderedSurveyState(State);
        for (const key of ['effectiveProjectVisibility', 'allProjectLayers', 'projectDepthDomains', 'projectBounds'] as const) {
            expect(State[key]).not.toBe(before[key]);
            expect(State[key].size).toBe(0);
        }
        expect(State.activeDepthDomain).toBeNull();
        for (const key of ['projectLayerStates', 'displayPreferences', 'gpsTrackCache', 'gisLayerCache', 'allStations', 'allNetworkLayers', 'allLandmarks', 'cylinderInstalls', 'layerGeneration'] as const) {
            expect(State[key]).toBe(before[key]);
        }
    });

    it('recomputes height from the current viewport and explicit fullscreen policy', () => {
        document.body.innerHTML = '<div id="map"></div>';
        const element = document.getElementById('map')!;
        // JSDOM does not compute layout or native viewport dimensions.
        vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 50, 800, 400));
        vi.stubGlobal('innerWidth', 1024);
        vi.stubGlobal('innerHeight', 300);
        let fullscreen = false;
        const update = createMapHeightUpdater(() => fullscreen);
        update();
        expect(element.style.height).toBe('600px');
        fullscreen = true;
        update();
        expect(element.style.height).toBe('250px');
        vi.stubGlobal('innerHeight', 900);
        update();
        expect(element.style.height).toBe('850px');
    });

    it('keeps private tools and action registration outside the entire public runtime graph', () => {
        const closure = runtimeClosure('frontend_public/static/ts/gis_view_main.ts');
        const relative = [...closure].map(file => path.relative(process.cwd(), file).replaceAll(path.sep, '/'));
        expect(relative.some(file => file.endsWith('/viewer_lifecycle.ts'))).toBe(true);
        expect(relative.filter(file => /\/(?:stations|surface_stations|landmarks|exploration_leads)\//.test(file)
            || /\/(?:geometry_editor\/editor|measurement\/tool|action_dispatcher|components\/(?:context_menu|settings))\.ts$/.test(file))).toEqual([]);
        const shared = runtimeClosure('frontend_private/static/private/ts/map_viewer/viewer_lifecycle.ts');
        const appRoot = path.resolve('frontend_private/static/private/ts/map_viewer') + path.sep;
        expect([...shared].filter(file => file.startsWith(appRoot)).map(file => path.basename(file)).sort())
            .toEqual(['defaults.ts', 'viewer_lifecycle.ts']);
        // The package closure contains pure definitions, never an application
        // controller or initialization side effect. Audit compiled installs too.
        const portable = [...shared].filter(file => !file.startsWith(appRoot));
        expect(portable).toHaveLength(3);
        for (const file of portable) {
            expect(file.replaceAll(path.sep, '/')).toMatch(/map-(?:core|viewer)\/(?:src|dist)\/(?:depth|preparation|expressions)\.[jt]s$/);
        }
    });
});
