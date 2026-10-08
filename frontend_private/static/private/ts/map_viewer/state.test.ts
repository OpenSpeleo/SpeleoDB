import type { ViewerState } from '../../../../../ts-types/domain/map-state.ts';
import { State, createDefaultDisplayPreferences } from './state.ts';
import { ViewerUpdates } from './viewer_updates.ts';

describe('State', () => {
    afterEach(() => {
        State.resetLayerState();
        State.displayPreferences = createDefaultDisplayPreferences();
        State.map = null;
        State.userTags = [];
        State.tagColors = [];
        State.currentStationForTagging = null;
        State.currentProjectId = null;
    });

    describe('initial values', () => {
        it('has null map', () => {
            expect(State.map).toBeNull();
        });

        it('has Map instances for layer tracking', () => {
            expect(State.projectLayerStates).toBeInstanceOf(Map);
            expect(State.effectiveProjectVisibility).toBeInstanceOf(Map);
            expect(State.networkLayerStates).toBeInstanceOf(Map);
            expect(State.allProjectLayers).toBeInstanceOf(Map);
            expect(State.allNetworkLayers).toBeInstanceOf(Map);
        });

        it('has Map instances for entity collections', () => {
            expect(State.allStations).toBeInstanceOf(Map);
            expect(State.allSurfaceStations).toBeInstanceOf(Map);
            expect(State.allLandmarks).toBeInstanceOf(Map);
            expect(State.explorationLeads).toBeInstanceOf(Map);
            expect(State.cylinderInstalls).toBeInstanceOf(Map);
        });

        it('has Map instances for depth domains and bounds', () => {
            expect(State.projectDepthDomains).toBeInstanceOf(Map);
            expect(State.projectBounds).toBeInstanceOf(Map);
            expect(State.networkBounds).toBeInstanceOf(Map);
        });

        it('has null activeDepthDomain', () => {
            expect(State.activeDepthDomain).toBeNull();
        });

        it('has empty arrays for tags', () => {
            expect(State.userTags).toEqual([]);
            expect(State.tagColors).toEqual([]);
        });

        it('has null currentStationForTagging and currentProjectId', () => {
            expect(State.currentStationForTagging).toBeNull();
            expect(State.currentProjectId).toBeNull();
        });

        it('has landmarksVisible set to true', () => {
            expect(State.landmarksVisible).toBe(true);
        });

        it('has Map instances for GPS track state', () => {
            expect(State.gpsTrackLayerStates).toBeInstanceOf(Map);
            expect(State.gpsTrackCache).toBeInstanceOf(Map);
            expect(State.gpsTrackLoadingStates).toBeInstanceOf(Map);
            expect(State.allGPSTrackLayers).toBeInstanceOf(Map);
            expect(State.gpsTrackBounds).toBeInstanceOf(Map);
        });

        it('has Map instances for GIS Layer state', () => {
            expect(State.gisLayerStates).toBeInstanceOf(Map);
            expect(State.gisLayerCache).toBeInstanceOf(Map);
            expect(State.gisLayerLoadingStates).toBeInstanceOf(Map);
            expect(State.allGISLayerLayers).toBeInstanceOf(Map);
            expect(State.gisLayerBounds).toBeInstanceOf(Map);
            expect(State.gisLayerClickableLayerIds).toBeInstanceOf(Set);
        });
    });

    describe('resetLayerState()', () => {
        it('replaces every collection after cancelling work and retains independent state identities', () => {
            const before = { ...State };
            type CollectionKey = { [Key in keyof ViewerState]: ViewerState[Key] extends Map<infer _K, infer _V> | Set<infer _S> ? Key : never }[keyof ViewerState];
            const containers = Object.entries(State).filter(([, value]) => value instanceof Map || value instanceof Set) as [CollectionKey, ViewerState[CollectionKey]][];
            State.displayUpdatePending = true;
            const cancel = vi.spyOn(ViewerUpdates, 'cancelAll').mockImplementation(() => {
                expect(State.layerGeneration).toBe(before.layerGeneration);
                for (const [key, value] of containers) expect(State[key]).toBe(value);
            });
            try {
                expect(State.resetLayerState()).toBeUndefined();
                expect(cancel).toHaveBeenCalledOnce();
                expect(State.layerGeneration).toBe(before.layerGeneration + 1);
                expect(State.displayUpdatePending).toBe(false);
                for (const [key, value] of containers) {
                    expect(State[key]).not.toBe(value);
                    expect(State[key].constructor).toBe(value.constructor);
                    expect(State[key].size).toBe(0);
                }
                for (const key of ['map', 'userTags', 'tagColors', 'currentStationForTagging', 'currentProjectId', 'displayPreferences'] as const) {
                    expect(State[key]).toBe(before[key]);
                }
            } finally {
                cancel.mockRestore();
            }
        });

        it('keeps the landmarks getter and setter tied to the current preference object', () => {
            const descriptor = Object.getOwnPropertyDescriptor(State, 'landmarksVisible');
            const preferences = createDefaultDisplayPreferences();
            State.displayPreferences = preferences;
            State.landmarksVisible = false;
            expect(preferences.categories.landmarks).toBe(false);
            preferences.categories.landmarks = true;
            expect(State.landmarksVisible).toBe(true);
            State.resetLayerState();
            expect(Object.getOwnPropertyDescriptor(State, 'landmarksVisible')).toEqual(descriptor);
        });

        it('resets all Map fields to empty Maps', () => {
            State.projectLayerStates.set('test', true);
            State.effectiveProjectVisibility.set('test', false);
            State.allStations.set('s1', { id: 's1' });
            State.explorationLeads.set('e1', { id: 'e1', coordinates: [1, 2], lineName: 'Survey Line', description: '', projectId: 'p1', createdAt: undefined });
            State.gpsTrackCache.set('t1', { type: 'FeatureCollection', features: [] });

            State.resetLayerState();

            expect(State.projectLayerStates.size).toBe(0);
            expect(State.effectiveProjectVisibility.size).toBe(0);
            expect(State.allStations.size).toBe(0);
            expect(State.explorationLeads.size).toBe(0);
            expect(State.gpsTrackCache.size).toBe(0);
        });

        it('resets activeDepthDomain to null', () => {
            State.activeDepthDomain = { min: 0, max: 100 };
            State.resetLayerState();
            expect(State.activeDepthDomain).toBeNull();
        });

        it('preserves display preferences across a map-data reset', () => {
            State.landmarksVisible = false;
            State.displayPreferences.colorMode = 'depth';
            State.displayPreferences.stationTypes.biology = false;
            State.resetLayerState();
            expect(State.landmarksVisible).toBe(false);
            expect(State.displayPreferences.colorMode).toBe('depth');
            expect(State.displayPreferences.stationTypes.biology).toBe(false);
        });

        it('creates new Map instances rather than clearing existing ones', () => {
            const oldStations = State.allStations;
            const oldBounds = State.projectBounds;

            State.resetLayerState();

            expect(State.allStations).not.toBe(oldStations);
            expect(State.projectBounds).not.toBe(oldBounds);
            expect(State.allStations).toBeInstanceOf(Map);
            expect(State.projectBounds).toBeInstanceOf(Map);
        });

        it('resets all GPS track Maps', () => {
            State.gpsTrackLayerStates.set('t1', true);
            State.gpsTrackCache.set('t1', { type: 'FeatureCollection', features: [] });
            State.gpsTrackLoadingStates.set('t1', true);
            State.allGPSTrackLayers.set('t1', ['layer-1']);
            State.gpsTrackBounds.set('t1', [0, 0, 1, 1]);

            State.resetLayerState();

            expect(State.gpsTrackLayerStates.size).toBe(0);
            expect(State.gpsTrackCache.size).toBe(0);
            expect(State.gpsTrackLoadingStates.size).toBe(0);
            expect(State.allGPSTrackLayers.size).toBe(0);
            expect(State.gpsTrackBounds.size).toBe(0);
        });

        it('resets all GIS Layer Maps', () => {
            State.gisLayerStates.set('g1', true);
            State.gisLayerCache.set('g1', { type: 'FeatureCollection', features: [] });
            State.gisLayerGeometryTypeStates.set('g1', new Map([['Point', false]]));
            State.gisLayerLoadingStates.set('g1', true);
            State.allGISLayerLayers.set('g1', ['layer-1']);
            State.gisLayerBounds.set('g1', [0, 0, 1, 1]);
            State.gisLayerClickableLayerIds.add('gis-layer-g1-fill');

            State.resetLayerState();

            expect(State.gisLayerStates.size).toBe(0);
            expect(State.gisLayerCache.size).toBe(0);
            expect(State.gisLayerGeometryTypeStates.size).toBe(0);
            expect(State.gisLayerLoadingStates.size).toBe(0);
            expect(State.allGISLayerLayers.size).toBe(0);
            expect(State.gisLayerBounds.size).toBe(0);
            expect(State.gisLayerClickableLayerIds.size).toBe(0);
        });

        it('does not reset map, tags, currentStationForTagging, or currentProjectId', () => {
            const map = { addLayer: vi.fn(), addSource: vi.fn(), fitBounds: vi.fn() };
            // Reset only preserves this opaque identity; it invokes no map methods.
            State.map = map as unknown as NonNullable<ViewerState['map']>;
            const tags = [{ id: 'tag1', name: 'Tag', color: '#123456' }];
            State.userTags = tags;
            State.currentStationForTagging = 'station-1';
            State.currentProjectId = 'proj-1';

            State.resetLayerState();

            expect(State.map).toBe(map);
            expect(State.userTags).toBe(tags);
            expect(State.currentStationForTagging).toBe('station-1');
            expect(State.currentProjectId).toBe('proj-1');
        });
    });
});
