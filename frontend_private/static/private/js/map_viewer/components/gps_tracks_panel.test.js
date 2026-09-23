import { Config } from '../config.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';
import { GPSTracksPanel } from './gps_tracks_panel.js';
import { beginMapNavigation, resetMapNavigation } from '../map/navigation_intent.js';

vi.mock('../map/layers.js', () => ({ Layers: {
    isGPSTrackVisible: vi.fn(),
    isGPSTrackLoading: vi.fn(() => false),
    toggleGPSTrackVisibility: vi.fn(),
} }));

beforeEach(() => {
    globalThis.ResizeObserver = class { observe() {} disconnect() {} };
    document.body.innerHTML = '<div><div id="map"></div></div>';
    State.resetLayerState();
    State.map = { fitBounds: vi.fn() };
    Config._gpsTracks = [{ id: 'one', name: 'Track', color: '#123456', file: '/one' }];
    Layers.isGPSTrackVisible.mockImplementation(id => State.gpsTrackLayerStates.get(id) === true);
    Layers.toggleGPSTrackVisibility.mockImplementation(async (id, visible) => {
        State.gpsTrackLayerStates.set(id, visible);
        return true;
    });
});
afterEach(() => {
    GPSTracksPanel.destroy();
    resetMapNavigation();
    State.map = null;
    Config._gpsTracks = null;
    vi.clearAllMocks();
});

it('shows intent immediately and preserves a usable focused switch during load and reversal', async () => {
    let finish;
    Layers.toggleGPSTrackVisibility.mockImplementationOnce((id, visible) => {
        State.gpsTrackLayerStates.set(id, visible);
        return new Promise(resolve => { finish = resolve; });
    });
    GPSTracksPanel.init();
    const toggle = document.querySelector('.gps-track-button input');
    toggle.focus();
    toggle.click();
    expect(toggle.checked).toBe(true);
    expect(toggle.disabled).toBe(false);
    expect(document.querySelector('.gps-track-button').getAttribute('aria-busy')).toBe('true');
    toggle.click();
    expect(toggle.checked).toBe(false);
    finish(false);
    await vi.waitFor(() => expect(GPSTracksPanel._requests.size).toBe(0));
    expect(document.querySelector('.gps-track-button input')).toBe(toggle);
    expect(document.activeElement).toBe(toggle);
    expect(toggle.checked).toBe(false);
    expect(State.map.fitBounds).not.toHaveBeenCalled();
});

it.each(['hide', 'new-navigation', 'destroy'])('cancels a delayed locate after %s', async reason => {
    let finish;
    Layers.toggleGPSTrackVisibility.mockImplementationOnce((id, visible) => {
        State.gpsTrackLayerStates.set(id, visible);
        return new Promise(resolve => { finish = resolve; });
    });
    State.gpsTrackBounds.set('one', { bounds: true });
    GPSTracksPanel.init();
    const locating = GPSTracksPanel.activateAndFlyToTrack('one');
    if (reason === 'hide') await GPSTracksPanel.toggleTrack('one', false);
    if (reason === 'new-navigation') beginMapNavigation(State.map, 'project:other');
    if (reason === 'destroy') GPSTracksPanel.destroy();
    finish(true);
    await locating;
    expect(State.map.fitBounds).not.toHaveBeenCalled();
});
