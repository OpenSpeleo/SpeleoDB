import { FormModals } from './modals.js';

function cylinderDateToMonth(dateString) {
    return dateString ? dateString.substring(0, 7) : '';
}

function cylinderMonthToDate(monthString) {
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

export function cylinderPopulateForEdit($button) {
    $('#modal_cylinder_name').val($button.data('cylinder-name') || '');
    $('#modal_cylinder_serial').val($button.data('cylinder-serial') || '');
    $('#modal_cylinder_brand').val($button.data('cylinder-brand') || '');
    $('#modal_cylinder_owner').val($button.data('cylinder-owner') || '');
    $('#modal_cylinder_type').val($button.data('cylinder-type') || '');
    $('#modal_cylinder_notes').val($button.data('cylinder-notes') || '');
    $('#modal_cylinder_o2').val($button.data('cylinder-o2') ?? '');
    $('#modal_cylinder_he').val($button.data('cylinder-he') ?? '');
    $('#modal_cylinder_pressure').val($button.data('cylinder-pressure') ?? '');
    $('#modal_cylinder_unit_system').val($button.data('cylinder-unit-system') || 'imperial');
    $('#modal_cylinder_status').val($button.data('cylinder-status') || 'functional');
    $('#modal_cylinder_manufactured_date').val(cylinderDateToMonth($button.data('cylinder-manufactured-date')));
    $('#modal_cylinder_visual_date').val(cylinderDateToMonth($button.data('cylinder-visual-date')));
    $('#modal_cylinder_hydro_date').val(cylinderDateToMonth($button.data('cylinder-hydro-date')));
    $('#modal_cylinder_use_anode').prop('checked', $button.data('cylinder-use-anode') === true);
}

export function cylinderCollectPayload() {
    const o2 = $('#modal_cylinder_o2').val();
    const he = $('#modal_cylinder_he').val();
    const pressure = $('#modal_cylinder_pressure').val();
    if (!o2 || !he || !pressure) {
        FormModals.showError('O2, He, and Pressure are required.');
        return null;
    }
    return {
        name: $('#modal_cylinder_name').val().trim(),
        serial: $('#modal_cylinder_serial').val().trim(),
        brand: $('#modal_cylinder_brand').val().trim(),
        owner: $('#modal_cylinder_owner').val().trim(),
        type: $('#modal_cylinder_type').val().trim(),
        notes: $('#modal_cylinder_notes').val().trim(),
        o2_percentage: parseInt(o2, 10),
        he_percentage: parseInt(he, 10),
        pressure: parseInt(pressure, 10),
        unit_system: $('#modal_cylinder_unit_system').val(),
        status: $('#modal_cylinder_status').val(),
        manufactured_date: cylinderMonthToDate($('#modal_cylinder_manufactured_date').val()),
        last_visual_inspection_date: cylinderMonthToDate($('#modal_cylinder_visual_date').val()),
        last_hydrostatic_test_date: cylinderMonthToDate($('#modal_cylinder_hydro_date').val()),
        use_anode: $('#modal_cylinder_use_anode').is(':checked'),
    };
}

export function sensorResetForCreate() {
    $('#modal_sensor_name').val('');
    $('#modal_sensor_notes').val('');
    $('#modal_sensor_status').val('functional');
    $('#modal_status_container').addClass('hidden');
}

export function sensorPopulateForEdit($button) {
    $('#modal_sensor_name').val($button.data('sensor-name') || '');
    $('#modal_sensor_notes').val($button.data('sensor-notes') || '');
    $('#modal_sensor_status').val($button.data('sensor-status') || 'functional');
    $('#modal_status_container').removeClass('hidden');
}

export function sensorCollectPayload(isEdit) {
    const name = $('#modal_sensor_name').val().trim();
    const notes = $('#modal_sensor_notes').val().trim();
    if (!name) {
        FormModals.showError('Sensor name is required.');
        return null;
    }
    const payload = { name, notes };
    if (isEdit) payload.status = $('#modal_sensor_status').val();
    return payload;
}
