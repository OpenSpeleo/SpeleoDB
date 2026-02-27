import { Config } from './config.js';
import { API } from './api.js';

vi.mock('./api.js', () => ({
    API: {
        getAllProjects: vi.fn(),
        getAllSurfaceNetworks: vi.fn(),
        getGPSTracks: vi.fn(),
    },
}));

describe('Config loading and data methods', () => {
    let originalProjects;
    let originalNetworks;
    let originalGpsTracks;

    beforeEach(() => {
        originalProjects = Config._projects;
        originalNetworks = Config._networks;
        originalGpsTracks = Config._gpsTracks;
        Config._projects = null;
        Config._networks = null;
        Config._gpsTracks = null;
    });

    afterEach(() => {
        Config._projects = originalProjects;
        Config._networks = originalNetworks;
        Config._gpsTracks = originalGpsTracks;
        vi.restoreAllMocks();
        vi.clearAllMocks();
    });

    // ------------------------------------------------------------------ //
    // Getters
    // ------------------------------------------------------------------ //

    describe('projects getter', () => {
        it('returns empty array when _projects is null', () => {
            expect(Config.projects).toEqual([]);
        });

        it('returns the projects array when set', () => {
            Config._projects = [{ id: '1' }, { id: '2' }];
            expect(Config.projects).toEqual([{ id: '1' }, { id: '2' }]);
        });
    });

    describe('projectIds getter', () => {
        it('returns empty array when no projects loaded', () => {
            expect(Config.projectIds).toEqual([]);
        });

        it('returns array of project IDs', () => {
            Config._projects = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
            expect(Config.projectIds).toEqual(['a', 'b', 'c']);
        });
    });

    describe('networks getter', () => {
        it('returns empty array when _networks is null', () => {
            expect(Config.networks).toEqual([]);
        });

        it('returns the networks array when set', () => {
            Config._networks = [{ id: 'n-1' }];
            expect(Config.networks).toEqual([{ id: 'n-1' }]);
        });
    });

    describe('networkIds getter', () => {
        it('returns empty array when no networks loaded', () => {
            expect(Config.networkIds).toEqual([]);
        });

        it('returns array of network IDs', () => {
            Config._networks = [{ id: 'n-1' }, { id: 'n-2' }];
            expect(Config.networkIds).toEqual(['n-1', 'n-2']);
        });
    });

    describe('gpsTracks getter', () => {
        it('returns empty array when _gpsTracks is null', () => {
            expect(Config.gpsTracks).toEqual([]);
        });

        it('returns the tracks array when set', () => {
            Config._gpsTracks = [{ id: 't-1' }];
            expect(Config.gpsTracks).toEqual([{ id: 't-1' }]);
        });
    });

    describe('gpsTrackIds getter', () => {
        it('returns empty array when no tracks loaded', () => {
            expect(Config.gpsTrackIds).toEqual([]);
        });

        it('returns array of GPS track IDs', () => {
            Config._gpsTracks = [{ id: 't-1' }, { id: 't-2' }];
            expect(Config.gpsTrackIds).toEqual(['t-1', 't-2']);
        });
    });

    // ------------------------------------------------------------------ //
    // loadProjects()
    // ------------------------------------------------------------------ //

    describe('loadProjects()', () => {
        it('calls API.getAllProjects and maps response data', async () => {
            API.getAllProjects.mockResolvedValue({
                success: true,
                data: [
                    {
                        id: 'p-1',
                        name: 'Project 1',
                        permission: 'ADMIN',
                        description: 'Desc',
                        country: 'US',
                        latitude: 45.0,
                        longitude: -73.0,
                        visibility: 'public',
                        geojson_url: '/geojson/p1',
                    },
                ],
            });

            const result = await Config.loadProjects();

            expect(API.getAllProjects).toHaveBeenCalledOnce();
            expect(result).toEqual([
                {
                    id: 'p-1',
                    name: 'Project 1',
                    permissions: 'ADMIN',
                    description: 'Desc',
                    country: 'US',
                    latitude: 45.0,
                    longitude: -73.0,
                    visibility: 'public',
                    geojson_url: '/geojson/p1',
                },
            ]);
        });

        it('renames API "permission" field to "permissions"', async () => {
            API.getAllProjects.mockResolvedValue({
                success: true,
                data: [{ id: 'p-1', name: 'Test', permission: 'READ_ONLY' }],
            });

            await Config.loadProjects();

            expect(Config.projects[0].permissions).toBe('READ_ONLY');
            expect(Config.projects[0]).not.toHaveProperty('permission');
        });

        it('returns cached projects on subsequent calls without re-fetching', async () => {
            API.getAllProjects.mockResolvedValue({
                success: true,
                data: [{ id: 'p-1', name: 'Project', permission: 'ADMIN' }],
            });

            const first = await Config.loadProjects();
            const second = await Config.loadProjects();

            expect(API.getAllProjects).toHaveBeenCalledOnce();
            expect(first).toBe(second);
        });

        it('sets empty array when response success is false', async () => {
            API.getAllProjects.mockResolvedValue({ success: false });

            const result = await Config.loadProjects();
            expect(result).toEqual([]);
        });

        it('sets empty array when response data is not an array', async () => {
            API.getAllProjects.mockResolvedValue({ success: true, data: 'not-array' });

            const result = await Config.loadProjects();
            expect(result).toEqual([]);
        });

        it('sets empty array when response is null', async () => {
            API.getAllProjects.mockResolvedValue(null);

            const result = await Config.loadProjects();
            expect(result).toEqual([]);
        });

        it('sets empty array on API rejection and does not throw', async () => {
            API.getAllProjects.mockRejectedValue(new Error('Network error'));

            const result = await Config.loadProjects();
            expect(result).toEqual([]);
        });

        it('maps multiple projects correctly', async () => {
            API.getAllProjects.mockResolvedValue({
                success: true,
                data: [
                    { id: 'p-1', name: 'Cave A', permission: 'ADMIN' },
                    { id: 'p-2', name: 'Cave B', permission: 'READ_ONLY' },
                    { id: 'p-3', name: 'Cave C', permission: 'READ_AND_WRITE' },
                ],
            });

            await Config.loadProjects();

            expect(Config.projects).toHaveLength(3);
            expect(Config.projectIds).toEqual(['p-1', 'p-2', 'p-3']);
        });
    });

    // ------------------------------------------------------------------ //
    // loadNetworks()
    // ------------------------------------------------------------------ //

    describe('loadNetworks()', () => {
        it('calls API.getAllSurfaceNetworks and maps response data', async () => {
            API.getAllSurfaceNetworks.mockResolvedValue({
                success: true,
                data: [
                    {
                        id: 'n-1',
                        name: 'Network 1',
                        description: 'A network',
                        is_active: true,
                        created_by: 'user-1',
                        creation_date: '2024-01-01',
                        modified_date: '2024-06-01',
                        user_permission_level_label: 'ADMIN',
                        user_permission_level: 3,
                    },
                ],
            });

            const result = await Config.loadNetworks();

            expect(API.getAllSurfaceNetworks).toHaveBeenCalledOnce();
            expect(result).toEqual([
                {
                    id: 'n-1',
                    name: 'Network 1',
                    description: 'A network',
                    is_active: true,
                    created_by: 'user-1',
                    creation_date: '2024-01-01',
                    modified_date: '2024-06-01',
                    permissions: 'ADMIN',
                    permission_level: 3,
                },
            ]);
        });

        it('maps user_permission_level_label to permissions', async () => {
            API.getAllSurfaceNetworks.mockResolvedValue({
                success: true,
                data: [{ id: 'n-1', name: 'Net', user_permission_level_label: 'READ_ONLY', user_permission_level: 1 }],
            });

            await Config.loadNetworks();

            expect(Config.networks[0].permissions).toBe('READ_ONLY');
            expect(Config.networks[0].permission_level).toBe(1);
        });

        it('returns cached networks on subsequent calls', async () => {
            API.getAllSurfaceNetworks.mockResolvedValue({
                success: true,
                data: [{ id: 'n-1', name: 'Net', user_permission_level_label: 'ADMIN', user_permission_level: 3 }],
            });

            const first = await Config.loadNetworks();
            const second = await Config.loadNetworks();

            expect(API.getAllSurfaceNetworks).toHaveBeenCalledOnce();
            expect(first).toBe(second);
        });

        it('sets empty array on invalid response', async () => {
            API.getAllSurfaceNetworks.mockResolvedValue({ success: false });

            const result = await Config.loadNetworks();
            expect(result).toEqual([]);
        });

        it('sets empty array when data is not an array', async () => {
            API.getAllSurfaceNetworks.mockResolvedValue({ success: true, data: {} });

            const result = await Config.loadNetworks();
            expect(result).toEqual([]);
        });

        it('sets empty array on API rejection', async () => {
            API.getAllSurfaceNetworks.mockRejectedValue(new Error('Timeout'));

            const result = await Config.loadNetworks();
            expect(result).toEqual([]);
        });
    });

    // ------------------------------------------------------------------ //
    // loadGPSTracks()
    // ------------------------------------------------------------------ //

    describe('loadGPSTracks()', () => {
        it('calls API.getGPSTracks and maps response data', async () => {
            API.getGPSTracks.mockResolvedValue({
                success: true,
                data: [
                    {
                        id: 't-1',
                        name: 'Track 1',
                        file: '/tracks/t1.geojson',
                        sha256_hash: 'abc123',
                        creation_date: '2024-01-01',
                        modified_date: '2024-06-01',
                    },
                ],
            });

            const result = await Config.loadGPSTracks();

            expect(API.getGPSTracks).toHaveBeenCalledOnce();
            expect(result).toEqual([
                {
                    id: 't-1',
                    name: 'Track 1',
                    file: '/tracks/t1.geojson',
                    sha256_hash: 'abc123',
                    creation_date: '2024-01-01',
                    modified_date: '2024-06-01',
                },
            ]);
        });

        it('returns cached tracks on subsequent calls', async () => {
            API.getGPSTracks.mockResolvedValue({
                success: true,
                data: [{ id: 't-1', name: 'Track', file: '/t.geojson' }],
            });

            const first = await Config.loadGPSTracks();
            const second = await Config.loadGPSTracks();

            expect(API.getGPSTracks).toHaveBeenCalledOnce();
            expect(first).toBe(second);
        });

        it('sets empty array when data is not an array', async () => {
            API.getGPSTracks.mockResolvedValue({ success: true, data: null });

            const result = await Config.loadGPSTracks();
            expect(result).toEqual([]);
        });

        it('sets empty array on invalid response', async () => {
            API.getGPSTracks.mockResolvedValue({ success: false });

            const result = await Config.loadGPSTracks();
            expect(result).toEqual([]);
        });

        it('sets empty array on API rejection', async () => {
            API.getGPSTracks.mockRejectedValue(new Error('Server down'));

            const result = await Config.loadGPSTracks();
            expect(result).toEqual([]);
        });

        it('maps all expected fields', async () => {
            API.getGPSTracks.mockResolvedValue({
                success: true,
                data: [
                    {
                        id: 't-1',
                        name: 'Track',
                        file: '/file.geojson',
                        sha256_hash: 'hash',
                        creation_date: '2024-01-01',
                        modified_date: '2024-02-01',
                        extra_field: 'should be excluded',
                    },
                ],
            });

            await Config.loadGPSTracks();

            const track = Config.gpsTracks[0];
            expect(Object.keys(track).sort()).toEqual(
                ['creation_date', 'file', 'id', 'modified_date', 'name', 'sha256_hash']
            );
        });
    });

    // ------------------------------------------------------------------ //
    // setPublicProjects()
    // ------------------------------------------------------------------ //

    describe('setPublicProjects()', () => {
        it('maps projects with READ_ONLY permissions', () => {
            Config.setPublicProjects([
                { id: 'pub-1', name: 'Public Cave', geojson_url: '/geo/pub1' },
                { id: 'pub-2', name: 'Public Mine', geojson_file: '/geo/pub2' },
            ]);

            expect(Config.projects).toEqual([
                { id: 'pub-1', name: 'Public Cave', permissions: 'READ_ONLY', geojson_url: '/geo/pub1' },
                { id: 'pub-2', name: 'Public Mine', permissions: 'READ_ONLY', geojson_url: '/geo/pub2' },
            ]);
        });

        it('assigns READ_ONLY to every project regardless of input', () => {
            Config.setPublicProjects([
                { id: '1', name: 'A' },
                { id: '2', name: 'B' },
            ]);

            Config.projects.forEach(p => {
                expect(p.permissions).toBe('READ_ONLY');
            });
        });

        it('prefers geojson_url over geojson_file when both present', () => {
            Config.setPublicProjects([
                { id: '1', name: 'A', geojson_url: '/url', geojson_file: '/file' },
            ]);

            expect(Config.projects[0].geojson_url).toBe('/url');
        });

        it('falls back to geojson_file when geojson_url is absent', () => {
            Config.setPublicProjects([
                { id: '1', name: 'A', geojson_file: '/file' },
            ]);

            expect(Config.projects[0].geojson_url).toBe('/file');
        });

        it('sets geojson_url to undefined when neither field exists', () => {
            Config.setPublicProjects([{ id: '1', name: 'A' }]);

            expect(Config.projects[0].geojson_url).toBeUndefined();
        });

        it('overwrites previously loaded projects', () => {
            Config._projects = [{ id: 'old', name: 'Old' }];

            Config.setPublicProjects([{ id: 'new', name: 'New' }]);

            expect(Config.projectIds).toEqual(['new']);
        });
    });

    // ------------------------------------------------------------------ //
    // filterProjectsByGeoJSON()
    // ------------------------------------------------------------------ //

    describe('filterProjectsByGeoJSON()', () => {
        beforeEach(() => {
            Config._projects = [
                { id: '1', name: 'With URL', geojson_url: '/geo/1' },
                { id: '2', name: 'Without GeoJSON' },
                { id: '3', name: 'In metadata only' },
            ];
        });

        it('keeps projects that have geojson_url set on them', () => {
            Config.filterProjectsByGeoJSON([]);

            const ids = Config.projects.map(p => p.id);
            expect(ids).toContain('1');
            expect(ids).not.toContain('2');
            expect(ids).not.toContain('3');
        });

        it('keeps projects found in geojson metadata', () => {
            Config.filterProjectsByGeoJSON([{ id: '3', geojson_file: '/geo/3.json' }]);

            const ids = Config.projects.map(p => p.id);
            expect(ids).toContain('1');
            expect(ids).toContain('3');
        });

        it('removes projects without geojson_url or metadata entry', () => {
            Config.filterProjectsByGeoJSON([{ id: '3', geojson_file: '/geo/3.json' }]);

            const ids = Config.projects.map(p => p.id);
            expect(ids).not.toContain('2');
        });

        it('handles numeric IDs in metadata via string coercion', () => {
            Config._projects = [{ id: '42', name: 'Numeric' }];
            Config.filterProjectsByGeoJSON([{ id: 42, geojson_file: '/geo/42.json' }]);

            expect(Config.projects).toHaveLength(1);
            expect(Config.projects[0].id).toBe('42');
        });

        it('does nothing when _projects is null', () => {
            Config._projects = null;

            Config.filterProjectsByGeoJSON([{ id: '1', geojson_file: '/geo/1' }]);

            expect(Config._projects).toBeNull();
        });

        it('does nothing when metadata is not an array', () => {
            Config.filterProjectsByGeoJSON(null);

            expect(Config.projects).toHaveLength(3);
        });

        it('skips metadata entries that have no geojson_file', () => {
            Config.filterProjectsByGeoJSON([{ id: '3' }]);

            const ids = Config.projects.map(p => p.id);
            expect(ids).not.toContain('3');
            expect(ids).toContain('1');
        });

        it('combines both sources when building the keep-set', () => {
            Config._projects = [
                { id: '1', name: 'Has URL', geojson_url: '/geo/1' },
                { id: '2', name: 'In meta' },
                { id: '3', name: 'Neither' },
            ];

            Config.filterProjectsByGeoJSON([{ id: '2', geojson_file: '/geo/2' }]);

            expect(Config.projects.map(p => p.id)).toEqual(['1', '2']);
        });

        it('results in empty array when no projects match', () => {
            Config._projects = [
                { id: '10', name: 'No GeoJSON' },
                { id: '11', name: 'Also none' },
            ];

            Config.filterProjectsByGeoJSON([]);

            expect(Config.projects).toEqual([]);
        });
    });
});
