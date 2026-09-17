import { MeasurementTool } from './tool.js';
import { Config, DEFAULTS } from '../config.js';
import { Interactions } from '../map/interactions.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';
import { Geometry } from '../map/geometry.js';

// Only the browser/map boundary is simulated. Tool, dispatcher, geometry and
// renderer are the actual modules, including their DOM and GeoJSON output.
function createMap() {
    document.body.innerHTML = '<main class="map-viewer-shell"><div id="map"><canvas tabindex="0"></canvas></div></main>';
    const host = document.getElementById('map');
    const canvas = host.querySelector('canvas');
    Object.defineProperties(canvas, { clientWidth: { value: 800 }, clientHeight: { value: 600 } });
    host.getBoundingClientRect = () => ({ top: 0, left: 0, right: 800, bottom: 600, width: 800, height: 600 });
    canvas.getBoundingClientRect = () => host.getBoundingClientRect();
    const events = new Map();
    const sources = new Map();
    const layers = new Map();
    const images = new Map();
    let doubleClick = true;
    let pan = true;
    const map = {
        on(name, handler) { if (!events.has(name)) events.set(name, new Set()); events.get(name).add(handler); },
        off(name, handler) { events.get(name)?.delete(handler); },
        fire(name, event) { for (const handler of events.get(name) || []) handler(event); },
        listenerCount: () => [...events.values()].reduce((count, handlers) => count + handlers.size, 0),
        getCanvas: () => canvas,
        getContainer: () => host,
        getStyle: () => ({ layers: [...layers.values()] }),
        unproject: point => ({ lng: point.x / 10, lat: point.y / 10 }),
        project: coordinate => ({ x: (coordinate.lng ?? coordinate[0]) * 10, y: (coordinate.lat ?? coordinate[1]) * 10 }),
        isPointOnSurface: point => point.y >= 0,
        getSource: id => sources.get(id),
        addSource(id, source) { sources.set(id, { ...source, _data: source.data, setData: vi.fn(function (data) { this.data = data; this._data = data; }) }); },
        removeSource: id => sources.delete(id),
        getLayer: id => layers.get(id),
        addLayer: layer => layers.set(layer.id, layer),
        setLayoutProperty: vi.fn(),
        setFilter: vi.fn(),
        removeLayer: id => layers.delete(id),
        hasImage: id => images.has(id),
        addImage: (id, image) => images.set(id, image),
        removeImage: id => images.delete(id),
        queryRenderedFeatures: vi.fn(() => []),
        dragPan: { disable: vi.fn(() => { pan = false; }), enable: vi.fn(() => { pan = true; }), isEnabled: () => pan },
        doubleClickZoom: { isEnabled: () => doubleClick, disable: () => { doubleClick = false; }, enable: () => { doubleClick = true; } },
    };
    return map;
}

const event = (x, y, extra = {}) => ({
    point: { x, y }, lngLat: { lng: x / 10, lat: y / 10, toArray: () => [x / 10, y / 10] },
    originalEvent: { button: 0, detail: 1 }, preventDefault: vi.fn(), ...extra,
});
let map;
let tool;
let frames;
let originalProjects;
const flushFrames = () => {
    const callbacks = [...frames.values()];
    frames.clear();
    callbacks.forEach(callback => callback());
};
const click = (x, y) => {
    map.fire('mousedown', event(x, y));
    map.fire('mouseup', event(x, y));
    map.fire('click', event(x, y));
};
const source = kind => map.getSource(`${DEFAULTS.MEASUREMENT.LAYER_PREFIX}${kind}`);

beforeEach(() => {
    originalProjects = Config._projects;
    frames = new Map();
    let frame = 0;
    vi.stubGlobal('requestAnimationFrame', callback => { frames.set(++frame, callback); return frame; });
    vi.stubGlobal('cancelAnimationFrame', id => frames.delete(id));
    // Mapbox's DOM Marker boundary: the actual renderer owns the live capsule.
    vi.stubGlobal('mapboxgl', { Marker: class {
        constructor({ element }) { this.element = element; }
        setLngLat(coordinate) { this.coordinate = coordinate; return this; }
        addTo(map) { map.getContainer().append(this.element); return this; }
        remove() { this.element.remove(); return this; }
    } });
    map = createMap();
    tool = new MeasurementTool();
    map.getContainer().append(tool.onAdd(map));
    Interactions.init(map, { measurementTool: tool });
});

afterEach(() => {
    tool.destroy();
    State.map = null;
    State.allLandmarks.clear();
    State.explorationLeads.clear();
    Config._projects = originalProjects;
    Geometry.snapIndicatorEl?.remove();
    Geometry.snapIndicatorEl = null;
    document.body.replaceChildren();
    vi.unstubAllGlobals();
});

it('measures independent pairs, cancels only the draft, and clears all on toggling off', () => {
    tool.button.dispatchEvent(new MouseEvent('click', { detail: 1 }));
    expect(tool.button.getAttribute('aria-pressed')).toBe('true');
    expect(tool.gestures.textContent).toContain('Left-clickStart / stop');
    click(0, 0);
    flushFrames();
    expect(source('draft').data.features).toHaveLength(1);
    expect(tool.gestures.textContent).toContain('Right-click / EscCancel measurement');
    map.fire('mousemove', event(1, 1));
    flushFrames();
    expect(document.querySelector('.measurement-live-label').textContent).toMatch(/km.*mi/);
    expect(document.querySelector('.measurement-live-label').getAttribute('aria-hidden')).toBe('true');
    click(1, 1);
    click(10, 10);
    click(11, 11);
    expect(tool.measurements).toHaveLength(2);
    expect(tool.results.children).toHaveLength(2);
    expect(tool.results.textContent).toMatch(/km.*mi/);
    click(20, 20);
    const context = event(20, 20);
    map.fire('contextmenu', context);
    expect(context.preventDefault).toHaveBeenCalled();
    expect(tool.start).toBeNull();
    expect(tool.measurements).toHaveLength(2);
    expect(tool.isActive()).toBe(true);
    tool.button.click();
    expect(tool.measurements).toEqual([]);
    expect(tool.results.children).toHaveLength(0);
    expect(tool.instructions.hidden).toBe(true);
    expect(tool.button.getAttribute('aria-pressed')).toBe('false');
    expect(source('completed')).toBeUndefined();
    flushFrames();
    expect(source('draft')).toBeUndefined();
});

it('owns the real dispatcher without querying or dragging entities, then restores normal feature clicks', () => {
    const onStationClick = vi.fn();
    Interactions.handlers.onStationClick = onStationClick;
    map.queryRenderedFeatures.mockReturnValue([{ id: 'station', layer: { id: 'stations-one-circles' } }]);
    tool.activate();
    click(10, 10);
    map.fire('mousemove', event(11, 11));
    click(11, 11);
    expect(map.queryRenderedFeatures).not.toHaveBeenCalled();
    expect(onStationClick).not.toHaveBeenCalled();
    expect(map.dragPan.disable).not.toHaveBeenCalled();
    tool.deactivate();
    map.fire('click', event(10, 10));
    expect(onStationClick).toHaveBeenCalledWith('station', 'subsurface');
});

it.each([[false, true], [true, true], [false, false], [true, false]])(
    'cancels an entity drag before ruler ownership (moved=%s, handlers enabled=%s)', (moved, enabled) => {
        State.map = map;
        State.allLandmarks.set('landmark', { can_write: true, longitude: 1, latitude: 1 });
        const feature = { id: 'landmark', layer: { id: 'landmarks-layer' }, geometry: { type: 'Point', coordinates: [1, 1] }, properties: {} };
        map.addSource('landmarks-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [feature] } });
        map.queryRenderedFeatures.mockReturnValue([feature]);
        const preview = vi.fn((id, coordinate) => Layers.revertLandmarkPosition(id, coordinate));
        const complete = vi.fn();
        Interactions.handlers.onLandmarkDrag = preview;
        Interactions.handlers.onLandmarkDragEnd = complete;
        tool.onActivate = () => Interactions.cancelPendingDrag();
        if (!enabled) { map.dragPan.disable(); map.doubleClickZoom.disable(); }
        map.fire('mousedown', event(10, 10));
        expect(map.dragPan.isEnabled()).toBe(false);
        if (moved) {
            map.fire('mousemove', event(50, 50));
            expect(feature.geometry.coordinates).toEqual([5, 5]);
        }
        tool.activate({ keyboard: true });
        expect(feature.geometry.coordinates).toEqual([1, 1]);
        expect(State.allLandmarks.get('landmark')).toMatchObject({ longitude: 1, latitude: 1 });
        expect(map.dragPan.isEnabled()).toBe(enabled);
        expect(map.doubleClickZoom.isEnabled()).toBe(false);
        map.fire('mouseup', event(50, 50));
        tool.deactivate();
        expect(map.doubleClickZoom.isEnabled()).toBe(enabled);
        preview.mockClear();
        map.fire('mousemove', event(70, 70));
        map.fire('mouseup', event(70, 70));
        expect(preview).not.toHaveBeenCalled();
        expect(complete).not.toHaveBeenCalled();
        expect(feature.geometry.coordinates).toEqual([1, 1]);
    },
);

it.each([true, false])('completes a normal landmark drag and restores camera handlers (enabled=%s)', enabled => {
    State.map = map;
    State.allLandmarks.set('landmark', { can_write: true, longitude: 1, latitude: 1 });
    const feature = { id: 'landmark', layer: { id: 'landmarks-layer' }, geometry: { type: 'Point', coordinates: [1, 1] }, properties: {} };
    map.addSource('landmarks-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [feature] } });
    map.queryRenderedFeatures.mockReturnValue([feature]);
    const preview = vi.fn((id, coordinate) => Layers.revertLandmarkPosition(id, coordinate));
    const complete = vi.fn();
    Interactions.handlers.onLandmarkDrag = preview;
    Interactions.handlers.onLandmarkDragEnd = complete;
    map.getCanvas().style.cursor = 'grab';
    if (!enabled) { map.dragPan.disable(); map.doubleClickZoom.disable(); }
    map.fire('mousedown', event(10, 10));
    map.fire('mousemove', event(50, 50));
    expect(feature.geometry.coordinates).toEqual([5, 5]);
    map.fire('mouseup', event(50, 50));
    expect(complete).toHaveBeenCalledExactlyOnceWith('landmark', [5, 5], [1, 1]);
    expect(map.dragPan.isEnabled()).toBe(enabled);
    expect(map.doubleClickZoom.isEnabled()).toBe(enabled);
    expect(map.getCanvas().style.cursor).toBe('grab');
    preview.mockClear();
    map.fire('mousemove', event(70, 70));
    map.fire('mouseup', event(70, 70));
    expect(preview).not.toHaveBeenCalled();
    expect(complete).toHaveBeenCalledTimes(1);
    expect(feature.geometry.coordinates).toEqual([5, 5]);
});

it.each(['station', 'cylinder-install', 'exploration-lead'])('rolls back %s coordinates and feedback without completing its drag', kind => {
    State.map = map;
    const projectId = '00000000-0000-0000-0000-000000000001';
    Config._projects = [{ id: projectId, permissions: 'READ_AND_WRITE' }];
    const sourceId = kind === 'station' ? `stations-source-${projectId}`
        : kind === 'cylinder-install' ? 'cylinder-installs-source' : 'exploration-leads-source';
    const layerId = kind === 'station' ? `stations-${projectId}-circles`
        : kind === 'cylinder-install' ? 'cylinder-installs-layer' : 'exploration-leads-layer';
    const originalColor = '#123456';
    const feature = { id: 'entity', layer: { id: layerId }, geometry: { type: 'Point', coordinates: [1, 1] }, properties: { project_id: projectId, color: originalColor } };
    map.addSource(sourceId, { type: 'geojson', data: { type: 'FeatureCollection', features: [feature] } });
    map.addLayer({ id: layerId });
    if (kind === 'exploration-lead') State.explorationLeads.set('entity', { id: 'entity', coordinates: [1, 1], projectId });
    map.queryRenderedFeatures.mockReturnValue([feature]);
    const complete = vi.fn();
    Interactions.handlers.onStationDragEnd = complete;
    Interactions.handlers.onMarkerDragEnd = complete;
    map.fire('mousedown', event(10, 10));
    map.fire('mousemove', event(50, 50));
    expect(map.getSource(sourceId)._data.features[0].geometry.coordinates).toEqual([5, 5]);
    if (kind === 'station') expect(feature.properties.color).not.toBe(originalColor);
    else expect(map.getLayer('marker-drag-highlight')).toBeDefined();
    expect(Geometry.snapIndicatorEl.style.display).toBe('block');
    Interactions.cancelPendingDrag();
    expect(map.getSource(sourceId)._data.features[0].geometry.coordinates).toEqual([1, 1]);
    if (kind === 'station') expect(feature.properties.color).toBe(originalColor);
    expect(map.getLayer('marker-drag-highlight')).toBeUndefined();
    expect(map.getSource('marker-drag-highlight-source')).toBeUndefined();
    expect(Geometry.snapIndicatorEl.style.display).toBe('none');
    map.fire('mouseup', event(50, 50));
    expect(complete).not.toHaveBeenCalled();
    expect(map.dragPan.isEnabled()).toBe(true);
    expect(map.doubleClickZoom.isEnabled()).toBe(true);
});

it('keeps endpoint placement out of pan, pinch, touchend and cancelled gestures', () => {
    tool.activate();
    map.fire('mousedown', event(1, 1));
    map.fire('mousemove', event(40, 40));
    map.fire('mouseup', event(40, 40));
    map.fire('click', event(40, 40));
    expect(tool.start).toBeNull();
    map.fire('touchstart', event(1, 1, { points: [{ x: 1, y: 1 }] }));
    map.fire('touchend', event(1, 1));
    expect(tool.start).toBeNull();
    map.fire('click', event(1, 1));
    expect(tool.start[0]).toBeCloseTo(0.1);
    expect(tool.start[1]).toBeCloseTo(0.1);
    map.fire('touchstart', event(3, 3, { points: [{ x: 3, y: 3 }, { x: 9, y: 9 }] }));
    map.fire('touchmove', event(3, 3, { points: [{ x: 3, y: 3 }] }));
    map.fire('touchend', event(3, 3));
    map.fire('click', event(3, 3));
    expect(tool.measurements).toHaveLength(0);
    map.fire('touchstart', event(4, 4, { points: [{ x: 4, y: 4 }] }));
    map.getCanvas().dispatchEvent(new Event('touchcancel'));
    map.fire('click', event(4, 4));
    expect(tool.measurements).toHaveLength(0);
    click(5, 5);
    expect(tool.measurements).toHaveLength(1);
});

it('ignores repeated double-click events and coincident endpoints', () => {
    tool.activate();
    click(1, 1);
    click(1, 1);
    expect(tool.measurements).toHaveLength(0);
    expect(tool.start).not.toBeNull();
    click(2, 2);
    map.fire('click', event(2, 2, { originalEvent: { button: 0, detail: 2 } }));
    expect(tool.start).toBeNull();
    expect(tool.measurements).toHaveLength(1);
});

it('places keyboard endpoints at the center, ignores repeats, and gives dialogs their keys', async () => {
    tool.button.click();
    expect(document.activeElement).toBe(map.getCanvas());
    expect(tool.crosshair.hidden).toBe(false);
    const key = (name, repeat = false) => map.getCanvas().dispatchEvent(new KeyboardEvent('keydown', { key: name, repeat, bubbles: true }));
    key('Enter');
    expect(tool.start).toEqual([40, 30]);
    key('Enter', true);
    expect(tool.measurements).toHaveLength(0);
    map.unproject = point => ({ lng: point.x / 10 + 1, lat: point.y / 10 });
    map.project = coordinate => ({ x: (coordinate.lng - 1) * 10, y: coordinate.lat * 10 });
    map.fire('move');
    key('Enter');
    expect(tool.measurements).toHaveLength(1);
    key('Enter');
    const dialog = document.createElement('dialog');
    dialog.open = true;
    document.body.append(dialog);
    await Promise.resolve();
    flushFrames();
    key('Escape');
    expect(tool.start).not.toBeNull();
    expect(tool.crosshair.hidden).toBe(true);
    dialog.remove();
    await Promise.resolve();
    flushFrames();
    key('Escape');
    expect(tool.start).toBeNull();
    expect(tool.measurements).toHaveLength(1);
    expect(tool.crosshair.hidden).toBe(false);
});

it('hides previews on sky, canvas leave, window blur and dialog opening while preserving A', async () => {
    tool.activate();
    click(1, 1);
    map.fire('mousemove', event(3, 3));
    flushFrames();
    expect(document.querySelector('.measurement-live-label')).not.toBeNull();
    map.getCanvas().dispatchEvent(new Event('mouseleave'));
    flushFrames();
    expect(source('draft').data.features).toHaveLength(1);
    expect(document.querySelector('.measurement-live-label')).toBeNull();
    expect(tool.start).not.toBeNull();
    map.fire('mousemove', event(3, -3));
    flushFrames();
    expect(source('draft').data.features).toHaveLength(1);
    map.fire('mousemove', event(3, 3));
    window.dispatchEvent(new Event('blur'));
    flushFrames();
    expect(source('draft').data.features).toHaveLength(1);
    map.fire('mousemove', event(3, 3));
    const dialog = document.createElement('dialog');
    dialog.open = true;
    document.body.append(dialog);
    await Promise.resolve();
    flushFrames();
    flushFrames();
    expect(source('draft').data.features).toHaveLength(1);
    click(3, 3);
    expect(tool.measurements).toHaveLength(0);
});

it('keeps completed data stable through pointer updates and restores after a style reload', () => {
    tool.activate();
    click(1, 1);
    click(2, 2);
    const completed = source('completed');
    completed.setData.mockClear();
    click(3, 3);
    map.fire('mousemove', event(5, 5));
    map.fire('mousemove', event(6, 6));
    expect(frames.size).toBe(1);
    flushFrames();
    expect(completed.setData).not.toHaveBeenCalled();
    const data = completed.data;
    for (const layer of map.getStyle().layers) map.removeLayer(layer.id);
    map.removeSource(`${DEFAULTS.MEASUREMENT.LAYER_PREFIX}completed`);
    map.removeSource(`${DEFAULTS.MEASUREMENT.LAYER_PREFIX}draft`);
    map.fire('style.load');
    expect(source('completed').data).toEqual(data);
    expect(tool.measurements).toHaveLength(1);
});

it('keeps a mouse preview under the pointer through camera changes and commits the displayed endpoint', () => {
    tool.activate();
    click(1, 1);
    map.fire('mousemove', event(20, 20));
    flushFrames();
    expect(source('draft').data.features.filter(feature => feature.properties.role === 'endpoint').at(-1).geometry.coordinates)
        .toEqual([2, 2]);
    // Camera navigation changes the coordinate under a stationary pointer.
    map.unproject = point => ({ lng: point.x / 20, lat: point.y / 20 });
    map.project = coordinate => ({ x: coordinate.lng * 20, y: coordinate.lat * 20 });
    map.fire('move');
    flushFrames();
    const previewEndpoint = source('draft').data.features.filter(feature => feature.properties.role === 'endpoint').at(-1).geometry.coordinates;
    const previewLabel = document.querySelector('.measurement-live-label').textContent;
    expect(previewEndpoint).toEqual([1, 1]);
    click(20, 20);
    expect(tool.measurements[0].end).toEqual(previewEndpoint);
    expect(tool.results.textContent).toContain(previewLabel);
});

it('does not revive a mouse preview during a pan or after the pointer leaves the canvas', () => {
    tool.activate();
    click(1, 1);
    map.fire('mousemove', event(20, 20));
    flushFrames();
    map.getCanvas().dispatchEvent(new Event('mouseleave'));
    map.fire('move');
    flushFrames();
    expect(source('draft').data.features).toHaveLength(1);
    expect(document.querySelector('.measurement-live-label')).toBeNull();
    map.fire('mousemove', event(20, 20));
    flushFrames();
    map.fire('mousedown', event(20, 20));
    map.fire('mousemove', event(50, 50));
    map.fire('move');
    map.fire('mouseup', event(50, 50));
    // Inertia may continue moving the map after the pan gesture ends.
    map.fire('move');
    flushFrames();
    expect(source('draft').data.features).toHaveLength(1);
    expect(document.querySelector('.measurement-live-label')).toBeNull();
    expect(tool.start).not.toBeNull();
    expect(tool.measurements).toHaveLength(0);
});

it('restores cursor and original double-click state across activation, busy editing and removal', () => {
    map.getCanvas().style.cursor = 'grab';
    map.doubleClickZoom.disable();
    tool.activate();
    click(1, 1);
    tool.setAvailable(false);
    expect(tool.isActive()).toBe(false);
    expect(tool.button.disabled).toBe(true);
    expect(tool.button.title).toBe('Finish geometry editing to measure');
    expect(tool.activate()).toBe(false);
    expect(map.doubleClickZoom.isEnabled()).toBe(false);
    expect(map.getCanvas().style.cursor).toBe('grab');
    tool.setAvailable(true);
    map.doubleClickZoom.enable();
    tool.activate();
    click(1, 1);
    map.fire('remove');
    flushFrames();
    expect(document.querySelector('.measurement-control')).toBeNull();
    expect(source('draft')).toBeUndefined();
    expect(map.doubleClickZoom.isEnabled()).toBe(true);
    expect(map.getCanvas().style.cursor).toBe('grab');
    tool.destroy();
});

it('explains each input mode explicitly without a cancel button', () => {
    tool.activate();
    expect(tool.instructions.querySelectorAll('button')).toHaveLength(1);
    expect(tool.heading.textContent).toBe('Distance measurement instructions');
    const rows = () => [...tool.gestures.children].map(row => [...row.children].map(cell => cell.textContent));
    expect(rows()).toEqual([
        ['Left-click', 'Start / stop'],
        ['Left-drag', 'Pan map'],
        ['Right-click / Esc', 'Cancel measurement'], ['Ruler icon', 'Clear all & exit'],
    ]);
    tool.setInputMode(false, true);
    expect(rows()).toEqual([
        ['Tap', 'Start / stop'], ['Drag', 'Pan map'],
        ['Pinch', 'Zoom'], ['Ruler icon', 'Clear all & exit'],
    ]);
    tool.setInputMode(true, false);
    expect(rows()).toEqual([
        ['Enter', 'Start / stop at crosshair'], ['Arrow keys', 'Pan map'],
        ['+ / −', 'Zoom'], ['Esc', 'Cancel measurement'],
        ['Tab → ruler, Enter', 'Clear all & exit'],
    ]);
    expect(tool.instructions.textContent).not.toMatch(/point [AB]/i);
});

it('collapses instructions without measuring or clearing the draft and expands on each activation', () => {
    tool.activate();
    click(1, 1);
    click(2, 2);
    click(3, 3);
    const draftStart = [...tool.start];
    tool.heading.focus();
    const mapGesture = vi.fn();
    for (const name of ['mousedown', 'mouseup', 'click', 'touchstart', 'touchend']) map.getContainer().addEventListener(name, mapGesture);
    tool.heading.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    tool.heading.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    tool.heading.click();
    tool.heading.dispatchEvent(new Event('touchstart', { bubbles: true }));
    tool.heading.dispatchEvent(new Event('touchend', { bubbles: true }));
    expect(mapGesture).not.toHaveBeenCalled();
    expect(tool.heading.getAttribute('aria-controls')).toBe(tool.gestures.id);
    expect(tool.heading.getAttribute('aria-expanded')).toBe('false');
    expect(tool.gestures.hidden).toBe(true);
    expect(tool.instructions.hidden).toBe(false);
    expect(document.activeElement).toBe(tool.heading);
    expect(tool.measurements).toHaveLength(1);
    expect(tool.start).toEqual(draftStart);
    tool.heading.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(tool.measurements).toHaveLength(1);
    tool.deactivate();
    tool.activate();
    expect(tool.heading.getAttribute('aria-expanded')).toBe('true');
    expect(tool.gestures.hidden).toBe(false);
});

it('repositions the keyboard target when the instructions collapse or expand', () => {
    vi.stubGlobal('innerHeight', 390);
    map.getContainer().getBoundingClientRect = () => ({ top: 180, left: 0, right: 800, bottom: 780, width: 800, height: 600 });
    tool.instructions.getBoundingClientRect = () => ({ top: 192, left: 300, right: 600, bottom: tool.gestures.hidden ? 216 : 310 });
    tool.activate({ keyboard: true });
    expect(tool.crosshair.style.top).toBe('170px');
    tool.heading.focus();
    tool.heading.click();
    expect(tool.crosshair.style.top).toBe('105px');
    expect(document.activeElement).toBe(tool.heading);
    tool.heading.click();
    expect(tool.crosshair.style.top).toBe('170px');
});

it('does not activate when a dialog or editor owns the interaction', () => {
    tool.canActivate = () => false;
    expect(tool.activate()).toBe(false);
    tool.canActivate = () => true;
    const dialog = document.createElement('dialog');
    dialog.open = true;
    document.body.append(dialog);
    expect(tool.activate()).toBe(false);
});

it('tracks sibling panel visibility without placing instructions outside a narrow map', async () => {
    const panel = document.createElement('section');
    panel.id = 'project-panel';
    Object.defineProperty(tool.instructions, 'offsetHeight', { value: 70 });
    panel.getBoundingClientRect = () => ({ top: 12, right: 300, bottom: 200, left: 12, height: 188, width: 288 });
    map.getContainer().parentElement.append(panel);
    tool.activate();
    expect(tool.instructions.style.left).toBe('312px');
    panel.style.display = 'none';
    await Promise.resolve();
    flushFrames();
    expect(tool.instructions.style.left).toBe('12px');
    map.getContainer().getBoundingClientRect = () => ({ top: 0, left: 0, right: 320, bottom: 300, width: 320, height: 300 });
    panel.style.display = 'block';
    await Promise.resolve();
    flushFrames();
    expect(tool.instructions.style.left).toBe('12px');
    expect(tool.instructions.style.top).toBe('212px');
    expect(map.getContainer().classList.contains('measurement-compact-map')).toBe(true);
    tool.deactivate();
    panel.style.display = 'none';
    await Promise.resolve();
    expect(frames.size).toBe(0);
});

it('fits the rail to the visible viewport even when the map retains its desktop minimum height', () => {
    const height = window.innerHeight;
    vi.stubGlobal('innerHeight', 390);
    map.getContainer().getBoundingClientRect = () => ({ top: 180, left: 0, right: 844, bottom: 780, width: 844, height: 600 });
    window.dispatchEvent(new Event('resize'));
    flushFrames();
    expect(map.getContainer().classList.contains('measurement-compact-map')).toBe(true);
    vi.stubGlobal('innerHeight', height);
    window.dispatchEvent(new Event('resize'));
    flushFrames();
    expect(map.getContainer().classList.contains('measurement-compact-map')).toBe(false);
    window.dispatchEvent(new Event('scroll'));
    tool.destroy();
    expect(frames.size).toBe(0);
});

it('keeps keyboard targeting and its preview inside the visible canvas after viewport changes', () => {
    vi.stubGlobal('innerHeight', 390);
    map.getContainer().getBoundingClientRect = () => ({ top: 180, left: 0, right: 800, bottom: 780, width: 800, height: 600 });
    tool.activate({ keyboard: true });
    expect(tool.crosshair.style.top).toBe('105px');
    map.getCanvas().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(tool.start).toEqual([40, 10.5]);
    // Scrolling the map upwards changes the center of its visible portion.
    map.getContainer().getBoundingClientRect = () => ({ top: -100, left: 0, right: 800, bottom: 500, width: 800, height: 600 });
    window.dispatchEvent(new Event('scroll'));
    flushFrames();
    flushFrames();
    expect(tool.crosshair.style.top).toBe('295px');
    expect(source('draft').data.features.filter(feature => feature.properties.role === 'endpoint').at(-1).geometry.coordinates)
        .toEqual([40, 29.5]);
    map.getCanvas().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(tool.measurements[0].end).toEqual([40, 29.5]);
});

it('targets the visual viewport with offsets and rejects keyboard placement on a fully hidden map', () => {
    const viewport = new EventTarget();
    Object.assign(viewport, { offsetLeft: 100, offsetTop: 50, width: 400, height: 300 });
    vi.stubGlobal('visualViewport', viewport);
    map.getCanvas().getBoundingClientRect = () => ({ top: 20, left: 30, right: 830, bottom: 620, width: 800, height: 600 });
    tool.activate({ keyboard: true });
    expect(tool.crosshair.style.left).toBe('300px');
    expect(tool.crosshair.style.top).toBe('200px');
    map.getCanvas().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(tool.start).toEqual([27, 18]);
    map.getCanvas().getBoundingClientRect = () => ({ top: 700, left: 0, right: 800, bottom: 1300, width: 800, height: 600 });
    window.dispatchEvent(new Event('scroll'));
    flushFrames();
    expect(tool.crosshair.hidden).toBe(true);
    map.getCanvas().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(tool.measurements).toHaveLength(0);
    expect(tool.start).toEqual([27, 18]);
});

it('keeps the short-landscape keyboard target below its own instructions', () => {
    vi.stubGlobal('innerHeight', 390);
    map.getContainer().getBoundingClientRect = () => ({ top: 180, left: 0, right: 800, bottom: 780, width: 800, height: 600 });
    tool.instructions.getBoundingClientRect = () => ({ top: 192, left: 300, right: 500, bottom: 310, width: 200, height: 118 });
    tool.activate({ keyboard: true });
    expect(tool.crosshair.style.left).toBe('400px');
    expect(tool.crosshair.style.top).toBe('170px');
    map.getCanvas().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(tool.start).toEqual([40, 17]);
});

it('settles layout after positioning its own reticle without an observer feedback loop', async () => {
    tool.activate();
    window.dispatchEvent(new Event('resize'));
    flushFrames();
    await Promise.resolve();
    expect(frames.size).toBe(0);
    tool.setInputMode(true, false);
    await Promise.resolve();
    expect(frames.size).toBe(0);
});
