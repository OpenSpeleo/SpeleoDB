import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerUpdateResult } from '../../../../../../../ts-types/domain/viewer-updates.ts';
import { State } from '../../state.ts';
import { DEFAULTS } from '../../defaults.ts';
import type { GISGeometryResponse } from '../../../../../../../ts-types/domain/map-config.ts';
import type { AppliedGISGeometry } from '../../../../../../../ts-types/domain/map-layers.ts';
import { Config } from '../../config.ts';
import { API } from '../../api.ts';
import { Utils } from '../../utils.ts';
import { ViewerUpdates } from '../../viewer_updates.ts';
import { cancelMapNavigation } from '../navigation_intent.ts';
import { computeGeoJSONBounds } from '../geojson.ts';
import { addVectorOverlay } from '../vector_overlay.ts';
import { removeLayersAndSource } from './source_lifecycle.ts';
import { beginOverlayIntent, isOverlayIntentCurrent } from './lazy_overlay.ts';
const gisGeometryAppliedRecords = new Map<string, AppliedGISGeometry>();
export function clearAppliedGISGeometries(): void { gisGeometryAppliedRecords.clear(); }
interface GeometryLayerOwner {
    isGISGeometryVisible(id: EntityId): boolean;
    showGISGeometryLayers(id: EntityId, visible: boolean): void;
    addGISGeometry(record: GISGeometryResponse): void;
    reorderLayers(): Promise<ViewerUpdateResult> | undefined;
}

export function isGISGeometryVisible(id: EntityId) {
    return State.gisGeometryStates.get(String(id)) === true;
}

export function showGISGeometryLayers(id: EntityId, visible: boolean) {
    const key = String(id);
    const show = visible && State.gisGeometryEditingId !== key;
    for (const layerId of State.allGISGeometryLayers.get(key) || []) {
        if (State.map?.getLayer(layerId)) {
            State.map.setLayoutProperty(layerId, 'visibility', show ? 'visible' : 'none');
        }
    }
}

export async function toggleGISGeometryVisibility(this: Pick<GeometryLayerOwner, 'showGISGeometryLayers' | 'isGISGeometryVisible' | 'addGISGeometry'>, id: EntityId, visible: boolean) {
    const key = String(id);
    const operationKey = `gis-geometry:${key}`;
    const intent = beginOverlayIntent(operationKey);
    const map = State.map;
    const generation = State.layerGeneration;
    const sessionCurrent = () => State.map === map && State.layerGeneration === generation;
    const isCurrent = () => sessionCurrent() && isOverlayIntentCurrent(operationKey, intent);
    State.gisGeometryStates.set(key, visible);
    if (!visible) {
        cancelMapNavigation(operationKey);
        await ViewerUpdates.schedule(operationKey, () => {
            if (isCurrent()) this.showGISGeometryLayers(key, false);
        });
        return isCurrent();
    }
    let record = State.gisGeometryCache.get(key);
    let pending;
    try {
        if (!record) {
            pending = State.gisGeometryLoading.get(key);
            if (!pending) {
                pending = API.getGISGeometryDetails(key);
                State.gisGeometryLoading.set(key, pending);
            }
            record = await pending;
            if (!sessionCurrent()) return false;
            if (!record?.geojson) throw new Error('The geometry is unavailable.');
            const cached = State.gisGeometryCache.get(key);
            if (cached && cached.revision > record.revision) record = cached;
            State.gisGeometryCache.set(key, record);
            Config.upsertGISGeometry(record);
        }
        if (!isCurrent() || !this.isGISGeometryVisible(key)) return false;
        const result = await ViewerUpdates.schedule(operationKey, () => {
            if (!isCurrent()) return;
            // An editor save may have replaced the baseline during our paint wait.
            record = State.gisGeometryCache.get(key) || record;
            const ids = State.allGISGeometryLayers.get(key);
            const applied = gisGeometryAppliedRecords.get(key);
            if (!ids?.length || !State.map?.getLayer(ids[0]!) || applied?.record !== record
                || applied!.generation !== generation || applied!.map !== map) this.addGISGeometry(record!);
            this.showGISGeometryLayers(key, this.isGISGeometryVisible(key));
        });
        if (result.status === 'failed') throw result.error;
        return isCurrent() && result.status === 'applied';
    } catch (error) {
        if (!isCurrent()) return false;
        const cached = State.gisGeometryCache.get(key);
        if (cached && cached !== record) return this.isGISGeometryVisible(key);
        State.gisGeometryStates.set(key, false);
        this.showGISGeometryLayers(key, false);
        console.error('Failed to show GIS Geometry:', error);
        Utils.showNotification('error', 'Unable to display this geometry. Toggle it on to retry.');
        return false;
    } finally {
        if (sessionCurrent() && State.gisGeometryLoading.get(key) === pending) State.gisGeometryLoading.delete(key);
    }
}

export function addGISGeometry(this: Pick<GeometryLayerOwner, 'showGISGeometryLayers' | 'isGISGeometryVisible' | 'reorderLayers'>, record: GISGeometryResponse) {
    const map = State.map;
    if (!map) return;
    const id = String(record.id);
    const sourceId = `gis-geometry-source-${id}`;
    const layerIds = ['fill', 'outline', 'line', 'point'].map(role => `gis-geometry-${id}-${role}`) as [string, string, string, string];
    removeLayersAndSource(map, [...layerIds].reverse(), sourceId);
    addVectorOverlay(map, {
        sourceId, layerIds,
        data: { type: 'Feature', properties: { name: record.name! }, geometry: record.geojson! },
        color: record.color || DEFAULTS.COLORS.FALLBACK,
        fillOpacity: DEFAULTS.GIS_GEOMETRY.FILL_OPACITY,
    });
    State.allGISGeometryLayers.set(id, layerIds);
    gisGeometryAppliedRecords.set(id, { record, map, generation: State.layerGeneration });
    // Stored Geometry never has a trusted caller-supplied bbox.
    const bounds = computeGeoJSONBounds(record.geojson, { wrapLongitude: false });
    if (!bounds.isEmpty()) State.gisGeometryBounds.set(id, bounds);
    this.showGISGeometryLayers(id, this.isGISGeometryVisible(id));
    void this.reorderLayers();
}

export function acceptGISGeometry(this: Pick<GeometryLayerOwner, 'addGISGeometry'>, record: GISGeometryResponse) {
    const id = String(record.id);
    Config.upsertGISGeometry(record);
    State.gisGeometryCache.set(id, record);
    State.gisGeometryStates.set(id, true);
    return ViewerUpdates.schedule(`gis-geometry:${id}`, () => {
        if (State.gisGeometryCache.get(id) === record) this.addGISGeometry(record);
    });
}

export function refreshGISGeometry(this: Pick<GeometryLayerOwner, 'addGISGeometry'>, record: GISGeometryResponse) {
    const id = String(record.id);
    Config.upsertGISGeometry(record);
    State.gisGeometryCache.set(id, record);
    // Refresh the saved baseline without changing the pre-edit visibility.
    return ViewerUpdates.schedule(`gis-geometry:${id}`, () => {
        if (State.gisGeometryCache.get(id) === record) this.addGISGeometry(record);
    });
}
