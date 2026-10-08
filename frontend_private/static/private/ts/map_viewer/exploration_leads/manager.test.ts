import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { StationRecord, LeadWrite } from '../../../../../../ts-types/domain/station-records.ts';
import type { ViewerLandmark, ViewerLandmarkCollection, LandmarkFeatureProperties } from '../../../../../../ts-types/domain/map-entities.ts';
import type { ViewerExplorationLead } from '../../../../../../ts-types/domain/map-state.ts';
import type { ViewerProject } from '../../../../../../ts-types/domain/map-config.ts';
import { ExplorationLeadManager } from './manager.ts';

const API = vi.hoisted(() => ({
        getAllProjectExplorationLeadsGeoJSON: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getProjectExplorationLeads: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        createExplorationLead: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        updateExplorationLead: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        deleteExplorationLead: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
}));
vi.mock('../api.ts', () => ({ API }));

const State = vi.hoisted(() => ({
        explorationLeads: new Map<string, Partial<ViewerExplorationLead>>(),
}));
vi.mock('../state.ts', () => ({ State }));

const Config = vi.hoisted(() => ({
        projects: [] as ViewerProject[],
        hasProjectAccess: vi.fn<(id: EntityId) => boolean>(() => true),
}));
vi.mock('../config.ts', () => ({ Config }));


function makeFC(features: unknown[]) {
    return { type: 'FeatureCollection', features };
}

function makeLeadFeature(id: string, projectId: EntityId, coords = [6.5, 46.5]) {
    return {
        id,
        type: 'Feature',
        geometry: { type: 'Point', coordinates: coords },
        properties: {
            project: projectId,
            description: `Lead ${id}`,
            creation_date: '2025-01-01T00:00:00Z',
            created_by: 'tester',
        },
    };
}

describe('ExplorationLeadManager', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        State.explorationLeads.clear();
        ExplorationLeadManager.invalidateCache();
        Config.hasProjectAccess.mockReturnValue(true);
        Config.projects = [];
    });

    // ------------------------------------------------------------------ //
    // ensureAllLeadsLoaded
    // ------------------------------------------------------------------ //

    describe('ensureAllLeadsLoaded', () => {
        it('fetches all leads on first call', async () => {
            const fc = makeFC([makeLeadFeature('l1', 'p1')]);
            API.getAllProjectExplorationLeadsGeoJSON.mockResolvedValue(fc);

            await ExplorationLeadManager.ensureAllLeadsLoaded();

            expect(API.getAllProjectExplorationLeadsGeoJSON).toHaveBeenCalledTimes(1);
        });

        it('does not refetch when cache is populated', async () => {
            const fc = makeFC([makeLeadFeature('l1', 'p1')]);
            API.getAllProjectExplorationLeadsGeoJSON.mockResolvedValue(fc);

            await ExplorationLeadManager.ensureAllLeadsLoaded();
            await ExplorationLeadManager.ensureAllLeadsLoaded();

            expect(API.getAllProjectExplorationLeadsGeoJSON).toHaveBeenCalledTimes(1);
        });

        it('caches empty FeatureCollection on API failure', async () => {
            API.getAllProjectExplorationLeadsGeoJSON.mockRejectedValue(new Error('Network error'));

            await ExplorationLeadManager.ensureAllLeadsLoaded();

            expect(API.getAllProjectExplorationLeadsGeoJSON).toHaveBeenCalledTimes(1);
        });
    });

    // ------------------------------------------------------------------ //
    // loadLeadsForProject
    // ------------------------------------------------------------------ //

    describe('loadLeadsForProject', () => {
        it('returns filtered features for the given project', async () => {
            const fc = makeFC([
                makeLeadFeature('l1', 'p1'),
                makeLeadFeature('l2', 'p2'),
                makeLeadFeature('l3', 'p1'),
            ]);
            API.getAllProjectExplorationLeadsGeoJSON.mockResolvedValue(fc);

            const features = await ExplorationLeadManager.loadLeadsForProject('p1');

            expect(features).toHaveLength(2);
            expect(features.map(f => f.id)).toEqual(['l1', 'l3']);
        });

        it('populates State.explorationLeads', async () => {
            const fc = makeFC([makeLeadFeature('l1', 'p1', [6.5, 46.5])]);
            API.getAllProjectExplorationLeadsGeoJSON.mockResolvedValue(fc);

            await ExplorationLeadManager.loadLeadsForProject('p1');

            expect(State.explorationLeads.has('l1')).toBe(true);
            const stored = State.explorationLeads.get('l1')!;
            expect(stored.coordinates).toEqual([6.5, 46.5]);
            expect(stored.projectId).toBe('p1');
        });

        it('returns empty array when no read access', async () => {
            Config.hasProjectAccess.mockReturnValue(false);

            const features = await ExplorationLeadManager.loadLeadsForProject('p1');

            expect(features).toEqual([]);
            expect(API.getAllProjectExplorationLeadsGeoJSON).not.toHaveBeenCalled();
        });

        it('returns empty array on API error', async () => {
            API.getAllProjectExplorationLeadsGeoJSON.mockRejectedValue(new Error('fail'));

            const features = await ExplorationLeadManager.loadLeadsForProject('p1');

            expect(features).toEqual([]);
        });
    });

    // ------------------------------------------------------------------ //
    // loadAllLeads
    // ------------------------------------------------------------------ //

    describe('loadAllLeads', () => {
        it('loads leads for all accessible projects', async () => {
            Config.projects = [{ id: 'p1' }, { id: 'p2' }];
            Config.hasProjectAccess.mockReturnValue(true);

            const fc = makeFC([
                makeLeadFeature('l1', 'p1'),
                makeLeadFeature('l2', 'p2'),
            ]);
            API.getAllProjectExplorationLeadsGeoJSON.mockResolvedValue(fc);

            const allFeatures = await ExplorationLeadManager.loadAllLeads();

            expect(allFeatures).toHaveLength(2);
        });

        it('skips projects without read access', async () => {
            Config.projects = [{ id: 'p1' }, { id: 'p2' }];
            Config.hasProjectAccess.mockImplementation((id) => id === 'p1');

            const fc = makeFC([makeLeadFeature('l1', 'p1')]);
            API.getAllProjectExplorationLeadsGeoJSON.mockResolvedValue(fc);

            const allFeatures = await ExplorationLeadManager.loadAllLeads();

            expect(allFeatures).toHaveLength(1);
        });

        it('returns empty array when no projects exist', async () => {
            Config.projects = [];

            const allFeatures = await ExplorationLeadManager.loadAllLeads();

            expect(allFeatures).toEqual([]);
        });

        it('continues loading other projects when one fails', async () => {
            Config.projects = [{ id: 'p1' }, { id: 'p2' }];
            Config.hasProjectAccess.mockReturnValue(true);

            let callCount = 0;
            API.getAllProjectExplorationLeadsGeoJSON.mockImplementation(() => {
                callCount++;
                if (callCount === 1) {
                    return Promise.resolve(makeFC([makeLeadFeature('l1', 'p1')]));
                }
                return Promise.resolve(makeFC([makeLeadFeature('l1', 'p1')]));
            });

            const allFeatures = await ExplorationLeadManager.loadAllLeads();

            expect(allFeatures.length).toBeGreaterThanOrEqual(1);
        });
    });

    // ------------------------------------------------------------------ //
    // createLead
    // ------------------------------------------------------------------ //

    describe('createLead', () => {
        it('creates lead and stores in state', async () => {
            const createdLead = {
                id: 'l-new',
                latitude: '46.5000000',
                longitude: '6.5000000',
                description: 'A new lead',
                creation_date: '2025-01-01',
                created_by: 'tester',
            };
            API.createExplorationLead.mockResolvedValue(createdLead);

            const result = await ExplorationLeadManager.createLead('p1', [6.5, 46.5], 'A new lead');

            expect(result).toEqual(createdLead);
            expect(State.explorationLeads.has('l-new')).toBe(true);
            const stored = State.explorationLeads.get('l-new')!;
            expect(stored.coordinates).toEqual([6.5, 46.5]);
            expect(stored.projectId).toBe('p1');
        });

        it('formats coordinates to 7 decimal places', async () => {
            API.createExplorationLead.mockResolvedValue({ id: 'l1', latitude: '46.5', longitude: '6.5' });

            await ExplorationLeadManager.createLead('p1', [6.123456789, 46.987654321], 'desc');

            const [, leadData] = API.createExplorationLead.mock.calls[0]! as [EntityId, LeadWrite];
            expect(leadData.latitude).toBe('46.9876543');
            expect(leadData.longitude).toBe('6.1234568');
        });

        it('handles string coordinates without throwing', async () => {
            API.createExplorationLead.mockResolvedValue({ id: 'l2', latitude: '46.5', longitude: '6.5' });

            await ExplorationLeadManager.createLead('p1', ['6.123456789', '46.987654321'], 'desc');

            const [, leadData] = API.createExplorationLead.mock.calls[0]! as [EntityId, LeadWrite];
            expect(leadData.latitude).toBe('46.9876543');
            expect(leadData.longitude).toBe('6.1234568');
        });

        it('throws when API rejects', async () => {
            API.createExplorationLead.mockRejectedValue(new Error('network'));

            await expect(ExplorationLeadManager.createLead('p1', [6.5, 46.5], 'desc')).rejects.toThrow();
        });

        it('throws when API returns null', async () => {
            API.createExplorationLead.mockResolvedValue(null);

            await expect(ExplorationLeadManager.createLead('p1', [6.5, 46.5], 'desc')).rejects.toThrow();
        });
    });

    // ------------------------------------------------------------------ //
    // updateLead
    // ------------------------------------------------------------------ //

    describe('updateLead', () => {
        it('updates state with returned data', async () => {
            State.explorationLeads.set('l1', {
                id: 'l1',
                coordinates: [6.0, 46.0],
                description: 'Old',
                projectId: 'p1',
            });

            API.updateExplorationLead.mockResolvedValue({
                id: 'l1',
                latitude: '47.0',
                longitude: '7.0',
                description: 'Updated',
            });

            const result = await ExplorationLeadManager.updateLead('l1', { description: 'Updated' });

            expect(result.description).toBe('Updated');
            const stored = State.explorationLeads.get('l1')!;
            expect(stored.coordinates).toEqual([7.0, 47.0]);
            expect(stored.description).toBe('Updated');
        });

        it('throws when API rejects', async () => {
            API.updateExplorationLead.mockRejectedValue(new Error('network'));

            await expect(ExplorationLeadManager.updateLead('l1', {})).rejects.toThrow();
        });

        it('throws when API returns empty object', async () => {
            API.updateExplorationLead.mockResolvedValue({});

            await expect(ExplorationLeadManager.updateLead('l1', {})).rejects.toThrow(
                'Failed to update exploration lead'
            );
        });
    });

    // ------------------------------------------------------------------ //
    // deleteLead
    // ------------------------------------------------------------------ //

    describe('deleteLead', () => {
        it('removes lead from state and invalidates cache', async () => {
            State.explorationLeads.set('l1', { id: 'l1' });
            API.deleteExplorationLead.mockResolvedValue({ ok: true });

            await ExplorationLeadManager.deleteLead('l1');

            expect(State.explorationLeads.has('l1')).toBe(false);
        });

        it('propagates API errors', async () => {
            API.deleteExplorationLead.mockRejectedValue(new Error('delete failed'));

            await expect(ExplorationLeadManager.deleteLead('l1')).rejects.toThrow('delete failed');
        });
    });

    // ------------------------------------------------------------------ //
    // moveLead
    // ------------------------------------------------------------------ //

    describe('moveLead', () => {
        it('delegates to updateLead with formatted coordinates', async () => {
            State.explorationLeads.set('l1', { id: 'l1', coordinates: [6.0, 46.0] });
            API.updateExplorationLead.mockResolvedValue({
                id: 'l1',
                latitude: '47.5',
                longitude: '7.5',
                description: '',
            });

            const result = await ExplorationLeadManager.moveLead('l1', [7.5, 47.5]);

            expect(result.id).toBe('l1');
            expect(API.updateExplorationLead).toHaveBeenCalledWith('l1', {
                latitude: '47.5000000',
                longitude: '7.5000000',
            });
        });

        it('handles string coordinates without throwing', async () => {
            State.explorationLeads.set('l1', { id: 'l1', coordinates: [6.0, 46.0] });
            API.updateExplorationLead.mockResolvedValue({
                id: 'l1',
                latitude: '47.5',
                longitude: '7.5',
                description: '',
            });

            await ExplorationLeadManager.moveLead('l1', ['7.5', '47.5']);

            expect(API.updateExplorationLead).toHaveBeenCalledWith('l1', {
                latitude: '47.5000000',
                longitude: '7.5000000',
            });
        });
    });

    // ------------------------------------------------------------------ //
    // invalidateCache
    // ------------------------------------------------------------------ //

    describe('invalidateCache', () => {
        it('forces a refetch on next ensureAllLeadsLoaded call', async () => {
            const fc = makeFC([]);
            API.getAllProjectExplorationLeadsGeoJSON.mockResolvedValue(fc);

            await ExplorationLeadManager.ensureAllLeadsLoaded();
            expect(API.getAllProjectExplorationLeadsGeoJSON).toHaveBeenCalledTimes(1);

            ExplorationLeadManager.invalidateCache();
            await ExplorationLeadManager.ensureAllLeadsLoaded();
            expect(API.getAllProjectExplorationLeadsGeoJSON).toHaveBeenCalledTimes(2);
        });
    });
});

describe('ExplorationLeadManager shared in-flight cache', () => {
    it('shares one request while retaining distinct async wrapper promises and cached feature identity', async () => {
        ExplorationLeadManager.invalidateCache();
        vi.clearAllMocks();
        let settle!: (value: unknown) => void;
        const response = new Promise<unknown>(resolve => { settle = resolve; });
        API.getAllProjectExplorationLeadsGeoJSON.mockReturnValue(response);
        const first = ExplorationLeadManager.ensureAllLeadsLoaded();
        const second = ExplorationLeadManager.ensureAllLeadsLoaded();
        expect(first).not.toBe(second);
        expect(API.getAllProjectExplorationLeadsGeoJSON).toHaveBeenCalledOnce();
        const feature = { type: 'Feature', id: 'cache-id', geometry: { type: 'Point', coordinates: [1, 2] }, properties: { project: 'cache-project', network: 'cache-project' } };
        settle({ type: 'FeatureCollection', features: [feature] });
        await expect(first).resolves.toBeUndefined();
        await expect(second).resolves.toBeUndefined();
        const loaded = await ExplorationLeadManager.loadLeadsForProject('cache-project');
        expect(loaded[0]).toBe(feature);
        expect(API.getAllProjectExplorationLeadsGeoJSON).toHaveBeenCalledOnce();
    });
});
