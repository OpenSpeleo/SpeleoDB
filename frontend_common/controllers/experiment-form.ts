import { ExperimentExperimentFieldsItemType, v2ExperimentsCreateWithJson, v2ExperimentsUpdateWithJson } from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';
import { choice } from '../api/entity-forms.ts';
import { formText } from '../api/form-values.ts';
import { afterWindowLoad } from '../readiness.ts';
import { ExperimentFields } from '../../frontend_private/static/private/ts/experiment-fields.ts';
import { showApiErrorModal } from '../../frontend_private/static/private/ts/forms/api_errors.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';
import type { ExperimentFormContext, ExperimentFormField } from '../../ts-types/controllers/experiment-form.ts';
import type { EntityId } from '../../ts-types/domain/identifiers.ts';

function fieldInput(
    name: string,
    type: ExperimentFormField['type'],
    required: boolean,
    options: string[] = [],
    id?: string,
): ExperimentFormField {
    const field = { name, required, ...(id ? { id } : {}) };
    return type === 'select' ? { ...field, type, options } : { ...field, type };
}

function collectNewFields() {
    const fields: ExperimentFormField[] = [];
    $('#all_fields_container').children().each(function () {
        const $element = $(this);
        if ($element.hasClass('mandatory-field-item')) {
            fields.push(fieldInput(
                $element.data('field-name') as string,
                choice(ExperimentExperimentFieldsItemType, $element.data('field-type')),
                $element.data('field-required') as boolean,
            ));
        } else if ($element.hasClass('field-item')) {
            const name = ($element.find('.field-name').val() as string).trim();
            const type = $element.find('.field-type').val() as string;
            if (!name || !type) return;
            const options = $element.find('.field-tags-container .tag-text')
                .map(function () { return $(this).text(); }).get();
            fields.push(fieldInput(name, choice(ExperimentExperimentFieldsItemType, type),
                $element.find('.field-required').is(':checked'), options));
        }
    });
    return fields;
}

function collectExistingAndNewFields() {
    const fields: ExperimentFormField[] = [];
    $('#all_fields_container').children().each(function () {
        const $element = $(this);
        if ($element.hasClass('existing-field-item')) {
            const name = ($element.find('.existing-field-name').val() as string).trim();
            if (!name) return;
            let options: string[] = [];
            const rawOptions: unknown = $element.data('field-options');
            if (rawOptions) {
                try {
                    const parsed: unknown = typeof rawOptions === 'string' ? JSON.parse(rawOptions) : rawOptions;
                    if (Array.isArray(parsed)) options = parsed.filter((value): value is string => typeof value === 'string');
                } catch (error) {
                    console.warn('Failed to parse field options:', error);
                }
            }
            fields.push(fieldInput(name,
                choice(ExperimentExperimentFieldsItemType, $element.data('field-type')),
                $element.data('field-required') === true || $element.data('field-required') === 'true',
                options, String($element.data('field-id'))));
        } else if ($element.hasClass('field-item')) {
            const name = ($element.find('.field-name').val() as string).trim();
            const type = $element.find('.field-type').val() as string;
            if (!name || !type) return;
            const options = $element.find('.field-tags-container .tag-text')
                .map(function () { return $(this).text(); }).get();
            fields.push(fieldInput(name, choice(ExperimentExperimentFieldsItemType, type),
                $element.find('.field-required').is(':checked'), options));
        }
    });
    return fields;
}

function route(name: NonNullable<ExperimentFormContext['redirectRoute']>, value: EntityId) {
    const builder = window.Urls?.[name];
    if (typeof builder !== 'function') throw new Error(`Missing Django URL route: ${name}`);
    return builder(value);
}

export async function init(context: ExperimentFormContext) {
    await afterWindowLoad();
    ExperimentFields.initialize();
    const container = document.getElementById('all_fields_container');
    if (container) {
        window.Sortable.create(container, {
            animation: 150,
            handle: '.drag-handle',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            forceFallback: true,
            fallbackClass: 'sortable-fallback',
            draggable: context.mode === 'create'
                ? '.mandatory-field-item, .field-item'
                : '.existing-field-item, .field-item',
        });
    }

    $('#btn_submit').on('click', function (event) {
        event.preventDefault();
        const complete = ExperimentFields.validateFieldsComplete();
        if (!complete.isValid) {
            FormModals.showError(complete.errorMessage);
            return false;
        }
        if (!ExperimentFields.validateUniqueFieldNames()) {
            FormModals.showError('Duplicate field names detected. Each field must have a unique name. Please check the highlighted fields.');
            return false;
        }

        const fields = context.mode === 'create'
            ? collectNewFields()
            : collectExistingAndNewFields();
        if (context.mode === 'create' && fields.length === 2) {
            FormModals.showError('Please add at least one custom field for data collection.');
            return false;
        }

        const form = document.getElementById(context.formId) as HTMLFormElement;
        const data = new FormData(form);
        const payload = {
            name: formText(data, 'name'), code: formText(data, 'code'), description: formText(data, 'description'),
            start_date: formText(data, 'start_date') || null, end_date: formText(data, 'end_date') || null,
            ...((context.mode === 'create' || fields.length > 0) ? { experiment_fields: fields } : {}),
        };
        const request = context.mode === 'create'
            ? apiData(v2ExperimentsCreateWithJson(payload, undefined, webApiOptions()))
            : apiData(v2ExperimentsUpdateWithJson(context.experimentId!, payload, undefined, webApiOptions()));
        request.then(data => {
            FormModals.showSuccess(context.successMessage);
            window.setTimeout(() => {
                if (context.redirectRoute) window.location.href = route(context.redirectRoute, data.id);
                else window.location.reload();
            }, 2000);
        }).catch(showApiErrorModal);
        return false;
    });
}
