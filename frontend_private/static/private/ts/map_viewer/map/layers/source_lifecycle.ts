import type { RendererGeoJSON, RendererGeoJSONSource, RendererSourceOptions } from '../../../../../../../ts-types/domain/renderer.ts';
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

// Own the mutable marker data rather than reading undocumented engine internals.
// Weak source keys release removed/replaced sources without retaining their map.
const sourceData = new WeakMap<object, RendererGeoJSON>();

export function rememberSourceData(source: object, data: RendererGeoJSON) {
    sourceData.set(source, data);
}

export function getSourceData<Data extends RendererGeoJSON>(source: object | undefined): Data | undefined {
    return source ? sourceData.get(source) as Data | undefined : undefined;
}

export function addOwnedSource(map: ViewerMap, sourceId: string, options: RendererSourceOptions) {
    map.addSource(sourceId, options);
    const source = map.getSource(sourceId);
    if (source) rememberSourceData(source, options.data);
}

export function setOwnedSourceData(source: RendererGeoJSONSource, data: RendererGeoJSON) {
    rememberSourceData(source, data);
    source.setData(data);
}
