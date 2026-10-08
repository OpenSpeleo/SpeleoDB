import type { Position } from 'geojson';
import type { EntityId } from './identifiers.ts';
import type { DisplayConcern, DisplayPreferences, DepthDomain } from './map-display.ts';
import type { CameraBounds, DisplayGeometryType, ViewerGeoJSON } from './map-geometry.ts';
import type { RendererMap } from './renderer.ts';
import type { StationRecord, StationTagRecord } from './station-records.ts';
import type { ViewerLandmark, ViewerLandmarkCollection } from './map-entities.ts';
export type { ViewerLandmark } from './map-entities.ts';
import type { CylinderInstallRecord } from './fleet-records.ts';
import type { GISGeometryResponse } from './map-config.ts';

export type ViewerMap = RendererMap;
export interface ViewerExplorationLead {
    id: EntityId;
    coordinates: Position;
    lineName: string;
    description: string;
    projectId: EntityId | null;
    createdAt: string | undefined;
    createdBy?: string | undefined;
}
export interface ViewerCylinderInstall extends CylinderInstallRecord { coordinates: Position }

/** Mutable containers are owned by State; reset replaces rather than clears them. */
export interface ViewerState {
    map: ViewerMap | null;
    layerGeneration: number;
    displayUpdatePending: boolean;
    displayDirty: Set<DisplayConcern>;
    displayPreferences: DisplayPreferences;
    projectLayerStates: Map<EntityId, boolean>;
    effectiveProjectVisibility: Map<EntityId, boolean>;
    networkLayerStates: Map<EntityId, boolean>;
    userTags: StationTagRecord[];
    tagColors: string[];
    currentStationForTagging: EntityId | null;
    allProjectLayers: Map<EntityId, string[]>;
    allNetworkLayers: Map<EntityId, string[]>;
    currentProjectId: EntityId | null;
    allStations: Map<EntityId, StationRecord>;
    allSurfaceStations: Map<EntityId, StationRecord>;
    allLandmarks: Map<EntityId, ViewerLandmark>;
    landmarkCollections: Map<EntityId, ViewerLandmarkCollection>;
    projectDepthDomains: Map<EntityId, DepthDomain | null>;
    activeDepthDomain: DepthDomain | null;
    projectBounds: Map<EntityId, CameraBounds>;
    networkBounds: Map<EntityId, CameraBounds>;
    explorationLeads: Map<EntityId, ViewerExplorationLead>;
    cylinderInstalls: Map<EntityId, ViewerCylinderInstall>;
    landmarksVisible: boolean;
    gpsTrackLayerStates: Map<EntityId, boolean>;
    gpsTrackCache: Map<EntityId, ViewerGeoJSON>;
    gpsTrackLoadingStates: Map<EntityId, boolean>;
    allGPSTrackLayers: Map<EntityId, string[]>;
    gpsTrackBounds: Map<EntityId, CameraBounds>;
    gisLayerStates: Map<EntityId, boolean>;
    gisLayerCache: Map<EntityId, ViewerGeoJSON>;
    gisLayerGeometryTypeStates: Map<EntityId, Map<DisplayGeometryType, boolean>>;
    gisLayerLoadingStates: Map<EntityId, boolean>;
    allGISLayerLayers: Map<EntityId, string[]>;
    gisLayerBounds: Map<EntityId, CameraBounds>;
    gisLayerClickableLayerIds: Set<string>;
    gisGeometryStates: Map<EntityId, boolean>;
    gisGeometryCache: Map<EntityId, GISGeometryResponse>;
    gisGeometryLoading: Map<EntityId, Promise<GISGeometryResponse>>;
    allGISGeometryLayers: Map<EntityId, string[]>;
    gisGeometryBounds: Map<EntityId, CameraBounds>;
    gisGeometryEditingId: EntityId | null;
    resetLayerState(): void;
}
