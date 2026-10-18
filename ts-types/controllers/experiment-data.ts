import type { EntityId } from '../domain/identifiers.ts';
export interface ExperimentDataContext {
    experimentId: EntityId;
    gisToken: string;
}
