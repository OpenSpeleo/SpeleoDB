import type { Mock } from 'vitest';
import type { ApiError } from '../../../../../ts-types/domain/map-transport.ts';
import type { StationWrite } from '../../../../../ts-types/domain/station-records.ts';
import type { CylinderInstallWrite } from '../../../../../ts-types/domain/fleet-records.ts';

interface FixtureRequest { method: string; headers: Record<string, string>; credentials: string; body?: BodyInit; signal?: AbortSignal }
interface FixtureResponse {
    ok: boolean;
    status?: number;
    statusText?: string;
    headers?: { get(name: string): string | null };
    json?: () => Promise<unknown>;
    text?: () => Promise<string>;
}
type FixtureFetch = (url: string, config: FixtureRequest) => Promise<FixtureResponse>;
let fetch: Mock<FixtureFetch>;
const fetchStub = {
    set current(value: Mock<FixtureFetch>) { fetch = value; vi.stubGlobal('fetch', value); },
};
interface ResponseOptions { ok?: boolean; status?: number; headers?: Record<string, string>; statusText?: string; text?: string }
import { API } from './api.ts';
import { Utils } from './utils.ts';

vi.mock('./utils.ts', () => ({
    Utils: {
        getCSRFToken: vi.fn(() => 'test-csrf-token'),
    },
}));

function mockFetchResponse(
    data: unknown,
    {
        ok = true,
        status = 200,
        headers = { 'content-type': 'application/json' },
        statusText = '',
        text,
    }: ResponseOptions = {}
) {
    return vi.fn<FixtureFetch>(() =>
        Promise.resolve({
            ok,
            status,
            statusText,
            headers: {
                get: (name: string) => headers[name.toLowerCase()] || headers[name] || null,
            },
            json: () => Promise.resolve(data),
            text: () => Promise.resolve(
                text !== undefined
                    ? text
                    : (typeof data === 'string' ? data : JSON.stringify(data) || '')
            ),
        })
    );
}

describe('API module', () => {
    beforeEach(() => {
        vi.stubGlobal('Urls', new Proxy(
            {},
            {
                get: (_target, prop) =>
                    (...args: (string | number)[]) =>
                        `/api/${String(prop)}${args.length ? '/' + args.join('/') : ''}`,
            }
        ));
    });

    afterEach(() => {
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    // ------------------------------------------------------------------ //
    // apiRequest core behavior (tested through public API methods)
    // ------------------------------------------------------------------ //

    describe('request configuration', () => {
        it('observes the current CSRF facade method and receiver for every request', async () => {
            fetchStub.current = mockFetchResponse({});
            const original = Object.getOwnPropertyDescriptor(Utils, 'getCSRFToken')!;
            try {
                Utils.getCSRFToken = function () { return this === Utils ? 'first' : 'wrong receiver'; };
                await API.getAllProjects();
                Utils.getCSRFToken = () => 'second';
                await API.getAllProjects();
                expect(fetch.mock.calls.map(([, config]) => config.headers['X-CSRFToken'])).toEqual(['first', 'second']);
            } finally { Object.defineProperty(Utils, 'getCSRFToken', original); }
        });

        it('uses the private GIS Layer list and detail routes', async () => {
            fetchStub.current = mockFetchResponse({});

            await API.getGISLayers();
            await API.getGISLayerDetails('layer-1');

            expect(fetch.mock.calls.map(([url]) => url)).toEqual([
                '/api/api:v2:gis-layers',
                '/api/api:v2:gis-layer-detail/layer-1',
            ]);
        });

        it('includes CSRF token and Content-Type headers for JSON requests', async () => {
            fetchStub.current = mockFetchResponse({});

            await API.getAllProjects();

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'X-CSRFToken': 'test-csrf-token',
                        'Content-Type': 'application/json',
                    }) as unknown,
                })
            );
        });

        it('omits Content-Type header for FormData requests', async () => {
            fetchStub.current = mockFetchResponse({});
            const formData = new FormData();
            formData.append('file', 'test');

            await API.createStationLog('station-1', formData);

            const [, config] = fetch.mock.calls[0]!;
            expect(config.headers['Content-Type']).toBeUndefined();
            expect(config.headers['X-CSRFToken']).toBe('test-csrf-token');
        });

        it('sets credentials to same-origin', async () => {
            fetchStub.current = mockFetchResponse({});

            await API.getAllProjects();

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({ credentials: 'same-origin' })
            );
        });

        it('JSON-stringifies body for non-FormData POST requests', async () => {
            fetchStub.current = mockFetchResponse({});
            const stationData = { name: 'Test Station', lat: 45.0 };

            await API.createStation('proj-1', stationData);

            const [, config] = fetch.mock.calls[0]!;
            expect(config.body).toBe(JSON.stringify(stationData));
        });

        it('passes FormData body directly without JSON.stringify', async () => {
            fetchStub.current = mockFetchResponse({});
            const formData = new FormData();
            formData.append('file', 'test');

            await API.createStationResource('station-1', formData);

            const [, config] = fetch.mock.calls[0]!;
            expect(config.body).toBe(formData);
        });

        it('does not include body for GET requests', async () => {
            fetchStub.current = mockFetchResponse({});

            await API.getAllProjects();

            const [, config] = fetch.mock.calls[0]!;
            expect(config.body).toBeUndefined();
        });
    });

    describe('response handling', () => {
        it('returns { ok: true, status: 204 } for 204 No Content', async () => {
            fetchStub.current = vi.fn<FixtureFetch>(() =>
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
            const responseData = [{ id: '1' }];
            fetchStub.current = mockFetchResponse(responseData);

            const result = await API.getAllProjects();
            expect(result).toEqual(responseData);
        });

        it('returns null when a successful JSON response has an empty body', async () => {
            fetchStub.current = vi.fn<FixtureFetch>(() =>
                Promise.resolve({
                    ok: true,
                    status: 200,
                    headers: {
                        get: () => 'application/json',
                    },
                    json: () => Promise.reject(new SyntaxError('Unexpected end of JSON input')),
                    text: () => Promise.resolve(''),
                })
            );

            const result = await API.getAllProjects();
            expect(result).toBeNull();
        });
    });

    describe('error handling', () => {
        it('throws error with message from response for non-ok responses', async () => {
            fetchStub.current = mockFetchResponse({ message: 'Not found' }, { ok: false, status: 404 });

            await expect(API.getAllProjects()).rejects.toThrow('Not found');
        });

        it('attaches status and data to thrown error', async () => {
            const errorData = { message: 'Forbidden', detail: 'No permission' };
            fetchStub.current = mockFetchResponse(errorData, { ok: false, status: 403 });

            let caught: ApiError | undefined;
            try {
                await API.getAllProjects();
            } catch (error) {
                caught = error as ApiError;
            }

            expect(caught).toBeDefined();
            expect(caught!.status).toBe(403);
            expect(caught!.data).toEqual(errorData);
        });

        it('falls back to error field when message is absent', async () => {
            fetchStub.current = mockFetchResponse({ error: 'Server error' }, { ok: false, status: 500 });

            await expect(API.getAllProjects()).rejects.toThrow('Server error');
        });

        it('falls back to detail field when message and error are absent', async () => {
            fetchStub.current = mockFetchResponse({ detail: 'Auth required' }, { ok: false, status: 401 });

            await expect(API.getAllProjects()).rejects.toThrow('Auth required');
        });

        it('uses default message when no error fields present', async () => {
            fetchStub.current = mockFetchResponse({ foo: 'bar' }, { ok: false, status: 500 });

            await expect(API.getAllProjects()).rejects.toThrow('API request failed');
        });

        it('uses plain-text error bodies when JSON is unavailable', async () => {
            fetchStub.current = mockFetchResponse('Proxy exploded', {
                ok: false,
                status: 502,
                headers: { 'content-type': 'text/plain' },
            });

            await expect(API.getAllProjects()).rejects.toMatchObject({
                message: 'Proxy exploded',
                status: 502,
                data: 'Proxy exploded',
            });
        });

        it('rejects when fetch itself throws (network error)', async () => {
            fetchStub.current = vi.fn<FixtureFetch>(() => Promise.reject(new TypeError('Failed to fetch')));

            await expect(API.getAllProjects()).rejects.toThrow('Failed to fetch');
        });
    });

    // ------------------------------------------------------------------ //
    // HTTP method routing
    // ------------------------------------------------------------------ //

    describe('HTTP method routing', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('uses GET for read operations', async () => {
            await API.getAllProjects();
            expect(fetch.mock.calls[0]![1].method).toBe('GET');
        });

        it('uses POST for create operations', async () => {
            await API.createStation('proj-1', { name: 'Test' });
            expect(fetch.mock.calls[0]![1].method).toBe('POST');
        });

        it('uses PATCH for update operations', async () => {
            await API.updateStation('station-1', { name: 'Updated' });
            expect(fetch.mock.calls[0]![1].method).toBe('PATCH');
        });

        it('uses DELETE for delete operations', async () => {
            await API.deleteStation('station-1');
            expect(fetch.mock.calls[0]![1].method).toBe('DELETE');
        });

        it('uses PUT for import operations', async () => {
            const formData = new FormData();
            await API.importGPX(formData);
            expect(fetch.mock.calls[0]![1].method).toBe('PUT');
        });
    });

    // ------------------------------------------------------------------ //
    // Endpoint-specific tests
    // ------------------------------------------------------------------ //

    describe('station endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('createStation calls project-stations URL with POST', async () => {
            await API.createStation('proj-1', { name: 'New' });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:project-stations');
            expect(url).toContain('proj-1');
            expect(config.method).toBe('POST');
        });

        it('updateStation calls station-detail URL with PATCH', async () => {
            await API.updateStation('st-1', { name: 'Updated' });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:station-detail');
            expect(url).toContain('st-1');
            expect(config.method).toBe('PATCH');
        });

        it('deleteStation calls station-detail URL with DELETE', async () => {
            await API.deleteStation('st-1');
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:station-detail');
            expect(config.method).toBe('DELETE');
        });

        it('getProjectStations calls project-stations URL with GET', async () => {
            await API.getProjectStations('proj-1');
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:project-stations');
            expect(config.method).toBe('GET');
        });

        it('getStationDetails calls station-detail URL with GET', async () => {
            await API.getStationDetails('st-1');
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:station-detail');
            expect(config.method).toBe('GET');
        });

        it('getAllStationsGeoJSON calls subsurface-stations-geojson', async () => {
            await API.getAllStationsGeoJSON();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:subsurface-stations-geojson');
        });
    });

    describe('surface network and station endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getAllSurfaceNetworks calls surface-networks URL', async () => {
            await API.getAllSurfaceNetworks();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:surface-networks');
        });

        it('createSurfaceStation posts to network-stations URL', async () => {
            await API.createSurfaceStation('net-1', { name: 'Surface' });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:network-stations');
            expect(url).toContain('net-1');
            expect(config.method).toBe('POST');
        });

        it('getNetworkStations calls network-stations URL', async () => {
            await API.getNetworkStations('net-1');
            expect(fetch.mock.calls[0]![0]).toContain('net-1');
        });

        it('getNetworkStationsGeoJSON includes networkId in URL', async () => {
            await API.getNetworkStationsGeoJSON('net-1');
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('api:v2:network-stations-geojson');
            expect(url).toContain('net-1');
        });

        it('getAllSurfaceStations calls surface-stations URL', async () => {
            await API.getAllSurfaceStations();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:surface-stations');
        });

        it('getAllSurfaceStationsGeoJSON calls surface-stations-geojson', async () => {
            await API.getAllSurfaceStationsGeoJSON();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:surface-stations-geojson');
        });
    });

    describe('landmark endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('createLandmark posts to landmarks URL', async () => {
            await API.createLandmark({ name: 'Entrance' });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:landmarks');
            expect(config.method).toBe('POST');
        });

        it('updateLandmark patches landmark-detail URL', async () => {
            await API.updateLandmark('lm-1', { name: 'Updated' });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:landmark-detail');
            expect(config.method).toBe('PATCH');
        });

        it('deleteLandmark deletes from landmark-detail URL', async () => {
            await API.deleteLandmark('lm-1');
            expect(fetch.mock.calls[0]![1].method).toBe('DELETE');
        });

        it('getAllLandmarks calls landmarks URL', async () => {
            await API.getAllLandmarks();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:landmarks');
        });

        it('getLandmarkCollections calls landmark-collections URL', async () => {
            await API.getLandmarkCollections();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:landmark-collections');
        });

        it('getAllLandmarksGeoJSON calls landmarks-geojson', async () => {
            await API.getAllLandmarksGeoJSON();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:landmarks-geojson');
        });
    });

    describe('tag endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getUserTags calls station-tags URL', async () => {
            await API.getUserTags();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:station-tags');
        });

        it('getTagColors calls station-tag-colors URL', async () => {
            await API.getTagColors();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:station-tag-colors');
        });

        it('createTag posts name and color to station-tags', async () => {
            await API.createTag('Important', '#ff0000');
            const [, config] = fetch.mock.calls[0]!;
            expect(JSON.parse(config.body as string)).toEqual({ name: 'Important', color: '#ff0000' });
        });

        it('setStationTag posts tag_id to station-tags-manage', async () => {
            await API.setStationTag('st-1', 'tag-1');
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:station-tags-manage');
            expect(JSON.parse(config.body as string)).toEqual({ tag_id: 'tag-1' });
        });

        it('removeStationTag deletes from station-tags-manage', async () => {
            await API.removeStationTag('st-1');
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:station-tags-manage');
            expect(config.method).toBe('DELETE');
        });
    });

    describe('station log endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getStationLogs calls station-logs URL', async () => {
            await API.getStationLogs('st-1');
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:station-logs');
        });

        it('createStationLog sends FormData with POST', async () => {
            const formData = new FormData();
            await API.createStationLog('st-1', formData);
            const [, config] = fetch.mock.calls[0]!;
            expect(config.method).toBe('POST');
            expect(config.body).toBe(formData);
        });

        it('updateStationLog sends FormData with PATCH', async () => {
            const formData = new FormData();
            await API.updateStationLog('log-1', formData);
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:log-detail');
            expect(config.method).toBe('PATCH');
            expect(config.body).toBe(formData);
        });

        it('deleteStationLog calls log-detail with DELETE', async () => {
            await API.deleteStationLog('log-1');
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:log-detail');
            expect(config.method).toBe('DELETE');
        });
    });

    describe('experiment endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getExperiments calls experiments URL', async () => {
            await API.getExperiments();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:experiments');
        });

        it('getExperimentData passes stationId and experimentId', async () => {
            await API.getExperimentData('st-1', 'exp-1');
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('api:v2:experiment-records');
            expect(url).toContain('st-1');
            expect(url).toContain('exp-1');
        });

        it('createExperimentRecord posts JSON to experiment-records URL', async () => {
            const payload = { field: 'value' };
            await API.createExperimentRecord('st-1', 'exp-1', payload);
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:experiment-records');
            expect(url).toContain('st-1');
            expect(url).toContain('exp-1');
            expect(config.method).toBe('POST');
            expect(JSON.parse(config.body as string)).toEqual(payload);
        });

        it('updateExperimentRecord sends PUT to experiment-records-detail URL', async () => {
            const payload = { field: 'updated' };
            await API.updateExperimentRecord('record-1', payload);
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:experiment-records-detail');
            expect(url).toContain('record-1');
            expect(config.method).toBe('PUT');
            expect(JSON.parse(config.body as string)).toEqual(payload);
        });

        it('deleteExperimentRecord calls experiment-records-detail with DELETE', async () => {
            await API.deleteExperimentRecord('record-1');
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:experiment-records-detail');
            expect(url).toContain('record-1');
            expect(config.method).toBe('DELETE');
        });
    });

    describe('resource endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getStationResources calls station-resources URL', async () => {
            await API.getStationResources('st-1');
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:station-resources');
        });

        it('createStationResource sends FormData with POST', async () => {
            const formData = new FormData();
            await API.createStationResource('st-1', formData);
            const [, config] = fetch.mock.calls[0]!;
            expect(config.method).toBe('POST');
            expect(config.body).toBe(formData);
        });

        it('updateStationResource sends FormData with PATCH', async () => {
            const formData = new FormData();
            await API.updateStationResource('res-1', formData);
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:resource-detail');
            expect(config.method).toBe('PATCH');
            expect(config.body).toBe(formData);
        });

        it('deleteStationResource calls resource-detail with DELETE', async () => {
            await API.deleteStationResource('res-1');
            expect(fetch.mock.calls[0]![1].method).toBe('DELETE');
        });
    });

    describe('project endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getAllProjects calls projects URL', async () => {
            await API.getAllProjects();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:projects');
        });

        it('getAllProjectsGeoJSON calls all-projects-geojson', async () => {
            await API.getAllProjectsGeoJSON();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:all-projects-geojson');
        });
    });

    describe('exploration lead endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getProjectExplorationLeadsGeoJSON includes projectId', async () => {
            await API.getProjectExplorationLeadsGeoJSON('proj-1');
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('api:v2:project-exploration-leads-geojson');
            expect(url).toContain('proj-1');
        });

        it('getAllProjectExplorationLeadsGeoJSON calls all geojson URL', async () => {
            await API.getAllProjectExplorationLeadsGeoJSON();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:exploration-lead-all-geojson');
        });

        it('getProjectExplorationLeads calls project leads URL', async () => {
            await API.getProjectExplorationLeads('proj-1');
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:project-exploration-leads');
        });

        it('createExplorationLead posts to project exploration leads', async () => {
            await API.createExplorationLead('proj-1', { description: 'A lead' });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:project-exploration-leads');
            expect(url).toContain('proj-1');
            expect(config.method).toBe('POST');
        });

        it('updateExplorationLead patches exploration-lead-detail', async () => {
            await API.updateExplorationLead('lead-1', { description: 'Updated' });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:exploration-lead-detail');
            expect(config.method).toBe('PATCH');
        });

        it('deleteExplorationLead calls exploration-lead-detail with DELETE', async () => {
            await API.deleteExplorationLead('lead-1');
            expect(fetch.mock.calls[0]![1].method).toBe('DELETE');
        });
    });

    describe('sensor fleet and install endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getSensorFleets calls sensor-fleets URL', async () => {
            await API.getSensorFleets();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:sensor-fleets');
        });

        it('getSensorFleetDetails includes fleetId', async () => {
            await API.getSensorFleetDetails('fleet-1');
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('api:v2:sensor-fleet-detail');
            expect(url).toContain('fleet-1');
        });

        it('getSensorFleetSensors includes fleetId', async () => {
            await API.getSensorFleetSensors('fleet-1');
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:sensor-fleet-sensors');
        });

        it('getStationSensorInstalls calls station-sensor-installs URL', async () => {
            await API.getStationSensorInstalls('st-1');
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:station-sensor-installs');
        });

        it('getStationSensorInstallsWithStatus appends status query param', async () => {
            await API.getStationSensorInstallsWithStatus('st-1', 'active');
            expect(fetch.mock.calls[0]![0]).toContain('?status=active');
        });

        it('getStationSensorInstallsAsExcel returns raw response object', async () => {
            const rawResponse = { ok: true, status: 200 };
            fetchStub.current = vi.fn<FixtureFetch>(() => Promise.resolve(rawResponse));

            const result = await API.getStationSensorInstallsAsExcel('st-1');
            expect(result).toBe(rawResponse);
        });

        it('getStationSensorInstallsAsExcel includes CSRF token', async () => {
            fetchStub.current = vi.fn<FixtureFetch>(() => Promise.resolve({ ok: true }));

            await API.getStationSensorInstallsAsExcel('st-1');

            const [, config] = fetch.mock.calls[0]!;
            expect(config.headers['X-CSRFToken']).toBe('test-csrf-token');
            expect(config.credentials).toBe('same-origin');
        });

        it('getStationSensorInstallDetails passes stationId and installId', async () => {
            await API.getStationSensorInstallDetails('st-1', 'inst-1');
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('st-1');
            expect(url).toContain('inst-1');
        });

        it('createStationSensorInstalls sends FormData with POST', async () => {
            const formData = new FormData();
            await API.createStationSensorInstalls('st-1', formData);
            const [, config] = fetch.mock.calls[0]!;
            expect(config.method).toBe('POST');
            expect(config.body).toBe(formData);
        });

        it('updateStationSensorInstalls sends FormData with PATCH', async () => {
            const formData = new FormData();
            await API.updateStationSensorInstalls('st-1', 'inst-1', formData);
            const [, config] = fetch.mock.calls[0]!;
            expect(config.method).toBe('PATCH');
            expect(config.body).toBe(formData);
        });
    });

    describe('GPS track and GPX import endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getGPSTracks calls gps-tracks URL', async () => {
            await API.getGPSTracks();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:gps-tracks');
        });

        it('getGPSTrackDetails requests a fresh detail response', async () => {
            await API.getGPSTrackDetails('track-1');
            expect(fetch.mock.calls[0]![0]).toContain(
                'api:v2:gps-track-detail/track-1'
            );
        });

        it('importGPX sends FormData with PUT', async () => {
            const formData = new FormData();
            await API.importGPX(formData);
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:gpx-import');
            expect(config.method).toBe('PUT');
            expect(config.body).toBe(formData);
        });
    });

    describe('cylinder fleet endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getCylinderFleets calls cylinder-fleets URL', async () => {
            await API.getCylinderFleets();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:cylinder-fleets');
        });

        it('getCylinderFleetDetails includes fleetId', async () => {
            await API.getCylinderFleetDetails('fleet-1');
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('api:v2:cylinder-fleet-detail');
            expect(url).toContain('fleet-1');
        });

        it('getCylinderFleetCylinders includes fleetId', async () => {
            await API.getCylinderFleetCylinders('fleet-1');
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:cylinder-fleet-cylinders');
        });

        it('getCylinderInstalls builds query params from options', async () => {
            await API.getCylinderInstalls({
                cylinder_id: 'cyl-1',
                fleet_id: 'fleet-1',
                status: 'installed',
            });
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('cylinder_id=cyl-1');
            expect(url).toContain('fleet_id=fleet-1');
            expect(url).toContain('status=installed');
        });

        it('getCylinderInstalls omits query string when no params given', async () => {
            await API.getCylinderInstalls();
            const url = fetch.mock.calls[0]![0];
            expect(url).not.toContain('?');
        });

        it('getCylinderInstalls supports partial params', async () => {
            await API.getCylinderInstalls({ status: 'removed' });
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('status=removed');
            expect(url).not.toContain('cylinder_id');
            expect(url).not.toContain('fleet_id');
        });

        it('getCylinderInstallsGeoJSON calls cylinder-installs-geojson', async () => {
            await API.getCylinderInstallsGeoJSON();
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:cylinder-installs-geojson');
        });

        it('createCylinderInstall posts install data as JSON', async () => {
            await API.createCylinderInstall({ cylinder_id: 'cyl-1' } as unknown as CylinderInstallWrite);
            const [, config] = fetch.mock.calls[0]!;
            expect(config.method).toBe('POST');
            expect(JSON.parse(config.body as string)).toEqual({ cylinder_id: 'cyl-1' });
        });

        it('getCylinderInstallDetails includes installId', async () => {
            await API.getCylinderInstallDetails('inst-1');
            expect(fetch.mock.calls[0]![0]).toContain('inst-1');
        });

        it('updateCylinderInstall patches install-detail URL', async () => {
            await API.updateCylinderInstall('inst-1', { status: 'removed' });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:cylinder-install-detail');
            expect(config.method).toBe('PATCH');
        });

        it('deleteCylinderInstall calls install-detail with DELETE', async () => {
            await API.deleteCylinderInstall('inst-1');
            expect(fetch.mock.calls[0]![1].method).toBe('DELETE');
        });
    });

    describe('cylinder pressure check endpoints', () => {
        beforeEach(() => {
            fetchStub.current = mockFetchResponse({});
        });

        it('getCylinderPressureChecks calls pressure-checks URL', async () => {
            await API.getCylinderPressureChecks('inst-1');
            expect(fetch.mock.calls[0]![0]).toContain('api:v2:cylinder-install-pressure-checks');
        });

        it('createCylinderPressureCheck posts check data', async () => {
            await API.createCylinderPressureCheck('inst-1', { pressure: 200 });
            const [, config] = fetch.mock.calls[0]!;
            expect(config.method).toBe('POST');
            expect(JSON.parse(config.body as string)).toEqual({ pressure: 200 });
        });

        it('getCylinderPressureCheckDetails passes installId and checkId', async () => {
            await API.getCylinderPressureCheckDetails('inst-1', 'check-1');
            const url = fetch.mock.calls[0]![0];
            expect(url).toContain('inst-1');
            expect(url).toContain('check-1');
        });

        it('updateCylinderPressureCheck patches check detail', async () => {
            await API.updateCylinderPressureCheck('inst-1', 'check-1', { pressure: 180 });
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:cylinder-pressure-check-detail');
            expect(config.method).toBe('PATCH');
        });

        it('deleteCylinderPressureCheck calls detail URL with DELETE', async () => {
            await API.deleteCylinderPressureCheck('inst-1', 'check-1');
            const [url, config] = fetch.mock.calls[0]!;
            expect(url).toContain('api:v2:cylinder-pressure-check-detail');
            expect(config.method).toBe('DELETE');
        });
    });
});

describe('API literal transport edge contracts', () => {
    beforeEach(() => {
        vi.stubGlobal('Urls', { 'api:v2:projects': () => '/projects/', 'api:v2:project-stations': () => '/stations/', 'api:v2:gis-geometry-detail': () => '/geometry/' });
    });
    afterEach(() => { vi.unstubAllGlobals(); });
    it.each([null, false, 0, ''])('omits a falsey JSON body without changing the method', async body => {
        const request = vi.fn<FixtureFetch>().mockResolvedValue(new Response('{}'));
        vi.stubGlobal('fetch', request);
        await API.createStation('project', body as unknown as StationWrite);
        expect(request.mock.calls[0]![1]).not.toHaveProperty('body');
        expect(request.mock.calls[0]![1].method).toBe('POST');
    });
    it('preserves supplied AbortSignal identity', async () => {
        const request = vi.fn<FixtureFetch>().mockResolvedValue(new Response('{}'));
        vi.stubGlobal('fetch', request);
        const controller = new AbortController();
        await API.getGISGeometryDetails('geometry', { signal: controller.signal });
        expect(request.mock.calls[0]![1].signal).toBe(controller.signal);
    });
    it('returns the parsed JSON object itself and ordinary augmented errors retaining data identity', async () => {
        const data = { message: 'first', error: 'second', detail: 'third' };
        const response = { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => data };
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
        expect(await API.getAllProjects()).toBe(data);
        response.ok = false;
        try { await API.getAllProjects(); } catch (error) {
            expect(Object.getPrototypeOf(error)).toBe(Error.prototype);
            expect((error as ApiError).message).toBe('first');
            expect((error as ApiError).data).toBe(data);
            expect((error as ApiError).status).toBe(200);
        }
    });
    it('parses JSON under a text content type and preserves non-JSON response strings', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response('{"value":1}')).mockResolvedValueOnce(new Response(' plain text ')));
        expect(await API.getAllProjects()).toEqual({ value: 1 });
        expect(await API.getAllProjects()).toBe(' plain text ');
    });
});
