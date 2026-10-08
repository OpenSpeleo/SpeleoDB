import type { StationRecord } from '../../../../../../ts-types/domain/station-records.ts';
import { SurfaceStationUI } from './ui.ts';
import { Utils } from '../utils.ts';
vi.mock('../components/notification.ts', () => ({ Notification: { show: vi.fn() } }));
const SurfaceStationManager = vi.hoisted(() => ({ createStation: vi.fn<(...args: unknown[]) => Promise<unknown>>() }));
vi.mock('./manager.ts', () => ({ SurfaceStationManager }));
const StationDetails = vi.hoisted(() => ({ openModal: vi.fn() }));
vi.mock('../stations/details.ts', () => ({ StationDetails }));
const State = vi.hoisted(() => ({ allSurfaceStations: new Map<string, Partial<StationRecord>>() }));
vi.mock('../state.ts', () => ({ State }));
const Config = vi.hoisted(() => ({
    networks: [{ id: 'network', name: '<Network>' }], hasNetworkAccess: vi.fn(() => true),
}));
vi.mock('../config.ts', () => ({ DEFAULTS: { COLORS: { FALLBACK: '#94a3b8' } }, Config }));
const goToStation = vi.hoisted(() => vi.fn());
vi.mock('../map/navigation.ts', () => ({ goToStation }));
const { openMapDialog, closeMapDialog } = vi.hoisted(() => ({ openMapDialog: vi.fn(), closeMapDialog: vi.fn() }));
vi.mock('../components/dialog_lifecycle.ts', () => ({ openMapDialog, closeMapDialog }));
const Modal = vi.hoisted(() => ({
    base: vi.fn((id: string, title: string, content: string, footer: string) => `<div id="${id}">${content}${footer}</div>`),
    open: vi.fn((id: string, html: string, callback: () => void) => { document.body.insertAdjacentHTML('beforeend', html); callback(); }), close: vi.fn(),
}));
vi.mock('../components/modal.ts', () => ({ Modal }));
beforeEach(() => {
    vi.clearAllMocks();
    State.allSurfaceStations.clear();
    Config.networks = [{ id: 'network', name: '<Network>' }];
    Config.hasNetworkAccess.mockReturnValue(true);
    document.body.innerHTML = '<button id="map-managers-button"></button><div id="surface-station-manager-modal"><div id="surface-station-manager-content"></div></div>';
});
afterEach(() => { document.body.innerHTML = ''; vi.restoreAllMocks(); });

it('preserves manager receiver and return focus and missing-modal return', () => {
    const receiver = { ...SurfaceStationUI, loadSurfaceStationManagerContent: vi.fn() };
    receiver.openManagerModal();
    expect(receiver.loadSurfaceStationManagerContent).toHaveBeenCalledOnce();
    expect(openMapDialog).toHaveBeenCalledWith((document.getElementById('surface-station-manager-modal') as HTMLElement), {
        closeButton: '#surface-station-manager-close', returnFocus: (document.getElementById('map-managers-button') as HTMLElement),
    });
    document.body.innerHTML = '';
    expect(receiver.openManagerModal()).toBeUndefined();
});

it('hides creation for read-only networks and refuses direct creation', () => {
    Config.hasNetworkAccess.mockReturnValue(false);
    const notify = vi.spyOn(Utils, 'showNotification').mockImplementation(() => {});
    SurfaceStationUI.loadSurfaceStationManagerContent();
    expect(document.body.textContent).toContain('You need write access');
    SurfaceStationUI.showCreateStationModal();
    expect(Modal.open).not.toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith('error', expect.stringContaining('write access'));
});

it('escapes grouped station labels and forwards surface details context', () => {
    State.allSurfaceStations.set('station', { id: 'station', name: '<Station>', network: 'network', latitude: 2, longitude: 1 });
    SurfaceStationUI.loadSurfaceStationManagerContent();
    expect(document.body.innerHTML).toContain('&lt;Station&gt;');
    document.querySelector<HTMLElement>('.cursor-pointer[data-network-id]')!.click();
    expect(StationDetails.openModal).toHaveBeenCalledWith('station', 'network', false, 'surface', { fromManager: true });
});

it('focuses network selection only when multiple unselected networks exist', () => {
    Config.networks.push({ id: 'second', name: 'Second' });
    SurfaceStationUI.showCreateStationModal();
    expect(document.activeElement!.id).toBe('surface-station-network');
    (document.getElementById('create-surface-station-modal') as HTMLElement).remove();
    SurfaceStationUI.showCreateStationModal('second');
    expect(document.activeElement!.id).toBe('surface-station-name');
    expect((document.getElementById('surface-station-network') as HTMLSelectElement).value).toBe('second');
});

it('submits trimmed strings and numeric coordinates, closes managers, then opens details', async () => {
    SurfaceStationManager.createStation.mockResolvedValue({ id: 'created' });
    SurfaceStationUI.showCreateStationModal();
    (document.getElementById('surface-station-name') as HTMLInputElement).value = ' Name ';
    (document.getElementById('surface-station-description') as HTMLInputElement).value = ' Description ';
    (document.getElementById('surface-station-latitude') as HTMLInputElement).value = '2.25';
    (document.getElementById('surface-station-longitude') as HTMLInputElement).value = '1.5';
    await ((document.getElementById('create-surface-station-form') as HTMLFormElement).onsubmit as (event: Event) => Promise<void>)(new Event('submit'));
    expect(SurfaceStationManager.createStation).toHaveBeenCalledWith('network', { name: 'Name', description: 'Description', latitude: 2.25, longitude: 1.5 });
    expect(closeMapDialog).toHaveBeenCalledWith((document.getElementById('surface-station-manager-modal') as HTMLElement), { restoreFocus: false });
    expect(StationDetails.openModal).toHaveBeenCalledWith('created', 'network', true, 'surface');
});

it('rejects invalid coordinates before sending and catches create failures', async () => {
    const notify = vi.spyOn(Utils, 'showNotification').mockImplementation(() => {});
    SurfaceStationUI.showCreateStationModal();
    (document.getElementById('surface-station-name') as HTMLInputElement).value = 'Name';
    (document.getElementById('surface-station-latitude') as HTMLInputElement).value = '91';
    (document.getElementById('surface-station-longitude') as HTMLInputElement).value = '1';
    const submit = (document.getElementById('create-surface-station-form') as HTMLFormElement).onsubmit as (event: Event) => Promise<void>;
    await submit(new Event('submit'));
    expect(SurfaceStationManager.createStation).not.toHaveBeenCalled();
    (document.getElementById('surface-station-latitude') as HTMLInputElement).value = '1';
    SurfaceStationManager.createStation.mockRejectedValue(new Error('Denied'));
    await expect(submit(new Event('submit'))).resolves.toBeUndefined();
    expect(notify).toHaveBeenLastCalledWith('error', 'Denied');
});
