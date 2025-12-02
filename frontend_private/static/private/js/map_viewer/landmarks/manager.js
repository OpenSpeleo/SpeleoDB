import { API } from '../api.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';

export const LandmarkManager = {
    async loadAllLandmarks() {
        try {
            console.log('📍 Loading all Landmarks...');
            const response = await API.getAllLandmarksGeoJSON();

            // API returns { success: true, data: { type: "FeatureCollection", features: [...] } }
            if (!response || response.success !== true || !response.data) {
                throw new Error('Invalid Landmark GeoJSON response');
            }

            const landmarkData = response.data;
            const features = landmarkData.features || [];

            State.allLandmarks.clear();
            features.forEach(feature => {
                if (feature.properties && feature.properties.id) {
                    const coords = feature.geometry?.coordinates;
                    if (Array.isArray(coords) && coords.length >= 2) {
                        State.allLandmarks.set(feature.properties.id, {
                            ...feature.properties,
                            latitude: Number(coords[1]),
                            longitude: Number(coords[0]),
                            coordinates: coords,
                            name: feature.properties.name || 'Unnamed Landmark',
                            description: feature.properties.description || '',
                            created_by: feature.properties.created_by || 'Unknown',
                            creation_date: feature.properties.creation_date || new Date().toISOString()
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
            const landmarkData = result.data.landmark;

            // Refresh list and update map
            const featureCollection = await this.loadAllLandmarks();
            Layers.addLandmarkLayer(featureCollection);

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


