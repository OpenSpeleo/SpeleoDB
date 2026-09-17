import { readFileSync } from 'node:fs';
import { DEFAULTS } from '../config.js';
import { DisplayPreferences } from '../display_preferences.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';
import { MapSettings } from './settings.js';
import { MapManagersMenu } from './managers_menu.js';

const template = readFileSync('frontend_private/templates/pages/map_viewer.html', 'utf8');
let dialog;
let managers;

beforeEach(() => {
    localStorage.clear();
    State.map = null;
    State.resetLayerState();
    DisplayPreferences.init({ persist: true });
    document.body.innerHTML = template;
    dialog = document.getElementById('map-settings-dialog');
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
    vi.restoreAllMocks();
});

describe('private map Settings', () => {
    it('contains only color mode, marker categories, and station types', () => {
        expect([...dialog.querySelectorAll('[data-category]')].map(input => input.dataset.category))
            .toEqual(['surveyStations', 'surfaceStations', 'landmarks', 'explorationLeads', 'cylinders']);
        expect(dialog.querySelectorAll('[data-station-type]')).toHaveLength(DEFAULTS.DISPLAY.STATION_TYPES.length);
        for (const { id, label } of DEFAULTS.DISPLAY.CATEGORIES) {
            const input = dialog.querySelector(`[data-category="${id}"]`);
            expect(input.checked).toBe(true);
            expect(input.closest('label').textContent).toContain(label);
        }
        expect(dialog.querySelector('.map-settings-station-types').open).toBe(false);
        expect(dialog.querySelector('#map-settings-source')).toBeNull();
        expect(dialog.querySelector('#station-manager-button')).toBeNull();
        expect(dialog.querySelector('#map-settings-storage')).toBeNull();
        expect(dialog.querySelector('.map-settings-dismiss').textContent).toBe('Close');
        expect(dialog.querySelector('#map-settings-reset').textContent).toBe('Reset');
    });

    it('opens with heading focus, preserves disclosure and scrolling, and returns focus on Close', () => {
        const trigger = document.getElementById('map-settings-button');
        trigger.click();
        expect(dialog.showModal).toHaveBeenCalledOnce();
        expect(trigger.getAttribute('aria-expanded')).toBe('true');
        expect(document.activeElement.id).toBe('map-settings-title');
        dialog.querySelector('.map-settings-station-types').open = true;
        dialog.querySelector('.map-settings-body').scrollTop = 180;
        dialog.querySelector('.map-settings-dismiss').click();
        expect(dialog.open).toBe(false);
        expect(document.activeElement).toBe(trigger);
        expect(trigger.getAttribute('aria-expanded')).toBe('false');
        trigger.click();
        expect(dialog.querySelector('.map-settings-station-types').open).toBe(true);
        expect(dialog.querySelector('.map-settings-body').scrollTop).toBe(180);
    });

    it('wraps initial reverse Tab from its title to Close and forward Tab to the header close button', () => {
        MapSettings.open();
        const reverseTab = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
        document.activeElement.dispatchEvent(reverseTab);
        expect(reverseTab.defaultPrevented).toBe(true);
        expect(document.activeElement).toBe(dialog.querySelector('.map-settings-dismiss'));
        const forwardTab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
        document.activeElement.dispatchEvent(forwardTab);
        expect(forwardTab.defaultPrevented).toBe(true);
        expect(document.activeElement).toBe(dialog.querySelector('.map-settings-close'));
    });

    it('applies color and category changes immediately and persists them while staying open', () => {
        MapSettings.open();
        dialog.querySelector('[name="map-settings-color-mode"][value="depth"]').click();
        dialog.querySelector('[data-category="landmarks"]').click();
        expect(State.displayPreferences.colorMode).toBe('depth');
        expect(State.displayPreferences.categories.landmarks).toBe(false);
        expect(dialog.open).toBe(true);
        const saved = JSON.parse(localStorage.getItem(DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES));
        expect(saved.colorMode).toBe('depth');
        expect(saved.categories.landmarks).toBe(false);
    });

    it('preserves subtype selections when the station master is disabled and reenabled', () => {
        const sensor = dialog.querySelector('[data-station-type="sensor"]');
        sensor.click();
        const master = dialog.querySelector('[data-category="surveyStations"]');
        master.click();
        expect(dialog.querySelector('.map-settings-types').disabled).toBe(true);
        expect(dialog.querySelector('#map-settings-type-count').textContent).toBe('Survey stations off');
        master.click();
        expect(dialog.querySelector('.map-settings-types').disabled).toBe(false);
        expect(sensor.checked).toBe(false);
        expect(dialog.querySelector('[data-station-type="biology"]').checked).toBe(true);
        expect(dialog.querySelector('#map-settings-type-count').textContent).toContain('4 of 5');
    });

    it('reflects external reveal events without rebuilding controls or losing focus', () => {
        const landmarks = dialog.querySelector('[data-category="landmarks"]');
        landmarks.click();
        landmarks.focus();
        Layers.revealCategory('landmarks');
        expect(landmarks.checked).toBe(true);
        expect(dialog.querySelector('[data-category="landmarks"]')).toBe(landmarks);
        expect(document.activeElement).toBe(landmarks);
    });

    it('resets only display settings without touching source or individual selections', () => {
        localStorage.setItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE, 'esri-world-hillshade');
        State.projectLayerStates.set('project-1', false);
        State.gpsTrackLayerStates.set('track-1', true);
        State.gisGeometryStates.set('geometry-1', true);
        dialog.querySelector('[data-category="landmarks"]').click();
        dialog.querySelector('[data-station-type="sensor"]').click();
        dialog.querySelector('[name="map-settings-color-mode"][value="depth"]').click();
        document.getElementById('map-settings-reset').click();
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
        dialog.querySelector('[data-category="landmarks"]').dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Delete', bubbles: true, cancelable: true,
        }));
        dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
        expect(handler).not.toHaveBeenCalled();
        expect(dialog.open).toBe(false);
        document.removeEventListener('keydown', handler);
    });

    it('dismisses only a backdrop click, not blank space inside the dialog', () => {
        MapSettings.open();
        dialog.getBoundingClientRect = () => ({ left: 20, top: 20, right: 620, bottom: 700 });
        dialog.dispatchEvent(new MouseEvent('click', { clientX: 40, clientY: 40, bubbles: true }));
        expect(dialog.open).toBe(true);
        dialog.dispatchEvent(new MouseEvent('click', { clientX: 10, clientY: 10, bubbles: true }));
        expect(dialog.open).toBe(false);
    });

    it('remains usable when browser persistence fails', () => {
        vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
        dialog.querySelector('[data-category="landmarks"]').click();
        expect(State.displayPreferences.categories.landmarks).toBe(false);
        expect(DisplayPreferences.storageAvailable).toBe(false);
    });

    it('closes Managers before opening Settings', () => {
        MapManagersMenu.open();
        MapSettings.open();
        expect(document.getElementById('map-managers-menu').hidden).toBe(true);
        expect(document.getElementById('map-managers-button').getAttribute('aria-expanded')).toBe('false');
        expect(dialog.open).toBe(true);
    });

    it('reinitializes without duplicate listeners and removes handlers on destruction', () => {
        MapSettings.init({ managers });
        document.getElementById('station-manager-button').click();
        expect(managers.surveyStations).toHaveBeenCalledOnce();
        const trigger = document.getElementById('map-settings-button');
        MapSettings.destroy();
        trigger.click();
        expect(dialog.showModal).not.toHaveBeenCalled();
        document.getElementById('station-manager-button').click();
        expect(managers.surveyStations).toHaveBeenCalledOnce();
    });
});
