import { afterWindowLoad } from '../readiness.ts';
import { ExperimentFields } from '../../frontend_private/static/private/ts/experiment-fields.ts';
import { showAjaxErrorModal } from '../../frontend_private/static/private/ts/forms/ajax_errors.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';
import type { ExperimentFormContext, ExperimentFormField, ExperimentFormPayload } from '../../ts-types/controllers/experiment-form.ts';
import type { EntityId } from '../../ts-types/domain/identifiers.ts';

function collectNewFields() {
    const fields: ExperimentFormField[] = [];
    $('#all_fields_container').children().each(function () {
        const $element = $(this);
        if ($element.hasClass('mandatory-field-item')) {
            fields.push({
                name: $element.data('field-name') as string,
                type: $element.data('field-type') as string,
                required: $element.data('field-required') as boolean,
            });
        } else if ($element.hasClass('field-item')) {
            const name = ($element.find('.field-name').val() as string).trim();
            const type = $element.find('.field-type').val() as string;
            if (!name || !type) return;
            const field: ExperimentFormField = {
                name,
                type,
                required: $element.find('.field-required').is(':checked'),
            };
            if (type === 'select') {
                field.options = $element.find('.field-tags-container .tag-text')
                    .map(function () { return $(this).text(); }).get();
            }
            fields.push(field);
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
            const field: ExperimentFormField = {
                id: $element.data('field-id') as EntityId,
                name,
                type: $element.data('field-type') as string,
                required: $element.data('field-required') === true || $element.data('field-required') === 'true',
            };
            const rawOptions: unknown = $element.data('field-options');
            if (rawOptions) {
                try {
                    const options: unknown = typeof rawOptions === 'string' ? JSON.parse(rawOptions) : rawOptions;
                    if (Array.isArray(options) && options.length) field.options = options as string[];
                } catch (error) {
                    console.warn('Failed to parse field options:', error);
                }
            }
            fields.push(field);
        } else if ($element.hasClass('field-item')) {
            const name = ($element.find('.field-name').val() as string).trim();
            const type = $element.find('.field-type').val() as string;
            if (!name || !type) return;
            const field: ExperimentFormField = {
                name,
                type,
                required: $element.find('.field-required').is(':checked'),
            };
            if (type === 'select') {
                field.options = $element.find('.field-tags-container .tag-text')
                    .map(function () { return $(this).text(); }).get();
            }
            fields.push(field);
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
        const payload = Object.fromEntries(new FormData(form)) as ExperimentFormPayload;
        if (context.mode === 'create' || fields.length > 0) payload.experiment_fields = fields;
        $.ajax({
            url: context.endpoint,
            method: context.method,
            data: JSON.stringify(payload),
            contentType: 'application/json; charset=utf-8',
            cache: false,
            beforeSend(xhr) {
                xhr.setRequestHeader('X-CSRFToken', $('input[name^=csrfmiddlewaretoken]').val() as string);
            },
            success(data: { id: EntityId }) {
                FormModals.showSuccess(context.successMessage);
                window.setTimeout(() => {
                    if (context.redirectRoute) window.location.href = route(context.redirectRoute, data.id);
                    else window.location.reload();
                }, 2000);
            },
            error: showAjaxErrorModal,
        });
        return false;
    });
}
