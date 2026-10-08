type HtmlPrimitive = string | number | boolean | null | undefined;
import { CylinderInstalls } from './cylinders.ts';
import { configureRuntimeContext } from '../runtime_context.ts';

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
            showNotification: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
            showLoadingOverlay: vi.fn(() => document.createElement('div')),
            hideLoadingOverlay: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
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

vi.mock('../config.ts', () => ({
    Config: {},
}));

vi.mock('../components/modal.ts', () => ({
    Modal: {
        base: vi.fn(() => '<div id="cylinder-status-confirm-modal"></div>'),
        open: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        close: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
    },
}));

const API = vi.hoisted(() => ({
        getCylinderFleets: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getCylinderFleetCylinders: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        createCylinderInstall: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getCylinderInstallDetails: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getCylinderPressureChecks: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getCylinderPressureCheckDetails: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        createCylinderPressureCheck: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        updateCylinderPressureCheck: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        deleteCylinderPressureCheck: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        updateCylinderInstall: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
    }));
vi.mock('../api.ts', () => ({ API }));

describe('StationCylinders XSS', () => {
    beforeEach(() => {
        configureRuntimeContext({ icons: { cylinderOrange: 'https://example.test/cyl.png' } });
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
        configureRuntimeContext({});
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

        const fleetSelect = (document.getElementById('cylinder-fleet-select') as HTMLSelectElement);
        expect(fleetSelect.innerHTML).toContain('&lt;script&gt;');
        expect(fleetSelect.innerHTML).not.toContain('<script>fleet</script>');

        fleetSelect.value = 'f1';
        fleetSelect.dispatchEvent(new Event('change', { bubbles: true }));
        await Promise.resolve();
        await new Promise((r) => setTimeout(r, 0));

        const cylSelect = (document.getElementById('cylinder-select') as HTMLSelectElement);
        expect(cylSelect.innerHTML).toContain('&lt;img');
        expect(cylSelect.innerHTML).not.toContain('<img src=x');

        const locInput = (document.getElementById('install-location-name') as HTMLInputElement);
        expect(locInput.value).toBe('<b>loc</b>');
        const rawHtml = (document.getElementById('cylinder-modal-content') as HTMLElement).innerHTML;
        expect(rawHtml).not.toContain('"><script');
        expect(rawHtml).toMatch(/id="install-location-name"/);
    });

    it('handles string coordinates in showInstallModal without throwing', async () => {
        API.getCylinderFleets.mockResolvedValue([
            { id: 'f1', name: 'Fleet', cylinder_count: 0 },
        ]);
        API.getCylinderFleetCylinders.mockResolvedValue([]);

        await CylinderInstalls.showInstallModal(['-82.5', '27.5'], 'Test', 'p1');

        const latInput = (document.getElementById('install-latitude') as HTMLInputElement);
        const lonInput = (document.getElementById('install-longitude') as HTMLInputElement);
        expect(latInput.value).toBe('27.5000000');
        expect(lonInput.value).toBe('-82.5000000');
    });

    it('escapes fleet name with double quotes in option label text', async () => {
        API.getCylinderFleets.mockResolvedValue([
            { id: 'f-q', name: '"><img src=x onerror=1>', cylinder_count: 1 },
        ]);
        API.getCylinderFleetCylinders.mockResolvedValue([]);

        await CylinderInstalls.showInstallModal([0, 0], '', 'p1');

        const fleetSelect = (document.getElementById('cylinder-fleet-select') as HTMLSelectElement);
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
        expect((document.getElementById('install-location-name') as HTMLInputElement).value).toBe('');
        await CylinderInstalls.showInstallModal([1, 2], undefined, 'p1');
        expect((document.getElementById('install-location-name') as HTMLInputElement).value).toBe('');
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
            const el = (document.getElementById('cylinder-tab-content') as HTMLElement);
            return el && el.innerHTML.includes('&lt;svg');
        });

        let html = (document.getElementById('cylinder-modal-content') as HTMLElement).innerHTML;
        expect(html).toContain('&lt;svg');
        expect(html).toContain('&lt;iframe&gt;');
        expect(html).not.toContain('<svg onload');

        CylinderInstalls.switchTab('pressure', installId);
        await vi.waitFor(() => {
            const el = (document.getElementById('cylinder-tab-content') as HTMLElement);
            return el && el.innerHTML.includes('&lt;b&gt;who');
        });

        html = (document.getElementById('cylinder-tab-content') as HTMLElement).innerHTML;
        expect(html).toContain('&lt;b&gt;who');
        expect(html).toContain('&lt;img');
        expect(html).not.toContain('<img src=x');
    });
});

describe('CylinderInstalls literal contracts', () => {
    beforeEach(() => {
        CylinderInstalls.clearCache();
        vi.clearAllMocks();
        document.body.innerHTML = '<div id="cylinder-modal" class="hidden"><button id="cylinder-modal-close"></button><div id="cylinder-modal-title"></div><div id="cylinder-modal-content"></div></div>';
        API.getCylinderFleets.mockResolvedValue([{ id: 'f', name: 'Fleet', cylinder_count: 2 }]);
        API.getCylinderFleetCylinders.mockResolvedValue([
            { id: 'c', name: 'Ready', o2_percentage: 21, he_percentage: 0, pressure: 200, unit_system: 'metric', active_installs: [] },
            { id: 'busy', name: 'Busy', active_installs: [{}] },
        ]);
    });
    afterEach(() => { document.body.innerHTML = ''; });

    async function selectFleet() {
        const select = (document.getElementById('cylinder-fleet-select') as HTMLSelectElement);
        select.value = 'f';
        select.dispatchEvent(new Event('change'));
        await vi.waitFor(() => expect((document.getElementById('cylinder-select') as HTMLSelectElement).disabled).toBe(false));
    }

    it('reuses cylinder responses within a session and refreshes them on each modal opening', async () => {
        await CylinderInstalls.showInstallModal([1, 2], 'Location', 'p');
        await selectFleet();
        expect((document.getElementById('cylinder-select') as HTMLSelectElement).innerHTML).not.toContain('Busy');
        await selectFleet();
        expect(API.getCylinderFleetCylinders).toHaveBeenCalledOnce();
        await CylinderInstalls.showInstallModal([1, 2], 'Location', 'p');
        await selectFleet();
        expect(API.getCylinderFleetCylinders).toHaveBeenCalledTimes(2);
    });

    it('submits exact string coordinates and optional zero distance and dispatches on Document', async () => {
        await CylinderInstalls.showInstallModal([1, 2], ' Location ', 'p');
        await selectFleet();
        (document.getElementById('cylinder-select') as HTMLSelectElement).value = 'c';
        (document.getElementById('install-distance') as HTMLInputElement).value = '0';
        (document.getElementById('install-notes') as HTMLInputElement).value = ' Notes ';
        API.createCylinderInstall.mockResolvedValue({ id: 'created' });
        const eventSpy = vi.fn<(event: Event) => void>();
        document.addEventListener('speleo:refresh-cylinder-installs', eventSpy);
        await CylinderInstalls.handleInstall();
        expect(API.createCylinderInstall).toHaveBeenCalledWith({
            project: 'p', cylinder: 'c', latitude: '2.0000000', longitude: '1.0000000',
            location_name: 'Location', install_date: new Date().toISOString().split('T')[0],
            unit_system: 'metric', distance_from_entry: 0, notes: 'Notes',
        });
        expect(eventSpy).toHaveBeenCalledOnce();
        expect((eventSpy.mock.calls[0]![0] as CustomEvent<null>).detail).toBeNull();
        expect((document.getElementById('cylinder-modal') as HTMLElement).classList.contains('hidden')).toBe(true);
        document.removeEventListener('speleo:refresh-cylinder-installs', eventSpy);
    });

    it.each(['null', 'undefined', ''])('rejects invalid project context %s before sending', async project => {
        await CylinderInstalls.showInstallModal([0, 0], 'Location', project);
        await CylinderInstalls.handleInstall();
        expect(API.createCylinderInstall).not.toHaveBeenCalled();
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'No project context available. Please try again from the map.');
    });

    it('preserves pressure integer parsing and empty notes while omitting tab refresh without its DOM', async () => {
        document.body.innerHTML = '<input id="new-check-date" value="2025-01-01"><input id="new-check-pressure" value="123.9"><select id="new-check-unit"><option selected>imperial</option></select><textarea id="new-check-notes"> </textarea>';
        API.createCylinderPressureCheck.mockResolvedValue({});
        await CylinderInstalls.savePressureCheck('install');
        expect(API.createCylinderPressureCheck).toHaveBeenCalledWith('install', { check_date: '2025-01-01', pressure: 123, unit_system: 'imperial', notes: '' });
        expect(API.getCylinderPressureChecks).not.toHaveBeenCalled();
    });

    it('skips pressure deletion after cancellation and catches request failures after confirmation', async () => {
        vi.stubGlobal('confirm', vi.fn(() => false));
        await CylinderInstalls.deletePressureCheck('i', 'c');
        expect(API.deleteCylinderPressureCheck).not.toHaveBeenCalled();
        vi.stubGlobal('confirm', vi.fn(() => true));
        API.deleteCylinderPressureCheck.mockRejectedValue(new Error('Denied'));
        await expect(CylinderInstalls.deletePressureCheck('i', 'c')).resolves.toBeUndefined();
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Denied');
        vi.unstubAllGlobals();
    });

    it('keeps the close alias identical to the registered DOM listener', () => {
        const button = (document.getElementById('cylinder-modal-close') as HTMLElement);
        const spy = vi.spyOn(button, 'addEventListener');
        document.dispatchEvent(new Event('DOMContentLoaded'));
        expect(spy).toHaveBeenCalledWith('click', CylinderInstalls.closeModal);
        expect(CylinderInstalls.closeModal()).toBeUndefined();
    });
});
