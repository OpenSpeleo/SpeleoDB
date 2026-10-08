import { GLOBE_ATMOSPHERE_LAYER_ID } from '@speleodb/map-viewer';
import type { GlobeAtmosphereMap } from '@speleodb/map-viewer';
import type { CustomLayerInterface, SkySpecification } from 'maplibre-gl';
import { StationManager } from '../../frontend_private/static/private/ts/map_viewer/stations/manager.ts';
import { SurfaceStationManager } from '../../frontend_private/static/private/ts/map_viewer/surface_stations/manager.ts';
import { ExplorationLeadManager } from '../../frontend_private/static/private/ts/map_viewer/exploration_leads/manager.ts';
import type { RendererLayer } from '../../ts-types/domain/renderer.ts';
import { GeometryEditor } from '../../frontend_private/static/private/ts/map_viewer/geometry_editor/editor.ts';
import { ProjectPanel } from '../../frontend_private/static/private/ts/map_viewer/components/project_panel.ts';
import { GPSTracksPanel } from '../../frontend_private/static/private/ts/map_viewer/components/gps_tracks_panel.ts';
import { GISLayersPanel } from '../../frontend_private/static/private/ts/map_viewer/components/gis_layers_panel.ts';
import { GISGeometriesPanel } from '../../frontend_private/static/private/ts/map_viewer/components/gis_geometries_panel.ts';
import { Config } from '../../frontend_private/static/private/ts/map_viewer/config.ts';
import { State } from '../../frontend_private/static/private/ts/map_viewer/state.ts';
import { DisplayPreferences } from '../../frontend_private/static/private/ts/map_viewer/display_preferences.ts';
import { ViewerUpdates } from '../../frontend_private/static/private/ts/map_viewer/viewer_updates.ts';
import { DepthLegend } from '../../frontend_private/static/private/ts/map_viewer/components/depth_legend.ts';
import { MapSettings } from '../../frontend_private/static/private/ts/map_viewer/components/settings.ts';
import { configureRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';
import { initPrivateMapViewer } from '../../frontend_private/static/private/ts/map_viewer/main.ts';
import { initPublicGISViewer } from '../../frontend_public/static/ts/gis_view_main.ts';

interface VendorControl { onAdd?(map: unknown): HTMLElement; onRemove?(): void }
class VendorBounds {
    points: unknown[];
    constructor(...points: unknown[]) { this.points = points; }
    extend(point: unknown) { this.points.push(point); return this; }
    isEmpty() { return this.points.length === 0; }
}
interface VendorSource { data?: unknown; setData(data: unknown): void }
type VendorLayer = Omit<RendererLayer, 'type'> & { type: RendererLayer['type'] | CustomLayerInterface['type'] };
class VendorMap implements GlobeAtmosphereMap {
    sources = new Map<string, VendorSource>();
    layers = new Map<string, VendorLayer>();
    images = new Set<string>();
    styleLoaded = false;
    sky: SkySpecification | undefined;
    fits: { bounds: unknown; options: unknown }[] = [];
    addSource(id: string, definition: { data?: unknown }) {
        this.sources.set(id, { ...definition, setData(data) { this.data = data; } });
    }
    removeSource(id: string) { this.sources.delete(id); }
    addLayer(layer: VendorLayer) { this.layers.set(layer.id, layer); }
    removeLayer(id: string) { this.layers.delete(id); }
    setLayoutProperty(id: string, name: string, value: unknown) { Object.assign(this.layers.get(id)!.layout ??= {}, { [name]: value }); }
    setPaintProperty(id: string, name: string, value: unknown) { Object.assign(this.layers.get(id)!.paint ??= {}, { [name]: value }); }
    setFilter(id: string, filter: unknown) { Object.assign(this.layers.get(id)!, { filter }); }
    moveLayer() {}
    async loadImage(_url: string) { return { data: {} }; }

    addImage(id: string) { this.images.add(id); }
    fitBounds(bounds: unknown, options: unknown) { this.fits.push({ bounds, options }); }

    handlers = new Map<string, Set<(event: unknown) => unknown>>();
    controls: VendorControl[] = [];
    maxZoom: number | undefined;
    on(name: string, handler: (event: unknown) => unknown) {
        if (!this.handlers.has(name)) this.handlers.set(name, new Set());
        this.handlers.get(name)!.add(handler);
    }
    off(name: string, handler: (event: unknown) => unknown) { this.handlers.get(name)?.delete(handler); }
    async fire(name: string) {
        if (name === 'style.load') this.styleLoaded = true;
        await Promise.all([...this.handlers.get(name) || []].map(handler => handler(undefined)));
    }
    getContainer() { return document.getElementById('map')!; }
    getCanvas() { return this.getContainer().querySelector('canvas')!; }
    addControl(control: VendorControl) {
        this.controls.push(control);
        const element = control.onAdd?.(this);
        if (element) this.getContainer().append(element);
    }
    setMaxZoom(zoom: number) { this.maxZoom = zoom; }
    resize() {}
    jumpTo() {}
    setStyle() {
        this.styleLoaded = false;
        this.sources.clear(); this.layers.clear(); this.images.clear();
        this.sky = undefined;
    }
    isStyleLoaded() { return this.styleLoaded; }
    getSky() { return this.sky; }
    setSky(sky: SkySpecification) { this.sky = sky; }
    getLayersOrder() { return [...this.layers.keys()]; }
    getStyle() { return { layers: [...this.layers.values()], sources: Object.fromEntries(this.sources) }; }
    getLayer(id: string) { return this.layers.get(id); }
    getSource(id: string) { return this.sources.get(id); }
    hasImage(id: string) { return this.images.has(id); }
    queryRenderedFeatures() { return []; }
    doubleClickZoom = { isEnabled: () => true, enable() {}, disable() {} };
    dragPan = { isEnabled: () => true, enable() {}, disable() {} };
}

let map: VendorMap;
function captureMap(value: VendorMap) { map = value; }
let requests: string[];
let responses: Map<string, unknown>;
const project = { id: 'project', name: 'Survey', color: '#22c55e', country: 'US', permission: 'READ_ONLY', geojson_url: '/survey.geojson', geojson_file: '/survey.geojson' };
const survey = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { depth: 12 }, geometry: { type: 'LineString', coordinates: [[-87, 20], [-86.9, 20.1]] } }] };
const emptyGeoJSON = { type: 'FeatureCollection', features: [] };
let listeners: { target: EventTarget; type: string; handler: EventListenerOrEventListenerObject; options?: boolean | AddEventListenerOptions | undefined }[];
beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div id="map-viewer-shell"><div id="loading-overlay"><span id="loading-progress"></span></div><div id="map"><canvas></canvas></div></div>';
    localStorage.clear();
    State.resetLayerState();
    StationManager.invalidateCache();
    SurfaceStationManager.invalidateCache();
    ExplorationLeadManager.invalidateCache();
    Config._projects = null;
    Config._networks = null;
    Config._gpsTracks = null;
    Config._gisLayers = null;
    Config._gisGeometries = null;
    requests = [];
    responses = new Map();
    listeners = [];
    for (const target of [window, document]) {
        const original = target.addEventListener.bind(target);
        vi.spyOn(target, 'addEventListener').mockImplementation((type: string, handler: EventListenerOrEventListenerObject, options?: boolean | AddEventListenerOptions) => {
            listeners.push({ target, type, handler, options });
            original(type, handler, options);
        });
    }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
        requests.push(url);
        const response = responses.get(url);
        if (response instanceof Response) return response.clone();
        return Response.json(responses.get(url) ?? (url.includes('view-geojson') ? { projects: [], view_name: 'Public' } : url.endsWith('-geojson') ? emptyGeoJSON : []));
    }));
    vi.stubGlobal('Urls', {
        'api:v2:projects': () => '/projects',
        'api:v2:subsurface-stations-geojson': () => '/stations-geojson',
        'api:v2:landmark-collections': () => '/collections',
        'api:v2:landmarks-geojson': () => '/landmarks-geojson',
        'api:v2:exploration-lead-all-geojson': () => '/leads-geojson',
        'api:v2:cylinder-installs-geojson': () => '/cylinders-geojson',
        'api:v2:station-tags': () => '/tags',
        'api:v2:station-tag-colors': () => '/tag-colors',

        'api:v2:surface-networks': () => '/networks',
        'api:v2:gps-tracks': () => '/gps',
        'api:v2:gis-layers': () => '/gis-layers',
        'api:v2:gis-geometry-list': () => '/geometries',
        'api:v2:all-projects-geojson': () => '/metadata',
        'api:v2:gis-ogc:view-geojson': (token: string) => `/view-geojson/${token}`,
    });
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
    vi.stubGlobal('__mapRenderer', {
        Map: class extends VendorMap { constructor() { super(); captureMap(this); } },
        AttributionControl: class {
            onAdd() { return document.createElement('div'); }
            onRemove() {}
        },
        NavigationControl: class {}, FullscreenControl: class {}, ScaleControl: class {},
        addProtocol() {}, LngLatBounds: VendorBounds,
    });
});
afterEach(async () => {
    GeometryEditor.destroy(); ProjectPanel.destroy(); GPSTracksPanel.destroy(); GISLayersPanel.destroy(); GISGeometriesPanel.destroy();
    DepthLegend.destroy();
    MapSettings.destroy();
    DisplayPreferences.destroy();
    for (const control of map.controls) control.onRemove?.();
    await map.fire('remove');
    ViewerUpdates.cancelAll();
    for (const { target, type, handler, options } of listeners) target.removeEventListener(type, handler, options);
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    State.map = null;
    document.body.innerHTML = '';
});

it('composes the real private modules and starts six independent metadata requests before map load', async () => {
    configureRuntimeContext({ mapboxToken: '', icons: {} });
    await initPrivateMapViewer();
    expect(requests).toEqual(['/projects', '/networks', '/gps', '/gis-layers', '/geometries', '/metadata']);
    expect(State.map).toBe(map);
    expect(document.querySelector('.measurement-control')).not.toBeNull();
    expect(document.getElementById('map-source-control')).not.toBeNull();
    expect(map.handlers.get('click')?.size).toBeGreaterThan(0);
    expect(map.handlers.get('load')?.size).toBe(2);
    expect(DisplayPreferences._onChange).not.toBeNull();
});

it('composes the real public modules without private tools and starts its request before map load', async () => {
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared', allowPreciseZoom: false });
    await initPublicGISViewer();
    expect(requests).toEqual(['/view-geojson/shared']);
    expect(State.map).toBe(map);
    expect(map.maxZoom).toBe(13);
    expect(document.getElementById('map-source-control')).not.toBeNull();
    expect(document.querySelector('.measurement-control')).toBeNull();
    expect(map.handlers.has('click')).toBe(false);
    expect(DisplayPreferences._onChange).toBeNull();
    expect(map.handlers.get('load')?.size).toBe(2);
});

async function sourceChanged(reloadRequired: boolean) {
    const event = new CustomEvent('speleo:map-source-changed', { detail: { reloadRequired } });
    await Promise.all(listeners.filter(item => item.target === window && item.type === event.type).map(({ handler }): unknown => (
        typeof handler === 'function' ? handler.call(window, event) : handler.handleEvent(event)
    )));
    await ViewerUpdates.whenIdle();
}

it.each(['private', 'public'] as const)('hydrates the real %s viewer and restores survey sources after a style replacement', async mode => {
    vi.useRealTimers();
    responses.set('/projects', [project]);
    responses.set('/metadata', [project]);
    responses.set('/survey.geojson', survey);
    responses.set('/tag-colors', { colors: ['#22c55e'] });
    responses.set('/view-geojson/shared', { projects: [project], view_name: 'Public' });
    configureRuntimeContext(mode === 'public'
        ? { viewMode: 'public', gisToken: 'shared', allowPreciseZoom: false }
        : { icons: {} });

    await (mode === 'public' ? initPublicGISViewer() : initPrivateMapViewer());
    expect(map.isStyleLoaded()).toBe(false);
    expect(map.getLayer(GLOBE_ATMOSPHERE_LAYER_ID)).toBeUndefined();
    await map.fire('style.load');
    const atmosphere = map.getLayer(GLOBE_ATMOSPHERE_LAYER_ID);
    expect(atmosphere).toMatchObject({ type: 'custom' });
    await map.fire('load');
    await ViewerUpdates.whenIdle();

    expect(Config.projects.map(item => item.id)).toEqual(['project']);
    expect(map.getSource('project-geojson-project')?.data).toMatchObject(survey);
    expect(map.getLayer('project-layer-project')).toMatchObject({ type: 'line', source: 'project-geojson-project' });
    expect(State.effectiveProjectVisibility.get('project')).toBe(true);
    expect(State.projectBounds.has('project')).toBe(true);
    expect(map.fits).toHaveLength(1);
    expect(map.fits[0]!.options).toMatchObject({ maxZoom: mode === 'public' ? 13 : 16 });
    expect(document.querySelector('#loading-overlay')?.classList.contains('pointer-events-none')).toBe(true);
    const requestsBefore = [...requests];
    await sourceChanged(false);
    expect(requests).toEqual(requestsBefore);

    // A source requiring a style replacement has removed the former renderer state.
    map.setStyle();
    await map.fire('style.load');
    expect(map.getLayer(GLOBE_ATMOSPHERE_LAYER_ID)).toMatchObject({ type: 'custom' });
    expect(map.getLayer(GLOBE_ATMOSPHERE_LAYER_ID)).not.toBe(atmosphere);
    await sourceChanged(true);
    expect(map.getSource('project-geojson-project')?.data).toMatchObject(survey);
    expect(State.projectBounds.has('project')).toBe(true);
    expect(requests.filter(url => url === '/survey.geojson')).toHaveLength(2);
    expect(requests.filter(url => url === (mode === 'public' ? '/view-geojson/shared' : '/projects'))).toHaveLength(1);
    expect(map.fits).toHaveLength(1);
    if (mode === 'public') {
        expect(requests.some(url => /stations|collections|cylinders|tags/.test(url))).toBe(false);
        expect(map.handlers.has('contextmenu')).toBe(false);
    } else {
        expect(requests).toContain('/stations-geojson');
        expect(requests).toContain('/landmarks-geojson');
    }
});

it('consumes a failed public prefetch and retries through the real source-change lifecycle', async () => {
    vi.useRealTimers();
    responses.set('/view-geojson/shared', Response.json({ detail: 'Unavailable' }, { status: 503, statusText: 'Unavailable' }));
    responses.set('/survey.geojson', survey);
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    expect(requests).toEqual(['/view-geojson/shared']);
    expect(Config.projects).toEqual([]);
    expect(map.getSource('project-geojson-project')).toBeUndefined();
    expect(document.body.textContent).toContain('Failed to load map data');
    expect(document.querySelector('#loading-overlay')?.classList.contains('pointer-events-none')).toBe(true);

    responses.set('/view-geojson/shared', { projects: [project], view_name: 'Recovered' });
    await sourceChanged(true);
    expect(requests).toEqual(['/view-geojson/shared', '/view-geojson/shared', '/survey.geojson']);
    expect(map.getSource('project-geojson-project')?.data).toMatchObject(survey);
    expect(Config.projects.map(item => item.id)).toEqual(['project']);
    expect(map.fits).toEqual([]);
});
