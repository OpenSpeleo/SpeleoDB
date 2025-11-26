import { API } from '../api.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { Layers } from '../map/layers.js';

export const POIManager = {
    async loadAllPOIs() {
        try {
            console.log('📍 Loading all POIs...');
            const response = await API.getAllPOIsGeoJSON();
            
            // API returns { success: true, data: { type: "FeatureCollection", features: [...] } }
            if (!response || response.success !== true || !response.data) {
                throw new Error('Invalid POI GeoJSON response');
            }
            
            const poiData = response.data;
            const features = poiData.features || [];
            
            State.allPOIs.clear();
            features.forEach(feature => {
                if (feature.properties && feature.properties.id) {
                    const coords = feature.geometry?.coordinates;
                    if (Array.isArray(coords) && coords.length >= 2) {
                        State.allPOIs.set(feature.properties.id, {
                            ...feature.properties,
                            latitude: Number(coords[1]),
                            longitude: Number(coords[0]),
                            coordinates: coords,
                            name: feature.properties.name || 'Unnamed Point of Interest',
                            description: feature.properties.description || '',
                            created_by: feature.properties.created_by || 'Unknown',
                            creation_date: feature.properties.creation_date || new Date().toISOString()
                        });
                    }
                }
            });
            
            console.log(`📍 Loaded ${State.allPOIs.size} POIs`);
            return poiData;
        } catch (error) {
            console.error('Error loading POIs:', error);
            return { type: 'FeatureCollection', features: [] };
        }
    },

    async createPOI(data) {
        try {
            const result = await API.createPOI(data);
            const poiData = result.data || result;
            
            // Refresh list and update map
            const featureCollection = await this.loadAllPOIs();
            Layers.addPOILayer(featureCollection);
            
            return poiData;
        } catch (error) {
            console.error('Error creating POI:', error);
            throw error;
        }
    },

    async updatePOI(poiId, data) {
        try {
            const result = await API.updatePOI(poiId, data);
            
            // Refresh list and update map
            const featureCollection = await this.loadAllPOIs();
            Layers.addPOILayer(featureCollection);
            
            return result;
        } catch (error) {
            console.error('Error updating POI:', error);
            throw error;
        }
    },

    async deletePOI(poiId) {
        try {
            await API.deletePOI(poiId);
            
            // Update state
            State.allPOIs.delete(poiId);
            
            // Refresh list and update map
            const featureCollection = await this.loadAllPOIs();
            Layers.addPOILayer(featureCollection);
            
            return true;
        } catch (error) {
            console.error('Error deleting POI:', error);
            throw error;
        }
    },

    async movePOI(poiId, newCoords) {
        try {
            await this.updatePOI(poiId, {
                latitude: newCoords[1],
                longitude: newCoords[0]
            });
            return true;
        } catch (error) {
            // Revert on map if failed
            const poi = State.allPOIs.get(poiId);
            if (poi) {
                Layers.revertPOIPosition(poiId, [poi.longitude, poi.latitude]);
            }
            throw error;
        }
    }
};


