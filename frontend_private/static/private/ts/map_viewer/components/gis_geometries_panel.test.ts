import type { GISGeometryMetadata } from '../../../../../../ts-types/domain/map-config.ts';
import type { Mock } from 'vitest';
import type { ViewerState } from '../../../../../../ts-types/domain/map-state.ts';
import type { CameraBounds } from '../../../../../../ts-types/domain/map-geometry.ts';
import { Config } from '../config.ts';
import { State } from '../state.ts';
import { Layers as RuntimeLayers } from '../map/layers.ts';
import { GISGeometriesPanel } from './gis_geometries_panel.ts';

type MockFunctions<Owner> = { [Key in keyof Owner]: Owner[Key] extends (...args: infer Args) => infer Result ? Mock<(...args: Args) => Result> : Owner[Key] };
const Layers = RuntimeLayers as MockFunctions<typeof RuntimeLayers>;
let map: { fitBounds: Mock };

vi.mock('../map/layers.ts', () => ({ Layers: {
    isGISGeometryVisible: vi.fn(() => false),
    toggleGISGeometryVisibility: vi.fn(async () => true),
} }));

let editor: { create: Mock; edit: Mock<(record: GISGeometryMetadata) => Promise<boolean> | boolean> };
beforeEach(() => {
    document.body.innerHTML = '<div><div id="map"></div></div>';
    Config._gisGeometries = [];
    Config.gisGeometriesError = false;
    State.resetLayerState();
    Layers.isGISGeometryVisible.mockImplementation(id => State.gisGeometryStates.get(String(id)) === true);
    Layers.toggleGISGeometryVisibility.mockImplementation(async (id, visible) => {
        State.gisGeometryStates.set(String(id), visible);
        return true;
    });
    map = { fitBounds: vi.fn() };
    // This camera-only fixture never invokes the remaining map capabilities.
    State.map = map as unknown as ViewerState['map'];
    editor = { create: vi.fn(), edit: vi.fn() };
});
afterEach(() => { GISGeometriesPanel.destroy(); Config._gisGeometries = null; Config.gisGeometriesError = false; State.map = null; vi.restoreAllMocks(); vi.unstubAllGlobals();
    vi.clearAllMocks(); });

it('replaces panel DOM on repeated initialization while retaining row and request registries', () => {
    GISGeometriesPanel.init(editor);
    const panel = GISGeometriesPanel.panel!;
    const rows = GISGeometriesPanel.rows;
    const requests = GISGeometriesPanel.requests;
    GISGeometriesPanel.init(editor);
    expect(panel.isConnected).toBe(false);
    expect(GISGeometriesPanel.panel!).not.toBe(panel);
    expect(GISGeometriesPanel.rows).toBe(rows);
    expect(GISGeometriesPanel.requests).toBe(requests);
    expect(document.querySelectorAll<HTMLElement>('#gis-geometries-panel')).toHaveLength(1);
    expect(document.querySelectorAll('#map-panel-stack > .map-panel-slot')).toHaveLength(1);
});

it('is available inside the fullscreen map container even when empty', () => {
    GISGeometriesPanel.init(editor);
    expect(document.querySelector<HTMLElement>('#map > #map-panel-stack #gis-geometries-panel')!).not.toBeNull();
    expect(document.querySelector<HTMLElement>('#gis-geometries-panel-minimized')!.hidden).toBe(false);
    document.querySelector<HTMLElement>('#gis-geometries-panel-minimized')!.click();
    expect(document.querySelector<HTMLElement>('#gis-geometries-panel')!.hidden).toBe(false);
    expect(document.querySelector<HTMLElement>('.gis-geometries-create')!).toBeNull();
    expect(document.querySelector<HTMLElement>('.gis-geometries-empty')!.textContent).toContain('Choose Create Geometry above the map');
    expect(GISGeometriesPanel.minimized!.querySelector<HTMLElement>('svg path')!.getAttribute('d')).toBe('M9 5l7 7-7 7');
    const collapse = document.querySelector<HTMLElement>('.gis-geometries-icon-button')!;
    expect(collapse.querySelector<HTMLElement>('svg path')!.getAttribute('d')).toBe('M19 9l-7 7-7-7');
    collapse.click();
    expect(GISGeometriesPanel.minimized!.getAttribute('aria-expanded')).toBe('false');
});

it('exposes editing only to writers and safely renders untrusted names', () => {
    Config._gisGeometries = [
        { id: 'reader', revision: 1, name: '<img src=x onerror=alert(1)>', color: 'red;display:none', can_write: false },
        { id: 'writer', revision: 1, name: 'Outline', color: '#123456', can_write: true },
    ];
    GISGeometriesPanel.init(editor);
    expect(document.querySelector<HTMLElement>('img')!).toBeNull();
    expect(document.querySelectorAll<HTMLElement>('.gis-geometries-edit')).toHaveLength(1);
    const edit = document.querySelector<HTMLButtonElement>('.gis-geometries-edit')!;
    expect(edit.getAttribute('aria-label')).toBe('Edit Outline');
    expect(edit.querySelector('svg')).not.toBeNull();
    edit.click();
    expect(editor.edit).toHaveBeenCalledWith(Config._gisGeometries[1]);
});

it('renders full geometry names in case-insensitive alphabetical order', () => {
    const longName = 'A very long GIS geometry name that remains entirely available';
    Config._gisGeometries = [
        { id: 'z', revision: 1, name: 'Zulu', color: '#123456' },
        { id: 'b', revision: 1, name: 'bravo', color: '#123456' },
        { id: 'a', revision: 1, name: longName, color: '#123456' },
    ];
    GISGeometriesPanel.init(editor);

    expect([...document.querySelectorAll('.gis-geometries-name')].map(name => name.textContent))
        .toEqual([longName, 'bravo', 'Zulu']);
});

it('toggles without zoom and frames only on an explicit name click', async () => {
    Config._gisGeometries = [{ id: 'g1', revision: 1, name: 'Outline', color: '#123456', can_write: false }];
    State.gisGeometryBounds.set('g1', { bounds: true } as unknown as CameraBounds);
    GISGeometriesPanel.init(editor);
    const visibility = document.querySelector<HTMLElement>('.toggle-switch')!;
    expect(visibility.querySelector<HTMLInputElement>('input')!.getAttribute('aria-label')).toBe('Show Outline');
    expect(visibility.querySelector<HTMLInputElement>('input')!.checked).toBe(false);
    visibility.querySelector<HTMLElement>('.toggle-slider')!.click();
    await vi.waitFor(() => expect(Layers.toggleGISGeometryVisibility).toHaveBeenCalledWith('g1', true));
    expect(map.fitBounds).not.toHaveBeenCalled();
    document.querySelector<HTMLElement>('.gis-geometries-name')!.click();
    await vi.waitFor(() => expect(map.fitBounds).toHaveBeenCalledWith({ bounds: true }, {
        padding: 50, maxZoom: 16, bearing: 0, pitch: 0, retainPadding: false,
    }));
});

it('keeps a pending toggle usable and ignores an older completion after reversal', async () => {
    Config._gisGeometries = [{ id: 'g1', revision: 1, name: 'Outline', color: '#123456' }];
    Layers.isGISGeometryVisible.mockReturnValueOnce(true);
    let finish!: (result: boolean) => void;
    Layers.toggleGISGeometryVisibility.mockImplementationOnce((id, visible) => {
        State.gisGeometryStates.set(String(id), visible);
        return new Promise(resolve => { finish = resolve; });
    });
    GISGeometriesPanel.init(editor);
    const toggle = document.querySelector<HTMLInputElement>('.toggle-switch input')!;
    expect(toggle.checked).toBe(true);
    document.querySelector<HTMLElement>('.toggle-slider')!.click();
    expect(Layers.toggleGISGeometryVisibility).toHaveBeenCalledWith('g1', false);
    expect(toggle.disabled).toBe(false);
    expect(toggle.checked).toBe(false);
    document.querySelector<HTMLElement>('.toggle-slider')!.click();
    expect(Layers.toggleGISGeometryVisibility).toHaveBeenCalledTimes(2);
    expect(toggle.checked).toBe(true);
    finish(false);
    await vi.waitFor(() => expect(GISGeometriesPanel.requests.size).toBe(0));
    expect(document.querySelector<HTMLInputElement>('.toggle-switch input')!).toBe(toggle);
    expect(toggle.checked).toBe(true);
});

it('moves keyboard focus between the visible expand and collapse controls', () => {
    GISGeometriesPanel.init(editor);
    GISGeometriesPanel.minimized!.focus();
    GISGeometriesPanel.minimized!.click();
    const collapse = document.querySelector<HTMLElement>('.gis-geometries-icon-button')!;
    expect(document.activeElement).toBe(collapse);
    collapse.click();
    expect(document.activeElement).toBe(GISGeometriesPanel.minimized!);
});

it('preserves the same focused control during a pending visibility change', async () => {
    Config._gisGeometries = [{ id: 'g1', revision: 1, name: 'Outline', color: '#123456' }];
    let finish!: (result: boolean) => void;
    Layers.toggleGISGeometryVisibility.mockImplementationOnce((id, visible) => {
        State.gisGeometryStates.set(String(id), visible);
        return new Promise(resolve => { finish = resolve; });
    });
    GISGeometriesPanel.init(editor);
    GISGeometriesPanel.setExpanded(true);
    const toggle = document.querySelector<HTMLInputElement>('.gis-geometries-visibility')!;
    toggle.focus();
    toggle.click();
    expect(toggle.disabled).toBe(false);
    expect(document.activeElement).toBe(toggle);
    finish(true);
    await vi.waitFor(() => expect(document.activeElement).toBe(document.querySelector<HTMLInputElement>('.gis-geometries-visibility')!));
    expect(document.activeElement).toBe(toggle);
    expect((document.activeElement as HTMLInputElement).disabled).toBe(false);
});

it('does not steal focus moved elsewhere during a pending visibility change', async () => {
    Config._gisGeometries = [{ id: 'g1', revision: 1, name: 'Outline', color: '#123456' }];
    let finish!: (result: boolean) => void;
    Layers.toggleGISGeometryVisibility.mockImplementationOnce((id, visible) => {
        State.gisGeometryStates.set(String(id), visible);
        return new Promise(resolve => { finish = resolve; });
    });
    GISGeometriesPanel.init(editor);
    GISGeometriesPanel.setExpanded(true);
    const toggle = document.querySelector<HTMLInputElement>('.gis-geometries-visibility')!;
    toggle.focus();
    toggle.click();
    const other = document.createElement('button');
    document.body.append(other);
    other.focus();
    finish(true);
    await vi.waitFor(() => expect(GISGeometriesPanel.requests.size).toBe(0));
    expect(toggle.isConnected).toBe(true);
    expect(document.activeElement).toBe(other);
});

it('keeps the geometry slot available independently of desktop-only panel slots', () => {
    GISGeometriesPanel.init(editor);
    const slot = GISGeometriesPanel.panel!.closest('.map-panel-slot')!;
    expect(slot).not.toBeNull();
    expect(slot.classList.contains('map-panel-slot--desktop')).toBe(false);
    expect(GISGeometriesPanel.minimized!.parentElement).toBe(slot);
});

it('collapses after opening an editor but keeps the list open when the transition is declined', async () => {
    Config._gisGeometries = [{ id: 'g1', revision: 1, name: 'Outline', color: '#123456', can_write: true }];
    editor.edit.mockResolvedValueOnce(true).mockResolvedValueOnce(false);
    GISGeometriesPanel.init(editor);
    GISGeometriesPanel.setExpanded(true);
    document.querySelector<HTMLElement>('.gis-geometries-edit')!.click();
    await vi.waitFor(() => expect(GISGeometriesPanel.panel!.hidden).toBe(true));
    GISGeometriesPanel.setExpanded(true);
    document.querySelector<HTMLElement>('.gis-geometries-edit')!.click();
    await Promise.resolve();
    expect(GISGeometriesPanel.panel!.hidden).toBe(false);
});

it('distinguishes a load failure from an empty list and offers retry', async () => {
    Config.gisGeometriesError = true;
    vi.spyOn(Config, 'loadGISGeometries').mockImplementation(async () => {
        Config.gisGeometriesError = false;
        Config._gisGeometries = [{ id: 'g1', revision: 1, name: 'Recovered geometry', color: '#123456' }];
        return Config._gisGeometries;
    });
    GISGeometriesPanel.init(editor);
    expect(document.querySelector<HTMLElement>('.gis-geometries-empty')!).toBeNull();
    document.querySelector<HTMLButtonElement>('.gis-geometries-retry')!.click();
    expect(document.querySelector<HTMLButtonElement>('.gis-geometries-retry')!.disabled).toBe(true);
    await vi.waitFor(() => expect(document.querySelector<HTMLElement>('.gis-geometries-name')?.textContent).toBe('Recovered geometry'));
    expect(document.querySelector<HTMLElement>('.gis-geometries-load-error')!).toBeNull();
});

it('retains locally saved rows alongside an unresolved load failure', () => {
    Config.gisGeometriesError = true;
    Config._gisGeometries = [{ id: 'new', revision: 1, name: 'Just saved', color: '#123456' }];
    GISGeometriesPanel.init(editor);
    expect(document.querySelector<HTMLElement>('.gis-geometries-load-error')!).not.toBeNull();
    expect(document.querySelector<HTMLElement>('.gis-geometries-name')!.textContent).toBe('Just saved');
});

it('locks only the edited geometry visibility while preserving other row actions', () => {
    Config._gisGeometries = [
        { id: 'g1', revision: 1, name: 'Editing this one', color: '#123456', can_write: true },
        { id: 'g2', revision: 1, name: 'Other geometry', color: '#123456', can_write: true },
    ];
    State.gisGeometryEditingId = 'g1';
    GISGeometriesPanel.init(editor);
    const editing = document.querySelector<HTMLElement>('[data-geometry-id="g1"]')!;
    const other = document.querySelector<HTMLElement>('[data-geometry-id="g2"]')!;
    for (const selector of ['.gis-geometries-name', '.gis-geometries-visibility', '.gis-geometries-edit']) {
        expect(editing.querySelector<HTMLInputElement | HTMLButtonElement>(selector)!.disabled).toBe(true);
        expect(other.querySelector<HTMLInputElement | HTMLButtonElement>(selector)!.disabled).toBe(false);
    }
    editing.querySelector<HTMLElement>('.toggle-slider')!.click();
    expect(Layers.toggleGISGeometryVisibility).not.toHaveBeenCalled();
    other.querySelector<HTMLElement>('.gis-geometries-edit')!.click();
    expect(editor.edit).toHaveBeenCalledWith(Config._gisGeometries[1]);
});
