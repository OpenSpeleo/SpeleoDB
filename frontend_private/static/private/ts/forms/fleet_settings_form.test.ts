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

import { attachFleetSettingsForm } from './fleet_settings_form.ts';

it('requires endpoint and cancels blank names before AJAX', () => {
    expect(() => attachFleetSettingsForm({})).toThrow('endpoint is required');
    document.body.insertAdjacentHTML('beforeend', '<input id="name" value="   "><input id="description"><button id="btn_submit">Save</button>');
    const $ = jqueryHost.jQuery;
    $.ajax = vi.fn();
    attachFleetSettingsForm({ endpoint: '/fleet/' });
    $('#btn_submit').trigger('click');
    expect($.ajax).not.toHaveBeenCalled();
    expect($('#modal_error_txt').text()).toBe('Fleet name is required.');
});

it('trims configured fields and PUTs them with CSRF before deferred reload', () => {
    document.body.insertAdjacentHTML('beforeend', '<input name="csrfmiddlewaretoken" value="fleet-csrf"><input id="name" value=" Fleet "><input id="description" value=" Desc "><button id="btn_submit">Save</button>');
    const $ = jqueryHost.jQuery;
    $.ajax = vi.fn(() => ({}));
    attachFleetSettingsForm({ endpoint: '/fleet/', successMessage: 'Saved fleet', reloadDelayMs: 70 });
    $('#btn_submit').trigger('click');
    const request = $.ajax.mock.calls[0]![0];
    expect(request).toMatchObject({ method: 'PUT', headers: { 'X-CSRFToken': 'fleet-csrf' } });
    expect(JSON.parse(request.data!) as unknown).toEqual({ name: 'Fleet', description: 'Desc' });
    request.success();
    expect($('#modal_success_txt').text()).toBe('Saved fleet');
    expect(vi.getTimerCount()).toBe(1);
});
