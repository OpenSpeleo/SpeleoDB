import { afterWindowLoad } from '../readiness.ts';
import { initColorPicker } from '../../frontend_private/static/private/ts/color-picker.ts';
import { attachEntityCrudForm } from '../../frontend_private/static/private/ts/forms/entity_crud_form.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';
import type { CreatedEntity, EntityCrudContext, EntityRedirectRoute } from '../../ts-types/controllers/entity-crud.ts';
import type { FormPayload } from '../../ts-types/domain/forms/crud.ts';

const COLOR_PICKER_OPTIONS = {
    preview: '#color-preview',
    hiddenInput: '#color-value',
    nativePicker: '#color-picker',
    pickerBtn: '#color-picker-btn',
    hexInput: '#color-hex-input',
    presets: '.color-preset',
};

function collectSensors() {
    const sensors: Array<{ name: string; notes: string }> = [];
    $('.sensor-item').each(function () {
        const name = ($(this).find('.sensor-name').val() as string).trim();
        const notes = ($(this).find('.sensor-notes').val() as string).trim();
        if (name) sensors.push({ name, notes });
    });
    return sensors;
}

function initSensorRows() {
    let sensorIdCounter = 0;
    $('#add_sensor_btn').on('click', function () {
        sensorIdCounter += 1;
        $('#sensors_container').append(`
            <div class="bg-srgb-slate-700-50 rounded-lg p-4 border border-slate-600 sensor-item" data-sensor-id="${sensorIdCounter}">
                <div class="flex flex-col sm:flex-row sm:items-start gap-3">
                    <div class="flex-1">
                        <label class="block text-xs font-medium text-slate-400 mb-1">Sensor Name <span class="text-rose-600">*</span></label>
                        <input type="text" class="sensor-name form-input w-full" placeholder="e.g., Flow Meter #023" />
                    </div>
                    <div class="flex-1">
                        <label class="block text-xs font-medium text-slate-400 mb-1">Notes</label>
                        <textarea class="sensor-notes form-textarea w-full" rows="2" placeholder="Optional notes"></textarea>
                    </div>
                    <div class="flex flex-col gap-2 mt-5 sm:mt-0">
                        <button type="button" class="remove-sensor-btn btn-sm bg-rose-500 hover:bg-rose-600 text-white">
                            <svg class="w-3 h-3 fill-current inline-block" viewBox="0 0 16 16">
                                <path d="M5 7h6a1 1 0 010 2H5a1 1 0 010-2z" />
                            </svg>
                            Remove
                        </button>
                    </div>
                </div>
            </div>
        `);
    });
    $(document).on('click', '.remove-sensor-btn', function () {
        $(this).closest('.sensor-item').remove();
    });
}

function redirectFromRoute(routeName?: EntityRedirectRoute) {
    if (!routeName) return undefined;
    return (response: CreatedEntity) => {
        const route = window.Urls?.[routeName];
        if (typeof route !== 'function') {
            throw new Error(`Missing Django URL route: ${routeName}`);
        }
        return route(response.id);
    };
}

export async function init(context: EntityCrudContext) {
    await afterWindowLoad();

    if (context.colorPicker) initColorPicker(COLOR_PICKER_OPTIONS);
    if (context.sensorRows) initSensorRows();

    const beforeSubmit = context.requiredField || context.sensorRows
        ? (payload: FormPayload) => {
            if (context.requiredField) {
                const value = payload[context.requiredField];
                if (!value || !(value as string).trim()) {
                    FormModals.showError(context.requiredMessage as string);
                    return false;
                }
            }
            if (context.sensorRows) {
                const sensors = collectSensors();
                if (sensors.length > 0) payload.sensors = sensors;
            }
            return true;
        }
        : undefined;

    const serialize = context.serializeCheckboxes
        ? (payload: FormPayload) => {
            $(`#${context.formId}`).find('input[type=checkbox]').each(function () {
                payload[$(this).attr('name') as string] = $(this).is(':checked');
            });
            return JSON.stringify(payload);
        }
        : undefined;

    attachEntityCrudForm({
        formId: context.formId,
        endpoint: context.endpoint,
        method: context.method,
        successMessage: context.successMessage,
        successRedirect: context.successRedirect,
        reloadOnSuccess: context.reloadOnSuccess,
        redirectFromResponse: redirectFromRoute(context.redirectRoute),
        beforeSubmit,
        serialize,
    });
}
