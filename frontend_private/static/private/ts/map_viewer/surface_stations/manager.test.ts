import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { StationRecord, LeadWrite } from '../../../../../../ts-types/domain/station-records.ts';
import type { ViewerLandmark, ViewerLandmarkCollection, LandmarkFeatureProperties } from '../../../../../../ts-types/domain/map-entities.ts';
import type { ViewerExplorationLead } from '../../../../../../ts-types/domain/map-state.ts';
import type { ViewerProject } from '../../../../../../ts-types/domain/map-config.ts';
import { SurfaceStationManager } from './manager.ts';

const API = vi.hoisted(() => ({
        getAllSurfaceStationsGeoJSON: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        createSurfaceStation: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        updateStation: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        deleteStation: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
}));
vi.mock('../api.ts', () => ({ API }));

const State = vi.hoisted(() => ({
        allSurfaceStations: new Map<string, Partial<StationRecord>>(),
}));
vi.mock('../state.ts', () => ({ State }));

const Layers = vi.hoisted(() => ({
        refreshSurfaceStationsAfterChange: vi.fn<(...args: unknown[]) => Promise<void>>().mockResolvedValue(),
        updateSurfaceStationPosition: vi.fn<(...args: unknown[]) => void>(),
}));
vi.mock('../map/layers.ts', () => ({ Layers }));

vi.mock('../config.ts', () => ({ Config: {} }));

const GEOJSON = {
    type: 'FeatureCollection',
    features: [
        {
            id: 'surf-1',
            type: 'Feature',
            properties: { name: 'Station A', network: 'net-1' },
            geometry: { type: 'Point', coordinates: [2.0, 48.0] },
        },
        {
            id: 'surf-2',
            type: 'Feature',
            properties: { name: 'Station B', network: 'net-1' },
            geometry: { type: 'Point', coordinates: [3.0, 49.0] },
        },
        {
            id: 'surf-3',
            type: 'Feature',
            properties: { name: 'Station C', network: 'net-2' },
            geometry: { type: 'Point', coordinates: [4.0, 50.0] },
        },
    ],
};

describe('SurfaceStationManager', () => {
    beforeEach(() => {
        State.allSurfaceStations = new Map();
        SurfaceStationManager.invalidateCache();
        vi.clearAllMocks();
    });

    // ------------------------------------------------------------------ //
    // invalidateCache
    // ------------------------------------------------------------------ //

    describe('invalidateCache', () => {
        it('forces re-fetch on next load', async () => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledTimes(1);

            SurfaceStationManager.invalidateCache();

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledTimes(2);
        });
    });

    // ------------------------------------------------------------------ //
    // ensureAllSurfaceStationsLoaded
    // ------------------------------------------------------------------ //

    describe('ensureAllSurfaceStationsLoaded', () => {
        it('fetches and caches GeoJSON on first call', async () => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();

            expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledTimes(1);
        });

        it('does not re-fetch when already cached', async () => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();

            expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledTimes(1);
        });

        it('falls back to empty collection on invalid response', async () => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue({ invalid: true });

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();

            // Cached fallback prevents re-fetch
            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledTimes(1);
        });

        it('falls back to empty collection on network error', async () => {
            API.getAllSurfaceStationsGeoJSON.mockRejectedValue(new Error('Network error'));

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();

            // Should not throw, falls back gracefully
            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledTimes(1);
        });
    });

    // ------------------------------------------------------------------ //
    // loadStationsForNetwork
    // ------------------------------------------------------------------ //

    describe('loadStationsForNetwork', () => {
        it('returns features filtered by network ID', async () => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            const features = await SurfaceStationManager.loadStationsForNetwork('net-1');

            expect(features).toHaveLength(2);
            expect(features[0]!.id).toBe('surf-1');
            expect(features[1]!.id).toBe('surf-2');
        });

        it('populates State.allSurfaceStations for matched features', async () => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            await SurfaceStationManager.loadStationsForNetwork('net-1');

            expect(State.allSurfaceStations.has('surf-1')).toBe(true);
            expect(State.allSurfaceStations.has('surf-2')).toBe(true);
            expect(State.allSurfaceStations.has('surf-3')).toBe(false);
        });

        it('sets correct station properties from GeoJSON feature', async () => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            await SurfaceStationManager.loadStationsForNetwork('net-1');

            const station = State.allSurfaceStations.get('surf-1')!;
            expect(station.id).toBe('surf-1');
            expect(station.latitude).toBe(48.0);
            expect(station.longitude).toBe(2.0);
            expect(station.network).toBe('net-1');
            expect(station.station_type).toBe('surface');
        });

        it('returns empty array when network has no stations', async () => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            const features = await SurfaceStationManager.loadStationsForNetwork('net-999');

            expect(features).toHaveLength(0);
        });

        it('returns empty array on API error', async () => {
            API.getAllSurfaceStationsGeoJSON.mockRejectedValue(new Error('fail'));

            const features = await SurfaceStationManager.loadStationsForNetwork('net-1');

            expect(features).toHaveLength(0);
        });

        it('skips features with missing geometry', async () => {
            const partial = {
                type: 'FeatureCollection',
                features: [
                    {
                        id: 'no-geom',
                        type: 'Feature',
                        properties: { network: 'net-1' },
                        geometry: null,
                    },
                ],
            };
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(partial);

            await SurfaceStationManager.loadStationsForNetwork('net-1');

            expect(State.allSurfaceStations.has('no-geom')).toBe(false);
        });
    });

    // ------------------------------------------------------------------ //
    // createStation
    // ------------------------------------------------------------------ //

    describe('createStation', () => {
        beforeEach(() => {
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);
        });

        it('creates station via API and adds to state', async () => {
            const newStation = { id: 'new-1', name: 'New Station' };
            API.createSurfaceStation.mockResolvedValue(newStation);

            const result = await SurfaceStationManager.createStation('net-1', { name: 'New Station' });

            expect(result).toEqual(newStation);
            expect(State.allSurfaceStations.has('new-1')).toBe(true);
            const stored = State.allSurfaceStations.get('new-1')!;
            expect(stored.network).toBe('net-1');
            expect(stored.station_type).toBe('surface');
        });

        it('invalidates cache after creation', async () => {
            API.createSurfaceStation.mockResolvedValue({ id: 'new-1' });

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            await SurfaceStationManager.createStation('net-1', {});

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledTimes(2);
        });

        it('refreshes surface station layers', async () => {
            API.createSurfaceStation.mockResolvedValue({ id: 'new-1' });

            await SurfaceStationManager.createStation('net-1', {});

            expect(Layers.refreshSurfaceStationsAfterChange).toHaveBeenCalledWith('net-1');
        });

        it('throws on API error', async () => {
            API.createSurfaceStation.mockRejectedValue(new Error('Create failed'));

            await expect(
                SurfaceStationManager.createStation('net-1', {})
            ).rejects.toThrow('Create failed');
        });
    });

    // ------------------------------------------------------------------ //
    // updateStation
    // ------------------------------------------------------------------ //

    describe('updateStation', () => {
        it('updates station via API and merges state', async () => {
            State.allSurfaceStations.set('surf-1', { id: 'surf-1', network: 'net-1', name: 'Old' });
            API.updateStation.mockResolvedValue({ name: 'Updated' });

            const result = await SurfaceStationManager.updateStation('surf-1', { name: 'Updated' });

            expect(result).toEqual({ name: 'Updated' });
            expect(State.allSurfaceStations.get('surf-1')!.name).toBe('Updated');
        });

        it('updates map position when coordinates change', async () => {
            State.allSurfaceStations.set('surf-1', { id: 'surf-1', network: 'net-1' });
            API.updateStation.mockResolvedValue({});

            await SurfaceStationManager.updateStation('surf-1', { latitude: 49.0, longitude: 3.0 });

            expect(Layers.updateSurfaceStationPosition).toHaveBeenCalledWith(
                'surface-stations-net-1', 'surf-1', [3.0, 49.0]
            );
        });

        it('does not update position when only non-coordinate fields change', async () => {
            State.allSurfaceStations.set('surf-1', { id: 'surf-1', network: 'net-1' });
            API.updateStation.mockResolvedValue({ name: 'Updated' });

            await SurfaceStationManager.updateStation('surf-1', { name: 'Updated' });

            expect(Layers.updateSurfaceStationPosition).not.toHaveBeenCalled();
        });

        it('handles station not in state', async () => {
            API.updateStation.mockResolvedValue({ name: 'New' });

            const result = await SurfaceStationManager.updateStation('unknown', { name: 'New' });

            expect(result).toEqual({ name: 'New' });
            expect(Layers.updateSurfaceStationPosition).not.toHaveBeenCalled();
        });

        it('throws on API error', async () => {
            API.updateStation.mockRejectedValue(new Error('Update failed'));

            await expect(
                SurfaceStationManager.updateStation('surf-1', {})
            ).rejects.toThrow('Update failed');
        });
    });

    // ------------------------------------------------------------------ //
    // deleteStation
    // ------------------------------------------------------------------ //

    describe('deleteStation', () => {
        it('deletes station and removes from state', async () => {
            State.allSurfaceStations.set('surf-1', { id: 'surf-1', network: 'net-1' });
            API.deleteStation.mockResolvedValue({});
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            const result = await SurfaceStationManager.deleteStation('surf-1');

            expect(result).toBe(true);
            expect(State.allSurfaceStations.has('surf-1')).toBe(false);
            expect(API.deleteStation).toHaveBeenCalledWith('surf-1');
        });

        it('refreshes network layer after deletion', async () => {
            State.allSurfaceStations.set('surf-1', { id: 'surf-1', network: 'net-1' });
            API.deleteStation.mockResolvedValue({});
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            await SurfaceStationManager.deleteStation('surf-1');

            expect(Layers.refreshSurfaceStationsAfterChange).toHaveBeenCalledWith('net-1');
        });

        it('skips layer refresh when station was not in state', async () => {
            API.deleteStation.mockResolvedValue({});

            const result = await SurfaceStationManager.deleteStation('nonexistent');

            expect(result).toBe(true);
            expect(Layers.refreshSurfaceStationsAfterChange).not.toHaveBeenCalled();
        });

        it('throws on API error', async () => {
            State.allSurfaceStations.set('surf-1', { id: 'surf-1', network: 'net-1' });
            API.deleteStation.mockRejectedValue(new Error('Delete failed'));

            await expect(
                SurfaceStationManager.deleteStation('surf-1')
            ).rejects.toThrow('Delete failed');
        });

        it('invalidates cache after deletion', async () => {
            State.allSurfaceStations.set('surf-1', { id: 'surf-1', network: 'net-1' });
            API.deleteStation.mockResolvedValue({});
            API.getAllSurfaceStationsGeoJSON.mockResolvedValue(GEOJSON);

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            await SurfaceStationManager.deleteStation('surf-1');

            await SurfaceStationManager.ensureAllSurfaceStationsLoaded();
            expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledTimes(2);
        });
    });
});

describe('SurfaceStationManager shared in-flight cache', () => {
    it('shares one request while retaining distinct async wrapper promises and cached feature identity', async () => {
        SurfaceStationManager.invalidateCache();
        vi.clearAllMocks();
        let settle!: (value: unknown) => void;
        const response = new Promise<unknown>(resolve => { settle = resolve; });
        API.getAllSurfaceStationsGeoJSON.mockReturnValue(response);
        const first = SurfaceStationManager.ensureAllSurfaceStationsLoaded();
        const second = SurfaceStationManager.ensureAllSurfaceStationsLoaded();
        expect(first).not.toBe(second);
        expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledOnce();
        const feature = { type: 'Feature', id: 'cache-id', geometry: { type: 'Point', coordinates: [1, 2] }, properties: { project: 'cache-project', network: 'cache-project' } };
        settle({ type: 'FeatureCollection', features: [feature] });
        await expect(first).resolves.toBeUndefined();
        await expect(second).resolves.toBeUndefined();
        const loaded = await SurfaceStationManager.loadStationsForNetwork('cache-project');
        expect(loaded[0]).toBe(feature);
        expect(API.getAllSurfaceStationsGeoJSON).toHaveBeenCalledOnce();
    });
});
