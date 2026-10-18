import { createLandmarkIconRegistry } from '@speleodb/map-viewer/landmark-icons';
import { createLandmarkLayers, landmarkColorExpression, landmarkHaloExpression } from '@speleodb/map-viewer';
import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerUpdateResult } from '@speleodb/map-viewer/update-scheduler';
import { State } from '../../state.ts';
import { DEFAULTS } from '../../defaults.ts';
import type { MapPointCollection, RendererLayer, LandmarkPointProperties } from '../../../../../../../ts-types/domain/renderer.ts';
import type { DisplayCategory } from '../../../../../../../ts-types/domain/map-display.ts';
import { removeLayersAndSource, addOwnedSource, getSourceData } from './source_lifecycle.ts';
let iconRegistry: ReturnType<typeof createLandmarkIconRegistry> | null = null;
let iconMap: typeof State.map = null;
let renderIcons: (() => void) | null = null;

export function disposeLandmarkIcons() {
    iconRegistry?.dispose();
    iconRegistry = null;
    iconMap = null;
    renderIcons = null;
}

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
        disposeLandmarkIcons();
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
    // Landmark symbol layer (chosen icon visible from far zoom)
    // Landmark labels (visible from moderate zoom)
    // Default triangle and custom icons are supplied by the shared layer factory.
    if (iconMap && iconMap !== map) disposeLandmarkIcons();
    const render = (refresh = true) => {
        if (State.map !== map || (refresh && !map.getSource(sourceId))) return;
        const layers = createLandmarkLayers({
            sourceId, markerId: 'landmarks-layer', labelId: 'landmarks-labels',
            markerMinZoom: ZOOM_LEVELS.LANDMARK_SYMBOL, labelMinZoom: ZOOM_LEVELS.LANDMARK_LABEL,
            markerSize: ['interpolate', ['linear'], ['zoom'], 6, 10, 10, 14, 14, 20, 18, 28],
            labelSize: ['interpolate', ['linear'], ['zoom'], 10, 10, 14, 12, 18, 14],
            color: landmarkColorExpression(), haloColor: landmarkHaloExpression(),
            visible: State.landmarksVisible,
            availableIconIds: iconRegistry?.getAvailableImageIds() || [],
        });
        if (refresh) {
            const marker = layers.find(layer => layer.id === 'landmarks-layer');
            if (marker?.type === 'symbol' && map.getLayer(marker.id)) {
                const layout = marker.layout as RendererLayer['layout'];
                // Image decoding must install the complete shared symbol policy,
                // while preserving the layer's current visibility, filters and order.
                for (const property of ['icon-image', 'icon-size', 'icon-allow-overlap',
                    'icon-ignore-placement', 'icon-optional', 'text-optional', 'text-field'] as const) {
                    map.setLayoutProperty(marker.id, property, layout?.[property]);
                }
            }
        } else {
            layers.forEach(layer => map.addLayer(layer as RendererLayer));
        }
    };
    renderIcons = render;
    if (!iconRegistry) {
        iconMap = map;
        iconRegistry = createLandmarkIconRegistry(map, () => renderIcons?.());
    }
    // Install the fallback glyph synchronously; all five SVG icons then replace it.
    render(false);
    void iconRegistry?.prepare(data).catch(error => console.error('Unable to load landmark icons:', error));
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
