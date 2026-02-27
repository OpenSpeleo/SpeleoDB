import { API } from './api.js';

vi.mock('./utils.js', () => ({
    Utils: {
        getCSRFToken: vi.fn(() => 'test-csrf-token'),
    },
}));

function mockFetchResponse(data, { ok = true, status = 200 } = {}) {
    return vi.fn(() =>
        Promise.resolve({
            ok,
            status,
            json: () => Promise.resolve(data),
        })
    );
}

describe('API module', () => {
    beforeEach(() => {
        globalThis.Urls = new Proxy(
            {},
            {
                get: (_target, prop) =>
                    (...args) =>
                        `/api/${prop}${args.length ? '/' + args.join('/') : ''}`,
            }
        );
    });

    afterEach(() => {
        delete globalThis.Urls;
        vi.restoreAllMocks();
    });

    // ------------------------------------------------------------------ //
    // apiRequest core behavior (tested through public API methods)
    // ------------------------------------------------------------------ //

    describe('request configuration', () => {
        it('includes CSRF token and Content-Type headers for JSON requests', async () => {
            globalThis.fetch = mockFetchResponse({ success: true });

            await API.getAllProjects();

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'X-CSRFToken': 'test-csrf-token',
                        'Content-Type': 'application/json',
                    }),
                })
            );
        });

        it('omits Content-Type header for FormData requests', async () => {
            globalThis.fetch = mockFetchResponse({ success: true });
            const formData = new FormData();
            formData.append('file', 'test');

            await API.createStationLog('station-1', formData);

            const [, config] = fetch.mock.calls[0];
            expect(config.headers['Content-Type']).toBeUndefined();
            expect(config.headers['X-CSRFToken']).toBe('test-csrf-token');
        });

        it('sets credentials to same-origin', async () => {
            globalThis.fetch = mockFetchResponse({ success: true });

            await API.getAllProjects();

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({ credentials: 'same-origin' })
            );
        });

        it('JSON-stringifies body for non-FormData POST requests', async () => {
            globalThis.fetch = mockFetchResponse({ success: true });
            const stationData = { name: 'Test Station', lat: 45.0 };

            await API.createStation('proj-1', stationData);

            const [, config] = fetch.mock.calls[0];
            expect(config.body).toBe(JSON.stringify(stationData));
        });

        it('passes FormData body directly without JSON.stringify', async () => {
            globalThis.fetch = mockFetchResponse({ success: true });
            const formData = new FormData();
            formData.append('file', 'test');

            await API.createStationResource('station-1', formData);

            const [, config] = fetch.mock.calls[0];
            expect(config.body).toBe(formData);
        });

        it('does not include body for GET requests', async () => {
            globalThis.fetch = mockFetchResponse({ success: true });

            await API.getAllProjects();

            const [, config] = fetch.mock.calls[0];
            expect(config.body).toBeUndefined();
        });
    });

    describe('response handling', () => {
        it('returns { ok: true, status: 204 } for 204 No Content', async () => {
            globalThis.fetch = vi.fn(() =>
                Promise.resolve({
                    ok: true,
                    status: 204,
                    json: () => Promise.reject(new Error('should not parse body')),
                })
            );

            const result = await API.deleteStation('station-1');
            expect(result).toEqual({ ok: true, status: 204 });
        });

        it('returns parsed JSON for successful responses', async () => {
            const responseData = { success: true, data: [{ id: '1' }] };
            globalThis.fetch = mockFetchResponse(responseData);

            const result = await API.getAllProjects();
            expect(result).toEqual(responseData);
        });
    });

    describe('error handling', () => {
        it('throws error with message from response for non-ok responses', async () => {
            globalThis.fetch = mockFetchResponse({ message: 'Not found' }, { ok: false, status: 404 });

            await expect(API.getAllProjects()).rejects.toThrow('Not found');
        });

        it('attaches status and data to thrown error', async () => {
            const errorData = { message: 'Forbidden', detail: 'No permission' };
            globalThis.fetch = mockFetchResponse(errorData, { ok: false, status: 403 });

            let caught;
            try {
                await API.getAllProjects();
            } catch (error) {
                caught = error;
            }

            expect(caught).toBeDefined();
            expect(caught.status).toBe(403);
            expect(caught.data).toEqual(errorData);
        });

        it('falls back to error field when message is absent', async () => {
            globalThis.fetch = mockFetchResponse({ error: 'Server error' }, { ok: false, status: 500 });

            await expect(API.getAllProjects()).rejects.toThrow('Server error');
        });

        it('falls back to detail field when message and error are absent', async () => {
            globalThis.fetch = mockFetchResponse({ detail: 'Auth required' }, { ok: false, status: 401 });

            await expect(API.getAllProjects()).rejects.toThrow('Auth required');
        });

        it('uses default message when no error fields present', async () => {
            globalThis.fetch = mockFetchResponse({ foo: 'bar' }, { ok: false, status: 500 });

            await expect(API.getAllProjects()).rejects.toThrow('API request failed');
        });

        it('rejects when fetch itself throws (network error)', async () => {
            globalThis.fetch = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')));

            await expect(API.getAllProjects()).rejects.toThrow('Failed to fetch');
        });
    });

    // ------------------------------------------------------------------ //
    // HTTP method routing
    // ------------------------------------------------------------------ //

    describe('HTTP method routing', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('uses GET for read operations', async () => {
            await API.getAllProjects();
            expect(fetch.mock.calls[0][1].method).toBe('GET');
        });

        it('uses POST for create operations', async () => {
            await API.createStation('proj-1', { name: 'Test' });
            expect(fetch.mock.calls[0][1].method).toBe('POST');
        });

        it('uses PATCH for update operations', async () => {
            await API.updateStation('station-1', { name: 'Updated' });
            expect(fetch.mock.calls[0][1].method).toBe('PATCH');
        });

        it('uses DELETE for delete operations', async () => {
            await API.deleteStation('station-1');
            expect(fetch.mock.calls[0][1].method).toBe('DELETE');
        });

        it('uses PUT for import operations', async () => {
            const formData = new FormData();
            await API.importGPX(formData);
            expect(fetch.mock.calls[0][1].method).toBe('PUT');
        });
    });

    // ------------------------------------------------------------------ //
    // Endpoint-specific tests
    // ------------------------------------------------------------------ //

    describe('station endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('createStation calls project-stations URL with POST', async () => {
            await API.createStation('proj-1', { name: 'New' });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:project-stations');
            expect(url).toContain('proj-1');
            expect(config.method).toBe('POST');
        });

        it('updateStation calls station-detail URL with PATCH', async () => {
            await API.updateStation('st-1', { name: 'Updated' });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:station-detail');
            expect(url).toContain('st-1');
            expect(config.method).toBe('PATCH');
        });

        it('deleteStation calls station-detail URL with DELETE', async () => {
            await API.deleteStation('st-1');
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:station-detail');
            expect(config.method).toBe('DELETE');
        });

        it('getProjectStations calls project-stations URL with GET', async () => {
            await API.getProjectStations('proj-1');
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:project-stations');
            expect(config.method).toBe('GET');
        });

        it('getStationDetails calls station-detail URL with GET', async () => {
            await API.getStationDetails('st-1');
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:station-detail');
            expect(config.method).toBe('GET');
        });

        it('getAllStationsGeoJSON calls subsurface-stations-geojson', async () => {
            await API.getAllStationsGeoJSON();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:subsurface-stations-geojson');
        });
    });

    describe('surface network and station endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getAllSurfaceNetworks calls surface-networks URL', async () => {
            await API.getAllSurfaceNetworks();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:surface-networks');
        });

        it('createSurfaceStation posts to network-stations URL', async () => {
            await API.createSurfaceStation('net-1', { name: 'Surface' });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:network-stations');
            expect(url).toContain('net-1');
            expect(config.method).toBe('POST');
        });

        it('getNetworkStations calls network-stations URL', async () => {
            await API.getNetworkStations('net-1');
            expect(fetch.mock.calls[0][0]).toContain('net-1');
        });

        it('getNetworkStationsGeoJSON includes networkId in URL', async () => {
            await API.getNetworkStationsGeoJSON('net-1');
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('api:v1:network-stations-geojson');
            expect(url).toContain('net-1');
        });

        it('getAllSurfaceStations calls surface-stations URL', async () => {
            await API.getAllSurfaceStations();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:surface-stations');
        });

        it('getAllSurfaceStationsGeoJSON calls surface-stations-geojson', async () => {
            await API.getAllSurfaceStationsGeoJSON();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:surface-stations-geojson');
        });
    });

    describe('landmark endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('createLandmark posts to landmarks URL', async () => {
            await API.createLandmark({ name: 'Entrance' });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:landmarks');
            expect(config.method).toBe('POST');
        });

        it('updateLandmark patches landmark-detail URL', async () => {
            await API.updateLandmark('lm-1', { name: 'Updated' });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:landmark-detail');
            expect(config.method).toBe('PATCH');
        });

        it('deleteLandmark deletes from landmark-detail URL', async () => {
            await API.deleteLandmark('lm-1');
            expect(fetch.mock.calls[0][1].method).toBe('DELETE');
        });

        it('getAllLandmarks calls landmarks URL', async () => {
            await API.getAllLandmarks();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:landmarks');
        });

        it('getAllLandmarksGeoJSON calls landmarks-geojson', async () => {
            await API.getAllLandmarksGeoJSON();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:landmarks-geojson');
        });
    });

    describe('tag endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getUserTags calls station-tags URL', async () => {
            await API.getUserTags();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:station-tags');
        });

        it('getTagColors calls station-tag-colors URL', async () => {
            await API.getTagColors();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:station-tag-colors');
        });

        it('createTag posts name and color to station-tags', async () => {
            await API.createTag('Important', '#ff0000');
            const [, config] = fetch.mock.calls[0];
            expect(JSON.parse(config.body)).toEqual({ name: 'Important', color: '#ff0000' });
        });

        it('setStationTag posts tag_id to station-tags-manage', async () => {
            await API.setStationTag('st-1', 'tag-1');
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:station-tags-manage');
            expect(JSON.parse(config.body)).toEqual({ tag_id: 'tag-1' });
        });

        it('removeStationTag deletes from station-tags-manage', async () => {
            await API.removeStationTag('st-1');
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:station-tags-manage');
            expect(config.method).toBe('DELETE');
        });
    });

    describe('station log endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getStationLogs calls station-logs URL', async () => {
            await API.getStationLogs('st-1');
            expect(fetch.mock.calls[0][0]).toContain('api:v1:station-logs');
        });

        it('createStationLog sends FormData with POST', async () => {
            const formData = new FormData();
            await API.createStationLog('st-1', formData);
            const [, config] = fetch.mock.calls[0];
            expect(config.method).toBe('POST');
            expect(config.body).toBe(formData);
        });

        it('updateStationLog sends FormData with PATCH', async () => {
            const formData = new FormData();
            await API.updateStationLog('log-1', formData);
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:log-detail');
            expect(config.method).toBe('PATCH');
            expect(config.body).toBe(formData);
        });

        it('deleteStationLog calls log-detail with DELETE', async () => {
            await API.deleteStationLog('log-1');
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:log-detail');
            expect(config.method).toBe('DELETE');
        });
    });

    describe('experiment endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getExperiments calls experiments URL', async () => {
            await API.getExperiments();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:experiments');
        });

        it('getExperimentData passes stationId and experimentId', async () => {
            await API.getExperimentData('st-1', 'exp-1');
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('api:v1:experiment-records');
            expect(url).toContain('st-1');
            expect(url).toContain('exp-1');
        });
    });

    describe('resource endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getStationResources calls station-resources URL', async () => {
            await API.getStationResources('st-1');
            expect(fetch.mock.calls[0][0]).toContain('api:v1:station-resources');
        });

        it('createStationResource sends FormData with POST', async () => {
            const formData = new FormData();
            await API.createStationResource('st-1', formData);
            const [, config] = fetch.mock.calls[0];
            expect(config.method).toBe('POST');
            expect(config.body).toBe(formData);
        });

        it('updateStationResource sends FormData with PATCH', async () => {
            const formData = new FormData();
            await API.updateStationResource('res-1', formData);
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:resource-detail');
            expect(config.method).toBe('PATCH');
            expect(config.body).toBe(formData);
        });

        it('deleteStationResource calls resource-detail with DELETE', async () => {
            await API.deleteStationResource('res-1');
            expect(fetch.mock.calls[0][1].method).toBe('DELETE');
        });
    });

    describe('project endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getAllProjects calls projects URL', async () => {
            await API.getAllProjects();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:projects');
        });

        it('getAllProjectsGeoJSON calls all-projects-geojson', async () => {
            await API.getAllProjectsGeoJSON();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:all-projects-geojson');
        });
    });

    describe('exploration lead endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getProjectExplorationLeadsGeoJSON includes projectId', async () => {
            await API.getProjectExplorationLeadsGeoJSON('proj-1');
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('api:v1:project-exploration-leads-geojson');
            expect(url).toContain('proj-1');
        });

        it('getAllProjectExplorationLeadsGeoJSON calls all geojson URL', async () => {
            await API.getAllProjectExplorationLeadsGeoJSON();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:exploration-lead-all-geojson');
        });

        it('getProjectExplorationLeads calls project leads URL', async () => {
            await API.getProjectExplorationLeads('proj-1');
            expect(fetch.mock.calls[0][0]).toContain('api:v1:project-exploration-leads');
        });

        it('createExplorationLead posts to project exploration leads', async () => {
            await API.createExplorationLead('proj-1', { description: 'A lead' });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:project-exploration-leads');
            expect(url).toContain('proj-1');
            expect(config.method).toBe('POST');
        });

        it('updateExplorationLead patches exploration-lead-detail', async () => {
            await API.updateExplorationLead('lead-1', { description: 'Updated' });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:exploration-lead-detail');
            expect(config.method).toBe('PATCH');
        });

        it('deleteExplorationLead calls exploration-lead-detail with DELETE', async () => {
            await API.deleteExplorationLead('lead-1');
            expect(fetch.mock.calls[0][1].method).toBe('DELETE');
        });
    });

    describe('sensor fleet and install endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getSensorFleets calls sensor-fleets URL', async () => {
            await API.getSensorFleets();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:sensor-fleets');
        });

        it('getSensorFleetDetails includes fleetId', async () => {
            await API.getSensorFleetDetails('fleet-1');
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('api:v1:sensor-fleet-detail');
            expect(url).toContain('fleet-1');
        });

        it('getSensorFleetSensors includes fleetId', async () => {
            await API.getSensorFleetSensors('fleet-1');
            expect(fetch.mock.calls[0][0]).toContain('api:v1:sensor-fleet-sensors');
        });

        it('getStationSensorInstalls calls station-sensor-installs URL', async () => {
            await API.getStationSensorInstalls('st-1');
            expect(fetch.mock.calls[0][0]).toContain('api:v1:station-sensor-installs');
        });

        it('getStationSensorInstallsWithStatus appends status query param', async () => {
            await API.getStationSensorInstallsWithStatus('st-1', 'active');
            expect(fetch.mock.calls[0][0]).toContain('?status=active');
        });

        it('getStationSensorInstallsAsExcel returns raw response object', async () => {
            const rawResponse = { ok: true, status: 200 };
            globalThis.fetch = vi.fn(() => Promise.resolve(rawResponse));

            const result = await API.getStationSensorInstallsAsExcel('st-1');
            expect(result).toBe(rawResponse);
        });

        it('getStationSensorInstallsAsExcel includes CSRF token', async () => {
            globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true }));

            await API.getStationSensorInstallsAsExcel('st-1');

            const [, config] = fetch.mock.calls[0];
            expect(config.headers['X-CSRFToken']).toBe('test-csrf-token');
            expect(config.credentials).toBe('same-origin');
        });

        it('getStationSensorInstallDetails passes stationId and installId', async () => {
            await API.getStationSensorInstallDetails('st-1', 'inst-1');
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('st-1');
            expect(url).toContain('inst-1');
        });

        it('createStationSensorInstalls sends FormData with POST', async () => {
            const formData = new FormData();
            await API.createStationSensorInstalls('st-1', formData);
            const [, config] = fetch.mock.calls[0];
            expect(config.method).toBe('POST');
            expect(config.body).toBe(formData);
        });

        it('updateStationSensorInstalls sends FormData with PATCH', async () => {
            const formData = new FormData();
            await API.updateStationSensorInstalls('st-1', 'inst-1', formData);
            const [, config] = fetch.mock.calls[0];
            expect(config.method).toBe('PATCH');
            expect(config.body).toBe(formData);
        });
    });

    describe('GPS track and GPX import endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getGPSTracks calls gps-tracks URL', async () => {
            await API.getGPSTracks();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:gps-tracks');
        });

        it('importGPX sends FormData with PUT', async () => {
            const formData = new FormData();
            await API.importGPX(formData);
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:gpx-import');
            expect(config.method).toBe('PUT');
            expect(config.body).toBe(formData);
        });
    });

    describe('cylinder fleet endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getCylinderFleets calls cylinder-fleets URL', async () => {
            await API.getCylinderFleets();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:cylinder-fleets');
        });

        it('getCylinderFleetDetails includes fleetId', async () => {
            await API.getCylinderFleetDetails('fleet-1');
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('api:v1:cylinder-fleet-detail');
            expect(url).toContain('fleet-1');
        });

        it('getCylinderFleetCylinders includes fleetId', async () => {
            await API.getCylinderFleetCylinders('fleet-1');
            expect(fetch.mock.calls[0][0]).toContain('api:v1:cylinder-fleet-cylinders');
        });

        it('getCylinderInstalls builds query params from options', async () => {
            await API.getCylinderInstalls({
                cylinder_id: 'cyl-1',
                fleet_id: 'fleet-1',
                status: 'installed',
            });
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('cylinder_id=cyl-1');
            expect(url).toContain('fleet_id=fleet-1');
            expect(url).toContain('status=installed');
        });

        it('getCylinderInstalls omits query string when no params given', async () => {
            await API.getCylinderInstalls();
            const url = fetch.mock.calls[0][0];
            expect(url).not.toContain('?');
        });

        it('getCylinderInstalls supports partial params', async () => {
            await API.getCylinderInstalls({ status: 'removed' });
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('status=removed');
            expect(url).not.toContain('cylinder_id');
            expect(url).not.toContain('fleet_id');
        });

        it('getCylinderInstallsGeoJSON calls cylinder-installs-geojson', async () => {
            await API.getCylinderInstallsGeoJSON();
            expect(fetch.mock.calls[0][0]).toContain('api:v1:cylinder-installs-geojson');
        });

        it('createCylinderInstall posts install data as JSON', async () => {
            await API.createCylinderInstall({ cylinder_id: 'cyl-1' });
            const [, config] = fetch.mock.calls[0];
            expect(config.method).toBe('POST');
            expect(JSON.parse(config.body)).toEqual({ cylinder_id: 'cyl-1' });
        });

        it('getCylinderInstallDetails includes installId', async () => {
            await API.getCylinderInstallDetails('inst-1');
            expect(fetch.mock.calls[0][0]).toContain('inst-1');
        });

        it('updateCylinderInstall patches install-detail URL', async () => {
            await API.updateCylinderInstall('inst-1', { status: 'removed' });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:cylinder-install-detail');
            expect(config.method).toBe('PATCH');
        });

        it('deleteCylinderInstall calls install-detail with DELETE', async () => {
            await API.deleteCylinderInstall('inst-1');
            expect(fetch.mock.calls[0][1].method).toBe('DELETE');
        });
    });

    describe('cylinder pressure check endpoints', () => {
        beforeEach(() => {
            globalThis.fetch = mockFetchResponse({ success: true });
        });

        it('getCylinderPressureChecks calls pressure-checks URL', async () => {
            await API.getCylinderPressureChecks('inst-1');
            expect(fetch.mock.calls[0][0]).toContain('api:v1:cylinder-install-pressure-checks');
        });

        it('createCylinderPressureCheck posts check data', async () => {
            await API.createCylinderPressureCheck('inst-1', { pressure: 200 });
            const [, config] = fetch.mock.calls[0];
            expect(config.method).toBe('POST');
            expect(JSON.parse(config.body)).toEqual({ pressure: 200 });
        });

        it('getCylinderPressureCheckDetails passes installId and checkId', async () => {
            await API.getCylinderPressureCheckDetails('inst-1', 'check-1');
            const url = fetch.mock.calls[0][0];
            expect(url).toContain('inst-1');
            expect(url).toContain('check-1');
        });

        it('updateCylinderPressureCheck patches check detail', async () => {
            await API.updateCylinderPressureCheck('inst-1', 'check-1', { pressure: 180 });
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:cylinder-pressure-check-detail');
            expect(config.method).toBe('PATCH');
        });

        it('deleteCylinderPressureCheck calls detail URL with DELETE', async () => {
            await API.deleteCylinderPressureCheck('inst-1', 'check-1');
            const [url, config] = fetch.mock.calls[0];
            expect(url).toContain('api:v1:cylinder-pressure-check-detail');
            expect(config.method).toBe('DELETE');
        });
    });
});
