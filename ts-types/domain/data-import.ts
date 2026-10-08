import type { EntityId } from './identifiers.ts';
import type { CameraBounds } from './map-geometry.ts';
import type { ImportedMapResult } from './map-import.ts';

export type ImportTab = 'gpx' | 'kml';
export type ImportMode = 'places' | 'overlay';
export interface ImportReview {
    places: {
        unique_coordinate_count?: number;
        duplicate_coordinate_count?: number;
        skipped_placemarks?: number;
        eligible_placemarks?: number;
        point_count?: number;
    };
    overlay: {
        feature_count?: number;
        point_parts?: number;
        line_parts?: number;
        polygon_parts?: number;
        source_placemarks?: number;
    };
    warnings?: { code?: string; message?: string; modes?: string[]; count?: number }[];
    suggested_name?: string;
    source_placemarks?: number;
}
export interface ImportEligibility {
    file?: File | null;
    report?: ImportReview | null;
    mode?: ImportMode | null;
    collectionId?: string;
    layerName?: string;
    busy?: boolean;
    uncertain?: boolean;
}
export interface ImportCollection {
    id: EntityId;
    name: string;
    can_write?: boolean;
    is_personal?: boolean;
}
export interface ImportResponse {
    id?: EntityId;
    name?: string;
    collection_id?: EntityId;
    bounds?: CameraBounds | null;
    landmarks_created?: number;
    gps_tracks_created?: number;
    gps_track_ids?: EntityId[];
    landmarks_skipped?: number;
    duplicates_in_file?: number;
}
export interface ImportResult extends Omit<ImportedMapResult, 'layerId' | 'bounds'> {
    layerId: EntityId | undefined;
    collectionId: EntityId | undefined;
    bounds: CameraBounds | null | undefined;
    landmarksSkipped: number;
    duplicatesInFile: number;
    name: string;
}
export interface ImportSession {
    tab: ImportTab;
    gpxFile: File | null;
    kmlFile: File | null;
    mode: ImportMode | null;
    report: ImportReview | null;
    inspecting: boolean;
    busy: boolean;
    uncertain: boolean;
    errors: Record<ImportTab, string>;
    layerNameEdited: boolean;
    result: ImportResult | null;
    refreshing: boolean;
    refreshed: boolean;
    refreshError: string;
    showing: boolean;
    collectionsReady: boolean;
    collectionsLoading: boolean;
    collectionsError: string;
    progress: number | null;
    progressText: string;
}

export interface ImportPresentationHost {
    element: <T extends HTMLElement = HTMLElement>(id: string) => T;
    query: <T extends HTMLElement = HTMLElement>(selector: string) => T;
    eligible: () => boolean;
    interactionLocked: () => boolean;
    renderProgress: () => void;
}
