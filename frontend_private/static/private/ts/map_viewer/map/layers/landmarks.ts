import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerUpdateResult } from '../../../../../../../ts-types/domain/viewer-updates.ts';
import { State } from '../../state.ts';
import { DEFAULTS } from '../../defaults.ts';
import type { MapPointCollection, MapboxValue, LandmarkPointProperties } from '../../../../../../../ts-types/domain/mapbox.ts';
import type { DisplayCategory } from '../../../../../../../ts-types/domain/map-display.ts';
import { Colors } from '../colors.ts';
import { removeLayersAndSource } from './source_lifecycle.ts';
const ZOOM_LEVELS = DEFAULTS.ZOOM_LEVELS;
interface LandmarkLayerOwner {
    setCategoryVisibility(category: DisplayCategory, visible: boolean): Promise<ViewerUpdateResult> | undefined;
}

export function addLandmarkLayer(data: MapPointCollection<LandmarkPointProperties>) {
    const map = State.map;
    if (!map) return;

    const sourceId = 'landmarks-source';

    console.log(`📍 Adding ${data.features?.length || 0} Landmarks to map`);

    // Remove existing layer and source if they exist (to refresh)
    removeLayersAndSource(map, ['landmarks-labels', 'landmarks-layer'], sourceId);

    if (!data.features || data.features.length === 0) {
        console.log('📍 No Landmarks to display');
        return;
    }

    // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
    data.features.forEach(feature => {
        if (feature.id && !feature.properties.id) {
            feature.properties.id = feature.id;
        }
    });

    map.addSource(sourceId, {
        type: 'geojson',
        data: data,
        promoteId: 'id'
    });

    // Determine initial visibility based on state
    const visibility = State.landmarksVisible ? 'visible' : 'none';
    const landmarkColorExpression: MapboxValue = ['coalesce', ['get', 'collection_color'], Colors.FALLBACK_COLOR];
    const landmarkHaloColorExpression: MapboxValue = [
        'case',
        ['==', ['get', 'collection_color'], '#ffffff'],
        '#0f172a',
        '#ffffff'
    ];

    // Landmark symbol layer (triangle marker visible from far zoom)
    map.addLayer({
        id: 'landmarks-layer',
        type: 'symbol',
        source: sourceId,
        minzoom: ZOOM_LEVELS.LANDMARK_SYMBOL,
        layout: {
            'text-field': '▼',  // Triangle pointing down
            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
            'text-size': ['interpolate', ['linear'], ['zoom'], 6, 10, 10, 14, 14, 20, 18, 28],
            'text-allow-overlap': true,
            'text-ignore-placement': true,
            'visibility': visibility
        },
        paint: {
            'text-color': landmarkColorExpression,
            'text-halo-color': landmarkHaloColorExpression,
            'text-halo-width': 2,
            'text-halo-blur': 0.5
        }
    });

    // Landmark labels (visible from moderate zoom)
    map.addLayer({
        id: 'landmarks-labels',
        type: 'symbol',
        source: sourceId,
        minzoom: ZOOM_LEVELS.LANDMARK_LABEL,
        layout: {
            'text-field': ['get', 'name'],
            'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
            'text-offset': [0, 1.5],
            'text-size': ['interpolate', ['linear'], ['zoom'], 10, 10, 14, 12, 18, 14],
            'text-anchor': 'top',
            'text-allow-overlap': false,
            'visibility': visibility
        },
        paint: {
            'text-color': landmarkColorExpression,
            'text-halo-color': landmarkHaloColorExpression,
            'text-halo-width': 1.5
        }
    });
}

export function toggleLandmarkVisibility(this: Pick<LandmarkLayerOwner, 'setCategoryVisibility'>, isVisible: boolean) {
    void this.setCategoryVisibility('landmarks', isVisible);
}

export function revertLandmarkPosition(landmarkId: EntityId, originalCoords: [number, number]) {
    const map = State.map;
    if (!map) return;

    const source = map.getSource('landmarks-source');
    if (source && source._data) {
        const data = source._data as MapPointCollection;
        const feature = data.features.find(f => f.id === landmarkId);
        if (feature) {
            feature.geometry.coordinates = originalCoords;
            source.setData(data);

            // Reset internal state if needed
            const landmark = State.allLandmarks.get(landmarkId);
            if (landmark) {
                landmark.latitude = originalCoords[1];
                landmark.longitude = originalCoords[0];
            }
        }
    }
}
