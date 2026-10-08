import type { Mock } from 'vitest';
import type { DisplayPreferences as DisplayPreferencesValue } from '../../../../../../ts-types/domain/map-display.ts';
import { flushPreferenceWrites } from '../display_preference_storage.ts';
import { ViewerUpdates } from '../viewer_updates.ts';
import { readFileSync } from 'node:fs';
import { DEFAULTS } from '../config.ts';
import { DisplayPreferences } from '../display_preferences.ts';
import { State } from '../state.ts';
import { Layers } from '../map/layers.ts';
import { MapSettings } from './settings.ts';
import { MapManagersMenu } from './managers_menu.ts';

const template = readFileSync('frontend_private/templates/pages/map_viewer.html', 'utf8');
type TestDialog = Omit<HTMLDialogElement, 'showModal' | 'close'> & { showModal: Mock<() => void>; close: Mock<() => void> };
let dialog: TestDialog;
let managers: { surveyStations: Mock; surfaceStations: Mock; landmarks: Mock };

beforeEach(() => {
    localStorage.clear();
    State.map = null;
    State.resetLayerState();
    DisplayPreferences.init({ persist: true });
    document.body.innerHTML = template;
    dialog = document.getElementById('map-settings-dialog') as TestDialog;
    // JSDOM does not emulate the top layer; browser checks cover native isolation.
    dialog.showModal = vi.fn(() => { dialog.open = true; });
    dialog.close = vi.fn(() => {
        dialog.open = false;
        dialog.dispatchEvent(new Event('close'));
    });
    managers = { surveyStations: vi.fn(), surfaceStations: vi.fn(), landmarks: vi.fn() };
    MapSettings.init({ managers });
});

afterEach(() => {
    MapSettings.destroy();
    DisplayPreferences.destroy();
    State.map = null;
    document.body.innerHTML = '';
    ViewerUpdates.cancelAll();
    vi.restoreAllMocks();
});

describe('private map Settings', () => {
    it('contains appearance, marker categories, and station types', () => {
        expect([...dialog.querySelectorAll<HTMLInputElement>('[data-category]')].map(input => input.dataset.category))
            .toEqual(['caveEntrances', 'surveyStations', 'surfaceStations', 'landmarks', 'explorationLeads', 'cylinders']);
        expect(dialog.querySelectorAll<HTMLInputElement>('[data-station-type]')).toHaveLength(DEFAULTS.DISPLAY.STATION_TYPES.length);
        for (const { id, label } of DEFAULTS.DISPLAY.CATEGORIES) {
            const input = dialog.querySelector<HTMLInputElement>(`[data-category="${id}"]`)!;
            expect(input.checked).toBe(true);
            expect(input.closest('label')!.textContent).toContain(label);
        }
        expect([...dialog.querySelectorAll<HTMLInputElement>('[name="map-settings-color-mode"]')].map(input => input.value))
            .toEqual(['project', 'depth', 'shot']);
        expect(dialog.querySelector<HTMLElement>('#map-settings-color-help')!).toBeNull();
        expect(dialog.querySelector<HTMLDetailsElement>('.map-settings-station-types')!.open).toBe(false);
        expect(dialog.querySelector<HTMLElement>('#map-settings-source')!).toBeNull();
        expect(dialog.querySelector<HTMLElement>('#station-manager-button')!).toBeNull();
        expect(dialog.querySelector<HTMLElement>('#map-settings-storage')!).toBeNull();
        expect(dialog.querySelector<HTMLElement>('.map-settings-dismiss')!.textContent).toBe('Close');
        expect(dialog.querySelector<HTMLElement>('#map-settings-reset')!.textContent).toBe('Reset');
    });

    it('selects and restores By Shot through the actual radio group and hides depth controls', () => {
        dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="depth"]')!.click();
        const shot = dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="shot"]')!;
        shot.click();
        expect(State.displayPreferences.colorMode).toBe('shot');
        expect(shot.checked).toBe(true);
        expect(dialog.querySelector<HTMLDetailsElement>('#map-settings-depth-limit')!.hidden).toBe(true);
        flushPreferenceWrites();
        expect((JSON.parse(localStorage.getItem(DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES)!) as DisplayPreferencesValue).colorMode).toBe('shot');
        MapSettings.destroy();
        DisplayPreferences.init({ persist: true });
        MapSettings.init({ managers });
        expect(shot.checked).toBe(true);
        MapSettings.reset();
        expect(shot.checked).toBe(false);
        expect(dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="project"]')!.checked).toBe(true);
    });

    it('opens with heading focus, preserves disclosure and scrolling, and returns focus on Close', () => {
        const trigger = document.getElementById('map-settings-button')!;
        trigger.click();
        expect(dialog.showModal).toHaveBeenCalledOnce();
        expect(trigger.getAttribute('aria-expanded')).toBe('true');
        expect(document.activeElement!.id).toBe('map-settings-title');
        dialog.querySelector<HTMLDetailsElement>('.map-settings-station-types')!.open = true;
        dialog.querySelector<HTMLElement>('.map-settings-body')!.scrollTop = 180;
        dialog.querySelector<HTMLElement>('.map-settings-dismiss')!.click();
        expect(dialog.open).toBe(false);
        expect(document.activeElement).toBe(trigger);
        expect(trigger.getAttribute('aria-expanded')).toBe('false');
        trigger.click();
        expect(dialog.querySelector<HTMLDetailsElement>('.map-settings-station-types')!.open).toBe(true);
        expect(dialog.querySelector<HTMLElement>('.map-settings-body')!.scrollTop).toBe(180);
    });

    it('wraps initial reverse Tab from its title to Close and forward Tab to the header close button', () => {
        MapSettings.open();
        const reverseTab = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
        document.activeElement!.dispatchEvent(reverseTab);
        expect(reverseTab.defaultPrevented).toBe(true);
        expect(document.activeElement).toBe(dialog.querySelector<HTMLElement>('.map-settings-dismiss')!);
        const forwardTab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
        document.activeElement!.dispatchEvent(forwardTab);
        expect(forwardTab.defaultPrevented).toBe(true);
        expect(document.activeElement).toBe(dialog.querySelector<HTMLElement>('.map-settings-close')!);
    });

    it('applies color and category changes immediately and persists them while staying open', () => {
        MapSettings.open();
        dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="depth"]')!.click();
        dialog.querySelector<HTMLInputElement>('[data-category="caveEntrances"]')!.click();
        dialog.querySelector<HTMLInputElement>('[data-category="landmarks"]')!.click();
        expect(State.displayPreferences.colorMode).toBe('depth');
        expect(State.displayPreferences.categories.caveEntrances).toBe(false);
        expect(State.displayPreferences.categories.landmarks).toBe(false);
        expect(dialog.open).toBe(true);
        flushPreferenceWrites();
        const saved = (JSON.parse(localStorage.getItem(DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES)!) as DisplayPreferencesValue);
        expect(saved.colorMode).toBe('depth');
        expect(saved.categories.caveEntrances).toBe(false);
        expect(saved.categories.landmarks).toBe(false);
    });

    it('preserves subtype selections when the station master is disabled and reenabled', () => {
        const sensor = dialog.querySelector<HTMLInputElement>('[data-station-type="sensor"]')!;
        sensor.click();
        const master = dialog.querySelector<HTMLInputElement>('[data-category="surveyStations"]')!;
        master.click();
        expect(dialog.querySelector<HTMLFieldSetElement>('.map-settings-types')!.disabled).toBe(true);
        expect(dialog.querySelector<HTMLElement>('#map-settings-type-count')!.textContent).toBe('Survey stations off');
        master.click();
        expect(dialog.querySelector<HTMLFieldSetElement>('.map-settings-types')!.disabled).toBe(false);
        expect(sensor.checked).toBe(false);
        expect(dialog.querySelector<HTMLInputElement>('[data-station-type="biology"]')!.checked).toBe(true);
        expect(dialog.querySelector<HTMLElement>('#map-settings-type-count')!.textContent).toContain('4 of 5');
    });

    it('reflects external reveal events without rebuilding controls or losing focus', () => {
        MapSettings.open();
        const landmarks = dialog.querySelector<HTMLInputElement>('[data-category="landmarks"]')!;
        landmarks.click();
        landmarks.focus();
        expect(document.activeElement).toBe(landmarks);
        Layers.revealCategory('landmarks');
        expect(landmarks.checked).toBe(true);
        expect(dialog.querySelector<HTMLInputElement>('[data-category="landmarks"]')!).toBe(landmarks);
        expect(document.activeElement).toBe(landmarks);
    });

    it('resets only display settings without touching source or individual selections', () => {
        localStorage.setItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE, 'esri-world-hillshade');
        State.projectLayerStates.set('project-1', false);
        State.gpsTrackLayerStates.set('track-1', true);
        State.gisGeometryStates.set('geometry-1', true);
        dialog.querySelector<HTMLInputElement>('[data-category="caveEntrances"]')!.click();
        dialog.querySelector<HTMLInputElement>('[data-category="landmarks"]')!.click();
        dialog.querySelector<HTMLInputElement>('[data-station-type="sensor"]')!.click();
        dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="depth"]')!.click();
        document.getElementById('map-settings-reset')!.click();
        expect(State.displayPreferences.colorMode).toBe('project');
        expect(Object.values(State.displayPreferences.categories).every(Boolean)).toBe(true);
        expect(Object.values(State.displayPreferences.stationTypes).every(Boolean)).toBe(true);
        expect(localStorage.getItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE)).toBe('esri-world-hillshade');
        expect(State.projectLayerStates.get('project-1')).toBe(false);
        expect(State.gpsTrackLayerStates.get('track-1')).toBe(true);
        expect(State.gisGeometryStates.get('geometry-1')).toBe(true);
    });

    it('prevents form shortcuts and Escape from reaching map keyboard handlers', () => {
        const handler = vi.fn();
        document.addEventListener('keydown', handler);
        MapSettings.open();
        dialog.querySelector<HTMLInputElement>('[data-category="landmarks"]')!.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Delete', bubbles: true, cancelable: true,
        }));
        dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
        expect(handler).not.toHaveBeenCalled();
        expect(dialog.open).toBe(false);
        document.removeEventListener('keydown', handler);
    });

    it('dismisses only a backdrop click, not blank space inside the dialog', () => {
        MapSettings.open();
        dialog.getBoundingClientRect = () => ({ left: 20, top: 20, right: 620, bottom: 700 } as DOMRect);
        dialog.dispatchEvent(new MouseEvent('click', { clientX: 40, clientY: 40, bubbles: true }));
        expect(dialog.open).toBe(true);
        dialog.dispatchEvent(new MouseEvent('click', { clientX: 10, clientY: 10, bubbles: true }));
        expect(dialog.open).toBe(false);
    });

    it('remains usable when browser persistence fails', () => {
        vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
        dialog.querySelector<HTMLInputElement>('[data-category="landmarks"]')!.click();
        expect(State.displayPreferences.categories.landmarks).toBe(false);
        flushPreferenceWrites();
        expect(DisplayPreferences.storageAvailable).toBe(false);
    });

    it('closes Managers before opening Settings', () => {
        MapManagersMenu.open();
        MapSettings.open();
        expect(document.getElementById('map-managers-menu')!.hidden).toBe(true);
        expect(document.getElementById('map-managers-button')!.getAttribute('aria-expanded')).toBe('false');
        expect(dialog.open).toBe(true);
    });

    it('reinitializes without duplicate listeners and removes handlers on destruction', () => {
        MapSettings.init({ managers });
        document.getElementById('station-manager-button')!.click();
        expect(managers.surveyStations).toHaveBeenCalledOnce();
        const trigger = document.getElementById('map-settings-button')!;
        MapSettings.destroy();
        trigger.click();
        expect(dialog.showModal).not.toHaveBeenCalled();
        document.getElementById('station-manager-button')!.click();
        expect(managers.surveyStations).toHaveBeenCalledOnce();
    });
});

describe('private depth limit controls', () => {
    type DepthControls = { value: HTMLInputElement; limit: HTMLDetailsElement; summary: HTMLElement; error: HTMLElement; clear: HTMLButtonElement };
    const control = <Key extends keyof DepthControls>(id: Key) => dialog.querySelector(`#map-settings-depth-${id}`) as DepthControls[Key];
    const chooseUnit = (unit: string) => dialog.querySelector<HTMLInputElement>(`[name="map-settings-depth-unit"][value="${unit}"]`)!.click();
    const draft = (value: string) => {
        control('value').value = value;
        control('value').dispatchEvent(new Event('input', { bubbles: true }));
    };
    const commit = (value: string) => {
        draft(value);
        control('value').dispatchEvent(new Event('change', { bubbles: true }));
    };

    beforeEach(() => {
        MapSettings.open();
    });

    it('is initially hidden, reveals a collapsed disclosure only in depth mode, and preserves the cap across modes', () => {
        expect(control('limit').hidden).toBe(true);
        dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="depth"]')!.click();
        expect(control('limit').hidden).toBe(false);
        expect(control('limit').open).toBe(false);
        expect(control('summary').textContent).toBe('Full range');
        control('limit').open = true;
        commit('100');
        expect(control('summary').textContent).toBe('100 ft');
        expect(control('limit').classList.contains('has-limit')).toBe(true);
        dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="project"]')!.click();
        expect(control('limit').hidden).toBe(true);
        dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="depth"]')!.click();
        expect(control('value').value).toBe('100');
        expect(State.displayPreferences.depthLimitFeet).toBe(100);
    });

    it('validates while typing and applies once on Enter without forwarding map shortcuts', () => {
        void Layers.setColorMode('depth');
        const setter = vi.spyOn(Layers, 'setDepthLimit');
        const mapShortcut = vi.fn();
        document.addEventListener('keydown', mapShortcut);
        draft('1');
        draft('12');
        draft('125.5');
        expect(setter).not.toHaveBeenCalled();
        expect(State.displayPreferences.depthLimitFeet).toBeNull();
        const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
        control('value').dispatchEvent(enter);
        control('value').dispatchEvent(new Event('change', { bubbles: true }));
        expect(enter.defaultPrevented).toBe(true);
        expect(mapShortcut).not.toHaveBeenCalled();
        expect(setter).toHaveBeenCalledExactlyOnceWith(125.5, 'ft');
        expect(State.displayPreferences.depthLimitFeet).toBe(125.5);
        expect(dialog.open).toBe(true);
        document.removeEventListener('keydown', mapShortcut);
    });

    it('converts the field on unit changes without cumulative rounding drift', () => {
        const feet = 123.456789012345;
        Layers.setDepthLimit(feet, 'ft');
        for (let i = 0; i < 20; i++) {
            chooseUnit('m');
            expect(Number(control('value').value)).toBeCloseTo(feet * 0.3048, 9);
            chooseUnit('ft');
            expect(State.displayPreferences.depthLimitFeet).toBe(feet);
        }
        expect(control('summary').textContent).toBe('123.456789012 ft');
    });

    it('commits a pending draft in its original unit before switching units', () => {
        draft('100');
        chooseUnit('m');
        expect(State.displayPreferences.depthLimitFeet).toBe(100);
        expect(control('value').value).toBe('30.48');
        commit('12.5');
        expect(State.displayPreferences.depthLimitFeet).toBeCloseTo(12.5 / 0.3048, 10);
        expect(control('summary').textContent).toBe('12.5 m');
    });

    it.each(['0', '-1', '-0.01'])('rejects %s without changing the cap and preserves the draft during unrelated changes', value => {
        dialog.querySelector<HTMLInputElement>('[name="map-settings-color-mode"][value="depth"]')!.click();
        control('limit').querySelector('summary')!.click();
        Layers.setDepthLimit(100, 'ft');
        commit(value);
        expect(State.displayPreferences.depthLimitFeet).toBe(100);
        expect(control('error').hidden).toBe(false);
        expect(control('value').getAttribute('aria-invalid')).toBe('true');
        control('value').focus();
        expect(document.activeElement).toBe(control('value'));
        void Layers.setCategoryVisibility('landmarks', false);
        expect(control('value').value).toBe(value);
        expect(document.activeElement).toBe(control('value'));
        chooseUnit('m');
        expect(State.displayPreferences.depthUnit).toBe('ft');
        expect(dialog.querySelector<HTMLInputElement>('[name="map-settings-depth-unit"][value="ft"]')!.checked).toBe(true);
        expect(control('value').value).toBe(value);
    });

    it('rejects overflowing meter conversion and accepts a corrected fractional limit', () => {
        chooseUnit('m');
        commit('1e308');
        expect(State.displayPreferences.depthLimitFeet).toBeNull();
        expect(control('error').hidden).toBe(false);
        commit('0.125');
        expect(State.displayPreferences.depthLimitFeet).toBeCloseTo(0.125 / 0.3048, 10);
        expect(control('error').hidden).toBe(true);
        expect(control('value').validity.valid).toBe(true);
    });

    it('does not treat an incomplete browser number as an empty limit', () => {
        Layers.setDepthLimit(100, 'ft');
        // Browsers expose value="" with badInput=true while typing "-" or "e".
        draft('');
        const validity = vi.spyOn(control('value'), 'validity', 'get')
            .mockReturnValue({ badInput: true } as ValidityState);
        control('value').dispatchEvent(new Event('change', { bubbles: true }));
        expect(State.displayPreferences.depthLimitFeet).toBe(100);
        expect(control('error').hidden).toBe(false);
        validity.mockRestore();
        commit('');
        expect(State.displayPreferences.depthLimitFeet).toBeNull();
    });

    it('clears a limit or invalid draft and retains selected units for automatic depth labels', () => {
        chooseUnit('m');
        commit('20');
        expect(control('clear').hidden).toBe(false);
        control('clear').click();
        expect(State.displayPreferences.depthLimitFeet).toBeNull();
        expect(State.displayPreferences.depthUnit).toBe('m');
        expect(control('value').value).toBe('');
        expect(control('summary').textContent).toBe('Full range');
        expect(control('clear').hidden).toBe(true);
        draft('-20');
        control('clear').click();
        expect(control('error').hidden).toBe(true);
        expect(control('value').getAttribute('aria-invalid')).toBe('false');
    });

    it('persists valid changes, restores on reload, and resets limit, units and disclosure', () => {
        void Layers.setColorMode('depth');
        chooseUnit('m');
        commit('30');
        flushPreferenceWrites();
        const stored = (JSON.parse(localStorage.getItem(DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES)!) as DisplayPreferencesValue);
        expect(stored.depthLimitFeet).toBeCloseTo(30 / 0.3048, 10);
        expect(stored.depthUnit).toBe('m');
        DisplayPreferences.init({ persist: true });
        MapSettings.sync();
        expect(control('value').value).toBe('30');
        expect(control('summary').textContent).toBe('30 m');
        control('limit').open = true;
        draft('-1');
        document.getElementById('map-settings-reset')!.click();
        expect(State.displayPreferences.depthLimitFeet).toBeNull();
        expect(State.displayPreferences.depthUnit).toBe('ft');
        expect(control('limit').hidden).toBe(true);
        expect(control('limit').open).toBe(false);
        expect(control('error').hidden).toBe(true);
        expect(control('value').value).toBe('');
    });
});


it('shows the newest switch intent while map application is pending', async () => {
    MapSettings.open();
    let finish!: () => void;
    vi.spyOn(Layers, 'whenDisplayApplied').mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const input = dialog.querySelector<HTMLInputElement>('[data-category="landmarks"]')!;
    input.focus();
    expect(document.activeElement).toBe(input);
    input.click();
    expect(input.checked).toBe(false);
    expect(input.disabled).toBe(false);
    expect(dialog.getAttribute('aria-busy')).toBe('true');
    input.click();
    expect(input.checked).toBe(true);
    expect(State.displayPreferences.categories.landmarks).toBe(true);
    expect(document.activeElement).toBe(input);
    finish();
    await vi.waitFor(() => expect(dialog.hasAttribute('aria-busy')).toBe(false));
    expect(dialog.querySelector<HTMLInputElement>('[data-category="landmarks"]')!).toBe(input);
});

it('tears down listeners before a repeated init with missing dialog markup', () => {
    const listeners = MapSettings.listeners;
    const revision = MapSettings.applyRevision;
    document.body.innerHTML = '';
    MapSettings.init();
    expect(MapSettings.listeners).not.toBe(listeners);
    expect(MapSettings.listeners).toHaveLength(0);
    expect(MapSettings.applyRevision).toBe(revision + 1);
    expect(MapSettings.dialog).toBeNull();
    expect(MapSettings.trigger).toBeNull();
});
