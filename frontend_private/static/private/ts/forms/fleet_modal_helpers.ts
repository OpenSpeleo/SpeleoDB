import type { SensorPayload } from '../../../../../ts-types/domain/forms/fleet.ts';

import { FormModals } from './modals.ts';

function cylinderDateToMonth(dateString: string | null | undefined) {
    return dateString ? dateString.substring(0, 7) : '';
}

function cylinderMonthToDate(monthString: string | undefined) {
    return monthString ? `${monthString}-01` : null;
}

export function cylinderResetForCreate() {
    $('#modal_cylinder_name').val('');
    $('#modal_cylinder_serial').val('');
    $('#modal_cylinder_brand').val('');
    $('#modal_cylinder_owner').val('');
    $('#modal_cylinder_type').val('');
    $('#modal_cylinder_notes').val('');
    $('#modal_cylinder_o2').val('21');
    $('#modal_cylinder_he').val('0');
    $('#modal_cylinder_pressure').val('');
    $('#modal_cylinder_unit_system').val('imperial');
    $('#modal_cylinder_status').val('functional');
    $('#modal_cylinder_manufactured_date').val('');
    $('#modal_cylinder_visual_date').val('');
    $('#modal_cylinder_hydro_date').val('');
    $('#modal_cylinder_use_anode').prop('checked', false);
}

export function cylinderPopulateForEdit($button: JQuery<HTMLElement>) {
    $('#modal_cylinder_name').val(($button.data('cylinder-name') as string | undefined) || '');
    $('#modal_cylinder_serial').val(($button.data('cylinder-serial') as string | undefined) || '');
    $('#modal_cylinder_brand').val(($button.data('cylinder-brand') as string | undefined) || '');
    $('#modal_cylinder_owner').val(($button.data('cylinder-owner') as string | undefined) || '');
    $('#modal_cylinder_type').val(($button.data('cylinder-type') as string | undefined) || '');
    $('#modal_cylinder_notes').val(($button.data('cylinder-notes') as string | undefined) || '');
    $('#modal_cylinder_o2').val(($button.data('cylinder-o2') as string | number | undefined) ?? '');
    $('#modal_cylinder_he').val(($button.data('cylinder-he') as string | number | undefined) ?? '');
    $('#modal_cylinder_pressure').val(($button.data('cylinder-pressure') as string | number | undefined) ?? '');
    $('#modal_cylinder_unit_system').val(($button.data('cylinder-unit-system') as string | undefined) || 'imperial');
    $('#modal_cylinder_status').val(($button.data('cylinder-status') as string | undefined) || 'functional');
    $('#modal_cylinder_manufactured_date').val(cylinderDateToMonth($button.data('cylinder-manufactured-date') as string | null | undefined));
    $('#modal_cylinder_visual_date').val(cylinderDateToMonth($button.data('cylinder-visual-date') as string | null | undefined));
    $('#modal_cylinder_hydro_date').val(cylinderDateToMonth($button.data('cylinder-hydro-date') as string | null | undefined));
    $('#modal_cylinder_use_anode').prop('checked', $button.data('cylinder-use-anode') === true);
}

export function cylinderCollectPayload() {
    const o2 = $('#modal_cylinder_o2').val() as string;
    const he = $('#modal_cylinder_he').val() as string;
    const pressure = $('#modal_cylinder_pressure').val() as string;
    if (!o2 || !he || !pressure) {
        FormModals.showError('O2, He, and Pressure are required.');
        return null;
    }
    return {
        name: ($('#modal_cylinder_name').val() as string).trim(),
        serial: ($('#modal_cylinder_serial').val() as string).trim(),
        brand: ($('#modal_cylinder_brand').val() as string).trim(),
        owner: ($('#modal_cylinder_owner').val() as string).trim(),
        type: ($('#modal_cylinder_type').val() as string).trim(),
        notes: ($('#modal_cylinder_notes').val() as string).trim(),
        o2_percentage: parseInt(o2, 10),
        he_percentage: parseInt(he, 10),
        pressure: parseInt(pressure, 10),
        unit_system: $('#modal_cylinder_unit_system').val(),
        status: $('#modal_cylinder_status').val(),
        manufactured_date: cylinderMonthToDate($('#modal_cylinder_manufactured_date').val() as string | undefined),
        last_visual_inspection_date: cylinderMonthToDate($('#modal_cylinder_visual_date').val() as string | undefined),
        last_hydrostatic_test_date: cylinderMonthToDate($('#modal_cylinder_hydro_date').val() as string | undefined),
        use_anode: $('#modal_cylinder_use_anode').is(':checked'),
    };
}

export function sensorResetForCreate() {
    $('#modal_sensor_name').val('');
    $('#modal_sensor_notes').val('');
    $('#modal_sensor_status').val('functional');
    $('#modal_status_container').addClass('hidden');
}

export function sensorPopulateForEdit($button: JQuery<HTMLElement>) {
    $('#modal_sensor_name').val(($button.data('sensor-name') as string | undefined) || '');
    $('#modal_sensor_notes').val(($button.data('sensor-notes') as string | undefined) || '');
    $('#modal_sensor_status').val(($button.data('sensor-status') as string | undefined) || 'functional');
    $('#modal_status_container').removeClass('hidden');
}

export function sensorCollectPayload(isEdit: boolean) {
    const name = ($('#modal_sensor_name').val() as string).trim();
    const notes = ($('#modal_sensor_notes').val() as string).trim();
    if (!name) {
        FormModals.showError('Sensor name is required.');
        return null;
    }
    const payload: SensorPayload = { name, notes };
    if (isEdit) payload.status = $('#modal_sensor_status').val() as string;
    return payload;
}
