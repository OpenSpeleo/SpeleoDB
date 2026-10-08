import type { EntityId } from './identifiers.ts';
export interface ProjectCommitCount { id: EntityId; commit_count: number }
export interface StationTagPresentation {
    id: EntityId;
    name: string;
    color: string;
    station_count?: number | null;
    creation_date: string;
}
export interface ProjectUploadResponse {
    browser_url: string;
    geojson_status?: string;
}
export interface RevisionFormat { name: string; download_url: string }
export interface RevisionCommit {
    id: string;
    author_name: string;
    authored_date: string;
    message: string;
    url: string;
    formats: RevisionFormat[];
}
export interface RevisionHistoryResponse { commits?: RevisionCommit[]; error?: string }
export interface GitTreeCommit {
    message: string;
    authored_date: string;
    dt_since: string;
    url: string;
}
export interface GitTreeFile {
    path: string;
    name: string;
    size: string;
    download_url: string;
    commit: GitTreeCommit;
}
export interface GitTreeFolder {
    name: string;
    path: string;
    message?: string;
    dt_since?: string;
    commit_url?: string;
    datetime?: string;
}
export interface GitTreeResponse {
    commit?: { author_name: string; message: string; hexsha_short: string; dt_since: string };
    project?: { n_commits: number };
    files?: GitTreeFile[];
    error?: string;
}
