import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { StationRecord, LeadWrite } from '../../../../../../ts-types/domain/station-records.ts';
import type { ViewerLandmark, ViewerLandmarkCollection, LandmarkFeatureProperties } from '../../../../../../ts-types/domain/map-entities.ts';
import type { ViewerExplorationLead } from '../../../../../../ts-types/domain/map-state.ts';
import type { ViewerProject } from '../../../../../../ts-types/domain/map-config.ts';
import { StationManager } from './manager.ts';

const API = vi.hoisted(() => ({
        getAllStationsGeoJSON: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        createStation: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        updateStation: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        deleteStation: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
}));
vi.mock('../api.ts', () => ({ API }));

const State = vi.hoisted(() => ({
        allStations: new Map<string, Partial<StationRecord>>(),
}));
vi.mock('../state.ts', () => ({ State }));

const Layers = vi.hoisted(() => ({
        refreshStationsAfterChange: vi.fn<(...args: unknown[]) => Promise<void>>(),
        updateStationPosition: vi.fn<(...args: unknown[]) => void>(),
}));
vi.mock('../map/layers.ts', () => ({ Layers }));

const Config = vi.hoisted(() => ({
        hasProjectAccess: vi.fn<(id: EntityId) => boolean>(() => true),
}));
vi.mock('../config.ts', () => ({ Config }));


function makeFeatureCollection(features: unknown[]) {
    return { type: 'FeatureCollection', features };
}

function makeStationFeature(id: string, projectId: EntityId, coords = [6.5, 46.5]) {
    return {
        id,
        type: 'Feature',
        geometry: { type: 'Point', coordinates: coords },
        properties: { name: `Station ${id}`, project: projectId },
    };
}

describe('StationManager', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        State.allStations.clear();
        StationManager.invalidateCache();
        Config.hasProjectAccess.mockReturnValue(true);
    });

    // ------------------------------------------------------------------ //
    // ensureAllStationsLoaded
    // ------------------------------------------------------------------ //

    describe('ensureAllStationsLoaded', () => {
        it('fetches all stations on first call', async () => {
            const fc = makeFeatureCollection([makeStationFeature('s1', 'p1')]);
            API.getAllStationsGeoJSON.mockResolvedValue(fc);

            await StationManager.ensureAllStationsLoaded();

            expect(API.getAllStationsGeoJSON).toHaveBeenCalledTimes(1);
        });

        it('does not refetch when cache is populated', async () => {
            const fc = makeFeatureCollection([makeStationFeature('s1', 'p1')]);
            API.getAllStationsGeoJSON.mockResolvedValue(fc);

            await StationManager.ensureAllStationsLoaded();
            await StationManager.ensureAllStationsLoaded();

            expect(API.getAllStationsGeoJSON).toHaveBeenCalledTimes(1);
        });

        it('caches an empty FeatureCollection on API failure', async () => {
            API.getAllStationsGeoJSON.mockRejectedValue(new Error('Network error'));

            await StationManager.ensureAllStationsLoaded();

            expect(API.getAllStationsGeoJSON).toHaveBeenCalledTimes(1);
        });

        it('rejects invalid payloads', async () => {
            API.getAllStationsGeoJSON.mockResolvedValue({ type: 'bad' });

            await StationManager.ensureAllStationsLoaded();

            expect(API.getAllStationsGeoJSON).toHaveBeenCalledTimes(1);
        });
    });

    // ------------------------------------------------------------------ //
    // loadStationsForProject
    // ------------------------------------------------------------------ //

    describe('loadStationsForProject', () => {
        it('returns filtered features for the given project', async () => {
            const fc = makeFeatureCollection([
                makeStationFeature('s1', 'p1'),
                makeStationFeature('s2', 'p2'),
                makeStationFeature('s3', 'p1'),
            ]);
            API.getAllStationsGeoJSON.mockResolvedValue(fc);

            const features = await StationManager.loadStationsForProject('p1');

            expect(features).toHaveLength(2);
            expect(features.map(f => f.id)).toEqual(['s1', 's3']);
        });

        it('populates State.allStations for matching features', async () => {
            const fc = makeFeatureCollection([makeStationFeature('s1', 'p1', [6.5, 46.5])]);
            API.getAllStationsGeoJSON.mockResolvedValue(fc);

            await StationManager.loadStationsForProject('p1');

            expect(State.allStations.has('s1')).toBe(true);
            const stored = State.allStations.get('s1')!;
            expect(stored.latitude).toBe(46.5);
            expect(stored.longitude).toBe(6.5);
            expect(stored.project).toBe('p1');
        });

        it('returns empty array when project has no read access', async () => {
            Config.hasProjectAccess.mockReturnValue(false);

            const features = await StationManager.loadStationsForProject('p1');

            expect(features).toEqual([]);
            expect(API.getAllStationsGeoJSON).not.toHaveBeenCalled();
        });

        it('returns empty array on API error', async () => {
            API.getAllStationsGeoJSON.mockRejectedValue(new Error('fail'));

            const features = await StationManager.loadStationsForProject('p1');

            expect(features).toEqual([]);
        });

        it('skips features missing geometry or id', async () => {
            const fc = makeFeatureCollection([
                { id: null, type: 'Feature', geometry: { type: 'Point', coordinates: [0, 0] }, properties: { project: 'p1' } },
                { id: 's2', type: 'Feature', geometry: null, properties: { project: 'p1' } },
                makeStationFeature('s3', 'p1'),
            ]);
            API.getAllStationsGeoJSON.mockResolvedValue(fc);

            await StationManager.loadStationsForProject('p1');

            expect(State.allStations.size).toBe(1);
            expect(State.allStations.has('s3')).toBe(true);
        });
    });

    // ------------------------------------------------------------------ //
    // createStation
    // ------------------------------------------------------------------ //

    describe('createStation', () => {
        it('creates a station and updates state', async () => {
            const newStation = { id: 's-new', name: 'New Station' };
            API.createStation.mockResolvedValue(newStation);
            Layers.refreshStationsAfterChange.mockResolvedValue();

            const result = await StationManager.createStation('p1', { name: 'New Station' });

            expect(result).toEqual(newStation);
            expect(State.allStations.get('s-new')!).toEqual({ ...newStation, project: 'p1' });
            expect(Layers.refreshStationsAfterChange).toHaveBeenCalledWith('p1');
        });

        it('propagates API errors', async () => {
            API.createStation.mockRejectedValue(new Error('create failed'));

            await expect(StationManager.createStation('p1', {})).rejects.toThrow('create failed');
        });
    });

    // ------------------------------------------------------------------ //
    // updateStation
    // ------------------------------------------------------------------ //

    describe('updateStation', () => {
        it('updates state with returned data', async () => {
            State.allStations.set('s1', { id: 's1', name: 'Old', project: 'p1', latitude: 46.0, longitude: 6.0 });
            API.updateStation.mockResolvedValue({ id: 's1', name: 'Updated' });

            const result = await StationManager.updateStation('s1', { name: 'Updated' });

            expect(result.name).toBe('Updated');
            expect(State.allStations.get('s1')!.name).toBe('Updated');
        });

        it('updates layer position when coordinates change', async () => {
            State.allStations.set('s1', { id: 's1', project: 'p1', latitude: 46.0, longitude: 6.0 });
            API.updateStation.mockResolvedValue({ id: 's1' });

            await StationManager.updateStation('s1', { latitude: 47.0, longitude: 7.0 });

            expect(Layers.updateStationPosition).toHaveBeenCalledWith('stations-p1', 's1', [7.0, 47.0]);
        });

        it('does not update layer position when coordinates are absent', async () => {
            State.allStations.set('s1', { id: 's1', project: 'p1' });
            API.updateStation.mockResolvedValue({ id: 's1', name: 'Renamed' });

            await StationManager.updateStation('s1', { name: 'Renamed' });

            expect(Layers.updateStationPosition).not.toHaveBeenCalled();
        });

        it('propagates API errors', async () => {
            API.updateStation.mockRejectedValue(new Error('update failed'));

            await expect(StationManager.updateStation('s1', {})).rejects.toThrow('update failed');
        });
    });

    // ------------------------------------------------------------------ //
    // deleteStation
    // ------------------------------------------------------------------ //

    describe('deleteStation', () => {
        it('removes station from state and refreshes layers', async () => {
            State.allStations.set('s1', { id: 's1', project: 'p1' });
            API.deleteStation.mockResolvedValue({ ok: true, status: 204 });
            Layers.refreshStationsAfterChange.mockResolvedValue();

            const result = await StationManager.deleteStation('s1');

            expect(result).toBe(true);
            expect(State.allStations.has('s1')).toBe(false);
            expect(Layers.refreshStationsAfterChange).toHaveBeenCalledWith('p1');
        });

        it('does not refresh layers when station has no project', async () => {
            State.allStations.set('s1', { id: 's1' });
            API.deleteStation.mockResolvedValue({ ok: true, status: 204 });

            await StationManager.deleteStation('s1');

            expect(Layers.refreshStationsAfterChange).not.toHaveBeenCalled();
        });

        it('propagates API errors', async () => {
            State.allStations.set('s1', { id: 's1', project: 'p1' });
            API.deleteStation.mockRejectedValue(new Error('delete failed'));

            await expect(StationManager.deleteStation('s1')).rejects.toThrow('delete failed');
        });
    });

    // ------------------------------------------------------------------ //
    // moveStation
    // ------------------------------------------------------------------ //

    describe('moveStation', () => {
        it('delegates to updateStation with lat/lng from [lng, lat]', async () => {
            State.allStations.set('s1', { id: 's1', project: 'p1', latitude: 46.0, longitude: 6.0 });
            API.updateStation.mockResolvedValue({ id: 's1' });

            const result = await StationManager.moveStation('s1', [7.5, 47.5]);

            expect(result).toBe(true);
            expect(API.updateStation).toHaveBeenCalledWith('s1', { latitude: 47.5, longitude: 7.5 });
        });

        it('reverts visual position on failure', async () => {
            State.allStations.set('s1', { id: 's1', project: 'p1', latitude: 46.0, longitude: 6.0 });
            API.updateStation.mockRejectedValue(new Error('move failed'));

            await expect(StationManager.moveStation('s1', [7.5, 47.5])).rejects.toThrow('move failed');

            expect(Layers.updateStationPosition).toHaveBeenCalledWith('stations-p1', 's1', [6.0, 46.0]);
        });
    });

    // ------------------------------------------------------------------ //
    // invalidateCache
    // ------------------------------------------------------------------ //

    describe('invalidateCache', () => {
        it('forces a refetch on next ensureAllStationsLoaded call', async () => {
            const fc = makeFeatureCollection([]);
            API.getAllStationsGeoJSON.mockResolvedValue(fc);

            await StationManager.ensureAllStationsLoaded();
            expect(API.getAllStationsGeoJSON).toHaveBeenCalledTimes(1);

            StationManager.invalidateCache();
            await StationManager.ensureAllStationsLoaded();
            expect(API.getAllStationsGeoJSON).toHaveBeenCalledTimes(2);
        });
    });
});

describe('StationManager shared in-flight cache', () => {
    it('shares one request while retaining distinct async wrapper promises and cached feature identity', async () => {
        StationManager.invalidateCache();
        vi.clearAllMocks();
        let settle!: (value: unknown) => void;
        const response = new Promise<unknown>(resolve => { settle = resolve; });
        API.getAllStationsGeoJSON.mockReturnValue(response);
        const first = StationManager.ensureAllStationsLoaded();
        const second = StationManager.ensureAllStationsLoaded();
        expect(first).not.toBe(second);
        expect(API.getAllStationsGeoJSON).toHaveBeenCalledOnce();
        const feature = { type: 'Feature', id: 'cache-id', geometry: { type: 'Point', coordinates: [1, 2] }, properties: { project: 'cache-project', network: 'cache-project' } };
        settle({ type: 'FeatureCollection', features: [feature] });
        await expect(first).resolves.toBeUndefined();
        await expect(second).resolves.toBeUndefined();
        const loaded = await StationManager.loadStationsForProject('cache-project');
        expect(loaded[0]).toBe(feature);
        expect(API.getAllStationsGeoJSON).toHaveBeenCalledOnce();
    });
});
