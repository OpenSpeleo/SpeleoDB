import type { ExperimentRequest } from '@speleodb/api';

export interface ExperimentFormContext {
    mode: 'create' | 'edit';
    formId: string;
    experimentId?: string;
    successMessage: string;
    redirectRoute?: 'private:experiment_details';
}

/** The form builds the ordered-list branch of the generated experiment input. */
export type ExperimentFormField = Extract<NonNullable<ExperimentRequest['experiment_fields']>, unknown[]>[number];
