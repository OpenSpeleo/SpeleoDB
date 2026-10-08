export interface AdminExperimentField {
    name?: string;
    type?: string;
    required?: boolean;
    options?: string[];
    hash?: string;
}
/** Field slugs are backend-generated keys, including arbitrary user custom fields. */
export type AdminExperimentFields = Record<string, AdminExperimentField>;
