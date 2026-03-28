import { StationSensors } from './sensors.js';
import { API } from '../api.js';
import { Utils } from '../utils.js';
import { Config } from '../config.js';
import { State } from '../state.js';

vi.mock('../utils.js', () => {
    const escapeHtml = (text) => {
        if (text === null || text === undefined) return '';
        const str = String(text);
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    const RAW = Symbol('RAW_HTML');
    return {
        Utils: {
            showNotification: vi.fn(),
            showLoadingOverlay: vi.fn(() => document.createElement('div')),
            hideLoadingOverlay: vi.fn(),
            escapeHtml,
            safeCssColor: vi.fn((c, fb) => /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(c) ? c : (fb || '#94a3b8')),
            sanitizeUrl: vi.fn((url) => url || ''),
            raw: (html) => ({ [RAW]: true, value: String(html) }),
            safeHtml: (strings, ...values) => strings.reduce((r, s, i) => {
                if (i < values.length) {
                    const v = values[i];
                    if (v && typeof v === 'object' && v[RAW]) return r + s + v.value;
                    return r + s + escapeHtml(v);
                }
                return r + s;
            }, ''),
        },
    };
});

vi.mock('../api.js', () => ({
    API: {
        getStationSensorInstallsWithStatus: vi.fn(),
        getStationSensorInstalls: vi.fn(),
        getSensorFleets: vi.fn(),
        getSensorFleetSensors: vi.fn(),
        getStationSensorInstallDetails: vi.fn(),
        createStationSensorInstalls: vi.fn(),
        updateStationSensorInstalls: vi.fn(),
        getStationSensorInstallsAsExcel: vi.fn(),
    },
}));

vi.mock('../config.js', () => ({
    Config: {
        getScopedAccess: vi.fn(() => ({ write: true })),
    },
}));

vi.mock('../state.js', () => ({
    State: {
        allStations: new Map(),
        allSurfaceStations: new Map(),
    },
}));

describe('StationSensors XSS', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'station-modal-content';
        document.body.appendChild(container);
        State.allStations = new Map();
        State.allSurfaceStations = new Map();
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('escapes sensor and fleet names and install user in current installs HTML', async () => {
        const payload = '<img src=x onerror=alert(1)>';
        API.getStationSensorInstallsWithStatus.mockResolvedValue({
            success: true,
            data: [{
                id: 'inst-1',
                sensor_name: payload,
                sensor_fleet_name: '<script>evil()</script>',
                status: 'installed',
                install_date: '2020-01-15',
                install_user: '<b>user</b>',
            }],
        });

        await StationSensors.loadCurrentInstalls('st-safe', 'proj-safe', 'current', false);

        const html = container.innerHTML;
        const h4 = container.querySelector('#sensor-subtab-content h4');
        expect(h4.innerHTML).toContain('&lt;img');
        expect(h4.textContent).toBe(payload);
        expect(container.querySelectorAll('#sensor-subtab-content img')).toHaveLength(0);
        expect(html).not.toContain('<script>');
        expect(html).toContain('&lt;script&gt;');
        expect(html).toContain('&lt;b&gt;');
    });

    it('escapes double quotes in sensor name used inside onclick attribute strings', async () => {
        API.getStationSensorInstallsWithStatus.mockResolvedValue({
            success: true,
            data: [{
                id: 'i2',
                sensor_name: 'evil" onclick=alert(1)//',
                sensor_fleet_name: 'F',
                status: 'installed',
                install_date: '2020-01-01',
                install_user: 'u',
            }],
        });

        await StationSensors.loadCurrentInstalls('st-1', 'proj-1', 'current', false);

        const html = container.innerHTML;
        expect(html).toContain('&quot;');
        expect(html).toContain("'evil&quot; onclick=alert(1)//'");
    });

    it('escapes sensor fleet and user fields in history table HTML', async () => {
        API.getStationSensorInstalls.mockResolvedValue({
            success: true,
            data: [{
                sensor_name: '<td id=mal>',
                sensor_fleet_name: '"><img src=x onerror=1>',
                status: 'retrieved',
                install_date: '2020-01-01',
                install_user: '"break"',
                uninstall_date: '2020-02-01',
                uninstall_user: '<svg onload=1>',
                modified_date: '2020-03-01',
            }],
        });

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
        API.getSensorFleets.mockResolvedValue({
            success: true,
            data: [{ id: 'fleet-a', name: '<option value=evil>' }],
        });
        API.getSensorFleetSensors.mockResolvedValue({
            success: true,
            data: [{
                id: 'sen-1',
                name: '<script>x</script>',
                status: 'functional',
                active_installs: [],
            }],
        });

        await StationSensors.loadInstallForm('st-f', 'proj-f');

        const fleetSelect = document.getElementById('sensor-fleet-select');
        expect(fleetSelect.innerHTML).toContain('&lt;option');
        expect(fleetSelect.innerHTML).not.toMatch(/<option[^>]*\svalue=evil[\s>]/);

        await StationSensors.loadFleetSensors('fleet-a', 'st-f');

        const sensorSelect = document.getElementById('sensor-select');
        expect(sensorSelect.innerHTML).toContain('&lt;script&gt;');
        expect(sensorSelect.innerHTML).not.toContain('<script>');
    });

    it('escapes sensor name in status change modal body', () => {
        const malicious = '<strong>oops</strong>';
        StationSensors.showInstallStatusChangeModal('i1', 'lost', malicious, 's1', 'p1');

        const modal = document.getElementById('sensor-status-change-modal');
        expect(modal).toBeTruthy();
        expect(modal.innerHTML).toContain('&lt;strong&gt;');
        expect(modal.innerHTML).not.toContain('<strong>oops</strong>');
        modal.remove();
    });
});
