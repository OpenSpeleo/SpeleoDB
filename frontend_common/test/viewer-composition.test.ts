import type { ProjectMapRevision, ProjectRevisionMapContext } from '../../ts-types/controllers/project-revision-map.ts';
import { initReadOnlyViewer } from '../../frontend_private/static/private/ts/map_viewer/read_only_viewer.ts';
import { init as initProjectRevisionMap } from '../controllers/project-revision-map.ts';
import { setBrowserUrl, startApiServer } from './api-server.ts';
import type { ApiTestReply } from './api-server.ts';
import { GLOBE_ATMOSPHERE_LAYER_ID } from '@speleodb/map-viewer';
import type { GlobeAtmosphereMap } from '@speleodb/map-viewer';
import type { CustomLayerInterface, SkySpecification } from 'maplibre-gl';
import { StationManager } from '../../frontend_private/static/private/ts/map_viewer/stations/manager.ts';
import { SurfaceStationManager } from '../../frontend_private/static/private/ts/map_viewer/surface_stations/manager.ts';
import { ExplorationLeadManager } from '../../frontend_private/static/private/ts/map_viewer/exploration_leads/manager.ts';
import type { RendererLayer } from '../../ts-types/domain/renderer.ts';
import type { MapCreationOptions } from '../../ts-types/domain/map-core.ts';
import { GeometryEditor } from '../../frontend_private/static/private/ts/map_viewer/geometry_editor/editor.ts';
import { ProjectPanel } from '../../frontend_private/static/private/ts/map_viewer/components/project_panel.ts';
import { GPSTracksPanel } from '../../frontend_private/static/private/ts/map_viewer/components/gps_tracks_panel.ts';
import { GISLayersPanel } from '../../frontend_private/static/private/ts/map_viewer/components/gis_layers_panel.ts';
import { GISGeometriesPanel } from '../../frontend_private/static/private/ts/map_viewer/components/gis_geometries_panel.ts';
import { Config, DEFAULTS } from '../../frontend_private/static/private/ts/map_viewer/config.ts';
import { Layers } from '../../frontend_private/static/private/ts/map_viewer/map/layers.ts';
import { MapCore } from '../../frontend_private/static/private/ts/map_viewer/map/core.ts';
import { State, createDefaultDisplayPreferences } from '../../frontend_private/static/private/ts/map_viewer/state.ts';
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
    toArray(): [[number, number], [number, number]] { return [[-87, 20], [-86.9, 20.1]]; }
}
interface VendorSource { data?: unknown; setData(data: unknown): void }
type VendorLayer = Omit<RendererLayer, 'type'> & { type: RendererLayer['type'] | CustomLayerInterface['type'] };
// jsdom cannot create WebGL maps. This engine port is the only renderer
// substitute; viewer startup, state, configuration, layers and UI remain real.
class VendorMap implements GlobeAtmosphereMap {
    cancelPendingTileRequestsWhileZooming = true;
    sources = new Map<string, VendorSource>();
    layers = new Map<string, VendorLayer>();
    images = new Set<string>();
    styleLoaded = false;
    sky: SkySpecification | undefined;
    fits: { bounds: unknown; options: unknown }[] = [];
    cameraDurationMs = 0;
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
    fitBounds(bounds: unknown, options: unknown) { this.fits.push({ bounds, options }); setTimeout(() => { void this.fire('moveend'); }, this.cameraDurationMs); }
    stop() {}
    getZoom() { return 10; }
    getBearing() { return 0; }
    getPitch() { return 0; }
    project(point: readonly number[]) { return { x: point[0]!, y: point[1]! }; }

    handlers = new Map<string, Set<(event: unknown) => unknown>>();
    controls: VendorControl[] = [];
    maxZoom: number | undefined;
    creationOptions: MapCreationOptions | undefined;
    cameraJumps: unknown[] = [];
    resizeCount = 0;
    renderingBlocked = false;
    renderedLayers: string[][] = [];
    isSourceLoaded(id: string) { return this.sources.has(id); }
    triggerRepaint() { if (!this.renderingBlocked) setTimeout(() => { void this.fire('render'); }, 0); }
    on(name: string, handler: (event: unknown) => unknown) {
        if (!this.handlers.has(name)) this.handlers.set(name, new Set());
        this.handlers.get(name)!.add(handler);
    }
    off(name: string, handler: (event: unknown) => unknown) { this.handlers.get(name)?.delete(handler); }
    async fire(name: string) {
        if (name === 'style.load') this.styleLoaded = true;
        if (name === 'render') this.renderedLayers.push([...this.layers.values()]
            .filter(layer => layer.layout?.visibility !== 'none').map(layer => layer.id));
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
    resize() { this.resizeCount += 1; }
    jumpTo(options: unknown) { this.cameraJumps.push(options); }
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
let fullscreenContainers: (HTMLElement | undefined)[];
function captureMap(value: VendorMap) { map = value; }
let requests: string[];
let responses: Map<string, ApiTestReply>;
let server: Awaited<ReturnType<typeof startApiServer>>;
beforeAll(async () => { server = await startApiServer(); });
afterAll(async () => { await server.close(); });
const project = { id: 'project', name: 'Survey', color: '#22c55e', country: 'US', permission: 'READ_ONLY', geojson_file: '/survey.geojson' };
const survey = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { depth: 12 }, geometry: { type: 'LineString', coordinates: [[-87, 20], [-86.9, 20.1]] } }] };
const emptyGeoJSON = { type: 'FeatureCollection', features: [] };
let listeners: { target: EventTarget; type: string; handler: EventListenerOrEventListenerObject; options?: boolean | AddEventListenerOptions | undefined }[];
beforeEach(() => {
    map = new VendorMap();
    fullscreenContainers = [];
    server.reset();
    setBrowserUrl(server.origin);
    project.geojson_file = `${server.origin}/survey.geojson`;
    document.body.innerHTML = '<div id="map-viewer-shell"><div id="loading-overlay"><span id="loading-progress"></span></div><div id="map"><canvas></canvas></div></div>';
    localStorage.clear();
    State.resetLayerState();
    State.displayPreferences = createDefaultDisplayPreferences();
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
    // Forward native listener registration and retain handles solely for
    // teardown, since EventTarget has no listener-enumeration API.
    for (const target of [window, document]) {
        const original = target.addEventListener.bind(target);
        vi.spyOn(target, 'addEventListener').mockImplementation((type: string, handler: EventListenerOrEventListenerObject, options?: boolean | AddEventListenerOptions) => {
            listeners.push({ target, type, handler, options });
            original(type, handler, options);
        });
    }
    server.handle(request => {
        requests.push(request.path);
        return responses.get(request.path) ?? { json: request.path.includes('/gis-ogc/')
            ? { projects: [], view_name: 'Public' }
            : request.path.endsWith('/geojson/') && request.path !== '/api/v2/projects/geojson/' ? emptyGeoJSON : [] };
    });
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
    // JSDOM has no native media-query evaluation. Keep actual timers and rendering callbacks.
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
    vi.stubGlobal('__mapRenderer', {
        Map: class extends VendorMap { constructor(options: MapCreationOptions) { super(); this.creationOptions = options; captureMap(this); } },
        AttributionControl: class {
            onAdd() { return document.createElement('div'); }
            onRemove() {}
        },
        NavigationControl: class {},
        FullscreenControl: class { constructor(options?: { container: HTMLElement }) { fullscreenContainers.push(options?.container); } },
        ScaleControl: class {},
        addProtocol() {}, LngLatBounds: VendorBounds,
    });
});
afterEach(async () => {
    await new Promise(resolve => setTimeout(resolve, 20));
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
    State.map = null;
    Reflect.deleteProperty(document, 'fullscreenElement');
    document.body.innerHTML = '';
});

it('composes the real private modules and starts six independent metadata requests before map load', async () => {
    configureRuntimeContext({ mapboxToken: '', icons: {} });
    await initPrivateMapViewer();
    await vi.waitFor(() => expect(requests).toHaveLength(6));
    expect(requests).toEqual(['/api/v2/projects/', '/api/v2/surface-networks/', '/api/v2/gps_tracks/', '/api/v2/gis-layers/', '/api/v2/gis-geometries/', '/api/v2/projects/geojson/']);
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
    await vi.waitFor(() => expect(requests).toHaveLength(1));
    expect(requests).toEqual(['/api/v2/gis-ogc/view/shared/geojson']);
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
    responses.set('/api/v2/projects/', { json: [project] });
    responses.set('/api/v2/projects/geojson/', { json: [project] });
    responses.set('/survey.geojson', { json: survey });
    responses.set('/api/v2/station_tags/colors/', { json: { colors: ['#22c55e'] } });
    responses.set('/api/v2/gis-ogc/view/shared/geojson', { json: { projects: [project], view_name: 'Public' } });
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
    if (mode === 'private') State.gisLayerClickableLayerIds.add('retired-click-layer');
    map.setStyle();
    await map.fire('style.load');
    expect(map.getLayer(GLOBE_ATMOSPHERE_LAYER_ID)).toMatchObject({ type: 'custom' });
    expect(map.getLayer(GLOBE_ATMOSPHERE_LAYER_ID)).not.toBe(atmosphere);
    await sourceChanged(true);
    if (mode === 'private') expect(State.gisLayerClickableLayerIds.has('retired-click-layer')).toBe(false);
    expect(map.getSource('project-geojson-project')?.data).toMatchObject(survey);
    expect(State.projectBounds.has('project')).toBe(true);
    expect(requests.filter(url => url === '/survey.geojson')).toHaveLength(2);
    expect(requests.filter(url => url === (mode === 'public' ? '/api/v2/gis-ogc/view/shared/geojson' : '/api/v2/projects/'))).toHaveLength(1);
    expect(map.fits).toHaveLength(1);
    if (mode === 'public') {
        expect(requests.some(url => /stations|collections|cylinders|tags/.test(url))).toBe(false);
        expect(map.handlers.has('contextmenu')).toBe(false);
    } else {
        expect(requests).toContain('/api/v2/stations/subsurface/geojson/');
        expect(requests).toContain('/api/v2/landmarks/geojson/');
    }
});

it('reports a failed public prefetch without publishing a survey source', async () => {
    responses.set('/api/v2/gis-ogc/view/shared/geojson', { status: 503, json: { detail: 'Unavailable' } });
    responses.set('/survey.geojson', { json: survey });
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    await vi.waitFor(() => expect(requests).toHaveLength(1));
    expect(requests).toEqual(['/api/v2/gis-ogc/view/shared/geojson']);
    expect(Config.projects).toEqual([]);
    expect(map.getSource('project-geojson-project')).toBeUndefined();
    expect(document.body.textContent).toContain('Failed to load map data');
    expect(document.querySelector('#loading-overlay')?.classList.contains('pointer-events-none')).toBe(true);
});

it('frames loaded public surveys when another artifact is malformed', async () => {
    responses.set('/api/v2/gis-ogc/view/shared/geojson', { json: {
        projects: [project, { ...project, id: 'malformed', geojson_file: `${server.origin}/malformed.geojson` }],
        view_name: 'Partially available',
    } });
    responses.set('/survey.geojson', { json: survey });
    responses.set('/malformed.geojson', { text: 'invalid GeoJSON' });
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    await map.fire('style.load');
    await map.fire('load');
    expect(map.getSource('project-geojson-project')?.data).toMatchObject(survey);
    expect(map.getSource('project-geojson-malformed')).toBeUndefined();
    expect(map.fits).toHaveLength(1);
    expect((map.fits[0]!.bounds as VendorBounds).points).toContain(State.projectBounds.get('project'));
    expect(document.body.textContent).toContain('Failed to load survey data');
});

it('clips public surveys before rendering, depth and navigation and retains full inputs across style changes', async () => {
    const bound = { id: 'bound', revision: 1, color: '#a855f7', alias: 'Boundary label', geojson: {
        type: 'Polygon', coordinates: [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]],
    } };
    const outsideProject = { ...project, id: 'outside', name: 'Outside survey', geojson_file: `${server.origin}/outside.geojson` };
    responses.set('/api/v2/gis-ogc/view/shared/geojson', { json: {
        projects: [project, outsideProject], view_name: 'Bounded', geographic_bound: bound,
    } });
    responses.set('/survey.geojson', { json: { type: 'FeatureCollection', bbox: [-100, -80, 100, 80], features: [
        { type: 'Feature', properties: { depth: 8 }, geometry: { type: 'LineString', coordinates: [[-0.01, 0.005, 2], [0.02, 0.005, 8]] } },
        { type: 'Feature', properties: { depth: 12, section_name: 'Inside' }, geometry: { type: 'Point', coordinates: [0.005, 0.005] } },
        { type: 'Feature', properties: { depth: 999, section_name: 'Outside' }, geometry: { type: 'Point', coordinates: [1, 1] } },
    ] } });
    responses.set('/outside.geojson', { json: { type: 'FeatureCollection', features: [
        { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [1, 1] } },
    ] } });
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();

    const clipped = map.getSource('project-geojson-project')?.data;
    expect(clipped).toMatchObject({ type: 'FeatureCollection', features: [
        { geometry: { type: 'LineString', coordinates: [[expect.closeTo(0), 0.005, 0], [expect.closeTo(0.01), 0.005, 0]] } },
        { geometry: { type: 'Point', coordinates: [0.005, 0.005] } },
    ] });
    expect(clipped).not.toHaveProperty('bbox');
    expect(map.getSource('project-geojson-outside')).toBeUndefined();
    expect(Config.projects.map(item => item.id)).toEqual(['project']);
    expect(document.getElementById('project-list')?.textContent).not.toContain('Outside survey');
    expect(State.projectDepthDomains.get('project')).toEqual({ min: 0, max: 12 });
    expect(State.projectBounds.get('project')).toMatchObject({ points: [[expect.closeTo(0), 0.005], [expect.closeTo(0.01), 0.005]] });
    expect(map.getSource('gis-geometry-source-bound')?.data).toMatchObject({ type: 'Feature', geometry: bound.geojson });
    expect(map.getLayer('gis-geometry-bound-outline')).toMatchObject({ type: 'line', layout: { visibility: 'visible' } });
    expect((map.fits[0]?.bounds as VendorBounds).points).toContainEqual([0, 0]);
    expect((map.fits[0]?.bounds as VendorBounds).points).toContainEqual([0.01, 0.01]);
    expect(State.gisGeometryStates.get('bound')).toBe(true);
    expect(map.getLayer('gis-geometry-bound-fill')?.paint?.['fill-color']).toBe(bound.color);
    expect(map.getSource('gis-geometry-label-source-bound')?.data).toMatchObject({ properties: { alias: bound.alias, color: bound.color } });
    await Layers.setProjectVisibilityBatch([{ projectId: 'project', visible: false }]);
    await Layers.setGeometryLabelsVisible(false);
    await Layers.setColorMode('depth');
    Layers.setDepthLimit(1, 'ft');
    await ViewerUpdates.whenIdle();
    expect(map.getLayer('gis-geometry-bound-outline')?.layout?.visibility).toBe('visible');
    expect(map.getLayer('gis-geometry-bound-fill')?.layout?.visibility).toBe('visible');


    map.setStyle();
    await map.fire('style.load');
    await sourceChanged(true);
    expect(map.getSource('project-geojson-project')?.data).toEqual(clipped);
    expect(map.getSource('gis-geometry-source-bound')?.data).toMatchObject({ type: 'Feature', geometry: bound.geojson });
    expect(map.getLayer('gis-geometry-bound-outline')?.layout?.visibility).toBe('visible');
    expect(map.getSource('project-geojson-outside')).toBeUndefined();
    expect(requests.filter(url => url === '/outside.geojson')).toHaveLength(2);
    expect(requests.filter(url => url === '/api/v2/gis-ogc/view/shared/geojson')).toHaveLength(1);
    expect(Config.projects.map(item => item.id)).toEqual(['project']);
});

it.each([false, true])('displays and frames the boundary with no visible surveys (outside project: %s)', async includeOutside => {
    const polygon = { type: 'Polygon', coordinates: [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]] };
    responses.set('/api/v2/gis-ogc/view/shared/geojson', { json: {
        projects: includeOutside ? [project] : [], view_name: 'Empty bound',
        geographic_bound: { id: 'bound', revision: 1, geojson: polygon },
    } });
    responses.set('/survey.geojson', { json: survey });
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    expect(Config.projects).toEqual([]);
    expect(State.projectBounds.size).toBe(0);
    expect(State.projectDepthDomains.size).toBe(0);
    expect(State.gisGeometryStates.get('bound')).toBe(true);
    expect(map.getSource('gis-geometry-source-bound')?.data).toMatchObject({ type: 'Feature', geometry: polygon });
    expect(map.getLayer('gis-geometry-bound-outline')?.layout?.visibility).toBe('visible');
    expect(map.fits[0]?.bounds).toMatchObject({ points: [[0, 0], [0.01, 0.01]] });
});

it('reports one visible error without rendering full surveys when the public geographic bound is invalid', async () => {
    responses.set('/api/v2/gis-ogc/view/shared/geojson', { json: {
        projects: [project, { ...project, id: 'second' }], view_name: 'Invalid bound',
        geographic_bound: { id: 'bound', revision: 1, geojson: { type: 'LineString', coordinates: [[0, 0], [0.01, 0.01]] } },
    } });
    responses.set('/survey.geojson', { json: survey });
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    expect(requests).toContain('/survey.geojson');
    expect(map.getSource('project-geojson-project')).toBeUndefined();
    expect(Config.projects).toEqual([]);
    expect(State.projectDepthDomains.size).toBe(0);
    expect(State.projectBounds.size).toBe(0);
    expect(document.body.textContent?.split('Some survey data could not be displayed within the geographic bound.')).toHaveLength(2);
});

it('ignores stale public metadata after a newer style reload has completed', async () => {
    let releaseMetadata!: (reply: ApiTestReply) => void;
    const delayedMetadata = new Promise<ApiTestReply>(resolve => { releaseMetadata = resolve; });
    let metadataRequests = 0;
    const bound = { id: 'bound', revision: 2, geojson: {
        type: 'Polygon', coordinates: [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]],
    } };
    server.handle(request => {
        requests.push(request.path);
        if (request.path === '/api/v2/gis-ogc/view/shared/geojson') {
            metadataRequests += 1;
            if (metadataRequests === 1) return delayedMetadata;
            return { json: { projects: [], view_name: 'Current', geographic_bound: bound } };
        }
        return { json: survey };
    });
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    await map.fire('style.load');
    const initialLoad = map.fire('load');
    try {
        await vi.waitFor(() => expect(metadataRequests).toBe(1));
        map.setStyle();
        await map.fire('style.load');
        await sourceChanged(true);
        expect(metadataRequests).toBe(2);
        expect(Config.projects).toEqual([]);
    } finally {
        releaseMetadata({ json: { projects: [project], view_name: 'Stale', geographic_bound: null } });
        await initialLoad;
    }
    expect(Config.projects).toEqual([]);
    expect(map.getSource('project-geojson-project')).toBeUndefined();
    expect(requests).not.toContain('/survey.geojson');
    expect(document.getElementById('project-list')?.textContent).not.toContain('Survey');
    expect(document.getElementById('loading-overlay')?.classList.contains('pointer-events-none')).toBe(true);
});

it('does not let a stale unbounded source overwrite a newer style reload', async () => {
    let releaseSurvey!: (reply: ApiTestReply) => void;
    const delayedSurvey = new Promise<ApiTestReply>(resolve => { releaseSurvey = resolve; });
    let surveyRequests = 0;
    server.handle(request => {
        requests.push(request.path);
        if (request.path === '/api/v2/gis-ogc/view/shared/geojson') {
            return { json: { projects: [project], view_name: 'Public', geographic_bound: null } };
        }
        if (request.path === '/survey.geojson' && ++surveyRequests === 1) return delayedSurvey;
        return { json: survey };
    });
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    await map.fire('style.load');
    const initialLoad = map.fire('load');
    try {
        await vi.waitFor(() => expect(surveyRequests).toBe(1));
        map.setStyle();
        await map.fire('style.load');
        await sourceChanged(true);
        expect(surveyRequests).toBe(2);
        expect(map.getSource('project-geojson-project')?.data).toMatchObject(survey);
    } finally {
        releaseSurvey({ json: { type: 'FeatureCollection', features: [
            { type: 'Feature', properties: { depth: 999 }, geometry: { type: 'LineString', coordinates: [[1, 1], [2, 2]] } },
        ] } });
        await initialLoad;
    }
    expect(map.getSource('project-geojson-project')?.data).toMatchObject(survey);
    expect(State.projectDepthDomains.get('project')).toEqual({ min: 0, max: 12 });
});

it('rejects invalid public configuration through the real notification UI', async () => {
    configureRuntimeContext({ viewMode: 'private', gisToken: 'shared' });
    await initPublicGISViewer();
    expect(State.map).toBeNull();
    expect(requests).toEqual([]);
    expect(document.body.textContent).toContain('Invalid GIS View configuration');
});

it('uses precise public zoom and preserves project colors without country grouping', async () => {
    responses.set('/api/v2/gis-ogc/view/shared/geojson', { json: { projects: [project], view_name: 'Public' } });
    responses.set('/survey.geojson', { json: survey });
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared', mapboxToken: '', allowPreciseZoom: true });
    await initPublicGISViewer();
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    expect(map.maxZoom).toBe(22);
    expect(map.fits[0]!.options).toMatchObject({ maxZoom: 16 });
    expect(Config.projects[0]).toMatchObject({ color: '#22c55e', permissions: 'READ_ONLY' });
    expect(Config.projects[0]).not.toHaveProperty('country');
});

it.each(['depth', 'shot'])('keeps saved private %s preferences unchanged during public use', async colorMode => {
    const key = DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES;
    const saved = JSON.stringify({
        version: DEFAULTS.DISPLAY.STORAGE_VERSION,
        colorMode, depthLimitFeet: 125.75, depthUnit: 'm',
        categories: { caveEntrances: false, landmarks: false },
    });
    localStorage.setItem(key, saved);
    configureRuntimeContext({ viewMode: 'public', gisToken: 'shared' });
    await initPublicGISViewer();
    expect(State.displayPreferences).toMatchObject({
        colorMode: 'project', depthLimitFeet: null, depthUnit: 'ft',
        categories: { caveEntrances: true, landmarks: true },
    });
    window.dispatchEvent(new CustomEvent('speleo:display-preferences-changed', {
        detail: { preferences: State.displayPreferences },
    }));
    expect(localStorage.getItem(key)).toBe(saved);
});

it.each([
    { mode: 'private', width: 1024, fullscreen: false, height: '830px' },
    { mode: 'private', width: 640, fullscreen: false, height: '850px' },
    { mode: 'private', width: 1024, fullscreen: true, height: '850px' },
    { mode: 'public', width: 1024, fullscreen: true, height: '830px' },
    { mode: 'public', width: 640, fullscreen: false, height: '850px' },
] as const)('sizes the real $mode viewer for width $width and fullscreen=$fullscreen', async ({ mode, width, fullscreen, height }) => {
    const element = document.getElementById('map')!;
    // jsdom does not calculate layout or implement native fullscreen state.
    // Supply only those browser values; the viewer's height policy remains real.
    vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 50, 800, 400));
    Object.defineProperty(document, 'fullscreenElement', { configurable: true, value: fullscreen ? document.getElementById('map-viewer-shell') : null });
    vi.stubGlobal('innerWidth', width);
    vi.stubGlobal('innerHeight', 900);
    configureRuntimeContext(mode === 'public'
        ? { viewMode: 'public', gisToken: 'shared' }
        : { icons: {} });
    await (mode === 'public' ? initPublicGISViewer() : initPrivateMapViewer());
    expect(element.style.height).toBe(height);
});

it('keeps the historical map and its bottom controls within a tablet viewport as it resizes', async () => {
    const element = document.getElementById('map')!;
    // JSDOM has no layout or native viewport size; preserve the actual viewer
    // height policy while supplying the measured tablet map position.
    vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 221, 852, 600));
    vi.stubGlobal('innerWidth', 900);
    vi.stubGlobal('innerHeight', 800);
    await initProjectRevisionMap(revisionContext(project.geojson_file));
    expect(element.style.height).toBe('579px');
    expect(221 + Number.parseFloat(element.style.height)).toBeLessThanOrEqual(window.innerHeight);
    vi.stubGlobal('innerHeight', 700);
    window.dispatchEvent(new Event('resize'));
    expect(element.style.height).toBe('479px');
});

it('opens the actual geometry editor from the private top bar after map readiness', async () => {
    document.body.insertAdjacentHTML('beforeend', '<button id="create-geometry-btn">Create Geometry</button>');
    configureRuntimeContext({ icons: {} });
    await initPrivateMapViewer();
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    GISGeometriesPanel.setExpanded(true);
    expect(document.getElementById('gis-geometries-panel-minimized')!.getAttribute('aria-expanded')).toBe('true');
    document.getElementById('create-geometry-btn')!.click();
    await vi.waitFor(() => {
        expect(document.querySelector('[data-geometry-editor]')).not.toBeNull();
        expect(GeometryEditor.isActive()).toBe(true);
        expect(document.getElementById('gis-geometries-panel-minimized')!.getAttribute('aria-expanded')).toBe('false');
    });
});


it('restores the initial camera once after globe style loading and preserves later navigation', async () => {
    MapCore.init('');
    expect(map.creationOptions).toMatchObject({ container: 'map', style: null, attributionControl: false });
    expect(map.cameraJumps).toEqual([]);
    await map.fire('style.load');
    expect(map.cameraJumps).toEqual([{ center: DEFAULTS.MAP.CENTER, zoom: DEFAULTS.MAP.INITIAL_ZOOM }]);
    map.jumpTo({ center: [-87, 20], zoom: 12 });
    await map.fire('style.load');
    expect(map.cameraJumps).toHaveLength(2);
    expect(map.cameraJumps.at(-1)).toEqual({ center: [-87, 20], zoom: 12 });
});

it('passes the complete private toolbar and overlay shell to native fullscreen control', () => {
    const shell = document.getElementById('map-viewer-shell')!;
    MapCore.init('', 'map', { fullscreenContainer: shell });
    expect(fullscreenContainers).toEqual([shell]);
});

it('resizes through real timers and stops resize and pending display work on removal', async () => {
    MapCore.init('');
    expect(map.resizeCount).toBe(0);
    await vi.waitFor(() => expect(map.resizeCount).toBe(1));
    window.dispatchEvent(new Event('resize'));
    expect(map.resizeCount).toBe(2);
    const pending = Layers.setCategoryVisibility('caveEntrances', false);
    await map.fire('remove');
    expect(await pending).toEqual({ status: 'cancelled' });
    expect(State.map).toBeNull();
    window.dispatchEvent(new Event('resize'));
    await new Promise(resolve => setTimeout(resolve, DEFAULTS.MAP.RESIZE_DELAY_MS));
    expect(map.resizeCount).toBe(2);
    await map.fire('remove');
    expect(State.map).toBeNull();
});


function revisionContext(geojsonUrl: string, overrides: Partial<ProjectRevisionMapContext> = {}): ProjectRevisionMapContext {
    const selectedRevision: ProjectMapRevision = {
        commitSha: 'a'.repeat(40), artifactRevision: 'stored-artifact', url: `${server.origin}/revision/${'a'.repeat(40)}/`,
        geojsonUrl, dateLabel: 'Oct 21, 2026', displayDateLabel: 'Oct 21, 2026 at 00:35', timestampLabel: 'Oct 21, 2026 at 00:35',
        message: 'Initial survey', authorName: 'Diver', available: true,
    };
    return { mapboxToken: '', project: { ...project, geojson_file: geojsonUrl }, commitSha: selectedRevision.commitSha,
        artifactRevision: selectedRevision.artifactRevision!, selectedRevision, revisions: [selectedRevision], ...overrides };
}

function displayedSurveyData() {
    const sourceId = (State.allProjectLayers.get('project') ?? []).map(id => map.getLayer(id)?.source).find(Boolean);
    return sourceId ? map.getSource(sourceId)?.data : undefined;
}
it('loads only the historical artifact and retains it after replacing the basemap', async () => {
    responses.set('/old-survey.geojson', { json: survey });
    const historicalContext = revisionContext(`${server.origin}/old-survey.geojson`);
    await initProjectRevisionMap(historicalContext);
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    expect(displayedSurveyData()).toMatchObject(survey);
    expect(requests).toEqual(['/old-survey.geojson']);
    expect(map.handlers.has('contextmenu')).toBe(false);
    expect(document.querySelector('.measurement-control')).toBeNull();
    map.setStyle();
    await map.fire('style.load');
    await sourceChanged(true);
    expect(displayedSurveyData()).toMatchObject(survey);
    expect(requests).toEqual(['/old-survey.geojson', '/old-survey.geojson']);
});


it('reports a historical download failure without fetching current survey data', async () => {
    responses.set('/missing-survey.geojson', { status: 404, json: { detail: 'Missing' } });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'Historical', projects: [{ ...project, geojson_file: `${server.origin}/missing-survey.geojson` }] }), { showProjectPanel: false });
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    expect(requests).toEqual(['/missing-survey.geojson']);
    expect(map.getSource('project-geojson-project')).toBeUndefined();
    expect(await viewer.ready).toBe(false);
    expect(document.querySelector('#loading-overlay')?.classList.contains('pointer-events-none')).toBe(true);
});


it('keeps the historical toolbar in fullscreen without an Active Projects panel', async () => {
    const shell = document.getElementById('map-viewer-shell')!;
    responses.set('/survey.geojson', { json: survey });
    await initReadOnlyViewer({}, async () => ({ view_name: 'Historical', projects: [project] }), {
        showProjectPanel: false,
        fullscreenContainer: shell,
    });
    await map.fire('style.load');
    await map.fire('load');
    await ViewerUpdates.whenIdle();
    expect(fullscreenContainers).toEqual([shell]);
    expect(document.getElementById('project-panel')).toBeNull();
    expect(document.body.textContent).not.toContain('Active Projects');
});

it('leaves a usable camera viewport when history and playback overlap on a short screen', async () => {
    const shell = document.getElementById('map-viewer-shell')!;
    const panel = document.createElement('details');
    panel.className = 'historical-revisions';
    panel.open = true;
    const dock = document.createElement('div');
    dock.id = 'revision-timeline';
    shell.append(panel, dock);
    // JSDOM does not calculate overlay rectangles; supply only this native layout boundary.
    for (const [element, rect] of [
        [document.getElementById('map')!, new DOMRect(0, 0, 320, 200)],
        [panel, new DOMRect(12, 12, 230, 88)],
        [dock, new DOMRect(8, 94, 304, 106)],
    ] as const) {
        vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(rect);
        vi.spyOn(element, 'getClientRects').mockReturnValue(Object.assign([rect], { item: (index: number) => index === 0 ? rect : null }));
    }
    responses.set('/survey.geojson', { json: survey });
    await initProjectRevisionMap(revisionContext(project.geojson_file));
    panel.open = true;
    await map.fire('style.load');
    await map.fire('load');
    expect(map.fits).toHaveLength(1);
    const options = map.fits[0]!.options as { padding: number | { top: number; bottom: number; left: number; right: number } };
    const padding = typeof options.padding === 'number'
        ? { top: options.padding, bottom: options.padding, left: options.padding, right: options.padding }
        : options.padding;
    expect(padding.top + padding.bottom).toBeLessThan(200);
    expect(padding.left + padding.right).toBeLessThan(320);
});

it('changes historical artifacts in the same map and preserves the previous survey after a missing artifact', async () => {
    const otherSurvey = { ...survey, features: [{ ...survey.features[0], geometry: { type: 'LineString', coordinates: [[10, 20], [11, 21]] } }] };
    responses.set('/survey.geojson', { json: survey });
    responses.set('/other.geojson', { json: otherSurvey });
    responses.set('/missing.geojson', { status: 404 });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'Historical', projects: [project] }), { showProjectPanel: false });
    await map.fire('style.load');
    await map.fire('load');
    const originalMap = map;
    await Layers.setColorMode('depth');
    expect(await viewer.showProject({ ...project, geojson_file: `${server.origin}/other.geojson` })).toBe(true);
    expect(State.map).toBe(originalMap);
    expect(State.displayPreferences.colorMode).toBe('depth');
    expect(displayedSurveyData()).toMatchObject(otherSurvey);
    expect(map.fits).toHaveLength(2);
    expect(map.fits[1]!.bounds).toMatchObject({ points: [[10, 20], [11, 21]] });
    expect(await viewer.showProject({ ...project, geojson_file: `${server.origin}/missing.geojson` })).toBe(false);
    expect(displayedSurveyData()).toMatchObject(otherSurvey);
    expect(map.fits).toHaveLength(2);
});

it('keeps the latest historical selection through a style change and ignores a delayed older response', async () => {
    const latestSurvey = { ...survey, features: [{ ...survey.features[0], geometry: { type: 'LineString', coordinates: [[30, 40], [31, 41]] } }] };
    let releaseOlder!: (reply: ApiTestReply) => void;
    const olderResponse = new Promise<ApiTestReply>(resolve => { releaseOlder = resolve; });
    server.handle(request => {
        requests.push(request.path);
        if (request.path === '/older.geojson') return olderResponse;
        return { json: request.path === '/latest.geojson' ? latestSurvey : survey };
    });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    await map.fire('style.load');
    await map.fire('load');
    const older = viewer.showProject({ ...project, geojson_file: `${server.origin}/older.geojson` });
    await vi.waitFor(() => expect(requests).toContain('/older.geojson'));
    const latest = viewer.showProject({ ...project, geojson_file: `${server.origin}/latest.geojson` });
    map.setStyle();
    await map.fire('style.load');
    await sourceChanged(true);
    expect(await latest).toBe(true);
    expect(await older).toBe(false);
    releaseOlder({ json: survey });
    await vi.waitFor(() => expect(displayedSurveyData()).toMatchObject(latestSurvey));
    await ViewerUpdates.whenIdle();
    expect(map.fits).toHaveLength(2);
    expect(Config.projects[0]?.geojson_url).toBe(`${server.origin}/latest.geojson`);
});

it('accepts a historical selection before the initial map load', async () => {
    responses.set('/early.geojson', { json: survey });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    const selected = viewer.showProject({ ...project, geojson_file: `${server.origin}/early.geojson` });
    await map.fire('style.load');
    await map.fire('load');
    expect(await selected).toBe(true);
    expect(requests).toEqual(['/early.geojson']);
    expect(displayedSurveyData()).toMatchObject(survey);
});

it('does not reuse old bounds when switching to an empty historical artifact', async () => {
    responses.set('/survey.geojson', { json: survey });
    responses.set('/empty.geojson', { json: emptyGeoJSON });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    await map.fire('style.load');
    await map.fire('load');
    expect(await viewer.showProject({ ...project, geojson_file: `${server.origin}/empty.geojson` })).toBe(true);
    expect(displayedSurveyData()).toMatchObject(emptyGeoJSON);
    expect(State.projectBounds.has('project')).toBe(false);
    expect(map.fits).toHaveLength(1);
});

it('keeps disabled cave entrances hidden in every rendered historical replacement frame', async () => {
    const entrances = { ...survey, features: [...survey.features, {
        type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [-87, 20] },
    }] };
    responses.set('/survey.geojson', { json: entrances });
    responses.set('/next.geojson', { json: entrances });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    await map.fire('style.load');
    await map.fire('load');
    await Layers.setCategoryVisibility('caveEntrances', false);
    map.renderedLayers = [];
    expect(await viewer.showProject({ ...project, geojson_file: `${server.origin}/next.geojson` })).toBe(true);
    expect(map.renderedLayers.length).toBeGreaterThan(0);
    expect(map.renderedLayers.flat().filter(id => id.startsWith('project-points-'))).toEqual([]);
});

it('selects revisions after a cached page return and restores an uppercase initial SHA through Back', async () => {
    const nextSurvey = { ...survey, features: [{ ...survey.features[0], geometry: { type: 'LineString', coordinates: [[4, 5], [6, 7]] } }] };
    responses.set('/survey.geojson', { json: survey });
    responses.set('/next.geojson', { json: nextSurvey });
    const list = document.createElement('nav');
    list.className = 'historical-revision-list';
    const first = document.createElement('a');
    first.className = 'historical-revision is-selected';
    first.href = `${server.origin}/revision/${'a'.repeat(40)}/`;
    first.dataset.geojsonUrl = `${server.origin}/survey.geojson`;
    first.dataset.commitSha = 'a'.repeat(40);
    first.setAttribute('aria-current', 'page');
    const next = document.createElement('a');
    next.className = 'historical-revision';
    next.href = `${server.origin}/revision/next/`;
    next.dataset.geojsonUrl = `${server.origin}/next.geojson`;
    next.dataset.commitSha = 'b'.repeat(40);
    for (const [className, text] of [
        ['historical-revision-date', 'Oct 21, 2026 at 00:35'],
        ['historical-revision-message', 'initial'],
        ['historical-revision-author', 'by John Doe'],
    ]) {
        const metadata = document.createElement('span');
        metadata.className = className!;
        metadata.textContent = text!;
        next.append(metadata);
    }
    // JSDOM has no scrolling layout; browser checks cover native scrolling.
    first.scrollIntoView = () => {};
    next.scrollIntoView = () => {};
    list.append(first, next);
    document.getElementById('map-viewer-shell')!.append(list);
    history.replaceState(null, '', `${server.origin}/revision/${'A'.repeat(40)}/`);
    const context = revisionContext(project.geojson_file);
    context.revisions = [{ ...context.selectedRevision, commitSha: next.dataset.commitSha, url: next.href, geojsonUrl: next.dataset.geojsonUrl, message: 'Next survey' }, context.selectedRevision];
    await initProjectRevisionMap(context);
    await map.fire('style.load');
    await map.fire('load');
    const originalMap = map;
    await Layers.setColorMode('shot');
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    const click = new MouseEvent('click', { bubbles: true, cancelable: true });
    next.dispatchEvent(click);
    expect(click.defaultPrevented).toBe(true);
    await vi.waitFor(() => expect(next.getAttribute('aria-current')).toBe('page'));
    expect(first.hasAttribute('aria-current')).toBe(false);
    expect(next.textContent).not.toContain('Viewing');
    expect(displayedSurveyData()).toMatchObject(nextSurvey);
    expect(State.map).toBe(originalMap);
    expect(State.displayPreferences.colorMode).toBe('shot');
    expect(location.pathname).toBe('/revision/next/');
    // Metadata publishes on the accepted frame; camera movement follows the
    // asynchronous display update, so observe that separate completion.
    await vi.waitFor(() => expect(map.fits).toHaveLength(2));
    expect(map.fits[1]!.bounds).toMatchObject({ points: [[4, 5], [6, 7]] });
    history.back();
    await vi.waitFor(() => expect(first.getAttribute('aria-current')).toBe('page'));
    expect(displayedSurveyData()).toMatchObject(survey);
    expect(State.map).toBe(originalMap);
    expect(State.displayPreferences.colorMode).toBe('shot');
    expect(location.pathname).toBe(`/revision/${'A'.repeat(40)}/`);
    await vi.waitFor(() => expect(map.fits).toHaveLength(3));
    expect(map.fits[2]!.bounds).toEqual(map.fits[0]!.bounds);
});


it('restores the initial artifact when an early selection fails before any map was loaded', async () => {
    responses.set('/survey.geojson', { json: survey });
    responses.set('/missing.geojson', { status: 404 });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    const selection = viewer.showProject({ ...project, geojson_file: `${server.origin}/missing.geojson` });
    await map.fire('style.load');
    await map.fire('load');
    expect(await selection).toBe(false);
    expect(displayedSurveyData()).toMatchObject(survey);
});

it.each([false, true])('finishes initial readiness after canceling a superseding selection (initial frame accepted: %s)', async initialDisplayed => {
    let releaseInitial!: (reply: ApiTestReply) => void;
    let releaseSelection!: (reply: ApiTestReply) => void;
    const initialResponse = new Promise<ApiTestReply>(resolve => { releaseInitial = resolve; });
    const selectionResponse = new Promise<ApiTestReply>(resolve => { releaseSelection = resolve; });
    server.handle(request => {
        requests.push(request.path);
        return request.path === '/next.geojson' ? selectionResponse : initialResponse;
    });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    map.cameraDurationMs = 250;
    let ready: boolean | undefined;
    void viewer.ready.then(value => { ready = value; });
    await map.fire('style.load');
    const initialLoad = map.fire('load');
    await vi.waitFor(() => expect(requests).toContain('/survey.geojson'));
    if (initialDisplayed) {
        releaseInitial({ json: survey });
        await vi.waitFor(() => expect(map.fits).toHaveLength(1));
        expect(ready).toBeUndefined();
    }
    const controller = new AbortController();
    const selection = viewer.showProject({ ...project, geojson_file: `${server.origin}/next.geojson` }, { signal: controller.signal });
    await vi.waitFor(() => expect(requests).toContain('/next.geojson'));
    controller.abort();
    releaseInitial({ json: survey });
    releaseSelection({ json: emptyGeoJSON });
    expect(await selection).toBe(false);
    await initialLoad;
    await vi.waitFor(() => expect(ready).toBe(true));
    expect(displayedSurveyData()).toMatchObject(survey);
    expect(Config.projects[0]?.geojson_url).toBe(project.geojson_file);
});

it('clears the initial overlay when a cancellation preserves the first accepted frame', async () => {
    responses.set('/survey.geojson', { json: survey });
    responses.set('/next.geojson', { json: emptyGeoJSON });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    const controller = new AbortController();
    let selection: Promise<boolean> | undefined;
    map.on('render', async () => {
        // Let the native frame publish its geometry before interrupting the
        // remaining scheduled display update, without advancing a clock.
        await Promise.resolve();
        if (!selection && State.allProjectLayers.has('project')) {
            selection = viewer.showProject({ ...project, geojson_file: `${server.origin}/next.geojson` }, { signal: controller.signal });
            controller.abort();
        }
    });
    await map.fire('style.load');
    await map.fire('load');
    expect(await selection).toBe(false);
    expect(await viewer.ready).toBe(true);
    expect(displayedSurveyData()).toMatchObject(survey);
    expect(document.getElementById('loading-overlay')?.classList.contains('pointer-events-none')).toBe(true);
});

it('settles a queued historical selection when its map is removed before readiness', async () => {
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    let outcome: boolean | undefined;
    const selection = viewer.showProject(project).then(value => { outcome = value; });
    await map.fire('remove');
    await vi.waitFor(() => expect(outcome).toBe(false));
    await selection;
    expect(requests).toEqual([]);
});


it('keeps the displayed historical geometry when pause cancels a prepared replacement before rendering', async () => {
    responses.set('/survey.geojson', { json: survey });
    const nextSurvey = { ...survey, features: [{ ...survey.features[0], geometry: { type: 'LineString', coordinates: [[10, 20], [11, 21]] } }] };
    responses.set('/next.geojson', { json: nextSurvey });
    const viewer = await initReadOnlyViewer({}, async () => ({ view_name: 'History', projects: [project] }), { showProjectPanel: false });
    await map.fire('style.load');
    await map.fire('load');
    map.renderingBlocked = true;
    const abort = new AbortController();
    let displayed = false;
    const selecting = viewer.showProject({ ...project, geojson_file: `${server.origin}/next.geojson` }, {
        signal: abort.signal, camera: 'preserve', onDisplayed() { displayed = true; },
    });
    await vi.waitFor(() => expect([...map.sources.values()].some(source => JSON.stringify(source.data).includes('[[10,20],[11,21]]'))).toBe(true));
    expect(displayedSurveyData()).toMatchObject(survey);
    expect(displayed).toBe(false);
    abort.abort();
    expect(await selecting).toBe(false);
    map.renderingBlocked = false;
    await map.fire('render');
    expect(map.sources.size).toBe(1);
    expect(displayedSurveyData()).toMatchObject(survey);
    expect(displayed).toBe(false);
    expect(map.fits).toHaveLength(1);
});
