import { StationDetails } from './details.js';
import { Utils } from '../utils.js';
import { Config } from '../config.js';
import { State } from '../state.js';
import { API } from '../api.js';

vi.mock('../api.js', () => ({
    API: {
        getStationDetails: vi.fn(),
    },
}));

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
            escapeHtml: vi.fn(escapeHtml),
            safeCssColor: vi.fn((c, fb) => /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(String(c || '')) ? c : (fb || '#94a3b8')),
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
    Config: {
        getScopedAccess: vi.fn(() => ({ write: true, delete: true })),
        projects: [
            { id: 'project-1', name: 'Safe Project' },
        ],
        networks: [
            { id: 'net-1', name: 'Safe Network' },
        ],
    },
}));

vi.mock('../state.js', () => ({
    State: {
        allStations: new Map(),
        allSurfaceStations: new Map(),
    },
}));

vi.mock('./logs.js', () => ({
    StationLogs: { render: vi.fn() },
}));

vi.mock('./resources.js', () => ({
    StationResources: { render: vi.fn() },
}));

vi.mock('./experiments.js', () => ({
    StationExperiments: { render: vi.fn() },
}));

vi.mock('./sensors.js', () => ({
    StationSensors: { render: vi.fn() },
}));

vi.mock('./tags.js', () => ({
    StationTags: { openTagSelector: vi.fn() },
}));

vi.mock('./manager.js', () => ({
    StationManager: {
        updateStation: vi.fn(),
        deleteStation: vi.fn(),
    },
}));

vi.mock('../surface_stations/manager.js', () => ({
    SurfaceStationManager: {
        deleteStation: vi.fn(),
    },
}));

vi.mock('../map/layers.js', () => ({
    Layers: {
        updateStationProperties: vi.fn(),
        updateSurfaceStationProperties: vi.fn(),
    },
}));

describe('StationDetails XSS', () => {
    beforeEach(() => {
        window.MAPVIEWER_CONTEXT = {
            icons: {
                sensor: '/static/sensor.svg',
                biology: '/static/biology.svg',
                artifact: '/static/artifact.svg',
                bone: '/static/bone.svg',
                geology: '/static/geology.svg',
            },
        };
        document.body.innerHTML = `
            <div id="station-modal-title"></div>
            <div id="station-modal-content"></div>
        `;
        Config.projects = [{ id: 'project-1', name: 'Safe Project' }];
        Config.networks = [{ id: 'net-1', name: 'Safe Network' }];
        Config.getScopedAccess.mockReturnValue({ write: true, delete: true });
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete window.MAPVIEWER_CONTEXT;
    });

    it('escapes station.name in title and main heading', () => {
        const payload = '<script>evil()</script>';
        const station = {
            id: 'st-1',
            name: payload,
            latitude: 12.3456789,
            longitude: -98.7654321,
            project: 'project-1',
        };
        StationDetails.displayStationDetails(station, 'project-1', 'subsurface');
        const title = document.getElementById('station-modal-title').innerHTML;
        const content = document.getElementById('station-modal-content').innerHTML;
        expect(title).not.toContain('<script>');
        expect(title).toContain('&lt;script&gt;evil()&lt;/script&gt;');
        expect(content).not.toContain('<script>');
        expect(content).toContain('&lt;script&gt;evil()&lt;/script&gt;');
    });

    it('escapes station.tag.name and runs tag color through safeCssColor', () => {
        const tagNamePayload = '<img src=x onerror=alert(1)>';
        const maliciousColor = 'red; background:url(javascript:void(0))';
        const station = {
            id: 'st-2',
            name: 'N',
            latitude: 1,
            longitude: 2,
            project: 'project-1',
            tag: { name: tagNamePayload, color: maliciousColor },
        };
        StationDetails.displayStationDetails(station, 'project-1', 'subsurface');
        const content = document.getElementById('station-modal-content').innerHTML;
        expect(content).not.toContain('<img src=x');
        expect(content).toContain('&lt;img src=x onerror=alert(1)&gt;');
        expect(Utils.safeCssColor).toHaveBeenCalledWith(maliciousColor);
        expect(content).toContain('background-color: #94a3b8');
    });

    it('uses literal hex from safeCssColor when tag color is valid', () => {
        const station = {
            id: 'st-3',
            name: 'N',
            latitude: 1,
            longitude: 2,
            project: 'project-1',
            tag: { name: 'T', color: '#aabbcc' },
        };
        StationDetails.displayStationDetails(station, 'project-1', 'subsurface');
        const content = document.getElementById('station-modal-content').innerHTML;
        expect(Utils.safeCssColor).toHaveBeenCalledWith('#aabbcc');
        expect(content).toContain('background-color: #aabbcc');
    });

    it('escapes parentName and parentType in snap info for project stations', () => {
        const parentXss = '<b>proj</b>';
        Config.projects = [{ id: 'project-1', name: parentXss }];
        const station = {
            id: 'st-4',
            name: 'S',
            latitude: 3,
            longitude: 4,
            project: 'project-1',
        };
        StationDetails.displayStationDetails(station, 'project-1', 'subsurface');
        const content = document.getElementById('station-modal-content').innerHTML;
        expect(Utils.escapeHtml).toHaveBeenCalledWith('Project');
        expect(Utils.escapeHtml).toHaveBeenCalledWith(parentXss);
        expect(content).toContain('&lt;b&gt;proj&lt;/b&gt;');
        expect(content).not.toContain('<b>proj</b>');
    });

    it('escapes parentName and parentType in snap info for surface stations', () => {
        const parentXss = '<svg/onload=alert(1)>';
        Config.networks = [{ id: 'net-1', name: parentXss }];
        const station = {
            id: 'st-5',
            name: 'Surface S',
            latitude: 5,
            longitude: 6,
            network: 'net-1',
        };
        StationDetails.displayStationDetails(station, 'net-1', 'surface');
        const content = document.getElementById('station-modal-content').innerHTML;
        expect(Utils.escapeHtml).toHaveBeenCalledWith('Network');
        expect(Utils.escapeHtml).toHaveBeenCalledWith(parentXss);
        expect(content).toContain('&lt;svg/onload=alert(1)&gt;');
        expect(content).not.toContain('<svg/onload=alert(1)>');
    });
});

describe('StationDetails.loadStationDetails (no const-reassignment regression)', () => {
    beforeEach(() => {
        window.MAPVIEWER_CONTEXT = {
            icons: {
                sensor: '/static/sensor.svg',
                biology: '/static/biology.svg',
                artifact: '/static/artifact.svg',
                bone: '/static/bone.svg',
                geology: '/static/geology.svg',
            },
        };
        document.body.innerHTML = `
            <div id="station-modal-title"></div>
            <div id="station-modal-content"></div>
        `;
        Config.projects = [{ id: 'project-1', name: 'Safe Project' }];
        Config.networks = [{ id: 'net-1', name: 'Safe Network' }];
        Config.getScopedAccess.mockReturnValue({ write: true, delete: true });
        State.allStations.clear();
        State.allSurfaceStations.clear();
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete window.MAPVIEWER_CONTEXT;
        State.allStations.clear();
        State.allSurfaceStations.clear();
    });

    it('loads a subsurface station without throwing when state has no prior entry', async () => {
        API.getStationDetails.mockResolvedValue({
            id: 'st-new-1',
            name: 'Fresh Station',
            latitude: '12.34',
            longitude: '-56.78',
            type: 'sensor',
        });

        await StationDetails.loadStationDetails('st-new-1', 'project-1', 'subsurface');

        expect(API.getStationDetails).toHaveBeenCalledWith('st-new-1');
        expect(State.allStations.get('st-new-1')).toMatchObject({
            id: 'st-new-1',
            name: 'Fresh Station',
            latitude: 12.34,
            longitude: -56.78,
            station_type: 'subsurface',
            project: 'project-1',
        });
        const content = document.getElementById('station-modal-content').innerHTML;
        expect(content).toContain('Fresh Station');
        expect(content).not.toContain('Error loading station details');
    });

    it('loads a subsurface station that already exists in state (merge branch)', async () => {
        State.allStations.set('st-1', {
            id: 'st-1',
            name: 'Stale Name',
            latitude: 0,
            longitude: 0,
            project: 'project-1',
        });
        API.getStationDetails.mockResolvedValue({
            id: 'st-1',
            name: 'Updated Name',
            latitude: '9.99',
            longitude: '8.88',
            type: 'biology',
        });

        await StationDetails.loadStationDetails('st-1', 'project-1', 'subsurface');

        const merged = State.allStations.get('st-1');
        expect(merged).toMatchObject({
            id: 'st-1',
            name: 'Updated Name',
            latitude: 9.99,
            longitude: 8.88,
            station_type: 'subsurface',
            project: 'project-1',
        });
        const content = document.getElementById('station-modal-content').innerHTML;
        expect(content).toContain('Updated Name');
        expect(content).not.toContain('Error loading station details');
    });

    it('loads a surface station and stores it under the network parent', async () => {
        API.getStationDetails.mockResolvedValue({
            id: 'sf-1',
            name: 'Surface New',
            latitude: '1.11',
            longitude: '2.22',
        });

        await StationDetails.loadStationDetails('sf-1', 'net-1', 'surface');

        expect(State.allSurfaceStations.get('sf-1')).toMatchObject({
            id: 'sf-1',
            name: 'Surface New',
            latitude: 1.11,
            longitude: 2.22,
            station_type: 'surface',
            network: 'net-1',
        });
        expect(State.allStations.has('sf-1')).toBe(false);
        const content = document.getElementById('station-modal-content').innerHTML;
        expect(content).toContain('Surface New');
    });

    it('shows an error surface when the API response is missing id', async () => {
        API.getStationDetails.mockResolvedValue({ name: 'no id' });

        await StationDetails.loadStationDetails('st-bad', 'project-1', 'subsurface');

        const content = document.getElementById('station-modal-content').innerHTML;
        expect(content).toContain('Error loading station details');
    });

    it('shows an error surface when the API rejects', async () => {
        API.getStationDetails.mockRejectedValue(new Error('network boom'));

        await StationDetails.loadStationDetails('st-err', 'project-1', 'subsurface');

        const content = document.getElementById('station-modal-content').innerHTML;
        expect(content).toContain('Error loading station details');
    });
});
