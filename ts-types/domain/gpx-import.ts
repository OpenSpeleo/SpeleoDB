export interface GPXImportResponse {
    message?: string;
    error?: string;
    detail?: string;
    landmarks_created?: number;
    gps_tracks_created?: number;
}
