import type { ViewerMap } from '../../../../../../../ts-types/domain/map-state.ts';

/**
 * Remove map layers first, then their source to avoid dependent-layer issues.
 */
export function removeLayersAndSource(map: ViewerMap, layerIds: string[], sourceId: string) {
    layerIds.forEach((layerId) => {
        if (map.getLayer(layerId)) {
            map.removeLayer(layerId);
        }
    });

    if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
    }
}
