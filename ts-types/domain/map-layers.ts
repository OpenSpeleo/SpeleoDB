import type { EntityId } from './identifiers.ts';
import type { FeatureCollection } from 'geojson';
import type { DisplayGeometry, DisplayGeometryType, ViewerGeoJSON } from './map-geometry.ts';
import type { PreparedBounds } from './map-preparation.ts';
import type { GISGeometryResponse } from './map-config.ts';
import type { ViewerMap } from './map-state.ts';
import type { JSONObject } from './json.ts';

export interface OverlayVersion {
    generation: number;
    revision: string | null;
    data: ViewerGeoJSON;
}
export interface OverlayRequest {
    generation: number;
    revision: string | null;
    controller: AbortController;
    promise: Promise<ViewerGeoJSON>;
}
export interface PreparedGPSOverlay { boundsCoordinates: PreparedBounds | null }
export interface PreparedGISOverlay extends PreparedGPSOverlay {
    data: FeatureCollection<DisplayGeometry, JSONObject>;
    geometryTypes: DisplayGeometryType[];
}
export interface OverlayInstallOptions<Prepared> {
    isCurrent?: () => boolean;
    prepared?: Prepared | undefined;
}
export interface LazyOverlayOptions<Prepared> {
    kind: 'gps' | 'gis-layer';
    id: string;
    visible: boolean;
    cache: Map<EntityId, ViewerGeoJSON>;
    states: Map<EntityId, boolean>;
    layers: Map<EntityId, string[]>;
    details(this: void, signal: AbortSignal): Promise<ViewerGeoJSON>;
    prepare?(this: void, data: ViewerGeoJSON, isCurrent: () => boolean): Promise<Prepared>;
    install(this: void, data: ViewerGeoJSON, isCurrent: () => boolean, prepared: Prepared | undefined): Promise<void>;
    show(this: void, visible: boolean): void;
    loading?(this: void, loading: boolean): void;
    metadata?(this: void): { modified_date?: string | undefined } | null | undefined;
}
export interface AppliedGISGeometry { record: GISGeometryResponse; map: ViewerMap; generation: number }
export interface GISPopupFeature {
    properties?: JSONObject | null;
    geometry?: { type?: string } | null;
}
