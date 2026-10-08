import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';

import { State } from '../../state.ts';
import { DEFAULTS } from '../../defaults.ts';
import type { MapPointCollection, PointProperties } from '../../../../../../../ts-types/domain/mapbox.ts';
import { removeLayersAndSource } from './source_lifecycle.ts';
const ZOOM_LEVELS = DEFAULTS.ZOOM_LEVELS;
interface StationLayerOwner {
    applyProjectLayerVisibility(id: EntityId): void;
    applyNetworkLayerVisibility(id: EntityId): void;
}

export function addSubSurfaceStationLayer(this: Pick<StationLayerOwner, 'applyProjectLayerVisibility'>, projectId: EntityId, data: MapPointCollection) {
    const map = State.map;
    if (!map) return;

    const sourceId = `stations-source-${projectId}`;
    const circleLayerId = `stations-${projectId}-circles`;
    const biologyLayerId = `stations-${projectId}-biology-icons`;
    const boneLayerId = `stations-${projectId}-bone-icons`;
    const artifactLayerId = `stations-${projectId}-artifact-icons`;
    const geologyLayerId = `stations-${projectId}-geology-icons`;
    const labelLayerId = `stations-${projectId}-labels`;

    console.log(`📍 Adding ${data.features?.length || 0} stations to map for project ${projectId}`);

    // Remove existing layers and source if they exist (for refresh)
    removeLayersAndSource(
        map,
        [labelLayerId, geologyLayerId, artifactLayerId, boneLayerId, biologyLayerId, circleLayerId],
        sourceId
    );

    if (!data.features || data.features.length === 0) {
        console.log(`📍 No stations to display for project ${projectId}`);
        return;
    }

    // Ensure id and color properties are set on each feature
    // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
    data.features.forEach(feature => {
        if (feature.id && !feature.properties.id) {
            feature.properties.id = feature.id;
        }
        if (!feature.properties.color) {
            // Use tag color if available, otherwise use default orange
            const tag = feature.properties.tag;
            feature.properties.color = (tag && tag.color) ? tag.color : DEFAULTS.COLORS.DEFAULT_STATION;
        }
    });

    map.addSource(sourceId, {
        type: 'geojson',
        data: data,
        promoteId: 'id'
    });

    // Add Circle Layer for Sensor stations (type is null, undefined, or 'sensor')
    // Use data-driven color from feature properties
    map.addLayer({
        id: circleLayerId,
        type: 'circle',
        source: sourceId,
        filter: ['any',
            ['!', ['has', 'type']],
            ['==', ['get', 'type'], null],
            ['==', ['get', 'type'], 'sensor']
        ],
        minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
        paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 5, 18, 8],
            'circle-color': ['coalesce', ['get', 'color'], DEFAULTS.COLORS.DEFAULT_STATION],
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
            'circle-opacity': 1
        }
    });

    // Add Biology Station Icon Layer (for type === 'biology')
    if (map.hasImage('biology-station-icon')) {
        map.addLayer({
            id: biologyLayerId,
            type: 'symbol',
            source: sourceId,
            filter: ['==', ['get', 'type'], 'biology'],
            minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
            layout: {
                'icon-image': 'biology-station-icon',
                'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                'icon-allow-overlap': true,
                'icon-ignore-placement': true
            },
            paint: {
                'icon-opacity': 1
            }
        });
    }

    // Add Bone Station Icon Layer (for type === 'bone')
    if (map.hasImage('bone-station-icon')) {
        map.addLayer({
            id: boneLayerId,
            type: 'symbol',
            source: sourceId,
            filter: ['==', ['get', 'type'], 'bone'],
            minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
            layout: {
                'icon-image': 'bone-station-icon',
                'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                'icon-allow-overlap': true,
                'icon-ignore-placement': true
            },
            paint: {
                'icon-opacity': 1
            }
        });
    }

    // Add Artifact Station Icon Layer (for type === 'artifact')
    if (map.hasImage('artifact-station-icon')) {
        map.addLayer({
            id: artifactLayerId,
            type: 'symbol',
            source: sourceId,
            filter: ['==', ['get', 'type'], 'artifact'],
            minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
            layout: {
                'icon-image': 'artifact-station-icon',
                'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                'icon-allow-overlap': true,
                'icon-ignore-placement': true
            },
            paint: {
                'icon-opacity': 1
            }
        });
    }

    // Add Geology Station Icon Layer (for type === 'geology')
    if (map.hasImage('geology-station-icon')) {
        map.addLayer({
            id: geologyLayerId,
            type: 'symbol',
            source: sourceId,
            filter: ['==', ['get', 'type'], 'geology'],
            minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
            layout: {
                'icon-image': 'geology-station-icon',
                'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                'icon-allow-overlap': true,
                'icon-ignore-placement': true
            },
            paint: {
                'icon-opacity': 1
            }
        });
    }

    // Add Label Layer for all station types
    map.addLayer({
        id: labelLayerId,
        type: 'symbol',
        source: sourceId,
        minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_LABEL,
        layout: {
            'text-field': ['get', 'name'],
            'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
            'text-offset': [0, 1.2],
            'text-size': 12,
            'text-anchor': 'top',
            'text-allow-overlap': false,
            'text-ignore-placement': false
        },
        paint: {
            'text-color': '#222',
            'text-halo-color': '#ffffff',
            'text-halo-width': 2
        }
    });

    // Track layers
    if (!State.allProjectLayers.has(String(projectId))) {
        State.allProjectLayers.set(String(projectId), []);
    }
    const projectLayers = State.allProjectLayers.get(String(projectId))!;
    const newLayers = [circleLayerId, biologyLayerId, boneLayerId, artifactLayerId, geologyLayerId, labelLayerId];
    newLayers.forEach(layerId => {
        if (!projectLayers.includes(layerId)) {
            projectLayers.push(layerId);
        }
    });

    // Respect initial visibility through centralized project-layer logic.
    this.applyProjectLayerVisibility(projectId);
}

// Surface Station Layer - uses diamond (◆) symbol instead of circle
export function addSurfaceStationLayer(this: Pick<StationLayerOwner, 'applyNetworkLayerVisibility'>, networkId: EntityId, data: MapPointCollection) {
    const map = State.map;
    if (!map) return;

    const sourceId = `surface-stations-source-${networkId}`;
    const symbolLayerId = `surface-stations-${networkId}`;
    const labelLayerId = `surface-stations-${networkId}-labels`;

    console.log(`📍 Adding ${data.features?.length || 0} surface stations to map for network ${networkId}`);

    // Remove existing layer and source if they exist (for refresh)
    removeLayersAndSource(map, [labelLayerId, symbolLayerId], sourceId);

    if (!data.features || data.features.length === 0) {
        console.log(`📍 No surface stations to display for network ${networkId}`);
        return;
    }

    // Ensure id and color properties are set on each feature
    // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
    data.features.forEach(feature => {
        if (feature.id && !feature.properties.id) {
            feature.properties.id = feature.id;
        }
        if (!feature.properties.color) {
            // Use tag color if available, otherwise use default orange
            const tag = feature.properties.tag;
            feature.properties.color = (tag && tag.color) ? tag.color : DEFAULTS.COLORS.DEFAULT_STATION;
        }
    });

    map.addSource(sourceId, {
        type: 'geojson',
        data: data,
        promoteId: 'id'
    });

    // Add Diamond Symbol Layer (◆)
    // Use text-field with unicode diamond instead of circle
    map.addLayer({
        id: symbolLayerId,
        type: 'symbol',
        source: sourceId,
        minzoom: ZOOM_LEVELS.SURFACE_STATION_SYMBOL,
        layout: {
            'text-field': '◆',  // Diamond shape
            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
            'text-size': ['interpolate', ['linear'], ['zoom'], 14, 16, 18, 24],
            'text-allow-overlap': true,
            'text-ignore-placement': true
        },
        paint: {
            'text-color': ['coalesce', ['get', 'color'], DEFAULTS.COLORS.DEFAULT_STATION],
            'text-halo-color': '#ffffff',
            'text-halo-width': 2,
            'text-halo-blur': 0.5
        }
    });

    // Add Label Layer
    map.addLayer({
        id: labelLayerId,
        type: 'symbol',
        source: sourceId,
        minzoom: ZOOM_LEVELS.SURFACE_STATION_LABEL,
        layout: {
            'text-field': ['get', 'name'],
            'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
            'text-offset': [0, 1.2],
            'text-size': 12,
            'text-anchor': 'top',
            'text-allow-overlap': false,
            'text-ignore-placement': false
        },
        paint: {
            'text-color': '#222',
            'text-halo-color': '#ffffff',
            'text-halo-width': 2
        }
    });

    // Track layers
    if (!State.allNetworkLayers.has(String(networkId))) {
        State.allNetworkLayers.set(String(networkId), []);
    }
    const networkLayers = State.allNetworkLayers.get(String(networkId))!;
    if (!networkLayers.includes(symbolLayerId)) networkLayers.push(symbolLayerId);
    if (!networkLayers.includes(labelLayerId)) networkLayers.push(labelLayerId);

    // Respect initial visibility
    this.applyNetworkLayerVisibility(networkId);
}

export function updateSurfaceStationPosition(networkId: EntityId, stationId: EntityId, newCoords: [number, number]) {
    const map = State.map;
    if (!map) return;

    const sourceId = `surface-stations-source-${networkId}`;
    const source = map.getSource(sourceId);
    if (source && source._data) {
        const data = source._data as MapPointCollection;
        const feature = data.features.find(f => f.id === stationId);
        if (feature) {
            feature.geometry.coordinates = newCoords;
            source.setData(data);

            // Update in our local lookup as well
            const station = State.allSurfaceStations.get(stationId);
            if (station) {
                station.latitude = newCoords[1];
                station.longitude = newCoords[0];
            }
        }
    }
}

export function updateSurfaceStationColor(networkId: EntityId, stationId: EntityId, color: string) {
    const map = State.map;
    if (!map) return;

    const sourceId = `surface-stations-source-${networkId}`;
    const source = map.getSource(sourceId);
    if (source && source._data) {
        const data = source._data as MapPointCollection;
        const feature = data.features.find(f => f.id === stationId);
        if (feature) {
            feature.properties.color = color;
            source.setData(data);
        }
    }
}

export function updateSurfaceStationProperties(networkId: EntityId, stationId: EntityId, properties: Partial<PointProperties>) {
    const map = State.map;
    if (!map) return;

    const sourceId = `surface-stations-source-${networkId}`;
    const source = map.getSource(sourceId);
    if (source && source._data) {
        const data = source._data as MapPointCollection;
        const feature = data.features.find(f => f.id === stationId);
        if (feature) {
            // Update all provided properties
            Object.assign(feature.properties, properties);
            source.setData(data);
        }
    }
}

export async function refreshSurfaceStationsAfterChange(networkId: EntityId) {
    window.dispatchEvent(new CustomEvent('speleo:refresh-surface-stations', { detail: { networkId } }));
}

export function updateStationPosition(projectId: EntityId, stationId: EntityId, newCoords: [number, number]) {
    const map = State.map;
    if (!map) return;

    const sourceId = `stations-source-${projectId}`;
    const source = map.getSource(sourceId);
    if (source && source._data) {
        const data = source._data as MapPointCollection;
        const feature = data.features.find(f => f.id === stationId);
        if (feature) {
            feature.geometry.coordinates = newCoords;
            source.setData(data);

            // Update in our local lookup as well
            const station = State.allStations.get(stationId);
            if (station) {
                station.latitude = newCoords[1];
                station.longitude = newCoords[0];
            }
        }
    }
}

export function updateStationColor(projectId: EntityId, stationId: EntityId, color: string) {
    const map = State.map;
    if (!map) return;

    const sourceId = `stations-source-${projectId}`;
    const source = map.getSource(sourceId);
    if (source && source._data) {
        const data = source._data as MapPointCollection;
        const feature = data.features.find(f => f.id === stationId);
        if (feature) {
            feature.properties.color = color;
            source.setData(data);
        }
    }
}

// Update station properties (name, description, etc.) on the map
export function updateStationProperties(projectId: EntityId, stationId: EntityId, properties: Partial<PointProperties>) {
    const map = State.map;
    if (!map) return;

    const sourceId = `stations-source-${projectId}`;
    const source = map.getSource(sourceId);
    if (source && source._data) {
        const data = source._data as MapPointCollection;
        const feature = data.features.find(f => f.id === stationId);
        if (feature) {
            // Update all provided properties
            Object.assign(feature.properties, properties);
            source.setData(data);
        }
    }
}

export async function refreshStationsAfterChange(projectId: EntityId) {
    // This needs to call back to main/manager to fetch data
    // We will trigger a custom event 'speleo:refresh-stations'
    window.dispatchEvent(new CustomEvent('speleo:refresh-stations', { detail: { projectId } }));
}
