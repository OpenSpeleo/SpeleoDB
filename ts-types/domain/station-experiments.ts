import type { EntityId } from './identifiers.ts';
import type { ExperimentDefinition, ExperimentField, ExperimentValues } from './experiment-records.ts';

/** Existing viewer accepts both serialized arrays and UUID-keyed field definitions. */
export type ViewerExperimentField = Omit<ExperimentField, 'order'> & { order?: number };
export type ViewerExperimentFields = ViewerExperimentField[] | Record<string, Omit<ViewerExperimentField, 'id'> & { id?: string }>;
export type ViewerExperiment = Omit<ExperimentDefinition, 'experiment_fields'> & { experiment_fields: ViewerExperimentFields };
export interface ViewerExperimentRow { id?: EntityId; _id?: EntityId; data?: ExperimentValues }
export interface ExperimentAccess { write: boolean; delete: boolean }
export interface StationExperimentState {
    selectedExperimentId: EntityId | null;
    experimentDataRows: ViewerExperimentRow[];
    activeExperiments: ViewerExperiment[];
    experimentsById: Map<EntityId | null, ViewerExperiment>;
    currentContainer: HTMLElement | null;
    currentStationId: EntityId | null;
    experimentAccess: ExperimentAccess;
    rowsLoadState: 'idle' | 'loading' | 'loaded' | 'error';
    rowsLoadErrorMessage: string;
    activeRowsRequestToken: number;
}
export type ExperimentValidation = { valid: true } | { valid: false; message: string };
export interface ExperimentOperationError { status?: number; message?: string; data?: { errors?: unknown; message?: string } }
export interface RecordModalOptions { mode: 'add' | 'edit'; stationId: EntityId; experimentId: EntityId; rowId?: EntityId | null }
