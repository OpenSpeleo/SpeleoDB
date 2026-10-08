import type { EntityId } from './identifiers.ts';
/** GPXImportView returns counts, created track identities and geographic bounds. */
export interface GPXImportResult {
    landmarks_created: number;
    gps_tracks_created: number;
    gps_track_ids: EntityId[];
    collection_id: EntityId;
    bounds: number[] | null;
}

/** Presentation result retains omitted counts from overlay and duplicate-only imports. */
export interface ImportedMapResult {
    kind: 'overlay' | 'places' | 'gpx';
    layerId?: EntityId | undefined;
    landmarksCreated?: number;
    gpsTracksCreated?: number;
    gpsTrackIds?: EntityId[];
    bounds?: import('./map-geometry.ts').CameraBounds | null | undefined;
}
