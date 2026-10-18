import type { GISProjectViewInputRequest, Project, ProjectGeoJSONCommit, V2UserGisViewsCreateBody } from '@speleodb/api';

/** Only picker labels and identities are retained by the form. */
export type GisViewProject = Pick<Project, 'id'> & Partial<Pick<Project, 'name'>>;
export type GisViewCommit = Partial<Pick<ProjectGeoJSONCommit,
    'commit_date' | 'commit_sha' | 'commit_author_name' | 'commit_message'>>;
/** The form always emits its selected project mode and an empty SHA for latest. */
export type GisViewSelectedProject = Required<Omit<GISProjectViewInputRequest, 'commit_sha'>> & {
    commit_sha: NonNullable<GISProjectViewInputRequest['commit_sha']>;
};
export type GisViewFormPayload = Required<Omit<V2UserGisViewsCreateBody, 'projects'>> & {
    projects: GisViewSelectedProject[];
};
export interface GisViewFormOptions<Response = unknown> {
    save: (payload: GisViewFormPayload) => Promise<Response>;
    loadProjects: () => Promise<GisViewProject[]>;
    loadCommits: (projectId: string) => Promise<GisViewCommit[]>;
    onSuccess?: ((data: Response) => void) | undefined;
    seedFromExistingRows?: boolean;
    initialProjectCounter?: number;
    newRowIdPrefix?: string;
    successMessage?: string;
    reloadDelayMs?: number;
}
