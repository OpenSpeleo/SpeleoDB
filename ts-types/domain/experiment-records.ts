import type { EntityId } from './identifiers.ts';
import type { RecordDates } from './station-records.ts';
export type ExperimentValue = string | number | boolean | null;
/** Experiment field UUIDs are user-defined keys, not a fixed object contract. */
export type ExperimentValues = Record<string, ExperimentValue>;
export interface ExperimentField {
    id: string;
    name: string;
    type: string;
    required: boolean;
    order: number;
    options?: string[];
}
export interface ExperimentRecord extends RecordDates {
    id: EntityId;
    experiment: EntityId;
    station: EntityId;
    data: ExperimentValues;
}
export interface ExperimentDefinition extends RecordDates {
    id: EntityId;
    name: string;
    code: string;
    description: string;
    is_active: boolean;
    experiment_fields: ExperimentField[];
    start_date: string | null;
    end_date: string | null;
    can_write?: boolean;
    can_delete?: boolean;
    user_permission_level?: number;
    user_permission_level_label?: string;
}
