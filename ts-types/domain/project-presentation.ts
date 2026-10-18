export type { ProjectCommit as RevisionCommit } from '@speleodb/api';
export type { GitFile as GitTreeFile, GitCommit as GitTreeCommit } from '@speleodb/api';
export interface GitTreeFolder {
    name: string;
    path: string;
    message?: string;
    dt_since?: string;
    commit_url?: string | null;
    datetime?: string;
}
export type { ProjectGitExplorerResponse as GitTreeResponse } from '@speleodb/api';
