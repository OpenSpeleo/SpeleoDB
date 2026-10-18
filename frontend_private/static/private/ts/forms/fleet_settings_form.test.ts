import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div id="modal_error"><span id="modal_error_txt"></span></div><div id="modal_success"><span id="modal_success_txt"></span></div>';
});
afterEach(() => {
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
    vi.useRealTimers();
});

import { attachFleetSettingsForm } from './fleet_settings_form.ts';

it('requires save and cancels blank names before calling it', () => {
    expect(() => attachFleetSettingsForm({} as never)).toThrow('save is required');
    document.body.insertAdjacentHTML('beforeend', '<input id="name" value="   "><input id="description"><button id="btn_submit">Save</button>');
    const $ = jqueryHost.jQuery;
    const save = vi.fn(async () => ({}));
    attachFleetSettingsForm({ save });
    $('#btn_submit').trigger('click');
    expect(save).not.toHaveBeenCalled();
    expect($('#modal_error_txt').text()).toBe('Fleet name is required.');
});

it('trims configured fields before saving and schedules deferred reload', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input name="csrfmiddlewaretoken" value="fleet-csrf"><input id="name" value=" Fleet "><input id="description" value=" Desc "><button id="btn_submit">Save</button>');
    const $ = jqueryHost.jQuery;
    const save = vi.fn(async (_payload: { name: string; description: string }) => ({}));
    attachFleetSettingsForm({ save, successMessage: 'Saved fleet', reloadDelayMs: 70 });
    $('#btn_submit').trigger('click');
    expect(save).toHaveBeenCalledWith({ name: 'Fleet', description: 'Desc' });
    await Promise.resolve();
    expect($('#modal_success_txt').text()).toBe('Saved fleet');
    expect(vi.getTimerCount()).toBe(1);
});
