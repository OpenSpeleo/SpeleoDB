export type ProjectGeoJSONState = 'pending' | 'queued' | 'running' | 'ready' | 'failed' | 'skipped' | 'not_requested';
export interface ProjectGeoJSONStatus {
    state: ProjectGeoJSONState;
    error?: unknown;
    source_commit_sha?: string | null;
    geojson_commit_sha?: string | null;
    geojson_revision?: string;
}
