import type { ExperimentValue } from '../../../../../../ts-types/domain/experiment-records.ts';
import type { ViewerExperimentField, ViewerExperimentFields, ViewerExperiment, ExperimentValidation } from '../../../../../../ts-types/domain/station-experiments.ts';

export const MANDATORY_FIELD_UUIDS = {
    MEASUREMENT_DATE: '00000000-0000-0000-0000-000000000001',
    SUBMITTER_EMAIL: '00000000-0000-0000-0000-000000000002'
};

export function isSubmitterEmailField(field: ViewerExperimentField) {
    return Boolean(field) && field.id === MANDATORY_FIELD_UUIDS.SUBMITTER_EMAIL;
}

export function sortExperimentFields(fields: ViewerExperimentFields) {
    let fieldsArray: ViewerExperimentField[] = [];

    if (Array.isArray(fields)) {
        fieldsArray = fields.map((field: Omit<ViewerExperimentField, 'id'> & { id?: string }) => ({
            id: field.id!,
            ...field
        }));
    } else if (fields && typeof fields === 'object') {
        fieldsArray = Object.entries(fields).map(([uuid, field]) => ({
            id: uuid,
            ...field
        }));
    }

    fieldsArray.sort((a, b) => {
        const orderA = a.order !== undefined ? a.order : 999;
        const orderB = b.order !== undefined ? b.order : 999;
        return orderA - orderB;
    });

    return fieldsArray;
}

export function getEditableExperimentFields(experiment: ViewerExperiment | null) {
    return sortExperimentFields(experiment?.experiment_fields || {}).filter(field => !isSubmitterEmailField(field));
}

export function validateExperimentField(value: string | null | undefined, fieldType: string, required: boolean, fieldId = ''): ExperimentValidation {
    if (required && (value === null || value === undefined || value === '')) {
        return { valid: false, message: 'This field is required' };
    }
    if (!required && (value === null || value === undefined || value === '')) {
        return { valid: true };
    }

    switch (fieldType) {
        case 'number': {
            const num = parseFloat(value as string);
            if (Number.isNaN(num)) {
                return { valid: false, message: 'Must be a valid number' };
            }
            return { valid: true };
        }
        case 'date': {
            const date = new Date(value as string);
            if (Number.isNaN(date.getTime())) {
                return { valid: false, message: 'Must be a valid date' };
            }

            if (fieldId === MANDATORY_FIELD_UUIDS.MEASUREMENT_DATE) {
                const today = new Date();
                today.setHours(23, 59, 59, 999);
                if (date > today) {
                    return { valid: false, message: 'Measurement date cannot be in the future' };
                }
            }
            return { valid: true };
        }
        case 'text':
        case 'boolean':
        case 'select':
        default:
            return { valid: true };
    }
}

export function formatDateDisplay(value: ExperimentValue | undefined) {
    if (!value) {
        return '';
    }

    try {
        return new Date(value as string).toLocaleDateString();
    } catch (error) {
        return String(value);
    }
}

export function normalizeDateInputValue(value: ExperimentValue) {
    if (!value) {
        return '';
    }

    const valueAsString = String(value);
    const matchedDate = valueAsString.match(/^\d{4}-\d{2}-\d{2}/);
    if (matchedDate) {
        return matchedDate[0];
    }

    const parsedDate = new Date(valueAsString);
    if (Number.isNaN(parsedDate.getTime())) {
        return '';
    }

    return parsedDate.toISOString().split('T')[0];
}

export function normalizeFieldValueForInput(field: ViewerExperimentField, value: ExperimentValue | undefined) {
    if (value === null || value === undefined) {
        return '';
    }

    if (field.type === 'boolean') {
        return value ? 'true' : 'false';
    }

    if (field.type === 'date') {
        return normalizeDateInputValue(value);
    }

    return String(value);
}

export function parseFieldInputValue(field: ViewerExperimentField, value: string) {
    if (value === '') {
        return undefined;
    }

    switch (field.type) {
        case 'number':
            return parseFloat(value);
        case 'boolean':
            return value === 'true';
        case 'date':
        case 'select':
        case 'text':
        default:
            return value;
    }
}
