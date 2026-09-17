import { openMapDialog, closeMapDialog } from './dialog_lifecycle.js';
import { getMapOverlayHost, isMapDialogOpen } from './overlay_host.js';
import { Modal } from './modal.js';
import { StationUI } from '../stations/ui.js';
import { SurfaceStationUI } from '../surface_stations/ui.js';
import { LandmarkUI } from '../landmarks/ui.js';
import { State, createDefaultDisplayPreferences } from '../state.js';
import { Config } from '../config.js';
import { StationDetails, configureStationManagerNavigation, returnToStationManager } from '../stations/details.js';
import { StationTags } from '../stations/tags.js';

beforeEach(() => {
    document.body.innerHTML = '<main id="other-content"></main><section id="map-viewer-shell"><button id="map-managers-button">Managers</button><div id="map"></div></section>';
    State.resetLayerState();
    State.displayPreferences = createDefaultDisplayPreferences();
    State.userTags = [];
    State.tagColors = [];
    Config._projects = [];
    Config._networks = [];
});

afterEach(() => {
    document.querySelectorAll('[role="dialog"]').forEach(element => closeMapDialog(element));
    Config._projects = null;
    Config._networks = null;
    configureStationManagerNavigation({});
    document.body.innerHTML = '';
});

it.each(['subsurface', 'surface'])('returns %s details through injected navigation without a hidden button', async type => {
    document.getElementById('map-viewer-shell').insertAdjacentHTML('beforeend', '<div id="station-modal" class="hidden"><h2 id="station-modal-title">Station details</h2><button id="station-modal-close"></button><div id="station-modal-content"></div></div>');
    const handlers = { subsurface: vi.fn(), surface: vi.fn() };
    configureStationManagerNavigation(handlers);
    await StationDetails.openModal(null, null, false, type, { fromManager: true });
    expect(document.getElementById('station-modal-title').textContent).toContain('Station Details');
    returnToStationManager();
    expect(handlers[type]).toHaveBeenCalledOnce();
    expect(handlers[type === 'surface' ? 'subsurface' : 'surface']).not.toHaveBeenCalled();
    expect(document.getElementById('station-modal').classList.contains('hidden')).toBe(true);
});

it('hosts dialogs inside fullscreen, isolates the background, traps focus, and restores it', () => {
    const trigger = document.getElementById('map-managers-button');
    trigger.focus();
    const dialog = document.createElement('div');
    dialog.id = 'test-modal';
    dialog.innerHTML = '<h2>Map dialog</h2><button id="close">Close</button><input aria-label="Name"><button id="last">Done</button>';
    document.body.append(dialog);
    openMapDialog(dialog, { closeButton: '#close' });
    expect(getMapOverlayHost().contains(dialog)).toBe(true);
    expect(dialog.getAttribute('aria-labelledby')).toBe('test-modal-title');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(document.getElementById('other-content').inert).toBe(true);
    expect(document.activeElement.id).toBe('close');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
    expect(document.activeElement.id).toBe('last');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    expect(document.activeElement.id).toBe('close');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    expect(dialog.classList.contains('hidden')).toBe(true);
    expect(document.getElementById('other-content').inert).not.toBe(true);
    expect(document.activeElement).toBe(trigger);
    expect(isMapDialogOpen()).toBe(false);
});

it('honors a live dismissal guard for buttons, Escape, backdrop, direct close, and reopening', () => {
    const dialog = document.createElement('div');
    dialog.id = 'guarded-modal';
    dialog.innerHTML = '<h2>Import</h2><button id="guarded-close">Close</button>';
    document.body.append(dialog);
    let busy = true;
    openMapDialog(dialog, { closeButton: '#guarded-close', canDismiss: () => !busy });
    document.getElementById('guarded-close').click();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    dialog.click();
    closeMapDialog(dialog);
    openMapDialog(dialog);
    expect(dialog.classList.contains('hidden')).toBe(false);
    expect(document.getElementById('other-content').inert).toBe(true);
    busy = false;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(dialog.classList.contains('hidden')).toBe(true);
    expect(document.getElementById('other-content').inert).not.toBe(true);
});

it('preserves an upload form on backdrop clicks while allowing explicit dismissal', () => {
    const dialog = document.createElement('div');
    dialog.id = 'upload-modal';
    dialog.innerHTML = '<h2>Import</h2><input value="Selected file">';
    document.body.append(dialog);
    openMapDialog(dialog, { dismissOnBackdrop: false });
    dialog.click();
    expect(dialog.classList.contains('hidden')).toBe(false);
    expect(dialog.querySelector('input').value).toBe('Selected file');
    closeMapDialog(dialog);
    expect(dialog.classList.contains('hidden')).toBe(true);
});

it('suspends a parent dialog for its child and Escape closes only the child', () => {
    Modal.open('parent-modal', Modal.base('parent-modal', 'Parent', '<button id="child-trigger">Open child</button>'));
    document.getElementById('child-trigger').focus();
    Modal.open('child-modal', Modal.base('child-modal', 'Child', '<input aria-label="Child input">'));
    expect(document.getElementById('parent-modal').inert).toBe(true);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(document.getElementById('child-modal')).toBeNull();
    expect(document.getElementById('parent-modal').classList.contains('hidden')).toBe(false);
    expect(document.activeElement.id).toBe('child-trigger');
    Modal.close('parent-modal');
    expect(isMapDialogOpen()).toBe(false);
});

it('restores focus inside the parent when refreshed content removed the child trigger', () => {
    Modal.open('parent-modal', Modal.base('parent-modal', 'Parent', '<button id="child-trigger">Open child</button>'));
    document.getElementById('child-trigger').focus();
    Modal.open('child-modal', Modal.base('child-modal', 'Child', '<input aria-label="Child input">'));
    document.getElementById('child-trigger').remove();
    Modal.close('child-modal');
    expect(document.activeElement).toBe(document.querySelector('#parent-modal [data-close-modal]'));
    expect(document.getElementById('parent-modal').inert).not.toBe(true);
    expect(document.getElementById('map-managers-button').inert).toBe(true);
    Modal.close('parent-modal');
    expect(document.activeElement.id).toBe('map-managers-button');
});

it('isolates tag selector and creation overlays and resumes the station dialog afterward', () => {
    Modal.open('parent-modal', Modal.base('parent-modal', 'Station details', '<button id="tag-trigger">Tags</button>'));
    State.allStations.set('s1', { id: 's1', name: 'Station', tag: null });
    document.getElementById('tag-trigger').focus();
    StationTags.openTagSelector('s1');
    const selector = document.getElementById('tag-selector-overlay');
    expect(selector.getAttribute('role')).toBe('dialog');
    expect(selector.contains(document.activeElement)).toBe(true);
    expect(document.getElementById('parent-modal').inert).toBe(true);
    StationTags.openTagCreationModal();
    const creation = document.getElementById('tag-creation-overlay');
    expect(selector.isConnected).toBe(false);
    expect(creation.contains(document.activeElement)).toBe(true);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(creation.isConnected).toBe(false);
    expect(document.getElementById('parent-modal').inert).not.toBe(true);
    expect(document.activeElement.id).toBe('tag-trigger');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: false, bubbles: true, cancelable: true }));
    expect(document.activeElement.closest('#parent-modal')).not.toBeNull();
    Modal.close('parent-modal');
    expect(document.getElementById('other-content').inert).not.toBe(true);
});

it('recognizes native Settings and legacy import overlays for editor isolation', () => {
    const native = document.createElement('dialog');
    native.open = true;
    document.body.append(native);
    expect(isMapDialogOpen()).toBe(true);
    native.remove();
    document.body.insertAdjacentHTML('beforeend', '<div id="import-modal" class="fixed inset-0"></div>');
    expect(isMapDialogOpen()).toBe(true);
    document.getElementById('import-modal').classList.add('hidden');
    expect(isMapDialogOpen()).toBe(false);
});

it('recognizes the Managers menu for editor keyboard isolation only while open', () => {
    document.getElementById('map-viewer-shell').insertAdjacentHTML('beforeend', '<div id="map-managers-menu" role="menu" hidden><button role="menuitem">Survey stations</button></div>');
    const menu = document.getElementById('map-managers-menu');
    expect(isMapDialogOpen()).toBe(false);
    menu.hidden = false;
    expect(isMapDialogOpen()).toBe(true);
    menu.hidden = true;
    expect(isMapDialogOpen()).toBe(false);
});

it.each([
    ['station', StationUI], ['surface-station', SurfaceStationUI], ['landmark', LandmarkUI],
])('opens and closes the %s manager with accessible focus on every visit', (prefix, ui) => {
    document.getElementById('map-viewer-shell').insertAdjacentHTML('beforeend', `<div id="${prefix}-manager-modal" class="hidden"><h2>Manager</h2><button id="${prefix}-manager-close"></button><div id="${prefix}-manager-content"></div></div>`);
    const modal = document.getElementById(`${prefix}-manager-modal`);
    for (let visit = 0; visit < 2; visit += 1) {
        ui.openManagerModal();
        expect(document.activeElement.id).toBe(`${prefix}-manager-close`);
        expect(document.activeElement.getAttribute('aria-label')).toBe('Close dialog');
        expect(modal.getAttribute('role')).toBe('dialog');
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        expect(modal.classList.contains('hidden')).toBe(true);
        expect(document.activeElement.id).toBe('map-managers-button');
    }
});
