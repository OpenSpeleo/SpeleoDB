import { createLandmarkLayers } from '@speleodb/map-viewer';
import type { ExpressionSpecification } from 'maplibre-gl';
import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerUpdateResult } from '../../../../../../../ts-types/domain/viewer-updates.ts';
import { State } from '../../state.ts';
import { DEFAULTS } from '../../defaults.ts';
import type { MapPointCollection, RendererLayer, LandmarkPointProperties } from '../../../../../../../ts-types/domain/renderer.ts';
import type { DisplayCategory } from '../../../../../../../ts-types/domain/map-display.ts';
import { Colors } from '../colors.ts';
import { removeLayersAndSource, addOwnedSource, getSourceData } from './source_lifecycle.ts';
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

    // MapLibre requires promoteId for string IDs - copy feature.id to properties.id
    data.features.forEach(feature => {
        if (feature.id && !feature.properties.id) {
            feature.properties.id = feature.id;
        }
    });

    addOwnedSource(map, sourceId, {
        type: 'geojson',
        data: data,
        promoteId: 'id'
    });

    // Determine initial visibility based on state
    const landmarkColorExpression: ExpressionSpecification = ['coalesce', ['get', 'collection_color'], Colors.FALLBACK_COLOR];
    const landmarkHaloColorExpression: ExpressionSpecification = [
        'case',
        ['==', ['get', 'collection_color'], '#ffffff'],
        '#0f172a',
        '#ffffff'
    ];

    // Landmark symbol layer (triangle marker visible from far zoom)
    // Landmark labels (visible from moderate zoom)
    // Triangle pointing down is supplied by the common landmark layer factory.
    const layers = createLandmarkLayers({
        sourceId, markerId: 'landmarks-layer', labelId: 'landmarks-labels',
        markerMinZoom: ZOOM_LEVELS.LANDMARK_SYMBOL, labelMinZoom: ZOOM_LEVELS.LANDMARK_LABEL,
        markerSize: ['interpolate', ['linear'], ['zoom'], 6, 10, 10, 14, 14, 20, 18, 28],
        labelSize: ['interpolate', ['linear'], ['zoom'], 10, 10, 14, 12, 18, 14],
        color: landmarkColorExpression, haloColor: landmarkHaloColorExpression,
        visible: State.landmarksVisible,
    });
    layers.forEach(layer => map.addLayer(layer as RendererLayer));
}

export function toggleLandmarkVisibility(this: Pick<LandmarkLayerOwner, 'setCategoryVisibility'>, isVisible: boolean) {
    void this.setCategoryVisibility('landmarks', isVisible);
}

export function revertLandmarkPosition(landmarkId: EntityId, originalCoords: [number, number]) {
    const map = State.map;
    if (!map) return;

    const source = map.getSource('landmarks-source');
    const data = getSourceData<MapPointCollection>(source);
    if (source && data) {
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
