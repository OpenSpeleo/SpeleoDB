import { API } from '../api.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';
import { Config } from '../config.js';

// Cache for all surface stations GeoJSON
let allSurfaceStationsGeoJson = null;
let allSurfaceStationsFetchPromise = null;

export const SurfaceStationManager = {
    // Invalidate cache
    invalidateCache() {
        allSurfaceStationsGeoJson = null;
        allSurfaceStationsFetchPromise = null;
    },

    // Ensure all surface stations are loaded (single API call)
    async ensureAllSurfaceStationsLoaded() {
        if (allSurfaceStationsGeoJson && 
            allSurfaceStationsGeoJson.type === 'FeatureCollection' && 
            Array.isArray(allSurfaceStationsGeoJson.features)) {
            return;
        }

        if (allSurfaceStationsFetchPromise) {
            await allSurfaceStationsFetchPromise;
            return;
        }

        console.log('🔄 Fetching all surface stations (GeoJSON) via single API call...');
        allSurfaceStationsFetchPromise = API.getAllSurfaceStationsGeoJSON()
            .then(response => {
                if (!response || response.success !== true || !response.data || 
                    response.data.type !== 'FeatureCollection' || !Array.isArray(response.data.features)) {
                    throw new Error('Invalid all-surface-stations GeoJSON payload');
                }
                allSurfaceStationsGeoJson = response.data;
                console.log(`✅ Cached ${allSurfaceStationsGeoJson.features.length} surface stations from all-surface-stations GeoJSON`);
            })
            .catch(err => {
                console.error('❌ Failed to load all surface stations GeoJSON:', err);
                allSurfaceStationsGeoJson = { type: 'FeatureCollection', features: [] };
            })
            .finally(() => {
                allSurfaceStationsFetchPromise = null;
            });

        await allSurfaceStationsFetchPromise;
    },

    async loadStationsForNetwork(networkId) {
        try {
            // Ensure all surface stations are cached
            await this.ensureAllSurfaceStationsLoaded();

            // Filter stations for this network
            const allFc = allSurfaceStationsGeoJson || { type: 'FeatureCollection', features: [] };
            
            const features = allFc.features.filter(f => String(f?.properties?.network) === String(networkId));
            
            console.log(`📍 Loaded ${features.length} surface stations for network ${networkId}`);

            // Update State
            features.forEach(feature => {
                if (feature.properties && feature.properties.id && feature.geometry) {
                    State.allSurfaceStations.set(feature.properties.id, {
                        ...feature.properties,
                        latitude: Number(feature.geometry.coordinates[1]),
                        longitude: Number(feature.geometry.coordinates[0]),
                        network: networkId,
                        station_type: 'surface'
                    });
                }
            });
            
            return features;
        } catch (error) {
            console.error(`Error loading surface stations for network ${networkId}:`, error);
            return [];
        }
    },

    async createStation(networkId, stationData) {
        try {
            const result = await API.createSurfaceStation(networkId, stationData);
            const station = result.data || result;
            
            // Add to state
            State.allSurfaceStations.set(station.id, {
                ...station,
                network: networkId,
                station_type: 'surface'
            });
            
            // Invalidate cache and trigger layer refresh
            this.invalidateCache();
            await Layers.refreshSurfaceStationsAfterChange(networkId);
            
            return station;
        } catch (error) {
            console.error('Error creating surface station:', error);
            throw error;
        }
    },

    async updateStation(stationId, updateData) {
        try {
            const result = await API.updateStation(stationId, updateData);
            const updatedStation = result.data || result;
            
            // Update State
            const existing = State.allSurfaceStations.get(stationId);
            if (existing) {
                State.allSurfaceStations.set(stationId, { ...existing, ...updatedStation });
            }
            
            // Update Map Layer if coordinates changed
            if (existing && updateData.latitude !== undefined && updateData.longitude !== undefined) {
                const newCoords = [updateData.longitude, updateData.latitude];
                const sourceId = `surface-stations-${existing.network}`;
                Layers.updateSurfaceStationPosition(sourceId, stationId, newCoords);
            }
            
            return updatedStation;
        } catch (error) {
            console.error('Error updating surface station:', error);
            throw error;
        }
    },

    async deleteStation(stationId) {
        try {
            const station = State.allSurfaceStations.get(stationId);
            const networkId = station ? station.network : null;
            
            await API.deleteStation(stationId);
            
            // Remove from State
            State.allSurfaceStations.delete(stationId);
            
            // Invalidate cache so refresh fetches fresh data without deleted station
            this.invalidateCache();
            
            // Refresh Layer
            if (networkId) {
                await Layers.refreshSurfaceStationsAfterChange(networkId);
            }
            
            return true;
        } catch (error) {
            console.error('Error deleting surface station:', error);
            throw error;
        }
    },

    // Note: Surface stations are NOT draggable, so no moveStation method
};

