import { CylinderInstalls } from './cylinders.js';
import { API } from '../api.js';
import { Utils } from '../utils.js';

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

vi.mock('../config.js', () => ({
    Config: {},
}));

vi.mock('../components/modal.js', () => ({
    Modal: {
        base: vi.fn(() => '<div id="cylinder-status-confirm-modal"></div>'),
        open: vi.fn(),
        close: vi.fn(),
    },
}));

vi.mock('../api.js', () => ({
    API: {
        getCylinderFleets: vi.fn(),
        getCylinderFleetCylinders: vi.fn(),
        createCylinderInstall: vi.fn(),
        getCylinderInstallDetails: vi.fn(),
        getCylinderPressureChecks: vi.fn(),
        getCylinderPressureCheckDetails: vi.fn(),
        createCylinderPressureCheck: vi.fn(),
        updateCylinderPressureCheck: vi.fn(),
        deleteCylinderPressureCheck: vi.fn(),
        updateCylinderInstall: vi.fn(),
    },
}));

describe('StationCylinders XSS', () => {
    beforeEach(() => {
        window.MAPVIEWER_CONTEXT = { icons: { cylinderOrange: 'https://example.test/cyl.png' } };
        const modalShell = document.createElement('div');
        modalShell.id = 'cylinder-modal';
        const titleEl = document.createElement('div');
        titleEl.id = 'cylinder-modal-title';
        modalShell.appendChild(titleEl);
        document.body.appendChild(modalShell);
        const content = document.createElement('div');
        content.id = 'cylinder-modal-content';
        document.body.appendChild(content);
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete window.MAPVIEWER_CONTEXT;
    });

    it('escapes cylinder and fleet names and location in install UI HTML', async () => {
        // v2 API returns bare arrays for list endpoints (no {data: [...]}
        // envelope). See speleodb/api/v2/views/cylinder_fleet.py.
        API.getCylinderFleets.mockResolvedValue([
            { id: 'f1', name: '<script>fleet</script>', cylinder_count: 1 },
        ]);
        API.getCylinderFleetCylinders.mockResolvedValue([
            {
                id: 'cyl-1',
                name: '<img src=x onerror=1>',
                serial: 'S1',
                o2_percentage: 21,
                he_percentage: 0,
                pressure: 200,
                unit_system: 'metric',
                active_installs: [],
            },
        ]);

        await CylinderInstalls.showInstallModal([-82.5, 27.5], '<b>loc</b>', 'proj-1');

        const fleetSelect = document.getElementById('cylinder-fleet-select');
        expect(fleetSelect.innerHTML).toContain('&lt;script&gt;');
        expect(fleetSelect.innerHTML).not.toContain('<script>fleet</script>');

        fleetSelect.value = 'f1';
        fleetSelect.dispatchEvent(new Event('change', { bubbles: true }));
        await Promise.resolve();
        await new Promise((r) => setTimeout(r, 0));

        const cylSelect = document.getElementById('cylinder-select');
        expect(cylSelect.innerHTML).toContain('&lt;img');
        expect(cylSelect.innerHTML).not.toContain('<img src=x');

        const locInput = document.getElementById('install-location-name');
        expect(locInput.value).toBe('<b>loc</b>');
        const rawHtml = document.getElementById('cylinder-modal-content').innerHTML;
        expect(rawHtml).not.toContain('"><script');
        expect(rawHtml).toMatch(/id="install-location-name"/);
    });

    it('handles string coordinates in showInstallModal without throwing', async () => {
        API.getCylinderFleets.mockResolvedValue([
            { id: 'f1', name: 'Fleet', cylinder_count: 0 },
        ]);
        API.getCylinderFleetCylinders.mockResolvedValue([]);

        await CylinderInstalls.showInstallModal(['-82.5', '27.5'], 'Test', 'p1');

        const latInput = document.getElementById('install-latitude');
        const lonInput = document.getElementById('install-longitude');
        expect(latInput.value).toBe('27.5000000');
        expect(lonInput.value).toBe('-82.5000000');
    });

    it('escapes fleet name with double quotes in option label text', async () => {
        API.getCylinderFleets.mockResolvedValue([
            { id: 'f-q', name: '"><img src=x onerror=1>', cylinder_count: 1 },
        ]);
        API.getCylinderFleetCylinders.mockResolvedValue([]);

        await CylinderInstalls.showInstallModal([0, 0], '', 'p1');

        const fleetSelect = document.getElementById('cylinder-fleet-select');
        expect(fleetSelect.innerHTML).toContain('&lt;img src=x onerror=1&gt;');
        expect(fleetSelect.innerHTML).not.toContain('<img src=x onerror=1>');
        expect(fleetSelect.innerHTML).toMatch(/<option value="f-q">/);
    });

    it('treats null and undefined location name as empty via local escapeHtml', async () => {
        API.getCylinderFleets.mockResolvedValue([
            { id: 'f3', name: 'Ok', cylinder_count: 0 },
        ]);
        API.getCylinderFleetCylinders.mockResolvedValue([]);

        await CylinderInstalls.showInstallModal([1, 2], null, 'p1');
        expect(document.getElementById('install-location-name').value).toBe('');
        await CylinderInstalls.showInstallModal([1, 2], undefined, 'p1');
        expect(document.getElementById('install-location-name').value).toBe('');
    });

    it('escapes user-controlled fields in cylinder details and pressure table', async () => {
        const installId = 'install-clean-id';
        const baseInstall = {
            id: installId,
            cylinder_name: '<svg onload=1>',
            location_name: '<iframe>',
            status: 'installed',
            pressure_check_count: 1,
            cylinder_serial: '"><script>',
            cylinder_fleet_name: '<em>f</em>',
            project_name: '<strong>p</strong>',
            install_date: '2020-01-01',
            install_user: '"u"',
            latitude: '10',
            longitude: '20',
            cylinder_unit_system: 'metric',
            unit_system: 'metric',
        };

        API.getCylinderInstallDetails.mockResolvedValue(baseInstall);
        API.getCylinderPressureChecks.mockResolvedValue([{
            id: 'chk-1',
            user: '<b>who</b>',
            notes: '"><img src=x onerror=1>',
            pressure: 100,
            unit_system: 'metric',
            check_date: '2020-02-01',
            creation_date: '2020-02-01',
        }]);

        await CylinderInstalls.showCylinderDetails(installId);
        await vi.waitFor(() => {
            const el = document.getElementById('cylinder-tab-content');
            return el && el.innerHTML.includes('&lt;svg');
        });

        let html = document.getElementById('cylinder-modal-content').innerHTML;
        expect(html).toContain('&lt;svg');
        expect(html).toContain('&lt;iframe&gt;');
        expect(html).not.toContain('<svg onload');

        CylinderInstalls.switchTab('pressure', installId);
        await vi.waitFor(() => {
            const el = document.getElementById('cylinder-tab-content');
            return el && el.innerHTML.includes('&lt;b&gt;who');
        });

        html = document.getElementById('cylinder-tab-content').innerHTML;
        expect(html).toContain('&lt;b&gt;who');
        expect(html).toContain('&lt;img');
        expect(html).not.toContain('<img src=x');
    });
});
