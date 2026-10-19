import type { ExperimentExperimentFieldsItem, Experiment as ApiExperiment, ExperimentRecord as ApiExperimentRecord } from '@speleodb/api';
import type { EntityId } from './identifiers.ts';
import type { RecordDates } from './station-records.ts';
export type ExperimentValue = string | number | boolean | null;
/** Experiment field UUIDs are user-defined keys, not a fixed object contract. */
export type ExperimentValues = Record<string, ExperimentValue>;
export type ExperimentField = ExperimentExperimentFieldsItem;
export type ExperimentRecord = ApiExperimentRecord;
export type ExperimentReadValue = ApiExperimentRecord['data'][string];
export type ExperimentDefinition = ApiExperiment;
