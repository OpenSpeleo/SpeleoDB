import { API } from './api.ts';
import { ApiRequestError } from '../../../../../frontend_common/api/client.ts';
import { setBrowserUrl, startApiServer, useNativeFetchBodyConstructors } from '../../../../../frontend_common/test/api-server.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; server = await startApiServer(); });
beforeEach(() => {
    server.reset();
    setBrowserUrl(`${server.origin}/private/map/`);
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">';
});
afterEach(() => { document.body.innerHTML = ''; });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

interface RouteCase { name: string; call: () => Promise<unknown>; path: string; method?: string; status?: number; body?: unknown; empty?: boolean }

const reads: RouteCase[] = [
    { name: 'GIS geometry list', call: API.getGISGeometries, path: 'gis-geometries/' },
    { name: 'GIS geometry detail', call: () => API.getGISGeometryDetails('geometry'), path: 'gis-geometries/geometry/' },
    { name: 'GIS layers', call: API.getGISLayers, path: 'gis-layers/' },
    { name: 'GIS layer detail', call: () => API.getGISLayerDetails('layer'), path: 'gis-layers/layer/' },
    { name: 'project stations', call: () => API.getProjectStations('project'), path: 'projects/project/stations/' },
    { name: 'station detail', call: () => API.getStationDetails('station'), path: 'stations/station/' },
    { name: 'subsurface GeoJSON', call: API.getAllStationsGeoJSON, path: 'stations/subsurface/geojson/' },
    { name: 'surface networks', call: API.getAllSurfaceNetworks, path: 'surface-networks/' },
    { name: 'network stations', call: () => API.getNetworkStations('network'), path: 'surface-networks/network/stations/' },
    { name: 'network GeoJSON', call: () => API.getNetworkStationsGeoJSON('network'), path: 'surface-networks/network/stations/geojson/' },
    { name: 'surface stations', call: API.getAllSurfaceStations, path: 'stations/surface/' },
    { name: 'surface GeoJSON', call: API.getAllSurfaceStationsGeoJSON, path: 'stations/surface/geojson/' },
    { name: 'landmarks', call: API.getAllLandmarks, path: 'landmarks/' },
    { name: 'landmark collections', call: API.getLandmarkCollections, path: 'landmark-collections/' },
    { name: 'landmark GeoJSON', call: API.getAllLandmarksGeoJSON, path: 'landmarks/geojson/' },
    { name: 'tags', call: API.getUserTags, path: 'station_tags/' },
    { name: 'tag colors', call: API.getTagColors, path: 'station_tags/colors/' },
    { name: 'station logs', call: () => API.getStationLogs('station'), path: 'stations/station/logs/' },
    { name: 'experiments', call: API.getExperiments, path: 'experiments/' },
    { name: 'experiment data', call: () => API.getExperimentData('station', 'experiment'), path: 'stations/station/experiment/experiment/records/' },
    { name: 'station resources', call: () => API.getStationResources('station'), path: 'stations/station/resources/' },
    { name: 'projects', call: API.getAllProjects, path: 'projects/' },
    { name: 'project GeoJSON', call: API.getAllProjectsGeoJSON, path: 'projects/geojson/' },
    { name: 'project leads', call: () => API.getProjectExplorationLeads('project'), path: 'projects/project/exploration-leads/' },
    { name: 'project lead GeoJSON', call: () => API.getProjectExplorationLeadsGeoJSON('project'), path: 'projects/project/exploration-leads/geojson/' },
    { name: 'all lead GeoJSON', call: API.getAllProjectExplorationLeadsGeoJSON, path: 'exploration-leads/geojson/' },
    { name: 'sensor fleets', call: API.getSensorFleets, path: 'sensor-fleets/' },
    { name: 'sensor fleet detail', call: () => API.getSensorFleetDetails('fleet'), path: 'sensor-fleets/fleet/' },
    { name: 'fleet sensors', call: () => API.getSensorFleetSensors('fleet'), path: 'sensor-fleets/fleet/sensors/' },
    { name: 'station sensor installs', call: () => API.getStationSensorInstalls('station'), path: 'stations/station/sensor-installs/' },
    { name: 'filtered station sensors', call: () => API.getStationSensorInstallsWithStatus('station', 'active'), path: 'stations/station/sensor-installs/?status=active' },
    { name: 'station sensor detail', call: () => API.getStationSensorInstallDetails('station', 'install'), path: 'stations/station/sensor-installs/install/' },
    { name: 'GPS tracks', call: API.getGPSTracks, path: 'gps_tracks/' },
    { name: 'GPS detail', call: () => API.getGPSTrackDetails('track'), path: 'gps_tracks/track/' },
    { name: 'cylinder fleets', call: API.getCylinderFleets, path: 'cylinder-fleets/' },
    { name: 'cylinder fleet detail', call: () => API.getCylinderFleetDetails('fleet'), path: 'cylinder-fleets/fleet/' },
    { name: 'fleet cylinders', call: () => API.getCylinderFleetCylinders('fleet'), path: 'cylinder-fleets/fleet/cylinders/' },
    { name: 'cylinder installs', call: API.getCylinderInstalls, path: 'cylinder-installs/' },
    { name: 'cylinder GeoJSON', call: API.getCylinderInstallsGeoJSON, path: 'cylinder-installs/geojson/' },
    { name: 'all cylinder GeoJSON', call: API.getAllCylinderInstallsGeoJSON, path: 'cylinder-installs/geojson/' },
    { name: 'cylinder install detail', call: () => API.getCylinderInstallDetails('install'), path: 'cylinder-installs/install/' },
    { name: 'pressure checks', call: () => API.getCylinderPressureChecks('install'), path: 'cylinder-installs/install/pressure-checks/' },
    { name: 'pressure check detail', call: () => API.getCylinderPressureCheckDetails('install', 'check'), path: 'cylinder-installs/install/pressure-checks/check/' },
];

it.each(reads)('$name uses the generated GET route without a body', async ({ call, path }) => {
    await call();
    expect(server.requests).toHaveLength(1);
    expect(server.requests[0]).toMatchObject({ method: 'GET', path: `/api/v2/${path}`, body: '', headers: { 'x-csrftoken': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' } });
});

const mutations: RouteCase[] = [
    { name: 'create station', call: () => API.createStation('project', { name: 'Café', latitude: 12.5, longitude: -71, type: 'biology' }), method: 'POST', path: 'projects/project/stations/', status: 201, body: { name: 'Café', latitude: 12.5, longitude: -71, type: 'biology' } },
    { name: 'update station', call: () => API.updateStation('station', { name: 'Updated' }), method: 'PATCH', path: 'stations/station/', body: { name: 'Updated' } },
    { name: 'delete station', call: () => API.deleteStation('station'), method: 'DELETE', path: 'stations/station/' },
    { name: 'create surface station', call: () => API.createSurfaceStation('network', { name: 'Surface', latitude: 1, longitude: 2 }), method: 'POST', path: 'surface-networks/network/stations/', status: 201, body: { name: 'Surface', latitude: 1, longitude: 2 } },
    { name: 'create landmark', call: () => API.createLandmark({ name: 'Entrance', latitude: 1, longitude: 2 }), method: 'POST', path: 'landmarks/', status: 201, body: { name: 'Entrance', latitude: 1, longitude: 2 } },
    { name: 'update landmark', call: () => API.updateLandmark('landmark', { name: 'Updated' }), method: 'PATCH', path: 'landmarks/landmark/', body: { name: 'Updated' } },
    { name: 'delete landmark', call: () => API.deleteLandmark('landmark'), method: 'DELETE', path: 'landmarks/landmark/' },
    { name: 'create tag', call: () => API.createTag('Important', '#ff0000'), method: 'POST', path: 'station_tags/', status: 201, body: { name: 'Important', color: '#ff0000' } },
    { name: 'set station tag', call: () => API.setStationTag('station', 'tag'), method: 'POST', path: 'stations/station/tags/', body: { tag_id: 'tag' } },
    { name: 'remove station tag', call: () => API.removeStationTag('station'), method: 'DELETE', path: 'stations/station/tags/', empty: true },
    { name: 'delete log', call: () => API.deleteStationLog('log'), method: 'DELETE', path: 'logs/log/' },
    { name: 'create experiment record', call: () => API.createExperimentRecord('station', 'experiment', { field: 'value' }), method: 'POST', path: 'stations/station/experiment/experiment/records/', status: 201, body: { field: 'value' } },
    { name: 'update experiment record', call: () => API.updateExperimentRecord('record', { field: 'updated' }), method: 'PUT', path: 'experiment_records/record/', body: { field: 'updated' } },
    { name: 'delete experiment record', call: () => API.deleteExperimentRecord('record'), method: 'DELETE', path: 'experiment_records/record/' },
    { name: 'delete resource', call: () => API.deleteStationResource('resource'), method: 'DELETE', path: 'resources/resource/' },
    { name: 'create lead', call: () => API.createExplorationLead('project', { description: 'Lead', latitude: 1, longitude: 2 }), method: 'POST', path: 'projects/project/exploration-leads/', status: 201, body: { description: 'Lead', latitude: 1, longitude: 2 } },
    { name: 'update lead', call: () => API.updateExplorationLead('lead', { description: 'Updated' }), method: 'PATCH', path: 'exploration-leads/lead/', body: { description: 'Updated' } },
    { name: 'delete lead', call: () => API.deleteExplorationLead('lead'), method: 'DELETE', path: 'exploration-leads/lead/' },
    { name: 'create cylinder install', call: () => API.createCylinderInstall({ cylinder: 'cylinder', project: 'project', latitude: 1, longitude: 2, install_date: '2026-10-01' }), method: 'POST', path: 'cylinder-installs/', status: 201, body: { cylinder: 'cylinder', project: 'project', latitude: 1, longitude: 2, install_date: '2026-10-01' } },
    { name: 'update cylinder install', call: () => API.updateCylinderInstall('install', { status: 'retrieved' }), method: 'PATCH', path: 'cylinder-installs/install/', body: { status: 'retrieved' } },
    { name: 'delete cylinder install', call: () => API.deleteCylinderInstall('install'), method: 'DELETE', path: 'cylinder-installs/install/' },
    { name: 'create pressure check', call: () => API.createCylinderPressureCheck('install', { pressure: 200, unit_system: 'metric', check_date: '2026-10-01' }), method: 'POST', path: 'cylinder-installs/install/pressure-checks/', status: 201, body: { pressure: 200, unit_system: 'metric', check_date: '2026-10-01' } },
    { name: 'update pressure check', call: () => API.updateCylinderPressureCheck('install', 'check', { pressure: 180 }), method: 'PATCH', path: 'cylinder-installs/install/pressure-checks/check/', body: { pressure: 180 } },
    { name: 'delete pressure check', call: () => API.deleteCylinderPressureCheck('install', 'check'), method: 'DELETE', path: 'cylinder-installs/install/pressure-checks/check/' },
];

it.each(mutations)('$name preserves the generated verb and request body', async ({ call, method, path, status = 200, body, empty }) => {
    server.reply(empty ? { status, headers: { 'Content-Type': '' } } : { status, json: {} });
    const result = await call();
    expect(server.requests[0]).toMatchObject({ method, path: `/api/v2/${path}` });
    if (body) {
        expect(server.requests[0]!.headers['content-type']).toContain('application/json');
        expect(JSON.parse(server.requests[0]!.body)).toEqual(body);
    } else expect(server.requests[0]!.body).toBe('');
    if (empty) expect(result).toBeUndefined();
});

it('reads rotated CSRF tokens at request time and encodes query/path values', async () => {
    await API.getGISGeometryDetails('geometry /é');
    document.querySelector<HTMLInputElement>('input')!.value = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
    await API.getCylinderInstalls({ cylinder_id: 'cylinder &1', fleet_id: 'fleet', status: 'installed' });
    expect(server.requests[0]!.path).toBe('/api/v2/gis-geometries/geometry%20%2F%C3%A9/');
    expect(server.requests[0]!.headers['x-csrftoken']).toBe('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
    expect(server.requests[1]!.headers['x-csrftoken']).toBe('bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb');
    const query = new URL(server.requests[1]!.path, server.origin).searchParams;
    expect([...query.entries()]).toEqual([['cylinder_id', 'cylinder &1'], ['fleet_id', 'fleet'], ['status', 'installed']]);
});

it.each([
    { status: 403, json: { message: 'first', error: 'second', detail: 'third' }, message: 'first' },
    { status: 502, text: '<gateway>', headers: { 'Content-Type': 'text/plain' }, message: '<gateway>' },
])('preserves HTTP $status and error data through the UI boundary', async response => {
    server.reply(response);
    await expect(API.getAllProjects()).rejects.toMatchObject({ name: 'ApiRequestError', status: response.status, message: response.message });
});

it('rejects an unexpected success media type and malformed JSON', async () => {
    server.reply({ text: 'not JSON', headers: { 'Content-Type': 'text/plain' } });
    await expect(API.getAllProjects()).rejects.toBeInstanceOf(ApiRequestError);
    server.reply({ text: '{broken' });
    await expect(API.getAllProjects()).rejects.toThrow('The server returned invalid JSON.');
});

it('retains binary export bytes and response headers', async () => {
    server.reply({ bytes: new Uint8Array([0, 255, 5]), headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename="sensors.xlsx"' } });
    const response = await API.getStationSensorInstallsAsExcel('station');
    expect(response.kind).toBe('documented');
    expect(response.headers.get('content-disposition')).toContain('sensors.xlsx');
    if (response.kind !== 'documented' || response.status !== 200) throw new Error('Expected a documented binary response.');
    expect(new Uint8Array(await response.data.arrayBuffer())).toEqual(new Uint8Array([0, 255, 5]));
});

it('cancels caller-owned requests before transport and suppresses late responses', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(API.getGISGeometryDetails('geometry', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' });
    expect(server.requests).toHaveLength(0);
    let finish!: () => void;
    server.handle(() => new Promise(resolve => { finish = () => resolve({ json: { id: 'late' } }); }));
    const active = new AbortController();
    const pending = API.getGPSTrackDetails('track', { signal: active.signal });
    const rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    active.abort();
    await rejected;
    finish();
});


it.each([
    { name: 'create log', call: (data: FormData) => API.createStationLog('station', data), method: 'POST', path: 'stations/station/logs/', status: 201, fileKey: 'attachment' },
    { name: 'update log', call: (data: FormData) => API.updateStationLog('log', data), method: 'PATCH', path: 'logs/log/', status: 200, fileKey: 'attachment' },
    { name: 'create resource', call: (data: FormData) => API.createStationResource('station', data), method: 'POST', path: 'stations/station/resources/', status: 201, fileKey: 'file' },
    { name: 'update resource', call: (data: FormData) => API.updateStationResource('resource', data), method: 'PATCH', path: 'resources/resource/', status: 200, fileKey: 'file' },
    { name: 'import GPX', call: (data: FormData) => API.importGPX(data), method: 'PUT', path: 'import/gpx/', status: 200, fileKey: 'file' },
])('$name preserves actual multipart file bytes through form-to-SDK adaptation', async ({ call, method, path, status, fileKey }) => {
    const restore = useNativeFetchBodyConstructors();
    try {
        server.reply({ status, json: {} });
        const data = new FormData();
        data.set('title', 'Café'); data.set('notes', 'Notes'); data.set('description', 'Description'); data.set('resource_type', 'photo'); data.set('collection', 'collection');
        data.set(fileKey, new File(['<gpx>café 🦇</gpx>'], 'survey.gpx', { type: 'application/gpx+xml' }));
        await call(data);
        const request = server.requests[0]!;
        expect(request).toMatchObject({ method, path: `/api/v2/${path}` });
        expect(request.headers['content-type']).toContain('multipart/form-data; boundary=');
        expect(request.body).toContain(`name="${fileKey}"; filename="survey.gpx"`);
        expect(request.body).toContain('Content-Type: application/gpx+xml'); expect(request.body).toContain('<gpx>café 🦇</gpx>');
    } finally { restore(); }
});

it('converts sensor form blanks to nullable JSON while preserving required create fields', async () => {
    const data = new FormData(); data.set('sensor', 'sensor'); data.set('install_date', '2026-10-01');
    data.set('expiracy_memory_date', ''); data.set('expiracy_battery_date', 'null'); data.set('status', 'installed');
    server.reply({ status: 201, json: {} }); await API.createStationSensorInstalls('station', data);
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ sensor: 'sensor', install_date: '2026-10-01', expiracy_memory_date: null, expiracy_battery_date: null, status: 'installed' });
    const update = new FormData(); update.set('uninstall_date', ''); update.set('uninstall_user', ''); update.set('status', 'retrieved');
    server.reply({ json: {} }); await API.updateStationSensorInstalls('station', 'install', update);
    expect(server.requests[1]).toMatchObject({ method: 'PATCH', path: '/api/v2/stations/station/sensor-installs/install/' });
    expect(JSON.parse(server.requests[1]!.body)).toEqual({ uninstall_date: null, uninstall_user: null, status: 'retrieved' });
});

it('patches only supplied resource fields and keeps an explicitly cleared description', async () => {
    const restore = useNativeFetchBodyConstructors();
    try {
        const data = new FormData();
        data.set('title', 'Updated title');
        data.set('description', '');
        await API.updateStationResource('resource', data);
        const request = server.requests[0]!;
        expect(request).toMatchObject({ method: 'PATCH', path: '/api/v2/resources/resource/' });
        expect(request.body).toContain('name="title"\r\n\r\nUpdated title');
        expect(request.body).toContain('name="description"\r\n\r\n\r\n');
        for (const absent of ['resource_type', 'text_content', 'file', 'miniature']) {
            expect(request.body).not.toContain(`name="${absent}"`);
        }
    } finally { restore(); }
});

it('rejects missing files and unknown resource/status choices before sending HTTP', () => {
    expect(() => API.importGPX(new FormData())).toThrow('Choose a GPX file.');
    expect(() => API.createStationResource('station', new FormData())).toThrow('Choose a resource type.');
    const resource = new FormData(); resource.set('resource_type', 'unknown');
    expect(() => API.updateStationResource('resource', resource)).toThrow('Choose a resource type.');
    const data = new FormData(); data.set('status', 'unknown');
    expect(() => API.updateStationSensorInstalls('station', 'install', data)).toThrow('Choose a sensor installation status.');
    expect(server.requests).toHaveLength(0);
});
