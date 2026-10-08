import type { EntityId } from '../domain/identifiers.ts';

export interface ExperimentFormContext {
    mode: 'create' | 'edit';
    formId: string;
    endpoint: string;
    method: string;
    successMessage: string;
    redirectRoute?: 'private:experiment_details';
}

export interface ExperimentFormField {
    id?: EntityId;
    name: string;
    type: string;
    required: boolean;
    options?: string[];
}

export interface ExperimentFormPayload {
    name?: FormDataEntryValue;
    code?: FormDataEntryValue;
    description?: FormDataEntryValue;
    csrfmiddlewaretoken?: FormDataEntryValue;
    is_active?: FormDataEntryValue;
    start_date?: FormDataEntryValue;
    end_date?: FormDataEntryValue;
    experiment_fields?: ExperimentFormField[];
}
