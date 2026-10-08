import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerGeoJSON, DisplayGeometryType } from '../../../../../../../ts-types/domain/map-geometry.ts';
import type { OverlayInstallOptions, PreparedGISOverlay } from '../../../../../../../ts-types/domain/map-layers.ts';
import type { ViewerUpdateResult } from '../../../../../../../ts-types/domain/viewer-updates.ts';
import { Config, DEFAULTS } from '../../config.ts';
import { State } from '../../state.ts';
import { API } from '../../api.ts';
import { ViewerUpdates } from '../../viewer_updates.ts';

import { readViewerGeoJSON } from '../read_geojson.ts';
import { prepareGeoJSONBounds, prepareGISLayerGeoJSONAsync } from '../preparation.ts';
import { addVectorOverlay, VECTOR_OVERLAY_GEOMETRY_TYPES } from '../vector_overlay.ts';
import { gisLayerGeometryFilter } from '../gis_layer_geometry.ts';
import { removeLayersAndSource } from './source_lifecycle.ts';
import { toggleLazyOverlay } from './lazy_overlay.ts';

interface GISLayerOwner {
    addGISLayer(id: EntityId, data: ViewerGeoJSON, options?: OverlayInstallOptions<PreparedGISOverlay>): Promise<void>;
    showGISLayerLayers(id: EntityId, visible: boolean): void;
    setGISLayerLoading(id: EntityId, loading: boolean): void;
    closeGISFeaturePopups(): void;
    reorderLayers(): Promise<ViewerUpdateResult> | undefined;
}

// GIS Layers follow the same session-only lazy loading pattern as GPS Tracks.
export function isGISLayerVisible(layerId: EntityId) {
    return State.gisLayerStates.get(String(layerId)) === true;
}

export function isGISLayerLoading(layerId: EntityId) {
    return State.gisLayerLoadingStates.get(String(layerId)) === true;
}

export function getGISLayerGeometryTypes(layerId: EntityId) {
    return [...(State.gisLayerGeometryTypeStates.get(String(layerId))?.keys() || [])];
}

export function isGISLayerGeometryTypeVisible(layerId: EntityId, geometryType: DisplayGeometryType) {
    return State.gisLayerGeometryTypeStates.get(String(layerId))?.get(geometryType) !== false;
}

export function setGISLayerGeometryTypeVisibility(this: Pick<GISLayerOwner, 'closeGISFeaturePopups'>, layerId: EntityId, geometryType: DisplayGeometryType, isVisible: boolean) {
    const id = String(layerId);
    const states = State.gisLayerGeometryTypeStates.get(id);
    if (!states?.has(geometryType)) return;
    states.set(geometryType, isVisible);
    if (!isVisible) this.closeGISFeaturePopups();
    const generation = State.layerGeneration;
    return ViewerUpdates.schedule(`gis-types:${id}`, () => {
        if (generation !== State.layerGeneration) return;
        const enabledTypes = [...states].filter(([, visible]) => visible).map(([type]) => type);
        const map = State.map;
        if (!map) return;
        const layerIds = State.allGISLayerLayers.get(id) || [];
        layerIds.forEach((renderLayerId, index) => {
            if (map.getLayer(renderLayerId)) {
                map.setFilter(renderLayerId, gisLayerGeometryFilter(VECTOR_OVERLAY_GEOMETRY_TYPES[index]!, enabledTypes));
            }
        });
    });
}

export function setGISLayerLoading(layerId: EntityId, isLoading: boolean) {
    const id = String(layerId);
    State.gisLayerLoadingStates.set(id, isLoading);
    window.dispatchEvent(new CustomEvent('speleo:gis-layer-loading-changed', {
        detail: { layerId: id, isLoading }
    }));
}

export async function toggleGISLayerVisibility(this: Pick<GISLayerOwner, 'addGISLayer' | 'showGISLayerLayers' | 'setGISLayerLoading'>, layerId: EntityId, isVisible: boolean) {
    const id = String(layerId);
    return toggleLazyOverlay({
        metadata: () => Config.getGISLayerById?.(id),
        kind: 'gis-layer', id, visible: isVisible,
        cache: State.gisLayerCache, states: State.gisLayerStates, layers: State.allGISLayerLayers,
        details: async signal => {
            const record = await API.getGISLayerDetails(id, { signal });
            if (!record?.file) throw new Error('The GIS Layer has no display file.');
            const response = await fetch(record.file, { signal });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            // Existing display-file contract is asserted after transport, without new validation.
            return readViewerGeoJSON(response, { isCurrent: () => !signal.aborted }) as unknown as Promise<ViewerGeoJSON>;
        },
        prepare: async (data, isCurrent) => ({
            boundsCoordinates: await prepareGeoJSONBounds(data, { isCurrent }),
            ...await prepareGISLayerGeoJSONAsync(data, { isCurrent }),
        }),
        install: (data, isCurrent, prepared) => this.addGISLayer(id, data, { isCurrent, prepared }),
        show: visible => this.showGISLayerLayers(id, visible),
        loading: value => this.setGISLayerLoading(id, value),
    });
}

export function showGISLayerLayers(layerId: EntityId, isVisible: boolean) {
    const map = State.map;
    if (!map) return;
    const layerIds = State.allGISLayerLayers.get(String(layerId)) || [];
    layerIds.forEach(id => {
        if (map.getLayer(id)) {
            map.setLayoutProperty(id, 'visibility', isVisible ? 'visible' : 'none');
        }
    });
}

export async function addGISLayer(this: Pick<GISLayerOwner, 'reorderLayers'>, layerId: EntityId, geojsonData: ViewerGeoJSON, { isCurrent = () => true, prepared }: OverlayInstallOptions<PreparedGISOverlay> = {}) {
    const map = State.map;
    if (!map) return;
    const boundsCoordinates = prepared ? prepared.boundsCoordinates : await prepareGeoJSONBounds(geojsonData, { isCurrent });
    const { data, geometryTypes } = prepared || await prepareGISLayerGeoJSONAsync(geojsonData, { isCurrent });
    if (!isCurrent() || State.map !== map) return;

    const id = String(layerId);
    const sourceId = `gis-layer-source-${id}`;
    const fillLayerId = `gis-layer-${id}-fill`;
    const outlineLayerId = `gis-layer-${id}-outline`;
    const lineLayerId = `gis-layer-${id}-line`;
    const pointLayerId = `gis-layer-${id}-point`;
    const layerIds: [string, string, string, string] = [fillLayerId, outlineLayerId, lineLayerId, pointLayerId];
    State.gisLayerClickableLayerIds.delete(fillLayerId);
    State.gisLayerClickableLayerIds.delete(pointLayerId);
    removeLayersAndSource(map, [...layerIds].reverse(), sourceId);

    const previousStates = State.gisLayerGeometryTypeStates.get(id);
    const typeStates = new Map(geometryTypes.map(type => [
        type, geometryTypes.length === 1 || previousStates?.get(type) !== false
    ]));
    State.gisLayerGeometryTypeStates.set(id, typeStates);
    const enabledTypes = geometryTypes.filter(type => typeStates.get(type));
    const color = Config.getGISLayerById(id)?.color || DEFAULTS.COLORS.FALLBACK;
    addVectorOverlay(map, {
        sourceId, layerIds, data, color,
        filterForGeometry: type => gisLayerGeometryFilter(type, enabledTypes)
    });

    State.allGISLayerLayers.set(id, layerIds);
    State.gisLayerClickableLayerIds.add(fillLayerId);
    State.gisLayerClickableLayerIds.add(pointLayerId);
    if (boundsCoordinates) State.gisLayerBounds.set(id, new mapboxgl.LngLatBounds(boundsCoordinates[0], boundsCoordinates[1]));
    else State.gisLayerBounds.delete(id);
    void this.reorderLayers();
}
