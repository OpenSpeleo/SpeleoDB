import type { StationWrite } from '../../../../../../ts-types/domain/station-records.ts';
import type { StationFeatureCollection } from '../../../../../../ts-types/domain/map-entities.ts';
import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import { API } from '../api.ts';
import { State } from '../state.ts';
import { Layers } from '../map/layers.ts';
import { Config } from '../config.ts';

// Cache for all surface stations GeoJSON
let allSurfaceStationsGeoJson: StationFeatureCollection | null = null;
let allSurfaceStationsFetchPromise: Promise<void> | null = null;

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
                if (!response ||
                    response.type !== 'FeatureCollection' ||
                    !Array.isArray(response.features)
                ) {
                    throw new Error('Invalid all-surface-stations GeoJSON payload');
                }
                allSurfaceStationsGeoJson = response;
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

    async loadStationsForNetwork(networkId: EntityId) {
        try {
            // Ensure all surface stations are cached
            await this.ensureAllSurfaceStationsLoaded();

            // Filter stations for this network
            const allFc = allSurfaceStationsGeoJson || { type: 'FeatureCollection', features: [] };

            const features = allFc.features.filter(f => String(f?.properties?.network) === String(networkId));

            console.log(`📍 Loaded ${features.length} surface stations for network ${networkId}`);

            // Update State
            features.forEach(feature => {
                const featureId = feature.id;
                if (feature.properties && featureId && feature.geometry) {
                    State.allSurfaceStations.set(
                        featureId, {
                        ...feature.properties,
                        id: featureId,
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

    async createStation(networkId: EntityId, stationData: StationWrite) {
        try {
            const station = await API.createSurfaceStation(networkId, stationData);

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

    async updateStation(stationId: EntityId, updateData: StationWrite) {
        try {
            const updatedStation = await API.updateStation(stationId, updateData);

            // Update State
            const existing = State.allSurfaceStations.get(stationId);
            if (existing) {
                State.allSurfaceStations.set(stationId, { ...existing, ...updatedStation });
            }

            // Update Map Layer if coordinates changed
            if (existing && updateData.latitude !== undefined && updateData.longitude !== undefined) {
                // Existing callers supply numeric coordinates to the map layer boundary.
                    const newCoords = [updateData.longitude, updateData.latitude] as [number, number];
                const sourceId = `surface-stations-${existing.network}`;
                Layers.updateSurfaceStationPosition(sourceId, stationId, newCoords);
            }

            return updatedStation;
        } catch (error) {
            console.error('Error updating surface station:', error);
            throw error;
        }
    },

    async deleteStation(stationId: EntityId) {
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
