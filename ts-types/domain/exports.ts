export type ExportState = 'queued' | 'running' | 'retry_wait' | 'ready' | 'partial' | 'failed' | 'cancelled';
export interface ExportOmission {
    category?: unknown;
    name?: unknown;
    reason?: unknown;
    error?: unknown;
}
export interface ExportArtifact {
    size_bytes?: unknown;
    expires_at?: string;
    deleted_at?: string | null;
}
export interface ExportJob {
    id: string;
    state: ExportState;
    stage?: string;
    completed_items?: number;
    total_items?: number;
    created_at?: string;
    updated_at?: string;
    summary?: { omissions?: unknown; error?: string };
    notification_state?: string;
    artifact?: ExportArtifact | null;
    download_url?: string | null;
    expired?: boolean;
}
export interface ExportPage {
    results: ExportJob[];
    previous: string | null;
    next: string | null;
}
export interface ExportHistoryOptions {
    endpoint?: string;
    busy?: boolean;
    linkedJob?: ExportJob | null;
    focusId?: string | null;
    now?: number;
}
export interface ExportRequestFailure extends Error { status?: number }
