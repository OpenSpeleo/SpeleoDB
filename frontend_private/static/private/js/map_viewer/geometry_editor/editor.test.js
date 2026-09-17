import { readFileSync } from 'node:fs';
import { API } from '../api.js';
import { Config, DEFAULTS } from '../config.js';
import { GeometryEditor } from './editor.js';

vi.mock('../api.js', () => ({ API: { getGISGeometryDetails: vi.fn(), createGISGeometry: vi.fn(), updateGISGeometry: vi.fn() } }));
vi.mock('../utils.js', async () => {
    const actual = await vi.importActual('../utils.js');
    return { Utils: { ...actual.Utils, showNotification: vi.fn() } };
});

function mapMock() {
    const sources = new Map();
    const layers = new Map();
    return {
        sources, layers,
        getContainer: () => document.getElementById('map'),
        getCanvas: () => document.getElementById('canvas'),
        getStyle: () => ({ layers: [...layers.values()] }),
        getSource: id => sources.get(id),
        getLayer: id => layers.get(id),
        addSource: (id, data) => sources.set(id, { ...data, setData: vi.fn(value => { sources.get(id).data = value; }) }),
        addLayer: layer => layers.set(layer.id, layer),
        removeSource: id => sources.delete(id),
        removeLayer: id => layers.delete(id),
        queryRenderedFeatures: vi.fn(() => []),
        dragPan: { isEnabled: vi.fn(() => true), disable: vi.fn(), enable: vi.fn() },
        doubleClickZoom: { isEnabled: vi.fn(() => true), disable: vi.fn(), enable: vi.fn() },
    };
}

function event(lng, lat, x = 0, y = 0) {
    return { lngLat: { lng, lat }, point: { x, y }, preventDefault: vi.fn(), originalEvent: { button: 0 } };
}

function action(name) { return document.querySelector(`[data-editor-action="${name}"]`); }
function inputName(value) {
    GeometryEditor.nodes.name.value = value;
    GeometryEditor.nodes.name.dispatchEvent(new Event('input', { bubbles: true }));
}
function gps(latitude, longitude) {
    GeometryEditor.nodes.latitude.value = latitude;
    GeometryEditor.nodes.longitude.value = longitude;
    GeometryEditor.nodes.latitude.dispatchEvent(new Event('input', { bubbles: true }));
}

const existing = { id: 'geometry-1', name: 'Existing line', color: '#38bdf8', can_write: true, revision: 3, geojson: { type: 'LineString', coordinates: [[0, 0], [0.001, 0.001]] } };

describe('native GIS geometry editor', () => {
    const sharedCases = JSON.parse(readFileSync('speleodb/gis/tests/fixtures/gis_geometry_cases.json', 'utf8'));
    let map;
    let onSaved;
    let onPreview;
    beforeEach(() => {
        document.body.innerHTML = '<div><div id="map"><canvas id="canvas"></canvas></div></div>';
        Config._gisGeometries = [];
        Config.upsertGISGeometry(existing);
        vi.clearAllMocks();
        map = mapMock();
        onSaved = vi.fn();
        onPreview = vi.fn();
        GeometryEditor.init({ map, onSaved, onPreview, palette: ['#38bdf8', '#ef4444'] });
        API.getGISGeometryDetails.mockResolvedValue(structuredClone(existing));
    });
    afterEach(() => { GeometryEditor.destroy(); vi.restoreAllMocks(); });

    it('preserves an unsaved draft while Settings or a manager handles keyboard input', async () => {
        await GeometryEditor.create();
        inputName('Unsaved draft');
        const session = GeometryEditor.session;
        const dialog = document.createElement('dialog');
        dialog.open = true;
        document.body.append(dialog);
        for (const key of ['Escape', 'Delete', 'Backspace', 'Enter', 'z']) {
            document.dispatchEvent(new KeyboardEvent('keydown', { key, ctrlKey: key === 'z', bubbles: true }));
            expect(GeometryEditor.session).toBe(session);
            expect(GeometryEditor.session.name).toBe('Unsaved draft');
        }
        dialog.remove();
        document.body.insertAdjacentHTML('beforeend', '<div role="dialog" aria-modal="true"><button>Close</button></div>');
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        expect(GeometryEditor.session).toBe(session);
        expect(GeometryEditor.hasUnsavedChanges()).toBe(true);
    });

    it('selects a fresh palette color for each new draft and preserves stored colors on edit', async () => {
        const random = vi.spyOn(Math, 'random').mockReturnValueOnce(0).mockReturnValueOnce(0.99);
        await GeometryEditor.create();
        expect(GeometryEditor.session.color).toBe('#38bdf8');
        expect(GeometryEditor.hasUnsavedChanges()).toBe(false);
        await GeometryEditor.create();
        expect(GeometryEditor.session.color).toBe('#ef4444');
        expect(GeometryEditor.nodes.colors.querySelector('[aria-pressed="true"]').dataset.color).toBe('#ef4444');
        expect(GeometryEditor.hasUnsavedChanges()).toBe(false);
        await GeometryEditor.edit(existing);
        expect(GeometryEditor.session.color).toBe(existing.color);
        expect(random).toHaveBeenCalledTimes(2);
    });

    it('returns focus to Create Geometry after closing an editor opened directly from a URL', async () => {
        const create = document.createElement('button');
        create.id = 'create-geometry-btn';
        document.body.prepend(create);
        expect(document.activeElement).toBe(document.body);
        await GeometryEditor.edit(existing);
        expect(GeometryEditor.session.returnFocus).toBe(document.body);
        GeometryEditor.close();
        expect(document.activeElement).toBe(create);
    });

    it.each(['hidden', 'disabled', 'detached'])('uses a visible control when the original editor trigger becomes %s', async state => {
        const create = document.createElement('button');
        create.id = 'create-geometry-btn';
        const originalContainer = document.createElement('div');
        const original = document.createElement('button');
        originalContainer.append(original);
        document.body.prepend(create, originalContainer);
        original.focus();
        await GeometryEditor.edit(existing);
        if (state === 'hidden') originalContainer.hidden = true;
        if (state === 'disabled') original.disabled = true;
        if (state === 'detached') originalContainer.remove();
        GeometryEditor.close();
        expect(document.activeElement).toBe(create);
    });

    it('preserves the original trigger when it still accepts focus', async () => {
        const original = document.createElement('button');
        document.body.prepend(original);
        original.focus();
        await GeometryEditor.edit(existing);
        GeometryEditor.close();
        expect(document.activeElement).toBe(original);
    });

    it('uses the shared fallback when no palette is available', async () => {
        GeometryEditor.init({ map, palette: [] });
        await GeometryEditor.create();
        expect(GeometryEditor.session.color).toBe(DEFAULTS.COLORS.FALLBACK);
    });

    it('does not persist a new record until Save and uses identical GPS/map points', async () => {
        await GeometryEditor.create();
        const color = GeometryEditor.session.color;
        inputName('Test line');
        GeometryEditor.handleClick(event(0, 0));
        gps('0.001', '0.001');
        GeometryEditor.applyGPS();
        expect(GeometryEditor.session.draft.vertices).toEqual([[0, 0], [0.001, 0.001]]);
        expect(API.createGISGeometry).not.toHaveBeenCalled();
        API.createGISGeometry.mockResolvedValue({ ...existing, name: 'Test line' });
        await GeometryEditor.save();
        expect(API.createGISGeometry).toHaveBeenCalledWith({ name: 'Test line', color, geojson: existing.geojson });
        expect(onSaved).toHaveBeenCalledOnce();
        expect(GeometryEditor.isActive()).toBe(false);
        expect(map.sources.size).toBe(0);
    });

    it('flushes the focused coordinate input before Save', async () => {
        await GeometryEditor.edit(existing);
        GeometryEditor.select(1);
        gps('0.002', '0.003');
        GeometryEditor.nodes.longitude.focus();
        API.updateGISGeometry.mockResolvedValue(existing);
        await GeometryEditor.save();
        expect(API.updateGISGeometry).toHaveBeenCalledWith(existing.id, expect.objectContaining({ expected_revision: 3, geojson: { type: 'LineString', coordinates: [[0, 0], [0.003, 0.002]] } }));
    });

    it('keeps invalid GPS input and does not submit a stale geometry', async () => {
        await GeometryEditor.edit(existing);
        GeometryEditor.select(1);
        gps('91', '0.003');
        expect(await GeometryEditor.save()).toBe(false);
        expect(API.updateGISGeometry).not.toHaveBeenCalled();
        expect(GeometryEditor.nodes.status.textContent).toMatch(/latitude/);
        expect(GeometryEditor.nodes.latitude.value).toBe('91');
    });

    it('groups a vertex drag into one undo command and ignores its following click', async () => {
        await GeometryEditor.edit(existing);
        map.queryRenderedFeatures.mockReturnValue([{ properties: { role: 'vertex', index: 1 }, geometry: { type: 'Point', coordinates: [0.001, 0.001] } }]);
        GeometryEditor.handleMouseDown(event(0.001, 0.001));
        GeometryEditor.handleMouseMove(event(0.002, 0.002, 10, 10));
        GeometryEditor.handleMouseMove(event(0.003, 0.003, 20, 20));
        GeometryEditor.handleMouseUp();
        expect(GeometryEditor.session.draft.undo).toHaveLength(1);
        GeometryEditor.handleClick(event(0.003, 0.003));
        expect(GeometryEditor.session.draft.vertices).toHaveLength(2);
        GeometryEditor.performAction('undo');
        expect(GeometryEditor.session.draft.vertices).toEqual(existing.geojson.coordinates);
        expect(map.dragPan.enable).toHaveBeenCalled();
    });

    it('restores the original draft after a cancelled touch drag', async () => {
        await GeometryEditor.edit(existing);
        map.queryRenderedFeatures.mockReturnValue([{ properties: { role: 'vertex', index: 0 }, geometry: { type: 'Point', coordinates: [0, 0] } }]);
        GeometryEditor.handleMouseDown({ points: [{ x: 0, y: 0 }], lngLats: [{ lng: 0, lat: 0 }], preventDefault: vi.fn() });
        GeometryEditor.handleMouseMove({ points: [{ x: 20, y: 20 }], lngLats: [{ lng: 0.003, lat: 0.003 }] });
        window.dispatchEvent(new Event('touchcancel'));
        expect(GeometryEditor.session.draft.vertices).toEqual(existing.geojson.coordinates);
        expect(GeometryEditor.session.draft.undo).toHaveLength(0);
    });

    it('cancels a vertex drag when a second touch begins a map gesture', async () => {
        await GeometryEditor.edit(existing);
        map.queryRenderedFeatures.mockReturnValue([{ properties: { role: 'vertex', index: 0 }, geometry: { type: 'Point', coordinates: [0, 0] } }]);
        GeometryEditor.handleMouseDown({ points: [{ x: 0, y: 0 }], lngLats: [{ lng: 0, lat: 0 }], preventDefault: vi.fn() });
        GeometryEditor.handleMouseMove({ points: [{ x: 20, y: 20 }], lngLats: [{ lng: 0.003, lat: 0.003 }] });
        GeometryEditor.handleMouseDown({ points: [{ x: 20, y: 20 }, { x: 50, y: 50 }] });
        GeometryEditor.handleMouseMove({ points: [{ x: 30, y: 30 }, { x: 70, y: 70 }], lngLats: [{ lng: 0.004, lat: 0.004 }] });
        GeometryEditor.handleMouseUp();
        expect(GeometryEditor.session.drag).toBeNull();
        expect(GeometryEditor.session.draft.vertices).toEqual(existing.geojson.coordinates);
        expect(GeometryEditor.session.draft.undo).toHaveLength(0);
        expect(map.dragPan.enable).toHaveBeenCalled();
    });

    it('does not swallow the next pointer gesture when a drag generates no click', async () => {
        await GeometryEditor.edit(existing);
        map.queryRenderedFeatures.mockReturnValue([{ properties: { role: 'vertex', index: 1 }, geometry: { type: 'Point', coordinates: [0.001, 0.001] } }]);
        GeometryEditor.handleMouseDown(event(0.001, 0.001));
        GeometryEditor.handleMouseMove(event(0.002, 0.002, 10, 10));
        GeometryEditor.handleMouseUp();
        map.queryRenderedFeatures.mockReturnValue([]);
        GeometryEditor.performAction('drawing');
        GeometryEditor.handleMouseDown(event(0.003, 0.003));
        GeometryEditor.handleClick(event(0.003, 0.003));
        expect(GeometryEditor.session.draft.vertices).toHaveLength(3);
    });

    it('commits a drag before keyboard undo and does not restore it on pointer release', async () => {
        await GeometryEditor.edit(existing);
        map.queryRenderedFeatures.mockReturnValue([{ properties: { role: 'vertex', index: 1 }, geometry: { type: 'Point', coordinates: [0.001, 0.001] } }]);
        GeometryEditor.handleMouseDown(event(0.001, 0.001));
        GeometryEditor.handleMouseMove(event(0.002, 0.002, 10, 10));
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true }));
        GeometryEditor.handleMouseUp();
        expect(GeometryEditor.session.drag).toBeNull();
        expect(GeometryEditor.session.draft.vertices).toEqual(existing.geojson.coordinates);
        expect(GeometryEditor.session.draft.redo).toHaveLength(1);
        expect(map.dragPan.enable).toHaveBeenCalled();
    });

    it('preserves native Enter activation on editor buttons and disclosures', async () => {
        await GeometryEditor.create();
        for (const control of [action('color'), GeometryEditor.nodes.gpsDisclosure.querySelector('summary')]) {
            control.focus();
            const key = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
            control.dispatchEvent(key);
            expect(key.defaultPrevented).toBe(false);
            expect(GeometryEditor.session.drawing).toBe(true);
        }
        const canvasKey = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
        map.getCanvas().dispatchEvent(canvasKey);
        expect(canvasKey.defaultPrevented).toBe(true);
        expect(GeometryEditor.session.drawing).toBe(false);
    });

    it('inserts a midpoint once and permits undoing it', async () => {
        await GeometryEditor.edit(existing);
        map.queryRenderedFeatures.mockReturnValue([{ properties: { role: 'midpoint', index: 1 }, geometry: { type: 'Point', coordinates: [0.0005, 0.0005] } }]);
        GeometryEditor.handleMouseDown(event(0.0005, 0.0005));
        GeometryEditor.handleMouseUp();
        GeometryEditor.handleClick(event(0.0005, 0.0005));
        expect(GeometryEditor.session.draft.vertices).toHaveLength(3);
        GeometryEditor.performAction('undo');
        expect(GeometryEditor.session.draft.vertices).toHaveLength(2);
    });

    it('Revert discards changes without calling an API and restores saved visibility', async () => {
        await GeometryEditor.edit(existing);
        GeometryEditor.select(1);
        gps('0.003', '0.003');
        GeometryEditor.applyGPS();
        expect(GeometryEditor.requestClose()).toBe(false);
        expect(GeometryEditor.nodes.discard.hidden).toBe(false);
        action('discard').click();
        expect(API.updateGISGeometry).not.toHaveBeenCalled();
        expect(onPreview).toHaveBeenLastCalledWith(existing.id, false);
        expect(existing.geojson.coordinates[1]).toEqual([0.001, 0.001]);
    });

    it('preserves a draft after a conflict and prevents duplicate submissions', async () => {
        await GeometryEditor.edit(existing);
        inputName('Modified line');
        let reject;
        API.updateGISGeometry.mockReturnValue(new Promise((_, rejectPromise) => { reject = rejectPromise; }));
        const first = GeometryEditor.save();
        expect(await GeometryEditor.save()).toBe(false);
        reject(Object.assign(new Error('Conflict'), { status: 409 }));
        expect(await first).toBe(false);
        expect(API.updateGISGeometry).toHaveBeenCalledTimes(1);
        expect(GeometryEditor.isActive()).toBe(true);
        expect(GeometryEditor.nodes.status.textContent).toMatch(/changed while/);
    });

    it('disables Save above the bbox limit and restores it after undo', async () => {
        await GeometryEditor.create();
        inputName('Too large');
        GeometryEditor.handleClick(event(0, 0));
        GeometryEditor.handleClick(event(1, 1));
        expect(GeometryEditor.nodes.save.disabled).toBe(true);
        expect(GeometryEditor.nodes.root.classList.contains('is-over-limit')).toBe(true);
        GeometryEditor.performAction('undo');
        GeometryEditor.handleClick(event(0.001, 0.001));
        expect(GeometryEditor.nodes.save.disabled).toBe(false);
    });

    it('does not allow stale writer metadata to bypass fresh permissions', async () => {
        API.getGISGeometryDetails.mockResolvedValue({ ...existing, can_write: false });
        expect(await GeometryEditor.edit(existing)).toBe(false);
        expect(GeometryEditor.isActive()).toBe(false);
    });

    it('retains its draft while rebuilding layers after a style reset', async () => {
        await GeometryEditor.edit(existing);
        map.sources.clear();
        map.layers.clear();
        GeometryEditor.restoreLayers();
        expect(map.sources.size).toBe(1);
        expect(map.layers.size).toBe(5);
        expect(GeometryEditor.session.draft.vertices).toEqual(existing.geojson.coordinates);
    });

    it('treats names as text and gives keyboard users selectable vertex rows', async () => {
        await GeometryEditor.edit({ ...existing });
        inputName('<img src=x onerror=alert(1)>');
        expect(GeometryEditor.nodes.root.querySelector('img')).toBeNull();
        const vertex = GeometryEditor.nodes.vertices.querySelector('[data-editor-action="select"]');
        vertex.click();
        expect(GeometryEditor.session.selected).toBe(0);
        expect(GeometryEditor.nodes.gpsTitle.textContent).toContain('Point 1');
        expect(GeometryEditor.nodes.latitude.value).toBe('0');
    });

    it('keeps keyboard focus in vertex navigation when its controls refresh', async () => {
        await GeometryEditor.edit(existing);
        const choose = action('select');
        choose.focus();
        choose.click();
        expect(document.activeElement).toBe(action('select'));
        const next = action('next');
        next.focus();
        next.click();
        expect(GeometryEditor.session.selected).toBe(1);
        expect(document.activeElement).toBe(action('select'));
    });

    it('does not save an unchanged existing geometry', async () => {
        await GeometryEditor.edit(existing);
        expect(GeometryEditor.nodes.save.disabled).toBe(true);
        expect(await GeometryEditor.save()).toBe(false);
        expect(API.updateGISGeometry).not.toHaveBeenCalled();
    });

    it('preserves the draft when conflict reload fails and supplies a copy fallback', async () => {
        await GeometryEditor.edit(existing);
        inputName('Keep this draft');
        API.updateGISGeometry.mockRejectedValue(Object.assign(new Error('Conflict'), { status: 409 }));
        await GeometryEditor.save();
        await GeometryEditor.copyDraft();
        expect(GeometryEditor.nodes.copyFallback.hidden).toBe(false);
        expect(JSON.parse(GeometryEditor.nodes.copyFallback.value)).toEqual(existing.geojson);
        API.getGISGeometryDetails.mockRejectedValue(new Error('Offline'));
        expect(await GeometryEditor.reloadSaved()).toBe(false);
        expect(GeometryEditor.session.name).toBe('Keep this draft');
        expect(GeometryEditor.isActive()).toBe(true);
    });

    it.each(['create', 'edit'])('does not %s another draft while an unchanged conflict is reloading', async method => {
        await GeometryEditor.edit(existing);
        inputName('Conflicting change');
        API.updateGISGeometry.mockRejectedValue(Object.assign(new Error('Conflict'), { status: 409 }));
        await GeometryEditor.save();
        inputName(existing.name);
        expect(GeometryEditor.hasUnsavedChanges()).toBe(false);
        expect(GeometryEditor.nodes.conflict.hidden).toBe(false);
        let resolve;
        API.getGISGeometryDetails.mockReturnValue(new Promise(done => { resolve = done; }));
        GeometryEditor.performAction('reload');
        const session = GeometryEditor.session;
        GeometryEditor.performAction('discard');
        expect(session.saving).toBe(true);
        // Start the actual entry point without awaiting an accidentally opened
        // fetch: before the fix, edit() waits on the same pending detail response.
        const opening = method === 'create' ? GeometryEditor.create() : GeometryEditor.edit(existing);
        const unchanged = GeometryEditor.session === session;
        const requestCount = API.getGISGeometryDetails.mock.calls.length;
        resolve({ ...existing, revision: existing.revision + 1 });
        const result = await opening;
        await vi.waitFor(() => expect(GeometryEditor.session.record?.revision).toBe(existing.revision + 1));
        expect(unchanged).toBe(true);
        expect(requestCount).toBe(2);
        expect(result).toBe(false);
        expect(document.querySelectorAll('[data-geometry-editor]')).toHaveLength(1);
    });

    it.each(['resolve', 'reject'])('ignores clipboard %s after the editor closes', async outcome => {
        await GeometryEditor.edit(existing);
        let settle;
        const writeText = vi.fn(() => new Promise((resolve, reject) => {
            settle = outcome === 'resolve' ? resolve : reject;
        }));
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
        try {
            const copying = GeometryEditor.copyDraft();
            GeometryEditor.close(true);
            settle();
            await expect(copying).resolves.toBe(false);
            expect(GeometryEditor.isActive()).toBe(false);
        } finally {
            delete navigator.clipboard;
        }
    });

    it.each(['resolve', 'reject'])('does not leak clipboard %s into a replacement draft', async outcome => {
        await GeometryEditor.edit(existing);
        let settle;
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
            writeText: () => new Promise((resolve, reject) => { settle = outcome === 'resolve' ? resolve : reject; }),
        } });
        try {
            const copying = GeometryEditor.copyDraft();
            GeometryEditor.close(true);
            await GeometryEditor.create();
            const status = GeometryEditor.nodes.status.textContent;
            settle();
            await expect(copying).resolves.toBe(false);
            expect(GeometryEditor.nodes.status.textContent).toBe(status);
            expect(GeometryEditor.nodes.copyFallback.hidden).toBe(true);
            expect(GeometryEditor.nodes.copyFallback.value).toBe('');
        } finally {
            delete navigator.clipboard;
        }
    });

    it('shows the retained draft when asynchronous clipboard access is denied', async () => {
        await GeometryEditor.edit(existing);
        let reject;
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
            writeText: () => new Promise((_, rejectPromise) => { reject = rejectPromise; }),
        } });
        try {
            const copying = GeometryEditor.copyDraft();
            reject(new Error('Clipboard denied'));
            await expect(copying).resolves.toBe(true);
            expect(GeometryEditor.nodes.copyFallback.hidden).toBe(false);
            expect(JSON.parse(GeometryEditor.nodes.copyFallback.value)).toEqual(existing.geojson);
            expect(document.activeElement).toBe(GeometryEditor.nodes.copyFallback);
        } finally {
            delete navigator.clipboard;
        }
    });

    it('continues a requested session switch after discard and blocks accidental control map clicks', async () => {
        await GeometryEditor.edit(existing);
        inputName('Dirty edit');
        await GeometryEditor.create();
        expect(GeometryEditor.session.record.id).toBe(existing.id);
        const mapClick = vi.fn();
        map.getContainer().addEventListener('click', mapClick);
        action('discard').click();
        expect(GeometryEditor.session.record).toBeNull();
        expect(mapClick).not.toHaveBeenCalled();
    });

    it('shows provisional GPS area and prevents an oversize save before focus leaves the input', async () => {
        await GeometryEditor.edit(existing);
        GeometryEditor.select(1);
        gps('1', '1');
        expect(GeometryEditor.nodes.save.disabled).toBe(true);
        expect(GeometryEditor.nodes.root.classList.contains('is-over-limit')).toBe(true);
    });

    it.each([
        ['area_8000000', false, false],
        ['area_8000001', true, false],
        ['area_30000000', true, false],
        ['area_30000001', false, true],
    ])('shows precise warning/limit state for %s', async (id, near, over) => {
        const sample = sharedCases.find(item => item.id === id);
        API.getGISGeometryDetails.mockResolvedValue({ ...existing, geojson: sample.geojson });
        await GeometryEditor.edit(existing);
        inputName('Changed threshold geometry');
        expect(GeometryEditor.nodes.root.classList.contains('is-near-limit')).toBe(near);
        expect(GeometryEditor.nodes.root.classList.contains('is-over-limit')).toBe(over);
        expect(GeometryEditor.nodes.save.disabled).toBe(over);
        expect(GeometryEditor.nodes.areaValue.textContent).toContain('/ 30 km²');
    });

    it('offers only Line and Polygon and stops inserting vertices at the cap', async () => {
        await GeometryEditor.create();
        expect([...GeometryEditor.nodes.types.children].map(button => button.dataset.type)).toEqual(['LineString', 'Polygon']);
        GeometryEditor.session.draft.vertices = Array.from({ length: 100 }, (_, index) => [index * 0.00001, index * 0.00001]);
        GeometryEditor.session.drawing = false;
        GeometryEditor.render();
        expect(action('drawing').disabled).toBe(true);
        expect(GeometryEditor.nodes.apply.disabled).toBe(true);
        const handles = map.getSource('gis-geometry-draft-source').data.features;
        expect(handles.filter(item => item.properties.role === 'midpoint')).toHaveLength(0);
        expect(GeometryEditor.append([0.002, 0.002])).toBe(false);
        expect(GeometryEditor.session.draft.vertices).toHaveLength(100);
        GeometryEditor.select(0);
        GeometryEditor.refreshUI();
        expect(GeometryEditor.nodes.apply.disabled).toBe(false);
        gps('0', '0.000001');
        GeometryEditor.nodes.gps.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        expect(GeometryEditor.session.draft.vertices[0]).toEqual([0.000001, 0]);
        expect(GeometryEditor.session.draft.vertices).toHaveLength(100);
    });
});

describe('mobile geometry editor viewport placement', () => {
    let originalWidth;
    let originalHeight;
    let originalVisualViewport;
    let viewport;
    let map;
    let mapBounds;

    beforeEach(() => {
        originalWidth = Object.getOwnPropertyDescriptor(window, 'innerWidth');
        originalHeight = Object.getOwnPropertyDescriptor(window, 'innerHeight');
        originalVisualViewport = Object.getOwnPropertyDescriptor(window, 'visualViewport');
        Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 });
        Object.defineProperty(window, 'innerHeight', { configurable: true, value: 844 });
        viewport = Object.assign(new EventTarget(), { offsetTop: 0, height: 844 });
        Object.defineProperty(window, 'visualViewport', { configurable: true, value: viewport });
        document.body.innerHTML = '<div><div id="map"><canvas id="canvas"></canvas></div></div>';
        map = mapMock();
        mapBounds = { top: 382, bottom: 982, height: 600, left: 33, right: 357, width: 324 };
        vi.spyOn(map.getContainer(), 'getBoundingClientRect').mockImplementation(() => mapBounds);
        GeometryEditor.init({ map, palette: ['#38bdf8'] });
    });

    afterEach(() => {
        GeometryEditor.destroy();
        Object.defineProperty(window, 'innerWidth', originalWidth);
        Object.defineProperty(window, 'innerHeight', originalHeight);
        if (originalVisualViewport) Object.defineProperty(window, 'visualViewport', originalVisualViewport);
        else delete window.visualViewport;
        vi.restoreAllMocks();
    });

    it('keeps the footer above the viewport when the map extends below the screen', async () => {
        await GeometryEditor.create();
        const style = GeometryEditor.nodes.root.style;
        expect(style.getPropertyValue('--geometry-mobile-bottom')).toBe('148px');
        expect(style.getPropertyValue('--geometry-mobile-max-height')).toBe('331.5px');
        const footerBottom = mapBounds.bottom - parseFloat(style.getPropertyValue('--geometry-mobile-bottom'));
        expect(footerBottom).toBe(834);
    });

    it('tracks visual-viewport resizing and offsets while preserving access to focused inputs', async () => {
        await GeometryEditor.create();
        const root = GeometryEditor.nodes.root;
        vi.spyOn(root.querySelector('header'), 'getBoundingClientRect').mockReturnValue({ height: 60 });
        vi.spyOn(root.querySelector('footer'), 'getBoundingClientRect').mockReturnValue({ height: 180 });
        vi.spyOn(GeometryEditor.nodes.name, 'getBoundingClientRect').mockReturnValue({ height: 36 });
        const scroll = vi.spyOn(window, 'scrollBy').mockImplementation((_, amount) => {
            mapBounds = { ...mapBounds, top: mapBounds.top - amount, bottom: mapBounds.bottom - amount };
        });
        GeometryEditor.nodes.name.focus();
        viewport.height = 420;
        viewport.dispatchEvent(new Event('resize'));
        await vi.waitFor(() => expect(scroll).toHaveBeenCalledWith(0, 372));
        expect(root.style.getPropertyValue('--geometry-mobile-bottom')).toBe('200px');
        expect(root.style.getPropertyValue('--geometry-mobile-max-height')).toBe('390px');
        expect(mapBounds.bottom - parseFloat(root.style.getPropertyValue('--geometry-mobile-bottom'))).toBe(410);
    });

    it('uses fullscreen map bounds and removes mobile overrides after a desktop resize', async () => {
        await GeometryEditor.create();
        mapBounds = { ...mapBounds, top: 0, bottom: 844, height: 844 };
        document.dispatchEvent(new Event('fullscreenchange'));
        await vi.waitFor(() => expect(GeometryEditor.nodes.root.style.getPropertyValue('--geometry-mobile-bottom')).toBe('10px'));
        expect(GeometryEditor.nodes.root.style.getPropertyValue('--geometry-mobile-max-height')).toBe('618px');
        Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
        window.dispatchEvent(new Event('resize'));
        await vi.waitFor(() => expect(GeometryEditor.nodes.root.style.getPropertyValue('--geometry-mobile-bottom')).toBe(''));
        expect(GeometryEditor.nodes.root.style.getPropertyValue('--geometry-mobile-max-height')).toBe('');
    });

    it('removes visual-viewport listeners and queued callbacks when the editor closes', async () => {
        await GeometryEditor.create();
        const remove = vi.spyOn(viewport, 'removeEventListener');
        const cancel = vi.spyOn(window, 'cancelAnimationFrame');
        const listener = GeometryEditor._queueViewportUpdate;
        viewport.dispatchEvent(new Event('scroll'));
        GeometryEditor.close();
        expect(remove).toHaveBeenCalledWith('resize', listener);
        expect(remove).toHaveBeenCalledWith('scroll', listener);
        expect(cancel).toHaveBeenCalled();
        expect(GeometryEditor.isActive()).toBe(false);
    });
});
