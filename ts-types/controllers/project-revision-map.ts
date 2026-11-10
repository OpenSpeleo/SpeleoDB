import type { ProjectMapInput } from '../domain/map-config.ts';

export interface ProjectRevisionMapContext {
    mapboxToken: string;
    project: ProjectMapInput & { id: string; name: string; color: string; geojson_file: string };
    commitSha: string;
    artifactRevision: string;
}
