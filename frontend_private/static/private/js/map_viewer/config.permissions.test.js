import { Config } from './config.js';

function buildProjects() {
    return [
        { id: 'p-admin', permissions: 'ADMIN' },
        { id: 'p-write', permissions: 'READ_AND_WRITE' },
        { id: 'p-read', permissions: 'READ_ONLY' },
        { id: 'p-web', permissions: 'WEB_VIEWER' },
        { id: 'p-weird', permissions: 'SOMETHING_ELSE' },
        { id: '123', permissions: 'READ_ONLY' }
    ];
}

function buildNetworks() {
    return [
        { id: 'n-admin', permission_level: 3, permissions: 'READ_ONLY' },
        { id: 'n-write', permission_level: 2 },
        { id: 'n-read', permission_level: 1 },
        { id: 'n-none', permission_level: 0 },
        { id: 'n-label-admin', permissions: 'admin' },
        { id: 'n-label-write', permissions: 'read and write' },
        { id: 'n-label-read', permissions: 'read only' },
        { id: 'n-label-none', permissions: 'web viewer' },
        { id: '456', permission_level: 1 }
    ];
}

describe('Config permission refactor', () => {
    let originalProjects;
    let originalNetworks;

    beforeEach(() => {
        originalProjects = Config._projects;
        originalNetworks = Config._networks;
        Config._projects = buildProjects();
        Config._networks = buildNetworks();
    });

    afterEach(() => {
        Config._projects = originalProjects;
        Config._networks = originalNetworks;
        vi.restoreAllMocks();
    });

    describe('normalization helpers', () => {
        it('normalizes permission action and defaults unknown values to read', () => {
            expect(Config.normalizePermissionAction('WRITE')).toBe('write');
            expect(Config.normalizePermissionAction('Delete')).toBe('delete');
            expect(Config.normalizePermissionAction('read')).toBe('read');
            expect(Config.normalizePermissionAction('invalid-action')).toBe('read');
            expect(Config.normalizePermissionAction(null)).toBe('read');
        });

        it('normalizes project permission labels', () => {
            expect(Config.normalizeProjectPermissionLabel(' read and write ')).toBe('READ_AND_WRITE');
            expect(Config.normalizeProjectPermissionLabel('admin')).toBe('ADMIN');
            expect(Config.normalizeProjectPermissionLabel('')).toBeNull();
            expect(Config.normalizeProjectPermissionLabel(null)).toBeNull();
        });
    });

    describe('project permission matrix', () => {
        it('looks up projects by id and supports numeric-like ids', () => {
            expect(Config.getProjectById('p-read')?.id).toBe('p-read');
            expect(Config.getProjectById(123)?.id).toBe('123');
            expect(Config.getProjectById('missing')).toBeNull();
        });

        it('computes project permission rank per permission label', () => {
            expect(Config.getProjectPermissionRank('p-admin')).toBe(4);
            expect(Config.getProjectPermissionRank('p-write')).toBe(3);
            expect(Config.getProjectPermissionRank('p-read')).toBe(2);
            expect(Config.getProjectPermissionRank('p-web')).toBe(1);
            expect(Config.getProjectPermissionRank('p-weird')).toBe(0);
            expect(Config.getProjectPermissionRank('missing')).toBe(0);
        });

        it('enforces read/write/delete access for each project permission', () => {
            expect(Config.getProjectAccess('p-admin')).toEqual({ read: true, write: true, delete: true });
            expect(Config.getProjectAccess('p-write')).toEqual({ read: true, write: true, delete: false });
            expect(Config.getProjectAccess('p-read')).toEqual({ read: true, write: false, delete: false });
            expect(Config.getProjectAccess('p-web')).toEqual({ read: false, write: false, delete: false });
            expect(Config.getProjectAccess('p-weird')).toEqual({ read: false, write: false, delete: false });
            expect(Config.getProjectAccess('missing')).toEqual({ read: false, write: false, delete: false });
        });

        it('uses read threshold when action is invalid', () => {
            expect(Config.hasProjectAccess('p-read', 'not-an-action')).toBe(true);
            expect(Config.hasProjectAccess('p-web', 'not-an-action')).toBe(false);
        });

        it('keeps backward-compatible project helper behavior aligned', () => {
            expect(Config.hasProjectReadAccess('p-write')).toBe(Config.hasProjectAccess('p-write', 'read'));
            expect(Config.hasProjectWriteAccess('p-write')).toBe(Config.hasProjectAccess('p-write', 'write'));
            expect(Config.hasProjectAdminAccess('p-write')).toBe(Config.hasProjectAccess('p-write', 'delete'));
        });

        it('fails closed when project access evaluation throws', () => {
            const spy = vi.spyOn(Config, 'getProjectPermissionRank').mockImplementation(() => {
                throw new Error('boom');
            });
            expect(Config.hasProjectAccess('p-admin', 'read')).toBe(false);
            expect(spy).toHaveBeenCalled();
        });
    });

    describe('network permission matrix', () => {
        it('looks up networks by id and supports numeric-like ids', () => {
            expect(Config.getNetworkById('n-read')?.id).toBe('n-read');
            expect(Config.getNetworkById(456)?.id).toBe('456');
            expect(Config.getNetworkById('missing')).toBeNull();
        });

        it('prefers numeric permission level before text fallback', () => {
            // n-admin includes level 3 and a read-only text label: numeric value must win.
            expect(Config.getNetworkPermissionLevel('n-admin')).toBe(3);
        });

        it('falls back to text permission labels when numeric level is absent', () => {
            expect(Config.getNetworkPermissionLevel('n-label-admin')).toBe(3);
            expect(Config.getNetworkPermissionLevel('n-label-write')).toBe(2);
            expect(Config.getNetworkPermissionLevel('n-label-read')).toBe(1);
            expect(Config.getNetworkPermissionLevel('n-label-none')).toBe(0);
            expect(Config.getNetworkPermissionLevel('missing')).toBe(0);
        });

        it('enforces read/write/delete access for network levels', () => {
            expect(Config.getNetworkAccess('n-admin')).toEqual({ read: true, write: true, delete: true });
            expect(Config.getNetworkAccess('n-write')).toEqual({ read: true, write: true, delete: false });
            expect(Config.getNetworkAccess('n-read')).toEqual({ read: true, write: false, delete: false });
            expect(Config.getNetworkAccess('n-none')).toEqual({ read: false, write: false, delete: false });
        });

        it('uses read threshold when network action is invalid', () => {
            expect(Config.hasNetworkAccess('n-read', 'unknown-action')).toBe(true);
            expect(Config.hasNetworkAccess('n-none', 'unknown-action')).toBe(false);
        });

        it('keeps backward-compatible network helper behavior aligned', () => {
            expect(Config.hasNetworkReadAccess('n-write')).toBe(Config.hasNetworkAccess('n-write', 'read'));
            expect(Config.hasNetworkWriteAccess('n-write')).toBe(Config.hasNetworkAccess('n-write', 'write'));
            expect(Config.hasNetworkAdminAccess('n-write')).toBe(Config.hasNetworkAccess('n-write', 'delete'));
        });

        it('fails closed when network access evaluation throws', () => {
            const spy = vi.spyOn(Config, 'getNetworkPermissionLevel').mockImplementation(() => {
                throw new Error('boom');
            });
            expect(Config.hasNetworkAccess('n-admin', 'read')).toBe(false);
            expect(spy).toHaveBeenCalled();
        });
    });

    describe('scoped and station permission routing', () => {
        it('routes scoped checks to project or network access', () => {
            expect(Config.hasScopedAccess('project', 'p-write', 'write')).toBe(true);
            expect(Config.hasScopedAccess('network', 'n-write', 'write')).toBe(true);
            // Unknown scope types default to project behavior.
            expect(Config.hasScopedAccess('unknown-scope', 'p-write', 'write')).toBe(true);
        });

        it('returns scoped access objects for project and network', () => {
            expect(Config.getScopedAccess('project', 'p-read')).toEqual({ read: true, write: false, delete: false });
            expect(Config.getScopedAccess('network', 'n-read')).toEqual({ read: true, write: false, delete: false });
        });

        it('derives station scope correctly for null, subsurface, and surface stations', () => {
            expect(Config.getStationScope(null)).toEqual({ scopeType: 'project', scopeId: null });
            expect(Config.getStationScope({ station_type: 'subsurface', project: 'p-read' })).toEqual({
                scopeType: 'project',
                scopeId: 'p-read'
            });
            expect(Config.getStationScope({ station_type: 'surface', network: 'n-read', project: 'p-admin' })).toEqual({
                scopeType: 'network',
                scopeId: 'n-read'
            });
            expect(Config.getStationScope({ network: 'n-write', project: 'p-read' })).toEqual({
                scopeType: 'network',
                scopeId: 'n-write'
            });
        });

        it('returns station access based on derived scope', () => {
            expect(Config.getStationAccess({ station_type: 'subsurface', project: 'p-write' })).toEqual({
                scopeType: 'project',
                scopeId: 'p-write',
                read: true,
                write: true,
                delete: false
            });

            expect(Config.getStationAccess({ station_type: 'surface', network: 'n-admin' })).toEqual({
                scopeType: 'network',
                scopeId: 'n-admin',
                read: true,
                write: true,
                delete: true
            });
        });
    });
});

