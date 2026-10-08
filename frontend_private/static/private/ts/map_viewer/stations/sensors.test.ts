import type { StationRecord } from '../../../../../../ts-types/domain/station-records.ts';
type HtmlPrimitive = string | number | boolean | null | undefined;
import { StationSensors } from './sensors.ts';

const Utils = vi.hoisted(() => {
    const escapeHtml = (text: HtmlPrimitive) => {
        if (text === null || text === undefined) return '';
        const str = String(text);
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    const RAW = Symbol('RAW_HTML');
    type RawHTML = { [RAW]: true; value: string };
    return {
            showNotification: vi.fn(),
            showLoadingOverlay: vi.fn(() => document.createElement('div')),
            hideLoadingOverlay: vi.fn(),
            escapeHtml,
            mapActionAttributes: (action: string, ...args: unknown[]) => `data-map-action="${escapeHtml(action)}" data-map-args="${escapeHtml(JSON.stringify(args))}"`,
            safeCssColor: vi.fn((c: string, fb?: string) => /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(c) ? c : (fb || '#94a3b8')),
            sanitizeUrl: vi.fn((url: string | null | undefined) => url || ''),
            raw: (html: string): RawHTML => ({ [RAW]: true, value: String(html) }),
            safeHtml: (strings: TemplateStringsArray, ...values: (HtmlPrimitive | RawHTML)[]) => strings.reduce((r, s, i) => {
                if (i < values.length) {
                    const v = values[i];
                    if (v && typeof v === 'object' && v[RAW]) return r + s + v.value;
                    return r + s + escapeHtml(v as HtmlPrimitive);
                }
                return r + s;
            }, ''),
    };
});
vi.mock('../utils.ts', () => ({ Utils }));

const API = vi.hoisted(() => ({
        getStationSensorInstallsWithStatus: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getStationSensorInstalls: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getSensorFleets: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getSensorFleetSensors: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getStationSensorInstallDetails: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        createStationSensorInstalls: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        updateStationSensorInstalls: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getStationSensorInstallsAsExcel: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
    }));
vi.mock('../api.ts', () => ({ API }));

const Config = vi.hoisted(() => ({
        getScopedAccess: vi.fn(() => ({ write: true })),
    }));
vi.mock('../config.ts', () => ({ Config }));

const State = vi.hoisted(() => ({
        allStations: new Map<string, Partial<StationRecord>>(),
        allSurfaceStations: new Map<string, Partial<StationRecord>>(),
    }));
vi.mock('../state.ts', () => ({ State }));

describe('StationSensors XSS', () => {
    let container: HTMLDivElement;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'station-modal-content';
        document.body.appendChild(container);
        State.allStations = new Map<string, Partial<StationRecord>>();
        State.allSurfaceStations = new Map<string, Partial<StationRecord>>();
        vi.clearAllMocks();
        Config.getScopedAccess.mockReturnValue({ write: true });
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

it.each([
    { scope: 'project', write: false },
    { scope: 'network', write: false },
    { scope: 'project', write: true },
    { scope: 'network', write: true },
] as const)('keeps $scope history install actions gated by write=$write', async ({ scope, write }) => {
    Config.getScopedAccess.mockReturnValue({ write });
    if (scope === 'network') {
        State.allSurfaceStations.set('history-station', { id: 'history-station', network: 'scope-id' });
    } else {
        State.allStations.set('history-station', { id: 'history-station', project: 'scope-id' });
    }
    API.getStationSensorInstalls.mockResolvedValue([]);

    await StationSensors.loadHistory('history-station', 'scope-id');
    await vi.waitFor(() => expect(container.textContent).toContain('Sensor Management'));

    expect(Config.getScopedAccess).toHaveBeenCalledWith(scope, 'scope-id');
    expect(container.querySelector('[data-map-action="sensors.loadInstallForm"]') !== null).toBe(write);
    expect(container.querySelector('[data-map-action="sensors.loadCurrentInstalls"]')).not.toBeNull();
});

    it('escapes sensor and fleet names and install user in current installs HTML', async () => {
        const payload = '<img src=x onerror=alert(1)>';
        API.getStationSensorInstallsWithStatus.mockResolvedValue([{
            id: 'inst-1',
            sensor_name: payload,
            sensor_fleet_name: '<script>evil()</script>',
            status: 'installed',
            install_date: '2020-01-15',
            install_user: '<b>user</b>',
        }]);

        await StationSensors.loadCurrentInstalls('st-safe', 'proj-safe', 'current', false);

        const html = container.innerHTML;
        const h4 = container.querySelector('#sensor-subtab-content h4');
        expect(h4!.innerHTML).toContain('&lt;img');
        expect(h4!.textContent).toBe(payload);
        expect(container.querySelectorAll('#sensor-subtab-content img')).toHaveLength(0);
        expect(html).not.toContain('<script>');
        expect(html).toContain('&lt;script&gt;');
        expect(html).toContain('&lt;b&gt;');
    });

    it('serializes sensor names safely in delegated action data', async () => {
        const sensorName = 'evil" onclick=alert(1)//';
        API.getStationSensorInstallsWithStatus.mockResolvedValue([{
            id: 'i2',
            sensor_name: sensorName,
            sensor_fleet_name: 'F',
            status: 'installed',
            install_date: '2020-01-01',
            install_user: 'u',
        }]);

        await StationSensors.loadCurrentInstalls('st-1', 'proj-1', 'current', false);

        const html = container.innerHTML;
        const action = container.querySelector<HTMLElement>(
            '[data-map-action="sensors.showInstallStatusChangeModal"]'
        );
        expect((JSON.parse(action!.dataset.mapArgs!) as unknown[])[2]).toBe(sensorName);
        expect(container.querySelectorAll('[onclick]')).toHaveLength(0);
    });

    it('escapes sensor fleet and user fields in history table HTML', async () => {
        API.getStationSensorInstalls.mockResolvedValue([{
            sensor_name: '<td id=mal>',
            sensor_fleet_name: '"><img src=x onerror=1>',
            status: 'retrieved',
            install_date: '2020-01-01',
            install_user: '"break"',
            uninstall_date: '2020-02-01',
            uninstall_user: '<svg onload=1>',
            modified_date: '2020-03-01',
        }]);

        await StationSensors.loadHistory('hist-st', 'hist-proj');
        await vi.waitFor(() => {
            expect(container.innerHTML.length).toBeGreaterThan(0);
        });

        const html = container.innerHTML;
        expect(html).not.toContain('<td id=mal>');
        expect(html).toContain('&lt;td');
        expect(html).toContain('&lt;img src=x onerror=1&gt;');
        expect(html).toContain('&lt;svg');
    });

    it('escapes fleet and sensor names in install form options', async () => {
        API.getSensorFleets.mockResolvedValue([{ id: 'fleet-a', name: '<option value=evil>' }]);
        API.getSensorFleetSensors.mockResolvedValue([{
            id: 'sen-1',
            name: '<script>x</script>',
            status: 'functional',
            active_installs: [],
        }]);

        await StationSensors.loadInstallForm('st-f', 'proj-f');

        const fleetSelect = (document.getElementById('sensor-fleet-select') as HTMLSelectElement);
        expect(fleetSelect.innerHTML).toContain('&lt;option');
        expect(fleetSelect.innerHTML).not.toMatch(/<option[^>]*\svalue=evil[\s>]/);

        await StationSensors.loadFleetSensors('fleet-a', 'st-f');

        const sensorSelect = (document.getElementById('sensor-select') as HTMLSelectElement);
        expect(sensorSelect.innerHTML).toContain('&lt;script&gt;');
        expect(sensorSelect.innerHTML).not.toContain('<script>');
    });

    it('escapes sensor name in status change modal body', () => {
        const malicious = '<strong>oops</strong>';
        StationSensors.showInstallStatusChangeModal('i1', 'lost', malicious, 's1', 'p1');

        const modal = (document.getElementById('sensor-status-change-modal') as HTMLElement);
        expect(modal).toBeTruthy();
        expect(modal.innerHTML).toContain('&lt;strong&gt;');
        expect(modal.innerHTML).not.toContain('<strong>oops</strong>');
        modal.remove();
    });
});

describe('StationSensors literal lifecycle', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        StationSensors.cancelStatusChange();
        document.body.innerHTML = '<div id="station-modal-content"></div>';
    });
    afterEach(() => { StationSensors.cancelStatusChange(); document.body.innerHTML = ''; });

    function installInputs() {
        document.body.innerHTML += '<select id="sensor-select"><option value="sensor" selected>Sensor</option></select><input id="install-date" value="2025-01-02"><input id="expiracy-memory-date"><input id="expiracy-battery-date"><div id="expiracy-memory-date-error"></div>';
    }

    it('omits empty expiries on creation and preserves literal null strings on edit', async () => {
        installInputs();
        const receiver = { ...StationSensors, loadCurrentInstalls: vi.fn(() => new Promise<void>(() => {})) };
        API.createStationSensorInstalls.mockResolvedValue({});
        API.updateStationSensorInstalls.mockResolvedValue({});
        await receiver.handleInstall('station', 'project');
        expect([...(API.createStationSensorInstalls.mock.calls[0]![1] as FormData).entries()]).toEqual([
            ['sensor', 'sensor'], ['install_date', '2025-01-02'],
        ]);
        await receiver.handleInstall('station', 'project', 'install');
        expect([...(API.updateStationSensorInstalls.mock.calls[0]![2] as FormData).entries()]).toEqual([
            ['sensor', 'sensor'], ['install_date', '2025-01-02'], ['expiracy_memory_date', 'null'], ['expiracy_battery_date', 'null'],
        ]);
        expect(receiver.loadCurrentInstalls).toHaveBeenCalledTimes(2);
    });

    it('validates dates before creating the loading overlay or sending requests', async () => {
        installInputs();
        (document.getElementById('expiracy-memory-date') as HTMLInputElement).value = '2025-01-01';
        await StationSensors.handleInstall('station', 'project');
        expect(API.createStationSensorInstalls).not.toHaveBeenCalled();
        expect(Utils.showLoadingOverlay).not.toHaveBeenCalled();
        expect((document.getElementById('expiracy-memory-date-error') as HTMLElement).textContent).toContain('on or after');
    });

    it('clears pending status after failure and preserves the error message', async () => {
        API.updateStationSensorInstalls.mockRejectedValue(new Error('Denied'));
        StationSensors.showInstallStatusChangeModal('install', 'lost', 'Sensor', 'station', 'project');
        await expect(StationSensors.confirmStatusChange()).resolves.toBeUndefined();
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Denied');
        await StationSensors.confirmStatusChange();
        expect(API.updateStationSensorInstalls).toHaveBeenCalledOnce();
        expect((document.getElementById('sensor-status-change-modal') as HTMLElement)).toBeNull();
    });

    it('retains earlier pending status when an unknown status is requested', async () => {
        API.updateStationSensorInstalls.mockResolvedValue({});
        const receiver = { ...StationSensors, loadCurrentInstalls: vi.fn() };
        receiver.showInstallStatusChangeModal('first', 'lost', 'Sensor', 'station', 'project');
        receiver.showInstallStatusChangeModal('second', 'unknown', 'Sensor', 'station', 'project');
        await receiver.confirmStatusChange();
        expect(API.updateStationSensorInstalls.mock.calls[0]!.slice(0, 2)).toEqual(['station', 'first']);
    });

    it('uses cached fleet results and includes the sensor being edited despite an active install', async () => {
        API.getSensorFleets.mockResolvedValue([{ id: 'fleet-cache', name: 'Fleet' }]);
        API.getSensorFleetSensors.mockResolvedValue([
            { id: 'current', name: 'Current', status: 'functional', active_installs: [{}] },
            { id: 'broken', name: 'Broken', status: 'broken', active_installs: [] },
            { id: 'ready', name: 'Ready', status: 'functional', active_installs: [] },
        ]);
        await StationSensors.loadInstallForm('station', 'project');
        await StationSensors.loadFleetSensors('fleet-cache', 'station', 'current');
        expect(API.getSensorFleetSensors).toHaveBeenCalledOnce();
        const select = (document.getElementById('sensor-select') as HTMLSelectElement);
        expect(select.innerHTML).toContain('Current');
        expect(select.innerHTML).toContain('Ready');
        expect(select.innerHTML).not.toContain('Broken');
        expect(select.value).toBe('current');
    });

    it('uses the receiver after awaiting dynamically imported station state', async () => {
        State.allSurfaceStations.set('station', { id: 'station', network: 'network' });
        const receiver = { ...StationSensors, loadCurrentInstalls: vi.fn().mockResolvedValue(undefined) };
        await receiver.render('station', (document.getElementById('station-modal-content') as HTMLElement));
        expect(receiver.loadCurrentInstalls).toHaveBeenCalledWith('station', 'network', 'current', 'network');
    });
});

it('keeps the fleet change callback ordinary and returns the receiver promise', async () => {
    document.body.innerHTML = '<div id="station-modal-content"></div>';
    API.getSensorFleets.mockResolvedValue([{ id: 'listener-fleet', name: 'Fleet' }]);
    API.getSensorFleetSensors.mockResolvedValue([]);
    const pending = Promise.resolve();
    const receiver = { ...StationSensors, loadFleetSensors: vi.fn(() => pending) };
    const registrations = vi.spyOn(HTMLSelectElement.prototype, 'addEventListener');
    await receiver.loadInstallForm('station', 'project');
    const listener = registrations.mock.calls.find(([type]) => type === 'change')![1] as () => Promise<void>;
    registrations.mockRestore();
    const select = document.getElementById('sensor-fleet-select') as HTMLSelectElement;
    select.value = 'listener-fleet';
    expect(listener()).toBe(pending);
    expect(receiver.loadFleetSensors).toHaveBeenCalledWith('listener-fleet', 'station');
    document.body.innerHTML = '';
});
