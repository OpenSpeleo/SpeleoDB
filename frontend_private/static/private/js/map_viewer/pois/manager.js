import { API } from '../api.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { Layers } from '../map/layers.js';

export const LandmarkManager = {
    async loadAllPOIs() {
        try {
            console.log('📍 Loading all Landmarks...');
            const response = await API.getAllLandmarksGeoJSON();

            // API returns { success: true, data: { type: "FeatureCollection", features: [...] } }
            if (!response || response.success !== true || !response.data) {
                throw new Error('Invalid Landmark GeoJSON response');
            }

            const poiData = response.data;
            const features = poiData.features || [];

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
            return poiData;
        } catch (error) {
            console.error('Error loading Landmarks:', error);
            return { type: 'FeatureCollection', features: [] };
        }
    },

    async createLandmark(data) {
        try {
            const result = await API.createLandmark(data);
            const poiData = result.data || result;

            // Refresh list and update map
            const featureCollection = await this.loadAllPOIs();
            Layers.addLandmarkLayer(featureCollection);

            return poiData;
        } catch (error) {
            console.error('Error creating Landmark:', error);
            throw error;
        }
    },

    async updateLandmark(poiId, data) {
        try {
            const result = await API.updateLandmark(poiId, data);

            // Refresh list and update map
            const featureCollection = await this.loadAllPOIs();
            Layers.addLandmarkLayer(featureCollection);

            return result;
        } catch (error) {
            console.error('Error updating Landmark:', error);
            throw error;
        }
    },

    async deleteLandmark(poiId) {
        try {
            await API.deleteLandmark(poiId);

            // Update state
            State.allLandmarks.delete(poiId);

            // Refresh list and update map
            const featureCollection = await this.loadAllPOIs();
            Layers.addLandmarkLayer(featureCollection);

            return true;
        } catch (error) {
            console.error('Error deleting Landmark:', error);
            throw error;
        }
    },

    async movePOI(poiId, newCoords) {
        try {
            await this.updateLandmark(poiId, {
                latitude: newCoords[1],
                longitude: newCoords[0]
            });
            return true;
        } catch (error) {
            // Revert on map if failed
            const poi = State.allLandmarks.get(poiId);
            if (poi) {
                Layers.revertPOIPosition(poiId, [poi.longitude, poi.latitude]);
            }
            throw error;
        }
    }
};


