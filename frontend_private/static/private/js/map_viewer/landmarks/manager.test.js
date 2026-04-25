import { LandmarkManager } from './manager.js';

vi.mock('../api.js', () => ({
    API: {
        getAllLandmarksGeoJSON: vi.fn(),
        getLandmarkCollections: vi.fn(),
        createLandmark: vi.fn(),
        updateLandmark: vi.fn(),
        deleteLandmark: vi.fn(),
    },
}));

vi.mock('../state.js', () => ({
    State: {
        allLandmarks: new Map(),
        landmarkCollections: new Map(),
    },
}));

vi.mock('../map/layers.js', () => ({
    Layers: {
        addLandmarkLayer: vi.fn(),
        reorderLayers: vi.fn(),
        revertLandmarkPosition: vi.fn(),
    },
}));

import { API } from '../api.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';

function makeLandmarkFC(features) {
    return { type: 'FeatureCollection', features };
}

function makeLandmarkFeature(id, coords = [6.5, 46.5], props = {}) {
    return {
        id,
        type: 'Feature',
        geometry: { type: 'Point', coordinates: coords },
        properties: {
            name: props.name || `Landmark ${id}`,
            description: props.description || '',
            created_by: props.created_by || 'tester',
            creation_date: props.creation_date || '2025-01-01T00:00:00Z',
            can_write: props.can_write ?? true,
            can_delete: props.can_delete ?? true,
            ...props,
        },
    };
}

describe('LandmarkManager', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        State.allLandmarks.clear();
        State.landmarkCollections.clear();
    });

    describe('loadCollections', () => {
        it('populates writable and admin flags from permission levels', async () => {
            API.getLandmarkCollections.mockResolvedValue([
                { id: 'coll-1', name: 'Read', color: '#111111', user_permission_level: 1 },
                { id: 'coll-2', name: 'Write', color: '#222222', user_permission_level: 2 },
                { id: 'coll-3', name: 'Admin', color: '#333333', user_permission_level: 3, collection_type: 'PERSONAL' },
            ]);

            const result = await LandmarkManager.loadCollections();

            expect(result).toHaveLength(3);
            expect(State.landmarkCollections.get('coll-1').can_write).toBe(false);
            expect(State.landmarkCollections.get('coll-2').can_write).toBe(true);
            expect(State.landmarkCollections.get('coll-2').color).toBe('#222222');
            expect(State.landmarkCollections.get('coll-3').can_admin).toBe(true);
            expect(State.landmarkCollections.get('coll-3').is_personal).toBe(true);
        });

        it('clears collection state on API error', async () => {
            State.landmarkCollections.set('old', { id: 'old' });
            API.getLandmarkCollections.mockRejectedValue(new Error('fail'));

            const result = await LandmarkManager.loadCollections();

            expect(result).toEqual([]);
            expect(State.landmarkCollections.size).toBe(0);
        });
    });

    // ------------------------------------------------------------------ //
    // loadAllLandmarks
    // ------------------------------------------------------------------ //

    describe('loadAllLandmarks', () => {
        it('populates State.allLandmarks from GeoJSON', async () => {
            const fc = makeLandmarkFC([
                makeLandmarkFeature('lm1', [6.5, 46.5]),
                makeLandmarkFeature('lm2', [7.0, 47.0]),
            ]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(fc);

            const result = await LandmarkManager.loadAllLandmarks();

            expect(result).toBe(fc);
            expect(State.allLandmarks.size).toBe(2);
            const lm1 = State.allLandmarks.get('lm1');
            expect(lm1.latitude).toBe(46.5);
            expect(lm1.longitude).toBe(6.5);
            expect(lm1.name).toBe('Landmark lm1');
            expect(lm1.can_write).toBe(true);
            expect(lm1.is_personal_collection).toBe(false);
        });

        it('stores collection metadata from GeoJSON properties', async () => {
            const fc = makeLandmarkFC([
                makeLandmarkFeature('lm1', [6.5, 46.5], {
                    collection: 'personal-1',
                    collection_name: 'Personal Landmarks',
                    collection_color: '#123456',
                    collection_type: 'PERSONAL',
                    is_personal_collection: true,
                }),
            ]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(fc);

            await LandmarkManager.loadAllLandmarks();

            const lm1 = State.allLandmarks.get('lm1');
            expect(lm1.collection).toBe('personal-1');
            expect(lm1.collection_color).toBe('#123456');
            expect(lm1.collection_type).toBe('PERSONAL');
            expect(lm1.is_personal_collection).toBe(true);
        });

        it('treats omitted write/delete flags as read-only', async () => {
            const feature = makeLandmarkFeature('lm1');
            delete feature.properties.can_write;
            delete feature.properties.can_delete;
            API.getAllLandmarksGeoJSON.mockResolvedValue(makeLandmarkFC([feature]));

            await LandmarkManager.loadAllLandmarks();

            const landmark = State.allLandmarks.get('lm1');
            expect(landmark.can_write).toBe(false);
            expect(landmark.can_delete).toBe(false);
        });

        it('falls back to hydrated collection color when GeoJSON omits it', async () => {
            State.landmarkCollections.set('shared-1', {
                id: 'shared-1',
                name: 'Shared',
                color: '#abcdef',
                collection_type: 'SHARED',
            });
            const fc = makeLandmarkFC([
                makeLandmarkFeature('lm1', [6.5, 46.5], {
                    collection: 'shared-1',
                    collection_name: 'Shared',
                }),
            ]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(fc);

            await LandmarkManager.loadAllLandmarks();

            expect(State.allLandmarks.get('lm1').collection_color).toBe('#abcdef');
        });

        it('clears previous landmarks before repopulating', async () => {
            State.allLandmarks.set('old', { id: 'old' });

            const fc = makeLandmarkFC([makeLandmarkFeature('lm1')]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(fc);

            await LandmarkManager.loadAllLandmarks();

            expect(State.allLandmarks.has('old')).toBe(false);
            expect(State.allLandmarks.size).toBe(1);
        });

        it('returns empty FeatureCollection on API error', async () => {
            API.getAllLandmarksGeoJSON.mockRejectedValue(new Error('fail'));

            const result = await LandmarkManager.loadAllLandmarks();

            expect(result).toEqual({ type: 'FeatureCollection', features: [] });
        });

        it('returns empty FeatureCollection on null response', async () => {
            API.getAllLandmarksGeoJSON.mockResolvedValue(null);

            const result = await LandmarkManager.loadAllLandmarks();

            expect(result).toEqual({ type: 'FeatureCollection', features: [] });
        });

        it('skips features with missing coordinates', async () => {
            const fc = makeLandmarkFC([
                makeLandmarkFeature('lm1', [6.5, 46.5]),
                { id: 'lm2', type: 'Feature', geometry: { type: 'Point', coordinates: [] }, properties: { name: 'Bad' } },
            ]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(fc);

            await LandmarkManager.loadAllLandmarks();

            expect(State.allLandmarks.size).toBe(1);
        });

        it('defaults name to "Unnamed Landmark" when absent', async () => {
            const fc = makeLandmarkFC([
                { id: 'lm1', type: 'Feature', geometry: { type: 'Point', coordinates: [6, 46] }, properties: {} },
            ]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(fc);

            await LandmarkManager.loadAllLandmarks();

            expect(State.allLandmarks.get('lm1').name).toBe('Unnamed Landmark');
        });
    });

    // ------------------------------------------------------------------ //
    // createLandmark
    // ------------------------------------------------------------------ //

    describe('createLandmark', () => {
        it('creates landmark, reloads all, and updates layers', async () => {
            const createdLandmark = { id: 'lm-new', name: 'New Landmark' };
            API.createLandmark.mockResolvedValue({ landmark: createdLandmark });

            const reloadedFC = makeLandmarkFC([makeLandmarkFeature('lm-new')]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(reloadedFC);

            const result = await LandmarkManager.createLandmark({ name: 'New Landmark', latitude: 46.5 });

            expect(result).toEqual(createdLandmark);
            expect(Layers.addLandmarkLayer).toHaveBeenCalledWith(reloadedFC);
            expect(Layers.reorderLayers).toHaveBeenCalled();
        });

        it('propagates API errors', async () => {
            API.createLandmark.mockRejectedValue(new Error('create failed'));

            await expect(LandmarkManager.createLandmark({})).rejects.toThrow('create failed');
        });
    });

    // ------------------------------------------------------------------ //
    // updateLandmark
    // ------------------------------------------------------------------ //

    describe('updateLandmark', () => {
        it('updates landmark and refreshes layers', async () => {
            const apiResult = { id: 'lm1', name: 'Updated' };
            API.updateLandmark.mockResolvedValue(apiResult);

            const reloadedFC = makeLandmarkFC([makeLandmarkFeature('lm1')]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(reloadedFC);

            const result = await LandmarkManager.updateLandmark('lm1', { name: 'Updated' });

            expect(result).toBe(apiResult);
            expect(Layers.addLandmarkLayer).toHaveBeenCalledWith(reloadedFC);
            expect(Layers.reorderLayers).toHaveBeenCalled();
        });

        it('propagates API errors', async () => {
            API.updateLandmark.mockRejectedValue(new Error('update failed'));

            await expect(LandmarkManager.updateLandmark('lm1', {})).rejects.toThrow('update failed');
        });
    });

    // ------------------------------------------------------------------ //
    // deleteLandmark
    // ------------------------------------------------------------------ //

    describe('deleteLandmark', () => {
        it('removes from state, reloads, and updates layers', async () => {
            State.allLandmarks.set('lm1', { id: 'lm1' });
            API.deleteLandmark.mockResolvedValue({ ok: true });

            const reloadedFC = makeLandmarkFC([]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(reloadedFC);

            const result = await LandmarkManager.deleteLandmark('lm1');

            expect(result).toBe(true);
            expect(State.allLandmarks.has('lm1')).toBe(false);
            expect(Layers.addLandmarkLayer).toHaveBeenCalledWith(reloadedFC);
        });

        it('propagates API errors', async () => {
            API.deleteLandmark.mockRejectedValue(new Error('delete failed'));

            await expect(LandmarkManager.deleteLandmark('lm1')).rejects.toThrow('delete failed');
        });
    });

    // ------------------------------------------------------------------ //
    // moveLandmark
    // ------------------------------------------------------------------ //

    describe('moveLandmark', () => {
        it('delegates to updateLandmark with lat/lng', async () => {
            State.allLandmarks.set('lm1', {
                id: 'lm1',
                latitude: 46.0,
                longitude: 6.0,
                can_write: true,
            });
            API.updateLandmark.mockResolvedValue({ id: 'lm1' });
            const reloadedFC = makeLandmarkFC([makeLandmarkFeature('lm1')]);
            API.getAllLandmarksGeoJSON.mockResolvedValue(reloadedFC);

            const result = await LandmarkManager.moveLandmark('lm1', [7.5, 47.5]);

            expect(result).toBe(true);
            expect(API.updateLandmark).toHaveBeenCalledWith('lm1', { latitude: 47.5, longitude: 7.5 });
        });

        it('reverts visual position on failure', async () => {
            State.allLandmarks.set('lm1', {
                id: 'lm1',
                latitude: 46.0,
                longitude: 6.0,
                can_write: true,
            });
            API.updateLandmark.mockRejectedValue(new Error('move failed'));

            await expect(LandmarkManager.moveLandmark('lm1', [7.5, 47.5])).rejects.toThrow('move failed');

            expect(Layers.revertLandmarkPosition).toHaveBeenCalledWith('lm1', [6.0, 46.0]);
        });

        it('rejects moving read-only collection landmarks', async () => {
            State.allLandmarks.set('lm1', {
                id: 'lm1',
                latitude: 46.0,
                longitude: 6.0,
                can_write: false,
            });

            await expect(LandmarkManager.moveLandmark('lm1', [7.5, 47.5])).rejects.toThrow('WRITE access');

            expect(API.updateLandmark).not.toHaveBeenCalled();
            expect(Layers.revertLandmarkPosition).toHaveBeenCalledWith('lm1', [6.0, 46.0]);
        });

        it('rejects moving a landmark missing permission state', async () => {
            API.updateLandmark.mockRejectedValue(new Error('move failed'));

            await expect(LandmarkManager.moveLandmark('lm-missing', [7.5, 47.5])).rejects.toThrow('WRITE access');

            expect(API.updateLandmark).not.toHaveBeenCalled();
            expect(Layers.revertLandmarkPosition).not.toHaveBeenCalled();
        });
    });
});
