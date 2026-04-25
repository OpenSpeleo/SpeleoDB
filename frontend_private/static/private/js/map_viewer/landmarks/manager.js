import { API } from '../api.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';

export const LandmarkManager = {
    async loadCollections() {
        try {
            console.log('📍 Loading Landmark Collections...');
            const response = await API.getLandmarkCollections();
            const collections = Array.isArray(response) ? response : [];

            State.landmarkCollections.clear();
            collections.forEach(collection => {
                const id = String(collection.id);
                State.landmarkCollections.set(id, {
                    id,
                    name: collection.name || 'Unnamed Collection',
                    description: collection.description || '',
                    color: collection.color || null,
                    collection_type: collection.collection_type || 'SHARED',
                    is_personal: collection.is_personal === true || collection.collection_type === 'PERSONAL',
                    user_permission_level: collection.user_permission_level,
                    user_permission_level_label: collection.user_permission_level_label,
                    can_write: Number(collection.user_permission_level) >= 2,
                    can_admin: Number(collection.user_permission_level) >= 3,
                });
            });

            console.log(`📍 Loaded ${State.landmarkCollections.size} Landmark Collections`);
            return collections;
        } catch (error) {
            console.error('Error loading Landmark Collections:', error);
            State.landmarkCollections.clear();
            return [];
        }
    },

    async loadAllLandmarks() {
        try {
            console.log('📍 Loading all Landmarks...');
            const landmarkData = await API.getAllLandmarksGeoJSON();

            if (!landmarkData) {
                throw new Error('Invalid Landmark GeoJSON response');
            }

            const features = landmarkData.features || [];

            State.allLandmarks.clear();
            features.forEach(feature => {
                const featureId = feature.id;
                if (feature.properties && featureId) {
                    const coords = feature.geometry?.coordinates;
                    if (Array.isArray(coords) && coords.length >= 2) {
                        const collectionId = feature.properties.collection ? String(feature.properties.collection) : null;
                        const collection = collectionId ? State.landmarkCollections.get(collectionId) : null;
                        State.allLandmarks.set(featureId, {
                            ...feature.properties,
                            id: featureId,
                            latitude: Number(coords[1]),
                            longitude: Number(coords[0]),
                            coordinates: coords,
                            name: feature.properties.name || 'Unnamed Landmark',
                            description: feature.properties.description || '',
                            created_by: feature.properties.created_by || 'Unknown',
                            creation_date: feature.properties.creation_date || new Date().toISOString(),
                            collection: collectionId,
                            collection_name: feature.properties.collection_name || collection?.name || null,
                            collection_type: feature.properties.collection_type || collection?.collection_type || null,
                            collection_color: feature.properties.collection_color || collection?.color || null,
                            is_personal_collection: feature.properties.is_personal_collection === true,
                            can_write: feature.properties.can_write === true,
                            can_delete: feature.properties.can_delete === true,
                        });
                    }
                }
            });

            console.log(`📍 Loaded ${State.allLandmarks.size} Landmarks`);
            return landmarkData;
        } catch (error) {
            console.error('Error loading Landmarks:', error);
            return { type: 'FeatureCollection', features: [] };
        }
    },

    async createLandmark(data) {
        try {
            const result = await API.createLandmark(data);
            const landmarkData = result.landmark;

            // Refresh list and update map
            const featureCollection = await this.loadAllLandmarks();
            Layers.addLandmarkLayer(featureCollection);
            
            // Ensure landmarks are rendered on top
            Layers.reorderLayers();

            return landmarkData;
        } catch (error) {
            console.error('Error creating Landmark:', error);
            throw error;
        }
    },

    async updateLandmark(landmarkId, data) {
        try {
            const result = await API.updateLandmark(landmarkId, data);

            // Refresh list and update map
            const featureCollection = await this.loadAllLandmarks();
            Layers.addLandmarkLayer(featureCollection);
            
            // Ensure landmarks are rendered on top
            Layers.reorderLayers();

            return result;
        } catch (error) {
            console.error('Error updating Landmark:', error);
            throw error;
        }
    },

    async deleteLandmark(landmarkId) {
        try {
            await API.deleteLandmark(landmarkId);

            // Update state
            State.allLandmarks.delete(landmarkId);

            // Refresh list and update map
            const featureCollection = await this.loadAllLandmarks();
            Layers.addLandmarkLayer(featureCollection);

            return true;
        } catch (error) {
            console.error('Error deleting Landmark:', error);
            throw error;
        }
    },

    async moveLandmark(landmarkId, newCoords) {
        try {
            const landmark = State.allLandmarks.get(landmarkId);
            if (!landmark || landmark.can_write !== true) {
                throw new Error('You do not have WRITE access to move this Landmark.');
            }

            await this.updateLandmark(landmarkId, {
                latitude: newCoords[1],
                longitude: newCoords[0]
            });
            return true;
        } catch (error) {
            // Revert on map if failed
            const landmark = State.allLandmarks.get(landmarkId);
            if (landmark) {
                Layers.revertLandmarkPosition(landmarkId, [landmark.longitude, landmark.latitude]);
            }
            throw error;
        }
    }
};
