import { State } from './state.js';

describe('State', () => {
    afterEach(() => {
        State.init();
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
    });

    describe('init()', () => {
        it('resets all Map fields to empty Maps', () => {
            State.projectLayerStates.set('test', true);
            State.allStations.set('s1', { id: 's1' });
            State.explorationLeads.set('e1', {});
            State.gpsTrackCache.set('t1', {});

            State.init();

            expect(State.projectLayerStates.size).toBe(0);
            expect(State.allStations.size).toBe(0);
            expect(State.explorationLeads.size).toBe(0);
            expect(State.gpsTrackCache.size).toBe(0);
        });

        it('resets activeDepthDomain to null', () => {
            State.activeDepthDomain = { min: 0, max: 100 };
            State.init();
            expect(State.activeDepthDomain).toBeNull();
        });

        it('resets landmarksVisible to true', () => {
            State.landmarksVisible = false;
            State.init();
            expect(State.landmarksVisible).toBe(true);
        });

        it('creates new Map instances rather than clearing existing ones', () => {
            const oldStations = State.allStations;
            const oldBounds = State.projectBounds;

            State.init();

            expect(State.allStations).not.toBe(oldStations);
            expect(State.projectBounds).not.toBe(oldBounds);
            expect(State.allStations).toBeInstanceOf(Map);
            expect(State.projectBounds).toBeInstanceOf(Map);
        });

        it('resets all GPS track Maps', () => {
            State.gpsTrackLayerStates.set('t1', true);
            State.gpsTrackCache.set('t1', { data: true });
            State.gpsTrackLoadingStates.set('t1', true);
            State.allGPSTrackLayers.set('t1', ['layer-1']);
            State.gpsTrackBounds.set('t1', [0, 0, 1, 1]);

            State.init();

            expect(State.gpsTrackLayerStates.size).toBe(0);
            expect(State.gpsTrackCache.size).toBe(0);
            expect(State.gpsTrackLoadingStates.size).toBe(0);
            expect(State.allGPSTrackLayers.size).toBe(0);
            expect(State.gpsTrackBounds.size).toBe(0);
        });

        it('does not reset map, tags, currentStationForTagging, or currentProjectId', () => {
            State.map = 'mock-map';
            State.userTags = ['tag1'];
            State.currentStationForTagging = 'station-1';
            State.currentProjectId = 'proj-1';

            State.init();

            expect(State.map).toBe('mock-map');
            expect(State.userTags).toEqual(['tag1']);
            expect(State.currentStationForTagging).toBe('station-1');
            expect(State.currentProjectId).toBe('proj-1');
        });
    });
});
