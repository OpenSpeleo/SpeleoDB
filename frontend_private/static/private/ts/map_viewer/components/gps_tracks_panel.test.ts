import type { Mock } from 'vitest';
import type { ViewerState } from '../../../../../../ts-types/domain/map-state.ts';
import type { CameraBounds } from '../../../../../../ts-types/domain/map-geometry.ts';
import { Config } from '../config.ts';
import { State } from '../state.ts';
import { Layers as RuntimeLayers } from '../map/layers.ts';
import { GPSTracksPanel } from './gps_tracks_panel.ts';
import { beginMapNavigation, resetMapNavigation } from '../map/navigation_intent.ts';

type MockFunctions<Owner> = { [Key in keyof Owner]: Owner[Key] extends (...args: infer Args) => infer Result ? Mock<(...args: Args) => Result> : Owner[Key] };
const Layers = RuntimeLayers as MockFunctions<typeof RuntimeLayers>;
let map: { fitBounds: Mock };

vi.mock('../map/layers.ts', () => ({ Layers: {
    isGPSTrackVisible: vi.fn(),
    isGPSTrackLoading: vi.fn(() => false),
    toggleGPSTrackVisibility: vi.fn(),
} }));

beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
    document.body.innerHTML = '<div><div id="map"></div></div>';
    State.resetLayerState();
    map = { fitBounds: vi.fn() };
    // This camera-only fixture never invokes the remaining map capabilities.
    State.map = map as unknown as ViewerState['map'];
    Config._gpsTracks = [{ id: 'one', name: 'Track', color: '#123456', file: '/one' }];
    Layers.isGPSTrackVisible.mockImplementation(id => State.gpsTrackLayerStates.get(String(id)) === true);
    Layers.toggleGPSTrackVisibility.mockImplementation(async (id, visible) => {
        State.gpsTrackLayerStates.set(String(id), visible);
        return true;
    });
});
afterEach(() => {
    GPSTracksPanel.destroy();
    resetMapNavigation();
    State.map = null;
    Config._gpsTracks = null;
    vi.unstubAllGlobals();
    vi.clearAllMocks();
});

it('skips rendering when no tracks exist and clears retained registries on teardown', () => {
    Config._gpsTracks = [];
    const rows = GPSTracksPanel._rows;
    const requests = GPSTracksPanel._requests;
    GPSTracksPanel.init();
    expect(document.getElementById('gps-tracks-panel')!).toBeNull();
    expect(GPSTracksPanel._rows).toBe(rows);
    expect(GPSTracksPanel._requests).toBe(requests);
    expect(rows.size).toBe(0);
    expect(requests.size).toBe(0);
});

it('disconnects observers and removes its loading listener without removing panel DOM', () => {
    GPSTracksPanel.init();
    const disconnect = vi.spyOn(GPSTracksPanel._resizeObserver!, 'disconnect');
    const row = document.querySelector<HTMLElement>('.gps-track-button')!;
    const update = vi.spyOn(GPSTracksPanel, 'updateRow');
    GPSTracksPanel.destroy();
    window.dispatchEvent(new CustomEvent('speleo:gps-track-loading-changed', { detail: { trackId: 'one' } }));
    expect(disconnect).toHaveBeenCalledOnce();
    expect(update).not.toHaveBeenCalled();
    expect(row.isConnected).toBe(true);
    update.mockRestore();
});

it('shows intent immediately and preserves a usable focused switch during load and reversal', async () => {
    let finish!: (result: boolean) => void;
    Layers.toggleGPSTrackVisibility.mockImplementationOnce((id, visible) => {
        State.gpsTrackLayerStates.set(String(id), visible);
        return new Promise(resolve => { finish = resolve; });
    });
    GPSTracksPanel.init();
    document.getElementById('gps-panel-expand')!.click();
    const toggle = document.querySelector<HTMLInputElement>('.gps-track-button input')!;
    toggle.focus();
    expect(document.activeElement).toBe(toggle);
    toggle.click();
    expect(toggle.checked).toBe(true);
    expect(toggle.disabled).toBe(false);
    expect(document.querySelector<HTMLElement>('.gps-track-button')!.getAttribute('aria-busy')).toBe('true');
    toggle.click();
    expect(toggle.checked).toBe(false);
    finish(false);
    await vi.waitFor(() => expect(GPSTracksPanel._requests.size).toBe(0));
    expect(document.querySelector<HTMLInputElement>('.gps-track-button input')!).toBe(toggle);
    expect(document.activeElement).toBe(toggle);
    expect(toggle.checked).toBe(false);
    expect(map.fitBounds).not.toHaveBeenCalled();
});

it.each(['hide', 'new-navigation', 'destroy'])('cancels a delayed locate after %s', async reason => {
    let finish!: (result: boolean) => void;
    Layers.toggleGPSTrackVisibility.mockImplementationOnce((id, visible) => {
        State.gpsTrackLayerStates.set(String(id), visible);
        return new Promise(resolve => { finish = resolve; });
    });
    State.gpsTrackBounds.set('one', { bounds: true } as unknown as CameraBounds);
    GPSTracksPanel.init();
    const locating = GPSTracksPanel.activateAndFlyToTrack('one');
    if (reason === 'hide') await GPSTracksPanel.toggleTrack('one', false);
    if (reason === 'new-navigation') beginMapNavigation(State.map, 'project:other');
    if (reason === 'destroy') GPSTracksPanel.destroy();
    finish(true);
    await locating;
    expect(map.fitBounds).not.toHaveBeenCalled();
});
