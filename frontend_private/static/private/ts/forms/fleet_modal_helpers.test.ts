import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
let originalAjax: FormTestJQuery['ajax'];
beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    vi.useFakeTimers();
    originalAjax = jqueryHost.jQuery.ajax;
    document.body.innerHTML = '<div id="modal_error"><span id="modal_error_txt"></span></div><div id="modal_success"><span id="modal_success_txt"></span></div>';
});
afterEach(() => {
    jqueryHost.jQuery.ajax = originalAjax;
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
    vi.useRealTimers();
});

import {
    cylinderCollectPayload, cylinderPopulateForEdit, cylinderResetForCreate,
    sensorCollectPayload, sensorPopulateForEdit, sensorResetForCreate,
} from './fleet_modal_helpers.ts';

function cylinderInputs(): void {
    const fields = ['name', 'serial', 'brand', 'owner', 'type', 'notes', 'o2', 'he', 'pressure', 'unit_system', 'status', 'manufactured_date', 'visual_date', 'hydro_date'];
    document.body.insertAdjacentHTML('beforeend', fields.map(field => `<input id="modal_cylinder_${field}">`).join('') + '<input type="checkbox" id="modal_cylinder_use_anode">');
}

it('keeps cylinder create defaults and distinguishes zero strings from missing gas/pressure', () => {
    cylinderInputs();
    cylinderResetForCreate();
    expect(jqueryHost.jQuery('#modal_cylinder_o2').val()).toBe('21');
    expect(jqueryHost.jQuery('#modal_cylinder_he').val()).toBe('0');
    expect(cylinderCollectPayload()).toBeNull();
    jqueryHost.jQuery('#modal_cylinder_pressure').val('0');
    expect(cylinderCollectPayload()).toMatchObject({ o2_percentage: 21, he_percentage: 0, pressure: 0, manufactured_date: null, use_anode: false });
});

it('preserves numeric zero edit values and roundtrips dates through month precision', () => {
    cylinderInputs();
    const button = document.createElement('button');
    button.dataset.cylinderO2 = '0';
    button.dataset.cylinderHe = '0';
    button.dataset.cylinderPressure = '0';
    button.dataset.cylinderName = ' Tank ';
    button.dataset.cylinderManufacturedDate = '2025-03-19';
    button.dataset.cylinderUseAnode = 'true';
    cylinderPopulateForEdit(jqueryHost.jQuery(button));
    expect(cylinderCollectPayload()).toMatchObject({ name: 'Tank', o2_percentage: 0, he_percentage: 0, pressure: 0, manufactured_date: '2025-03-01', use_anode: true });
});

it('omits sensor status during create and keeps it during edit', () => {
    document.body.insertAdjacentHTML('beforeend', '<input id="modal_sensor_name"><input id="modal_sensor_notes"><input id="modal_sensor_status"><div id="modal_status_container"></div>');
    sensorResetForCreate();
    expect(sensorCollectPayload(false)).toBeNull();
    jqueryHost.jQuery('#modal_sensor_name').val(' Sensor ');
    expect(sensorCollectPayload(false)).toEqual({ name: 'Sensor', notes: '' });
    const button = document.createElement('button');
    button.dataset.sensorName = 'Edited';
    button.dataset.sensorStatus = 'broken';
    sensorPopulateForEdit(jqueryHost.jQuery(button));
    expect(sensorCollectPayload(true)).toEqual({ name: 'Edited', notes: '', status: 'broken' });
    expect(jqueryHost.jQuery('#modal_status_container').hasClass('hidden')).toBe(false);
});
