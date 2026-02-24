import { API } from '../api.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';
import { Utils } from '../utils.js';
import { Config } from '../config.js';

// Cache for all stations GeoJSON
let allStationsGeoJson = null;
let allStationsFetchPromise = null;

export const StationManager = {
    // Invalidate cache
    invalidateCache() {
        allStationsGeoJson = null;
        allStationsFetchPromise = null;
    },

    // Ensure all stations are loaded (single API call)
    async ensureAllStationsLoaded() {
        if (allStationsGeoJson && allStationsGeoJson.type === 'FeatureCollection' && Array.isArray(allStationsGeoJson.features)) {
            return;
        }

        if (allStationsFetchPromise) {
            await allStationsFetchPromise;
            return;
        }

        console.log('🔄 Fetching all stations (GeoJSON) via single API call...');
        allStationsFetchPromise = API.getAllStationsGeoJSON()
            .then(response => {
                if (
                    !response ||
                    response.type !== 'FeatureCollection' ||
                    !Array.isArray(response.features)
                ) {
                    throw new Error('Invalid all-stations GeoJSON payload');
                }
                allStationsGeoJson = response;
                console.log(`✅ Cached ${allStationsGeoJson.features.length} stations from all-stations GeoJSON`);
            })
            .catch(err => {
                console.error('❌ Failed to load all stations GeoJSON:', err);
                allStationsGeoJson = { type: 'FeatureCollection', features: [] };
            })
            .finally(() => {
                allStationsFetchPromise = null;
            });

        await allStationsFetchPromise;
    },

    async loadStationsForProject(projectId) {
        try {
            // Skip loading stations when project read access is not granted.
            if (!Config.hasProjectAccess(projectId, 'read')) {
                console.log('⏭️ Skipping station load without project read access', projectId);
                return [];
            }

            // Ensure all stations are cached
            await this.ensureAllStationsLoaded();

            // Filter stations for this project
            const allFc = allStationsGeoJson || { type: 'FeatureCollection', features: [] };

            const features = allFc.features.filter(f => String(f?.properties?.project) === String(projectId));

            console.log(`📍 Loaded ${features.length} stations for project ${projectId}`);

            // Update State
            features.forEach(feature => {
                const featureId = feature.id;
                if (feature.properties && featureId && feature.geometry) {
                    State.allStations.set(featureId, {
                        ...feature.properties,
                        id: featureId,
                        latitude: Number(feature.geometry.coordinates[1]),
                        longitude: Number(feature.geometry.coordinates[0]),
                        project: projectId
                    });
                }
            });

            return features;
        } catch (error) {
            console.error(`Error loading stations for project ${projectId}:`, error);
            return [];
        }
    },

    async createStation(projectId, stationData) {
        try {
            const result = await API.createStation(projectId, stationData);
            const station = result.data;

            // Add to state
            State.allStations.set(station.id, {
                ...station,
                project: projectId
            });

            // Invalidate cache and trigger layer refresh
            this.invalidateCache();
            await Layers.refreshStationsAfterChange(projectId);

            return station;
        } catch (error) {
            console.error('Error creating station:', error);
            throw error;
        }
    },

    async updateStation(stationId, updateData) {
        try {
            const result = await API.updateStation(stationId, updateData);
            const updatedStation = result.data;

            // Update State
            const existing = State.allStations.get(stationId);
            if (existing) {
                State.allStations.set(stationId, { ...existing, ...updatedStation });
            }

            // Update Map Layer
            if (existing) {
                // If coordinates changed
                if (updateData.latitude !== undefined && updateData.longitude !== undefined) {
                    const newCoords = [updateData.longitude, updateData.latitude];
                    const sourceId = `stations-${existing.project}`;
                    Layers.updateStationPosition(sourceId, stationId, newCoords);
                }

                // If color/tag changed (not handled by updateStationPosition but helpful)
                // We usually just refresh the layer or update properties
            }

            return updatedStation;
        } catch (error) {
            console.error('Error updating station:', error);
            throw error;
        }
    },

    async deleteStation(stationId) {
        try {
            const station = State.allStations.get(stationId);
            const projectId = station ? station.project : null;

            await API.deleteStation(stationId);

            // Remove from State
            State.allStations.delete(stationId);

            // Invalidate cache so refresh fetches fresh data without deleted station
            this.invalidateCache();

            // Refresh Layer
            if (projectId) {
                await Layers.refreshStationsAfterChange(projectId);
            }

            return true;
        } catch (error) {
            console.error('Error deleting station:', error);
            throw error;
        }
    },

    async moveStation(stationId, newCoords) {
        try {
            await this.updateStation(stationId, {
                latitude: newCoords[1],
                longitude: newCoords[0]
            });
            return true;
        } catch (error) {
            // Revert visual position if failed
            const station = State.allStations.get(stationId);
            if (station) {
                const sourceId = `stations-${station.project}`;
                Layers.updateStationPosition(sourceId, stationId, [station.longitude, station.latitude]);
            }
            throw error;
        }
    }
};





