import { Config, DEFAULTS } from '../config.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';
import { GISGeometriesPanel } from './gis_geometries_panel.js';

vi.mock('../map/layers.js', () => ({ Layers: {
    isGISGeometryVisible: vi.fn(() => false),
    toggleGISGeometryVisibility: vi.fn(async () => true),
} }));

let editor;
beforeEach(() => {
    globalThis.ResizeObserver = class { observe() {} disconnect() {} };
    document.body.innerHTML = '<div><div id="map"></div></div>';
    Config._gisGeometries = [];
    Config.gisGeometriesError = false;
    State.resetLayerState();
    State.map = { fitBounds: vi.fn() };
    editor = { create: vi.fn(), edit: vi.fn() };
});
afterEach(() => { GISGeometriesPanel.destroy(); Config._gisGeometries = null; Config.gisGeometriesError = false; State.map = null; vi.restoreAllMocks(); vi.clearAllMocks(); });

it('is available inside the fullscreen map container even when empty', () => {
    GISGeometriesPanel.init(editor);
    expect(document.querySelector('#map > #gis-geometries-panel')).not.toBeNull();
    expect(document.querySelector('#gis-geometries-panel-minimized').hidden).toBe(false);
    document.querySelector('#gis-geometries-panel-minimized').click();
    expect(document.querySelector('#gis-geometries-panel').hidden).toBe(false);
    expect(document.querySelector('.gis-geometries-create')).toBeNull();
    expect(document.querySelector('.gis-geometries-empty').textContent).toContain('Choose Create Geometry above the map');
    expect(GISGeometriesPanel.minimized.querySelector('svg path').getAttribute('d')).toBe('M9 5l7 7-7 7');
    const collapse = document.querySelector('.gis-geometries-icon-button');
    expect(collapse.querySelector('svg path').getAttribute('d')).toBe('M19 9l-7 7-7-7');
    collapse.click();
    expect(GISGeometriesPanel.minimized.getAttribute('aria-expanded')).toBe('false');
});

it('exposes editing only to writers and safely renders untrusted names', () => {
    Config._gisGeometries = [
        { id: 'reader', name: '<img src=x onerror=alert(1)>', color: 'red;display:none', can_write: false },
        { id: 'writer', name: 'Outline', color: '#123456', can_write: true },
    ];
    GISGeometriesPanel.init(editor);
    expect(document.querySelector('img')).toBeNull();
    expect(document.querySelectorAll('.gis-geometries-edit')).toHaveLength(1);
    document.querySelector('.gis-geometries-edit').click();
    expect(editor.edit).toHaveBeenCalledWith(Config._gisGeometries[1]);
});

it('toggles without zoom and frames only on an explicit name click', async () => {
    Config._gisGeometries = [{ id: 'g1', name: 'Outline', color: '#123456', can_write: false }];
    State.gisGeometryBounds.set('g1', { bounds: true });
    GISGeometriesPanel.init(editor);
    const visibility = document.querySelector('.toggle-switch');
    expect(visibility.querySelector('input').getAttribute('aria-label')).toBe('Show Outline');
    expect(visibility.querySelector('input').checked).toBe(false);
    visibility.querySelector('.toggle-slider').click();
    await vi.waitFor(() => expect(Layers.toggleGISGeometryVisibility).toHaveBeenCalledWith('g1', true));
    expect(State.map.fitBounds).not.toHaveBeenCalled();
    document.querySelector('.gis-geometries-name').click();
    await vi.waitFor(() => expect(State.map.fitBounds).toHaveBeenCalledWith({ bounds: true }, {
        padding: 50, maxZoom: 16, bearing: 0, pitch: 0, retainPadding: false,
    }));
});

it('reflects visible geometry and disables the toggle while visibility is loading', async () => {
    Config._gisGeometries = [{ id: 'g1', name: 'Outline', color: '#123456' }];
    Layers.isGISGeometryVisible.mockReturnValueOnce(true);
    let finish;
    Layers.toggleGISGeometryVisibility.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    GISGeometriesPanel.init(editor);
    const toggle = document.querySelector('.toggle-switch input');
    expect(toggle.checked).toBe(true);
    document.querySelector('.toggle-slider').click();
    expect(Layers.toggleGISGeometryVisibility).toHaveBeenCalledWith('g1', false);
    expect(toggle.disabled).toBe(true);
    document.querySelector('.toggle-slider').click();
    expect(Layers.toggleGISGeometryVisibility).toHaveBeenCalledTimes(1);
    finish(false);
    await vi.waitFor(() => expect(document.querySelector('.toggle-switch input').disabled).toBe(false));
    expect(document.querySelector('.toggle-switch input').checked).toBe(false);
});

it('moves keyboard focus between the visible expand and collapse controls', () => {
    GISGeometriesPanel.init(editor);
    GISGeometriesPanel.minimized.focus();
    GISGeometriesPanel.minimized.click();
    const collapse = document.querySelector('.gis-geometries-icon-button');
    expect(document.activeElement).toBe(collapse);
    collapse.click();
    expect(document.activeElement).toBe(GISGeometriesPanel.minimized);
});

it('restores keyboard focus after a visibility toggle rebuilds the list', async () => {
    Config._gisGeometries = [{ id: 'g1', name: 'Outline', color: '#123456' }];
    let finish;
    Layers.toggleGISGeometryVisibility.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    GISGeometriesPanel.init(editor);
    GISGeometriesPanel.setExpanded(true);
    const toggle = document.querySelector('.gis-geometries-visibility');
    toggle.focus();
    toggle.click();
    // Browsers blur a focused input when it becomes disabled during the request.
    toggle.blur();
    finish(true);
    await vi.waitFor(() => expect(document.activeElement).toBe(document.querySelector('.gis-geometries-visibility')));
    expect(document.activeElement).not.toBe(toggle);
    expect(document.activeElement.disabled).toBe(false);
});

it('does not steal focus moved elsewhere during a pending visibility change', async () => {
    Config._gisGeometries = [{ id: 'g1', name: 'Outline', color: '#123456' }];
    let finish;
    Layers.toggleGISGeometryVisibility.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    GISGeometriesPanel.init(editor);
    GISGeometriesPanel.setExpanded(true);
    const toggle = document.querySelector('.gis-geometries-visibility');
    toggle.focus();
    toggle.click();
    const other = document.createElement('button');
    document.body.append(other);
    other.focus();
    finish(true);
    await vi.waitFor(() => expect(toggle.isConnected).toBe(false));
    expect(document.activeElement).toBe(other);
});

it('keeps its trigger and expanded list inside a short map when earlier panels overflow', () => {
    document.body.innerHTML = '<div id="project-panel"></div><div id="map"></div>';
    const map = document.getElementById('map');
    vi.spyOn(map, 'getBoundingClientRect').mockReturnValue({ top: 100, height: 320 });
    vi.spyOn(document.getElementById('project-panel'), 'getBoundingClientRect').mockReturnValue({ bottom: 900 });
    GISGeometriesPanel.init(editor);
    vi.spyOn(GISGeometriesPanel.minimized, 'getBoundingClientRect').mockReturnValue({ height: 44 });
    vi.spyOn(GISGeometriesPanel.panel, 'getBoundingClientRect').mockReturnValue({ height: 240 });
    GISGeometriesPanel.positionPanel();
    expect(GISGeometriesPanel.minimized.style.top).toBe(`${320 - 44 - DEFAULTS.UI.MAP_PANEL_EDGE_PX}px`);
    GISGeometriesPanel.setExpanded(true);
    expect(GISGeometriesPanel.panel.style.top).toBe(`${320 - 240 - DEFAULTS.UI.MAP_PANEL_EDGE_PX}px`);
    expect(GISGeometriesPanel.panel.style.maxHeight).toBe(`${320 - DEFAULTS.UI.MAP_PANEL_EDGE_PX * 2}px`);
});

it('retains the normal stack position when space is available', () => {
    document.body.innerHTML = '<div id="project-panel"></div><div id="map"></div>';
    vi.spyOn(document.getElementById('map'), 'getBoundingClientRect').mockReturnValue({ top: 100, height: 600 });
    vi.spyOn(document.getElementById('project-panel'), 'getBoundingClientRect').mockReturnValue({ bottom: 200 });
    GISGeometriesPanel.init(editor);
    vi.spyOn(GISGeometriesPanel.minimized, 'getBoundingClientRect').mockReturnValue({ height: 44 });
    GISGeometriesPanel.positionPanel();
    expect(GISGeometriesPanel.minimized.style.top).toBe(`${100 + DEFAULTS.UI.MAP_PANEL_GAP_PX}px`);
});

it('uses the top edge when desktop anchors are hidden by responsive CSS', () => {
    document.body.innerHTML = '<div id="project-panel"></div><div id="map"></div>';
    vi.spyOn(document.getElementById('map'), 'getBoundingClientRect').mockReturnValue({ top: 300, height: 600 });
    vi.spyOn(document.getElementById('project-panel'), 'getBoundingClientRect').mockReturnValue({ bottom: 0 });
    GISGeometriesPanel.init(editor);
    expect(GISGeometriesPanel.minimized.style.top).toBe(`${DEFAULTS.UI.MAP_PANEL_EDGE_PX}px`);
});

it('collapses after opening an editor but keeps the list open when the transition is declined', async () => {
    Config._gisGeometries = [{ id: 'g1', name: 'Outline', color: '#123456', can_write: true }];
    editor.edit.mockResolvedValueOnce(true).mockResolvedValueOnce(false);
    GISGeometriesPanel.init(editor);
    GISGeometriesPanel.setExpanded(true);
    document.querySelector('.gis-geometries-edit').click();
    await vi.waitFor(() => expect(GISGeometriesPanel.panel.hidden).toBe(true));
    GISGeometriesPanel.setExpanded(true);
    document.querySelector('.gis-geometries-edit').click();
    await Promise.resolve();
    expect(GISGeometriesPanel.panel.hidden).toBe(false);
});

it('distinguishes a load failure from an empty list and offers retry', async () => {
    Config.gisGeometriesError = true;
    vi.spyOn(Config, 'loadGISGeometries').mockImplementation(async () => {
        Config.gisGeometriesError = false;
        Config._gisGeometries = [{ id: 'g1', name: 'Recovered geometry', color: '#123456' }];
    });
    GISGeometriesPanel.init(editor);
    expect(document.querySelector('.gis-geometries-empty')).toBeNull();
    document.querySelector('.gis-geometries-retry').click();
    expect(document.querySelector('.gis-geometries-retry').disabled).toBe(true);
    await vi.waitFor(() => expect(document.querySelector('.gis-geometries-name')?.textContent).toBe('Recovered geometry'));
    expect(document.querySelector('.gis-geometries-load-error')).toBeNull();
});

it('retains locally saved rows alongside an unresolved load failure', () => {
    Config.gisGeometriesError = true;
    Config._gisGeometries = [{ id: 'new', name: 'Just saved', color: '#123456' }];
    GISGeometriesPanel.init(editor);
    expect(document.querySelector('.gis-geometries-load-error')).not.toBeNull();
    expect(document.querySelector('.gis-geometries-name').textContent).toBe('Just saved');
});

it('locks only the edited geometry visibility while preserving other row actions', () => {
    Config._gisGeometries = [
        { id: 'g1', name: 'Editing this one', color: '#123456', can_write: true },
        { id: 'g2', name: 'Other geometry', color: '#123456', can_write: true },
    ];
    State.gisGeometryEditingId = 'g1';
    GISGeometriesPanel.init(editor);
    const editing = document.querySelector('[data-geometry-id="g1"]');
    const other = document.querySelector('[data-geometry-id="g2"]');
    for (const selector of ['.gis-geometries-name', '.gis-geometries-visibility', '.gis-geometries-edit']) {
        expect(editing.querySelector(selector).disabled).toBe(true);
        expect(other.querySelector(selector).disabled).toBe(false);
    }
    editing.querySelector('.toggle-slider').click();
    expect(Layers.toggleGISGeometryVisibility).not.toHaveBeenCalled();
    other.querySelector('.gis-geometries-edit').click();
    expect(editor.edit).toHaveBeenCalledWith(Config._gisGeometries[1]);
});
