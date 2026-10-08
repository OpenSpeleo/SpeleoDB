import type { Feature, Geometry } from 'geojson';
import type { EntityId } from './identifiers.ts';
import type { Coordinate2D } from './map-geometry.ts';
import type { SnapIndicatorMap, SnapResult } from './map-snapping.ts';
import type { ScreenPoint } from './measurement.ts';

export interface PointerLongitudeLatitude {
    lng: number;
    lat: number;
    toArray(): [number, number];
}
export interface MapPointerEvent {
    point: ScreenPoint;
    lngLat: PointerLongitudeLatitude;
    originalEvent: { button?: number };
    defaultPrevented?: boolean;
}
export interface RenderedFeatureProperties {
    name?: string;
    color?: string;
    project_id?: EntityId;
}
export type RenderedMapFeature = Feature<Geometry, RenderedFeatureProperties> & { layer?: { id: string } };
export interface MapGestureToggle {
    isEnabled?(): boolean;
    enable(): unknown;
    disable(): unknown;
}
export interface InteractionMap extends SnapIndicatorMap {
    on(event: string, callback: (event: MapPointerEvent) => void): unknown;
    queryRenderedFeatures(point: ScreenPoint | number[][], options?: { layers: string[] }): RenderedMapFeature[];
    getCanvas(): { style: { cursor: string } };
    dragPan: MapGestureToggle;
    doubleClickZoom: MapGestureToggle;
}
export interface ActiveMapTool {
    isActive(): boolean;
    handleClick?(event: MapPointerEvent): unknown;
    handleMouseDown?(event: MapPointerEvent): unknown;
    handleMouseMove?(event: MapPointerEvent): unknown;
    handleMouseUp?(event: MapPointerEvent): unknown;
    handleContextMenu?(event: MapPointerEvent): unknown;
    handleCancel?(event: MapPointerEvent): unknown;
}
export type ActiveToolMethod = Exclude<keyof ActiveMapTool, 'isActive'>;
export type DraggedMarkerType = 'station' | 'landmark' | 'cylinder-install' | 'exploration-lead';
export type StationKind = 'subsurface' | 'surface';
export type ContextTarget = 'station' | 'surface-station' | 'landmark' | 'cylinder-install' | 'exploration-lead' | 'map';
export type ContextFeature = { id: EntityId | undefined; feature: RenderedMapFeature; stationType?: StationKind } | { coordinates: Coordinate2D };
export interface InteractionHandlers {
    geometryEditor?: ActiveMapTool;
    measurementTool?: ActiveMapTool;
    onStationClick?(stationId: EntityId | undefined, type: StationKind): unknown;
    onLandmarkClick?(landmarkId: EntityId | undefined): unknown;
    onExplorationLeadClick?(leadId: EntityId | undefined): unknown;
    onCylinderInstallClick?(installId: EntityId | undefined): unknown;
    onGISFeatureClick?(feature: RenderedMapFeature, coordinates: PointerLongitudeLatitude): unknown;
    onMapClick?(coordinates: Coordinate2D): unknown;
    onLandmarkDrag?(landmarkId: EntityId, coordinates: Coordinate2D): unknown;
    onStationDrag?(stationId: EntityId, projectId: EntityId, coordinates: Coordinate2D): unknown;
    onStationDragEnd?(stationId: EntityId, projectId: EntityId | null, snap: SnapResult, original: readonly number[]): unknown;
    onMarkerDragEnd?(type: 'cylinder-install' | 'exploration-lead', id: EntityId, snap: SnapResult, original: readonly number[]): unknown;
    onLandmarkDragEnd?(id: EntityId, coordinates: Coordinate2D, original: readonly number[]): unknown;
    onContextMenu?(event: MapPointerEvent, type: ContextTarget, feature: ContextFeature): unknown;
}
export interface MapInteractions {
    handlers: InteractionHandlers;
    QUERY_PADDING: number;
    cancelPendingDrag?: () => void;
    init(map: InteractionMap, handlers?: InteractionHandlers | null): void;
    getActiveTool(): ActiveMapTool | null;
    dispatchToActiveTool(method: ActiveToolMethod, event: MapPointerEvent): boolean;
    setupHoverEffects(map: InteractionMap): void;
    setupClickHandlers(map: InteractionMap): void;
    setupDragHandlers(map: InteractionMap): void;
    setupContextMenu(map: InteractionMap): void;
}
