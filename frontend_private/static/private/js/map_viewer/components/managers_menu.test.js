import { MapManagersMenu } from './managers_menu.js';

let menu;
let trigger;
let managers;

beforeEach(() => {
    document.body.innerHTML = `<button id="map-managers-button">Managers</button><button id="map-settings-button">Settings</button>
        <div id="map-managers-menu" role="menu" hidden>
            <button id="station-manager-button" role="menuitem" tabindex="-1">Survey Stations</button>
            <button id="surface-station-manager-button" role="menuitem" tabindex="-1">Surface Stations</button>
            <button id="landmark-manager-button" role="menuitem" tabindex="-1">Landmarks</button>
        </div>`;
    menu = document.getElementById('map-managers-menu');
    trigger = document.getElementById('map-managers-button');
    managers = { surveyStations: vi.fn(), surfaceStations: vi.fn(), landmarks: vi.fn() };
    MapManagersMenu.init({ managers });
});

afterEach(() => { MapManagersMenu.destroy(); document.body.innerHTML = ''; });

function key(key, shiftKey = false) {
    document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true }));
}

it('supports arrow navigation, wrapping, Home/End, and Escape focus return', () => {
    trigger.click();
    expect(menu.hidden).toBe(false);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(document.activeElement.id).toBe('station-manager-button');
    key('ArrowUp');
    expect(document.activeElement.id).toBe('landmark-manager-button');
    key('ArrowDown');
    expect(document.activeElement.id).toBe('station-manager-button');
    key('End');
    expect(document.activeElement.id).toBe('landmark-manager-button');
    key('Home');
    expect(document.activeElement.id).toBe('station-manager-button');
    key('Escape');
    expect(menu.hidden).toBe(true);
    expect(document.activeElement).toBe(trigger);
});

it('opens the last item with ArrowUp and exits with Tab to the next toolbar action', () => {
    trigger.focus();
    key('ArrowUp');
    expect(document.activeElement.id).toBe('landmark-manager-button');
    key('Tab');
    expect(menu.hidden).toBe(true);
    expect(document.activeElement.id).toBe('map-settings-button');
    trigger.click();
    key('Tab', true);
    expect(document.activeElement).toBe(trigger);
});

it.each([
    ['station-manager-button', 'surveyStations'],
    ['surface-station-manager-button', 'surfaceStations'],
    ['landmark-manager-button', 'landmarks'],
])('closes the menu before launching %s', (id, manager) => {
    managers[manager].mockImplementation(() => expect(menu.hidden).toBe(true));
    trigger.click();
    document.getElementById(id).click();
    expect(managers[manager]).toHaveBeenCalledOnce();
});

it('dismisses on an outside pointer without stealing focus or responding to an internal pointer', () => {
    trigger.click();
    document.getElementById('station-manager-button').dispatchEvent(new Event('pointerdown', { bubbles: true }));
    expect(menu.hidden).toBe(false);
    const settings = document.getElementById('map-settings-button');
    settings.focus();
    settings.dispatchEvent(new Event('pointerdown', { bubbles: true }));
    expect(menu.hidden).toBe(true);
    expect(document.activeElement).toBe(settings);
});

it('reinitializes without duplicate callbacks and removes listeners on destroy', () => {
    MapManagersMenu.init({ managers });
    trigger.click();
    document.getElementById('station-manager-button').click();
    expect(managers.surveyStations).toHaveBeenCalledOnce();
    MapManagersMenu.destroy();
    trigger.click();
    expect(menu.hidden).toBe(true);
    document.getElementById('station-manager-button').click();
    expect(managers.surveyStations).toHaveBeenCalledOnce();
});
