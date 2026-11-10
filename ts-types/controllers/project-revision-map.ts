import type { ProjectMapInput } from '../domain/map-config.ts';

export interface ProjectMapRevision {
    commitSha: string;
    artifactRevision: string | null;
    url: string;
    geojsonUrl: string | null;
    dateLabel: string;
    displayDateLabel: string;
    timestampLabel: string;
    message: string;
    authorName: string;
    available: boolean;
}

export interface ProjectRevisionMapContext {
    mapboxToken: string;
    project: ProjectMapInput & { id: string; name: string; color: string; geojson_file: string };
    commitSha: string;
    artifactRevision: string;
    selectedRevision: ProjectMapRevision;
    revisions: ProjectMapRevision[];
}
