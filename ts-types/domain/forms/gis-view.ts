export interface GisViewProject {
    id: string;
    name?: string | null;
}
export interface GisViewCommit {
    commit_date?: string | null;
    commit_sha?: string | null;
    commit_author_name?: string | null;
    commit_message?: string | null;
}
export interface GisViewSelectedProject {
    project_id: string;
    use_latest: boolean;
    commit_sha: string;
}
export interface GisViewFormOptions<Response = unknown> {
    endpoint?: string;
    method?: string;
    projectsEndpoint?: string;
    commitsEndpointBuilder?: (projectId: string) => string;
    onSuccess?: ((data: Response) => void) | undefined;
    seedFromExistingRows?: boolean;
    initialProjectCounter?: number;
    newRowIdPrefix?: string;
    successMessage?: string;
    reloadDelayMs?: number;
}
