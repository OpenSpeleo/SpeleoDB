import type { StationRecord } from '../../../../../../ts-types/domain/station-records.ts';
import { StationUI } from './ui.ts';
import { Utils } from '../utils.ts';
const StationDetails = vi.hoisted(() => ({ openModal: vi.fn() }));
vi.mock('./details.ts', () => ({ StationDetails }));
const StationManager = vi.hoisted(() => ({ createStation: vi.fn<(...args: unknown[]) => Promise<unknown>>() }));
vi.mock('./manager.ts', () => ({ StationManager }));
const State = vi.hoisted(() => ({ allStations: new Map<string, Partial<StationRecord>>() }));
vi.mock('../state.ts', () => ({ State }));
vi.mock('../config.ts', () => ({ DEFAULTS: { COLORS: { FALLBACK: "#94a3b8" } }, Config: { projects: [{ id: 'project', name: '<Project>' }] } }));
const goToStation = vi.hoisted(() => vi.fn());
vi.mock('../map/navigation.ts', () => ({ goToStation }));
const Geometry = vi.hoisted(() => ({ findNearestSnapPointWithinRadius: vi.fn<(...args: unknown[]) => unknown>(), getSnapRadius: vi.fn(() => 10) }));
vi.mock('../map/geometry.ts', () => ({ Geometry }));
const { openMapDialog, closeMapDialog } = vi.hoisted(() => ({ openMapDialog: vi.fn(), closeMapDialog: vi.fn() }));
vi.mock('../components/dialog_lifecycle.ts', () => ({ openMapDialog, closeMapDialog }));
const Modal = vi.hoisted(() => ({
    base: vi.fn((id: string, title: string, content: string, footer: string) => `<div id="${id}">${content}${footer}</div>`),
    open: vi.fn((id: string, html: string, callback: () => void) => { document.body.insertAdjacentHTML('beforeend', html); callback(); }),
    close: vi.fn(),
}));
vi.mock('../components/modal.ts', () => ({ Modal }));

beforeEach(() => {
    vi.clearAllMocks();
    State.allStations.clear();
    document.body.innerHTML = '<button id="map-managers-button"></button><div id="station-manager-modal"><div id="station-manager-content"></div></div>';
});
afterEach(() => { document.body.innerHTML = ''; vi.restoreAllMocks(); });

it('renders manager content before opening with the existing return focus', () => {
    const receiver = { ...StationUI, loadStationManagerContent: vi.fn() };
    receiver.openManagerModal();
    expect(receiver.loadStationManagerContent).toHaveBeenCalledOnce();
    expect(openMapDialog).toHaveBeenCalledWith((document.getElementById('station-manager-modal') as HTMLElement), {
        closeButton: '#station-manager-close', returnFocus: (document.getElementById('map-managers-button') as HTMLElement),
    });
    expect(receiver.loadStationManagerContent.mock.invocationCallOrder[0]!).toBeLessThan(openMapDialog.mock.invocationCallOrder[0]!);
});

it('tolerates absent manager DOM and keeps empty-state output', () => {
    StationUI.loadStationManagerContent();
    expect(document.body.textContent).toContain('No Stations Yet');
    document.body.innerHTML = '';
    expect(StationUI.openManagerModal()).toBeUndefined();
    expect(StationUI.loadStationManagerContent()).toBeUndefined();
});

it('sorts and escapes station labels, forwards details context, and separates navigation', () => {
    State.allStations.set('b', { id: 'b', name: 'Z', type: 'sensor', project: 'project', latitude: 2, longitude: 1 });
    State.allStations.set('a', { id: 'a', name: '<A>', type: 'biology', project: 'project', latitude: '4', longitude: '3' });
    StationUI.loadStationManagerContent();
    const content = (document.getElementById('station-manager-content') as HTMLElement);
    expect(content.innerHTML).toContain('&lt;Project&gt;');
    const cards = content.querySelectorAll<HTMLElement>('.cursor-pointer[data-project-id]');
    expect(cards[0]!.dataset.stationId).toBe('a');
    cards[0]!.click();
    expect(StationDetails.openModal).toHaveBeenCalledWith('a', 'project', false, 'subsurface', { fromManager: true });
    content.querySelector<HTMLElement>('.go-to-station-btn')!.click();
    expect(goToStation).toHaveBeenCalledWith('a', 4, 3);
    expect(closeMapDialog).toHaveBeenLastCalledWith((document.getElementById('station-manager-modal') as HTMLElement));
});

it('preserves the unknown station type failure', () => {
    State.allStations.set('a', { id: 'a', type: 'unknown' });
    expect(() => StationUI.loadStationManagerContent()).toThrow(TypeError);
});

it('rejects unsnapped creation and preserves trimmed snapped payload and details opening', async () => {
    const notify = vi.spyOn(Utils, 'showNotification').mockImplementation(() => {});
    Geometry.findNearestSnapPointWithinRadius.mockReturnValue({ snapped: false });
    expect(StationUI.showCreateStationModal([1, 2], 'fallback', 'sensor')).toBeUndefined();
    expect(Modal.open).not.toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith('warning', expect.stringContaining('Too far'));
    Geometry.findNearestSnapPointWithinRadius.mockReturnValue({ snapped: true, coordinates: [3, 4], projectId: 'detected', distance: 1, pointType: 'start' });
    StationManager.createStation.mockResolvedValue({ id: 'created' });
    StationUI.showCreateStationModal([1, 2], 'fallback', 'sensor');
    (document.getElementById('station-name') as HTMLInputElement).value = ' Name ';
    (document.getElementById('station-description') as HTMLInputElement).value = ' Description ';
    await ((document.getElementById('create-station-form') as HTMLFormElement).onsubmit as (event: Event) => Promise<void>)(new Event('submit'));
    expect(StationManager.createStation).toHaveBeenCalledWith('detected', { name: 'Name', description: 'Description', latitude: 4, longitude: 3, type: 'sensor' });
    expect(StationDetails.openModal).toHaveBeenCalledWith('created', 'detected', true);
});

it('closes drag confirmation before invoking the original callback', () => {
    const confirm = vi.fn(() => expect(Modal.close).toHaveBeenCalledWith('drag-confirm-modal'));
    const cancel = vi.fn();
    StationUI.showDragConfirmModal(null, confirm, cancel);
    (document.getElementById('drag-confirm-btn') as HTMLElement).click();
    expect(confirm).toHaveBeenCalledOnce();
    (document.getElementById('drag-cancel-btn') as HTMLElement).click();
    expect(cancel).toHaveBeenCalledOnce();
});
