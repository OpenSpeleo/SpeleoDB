import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    document.body.innerHTML = '<div id="modal_error"><span id="modal_error_txt"></span></div><div id="modal_success"><span id="modal_success_txt"></span></div>';
});
afterEach(() => {
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
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
    const reload = vi.fn();
    const location = window.location;
    // JSDOM cannot navigate; observe only that boundary while the real delay runs.
    Object.defineProperty(window, 'location', { configurable: true, value: { reload } });
    try {
        attachFleetSettingsForm({ save, successMessage: 'Saved fleet', reloadDelayMs: 70 });
        $('#btn_submit').trigger('click');
        expect(save).toHaveBeenCalledWith({ name: 'Fleet', description: 'Desc' });
        await vi.waitFor(() => expect($('#modal_success_txt').text()).toBe('Saved fleet'));
        expect(reload).not.toHaveBeenCalled();
        await vi.waitFor(() => expect(reload).toHaveBeenCalledOnce());
        expect(save).toHaveBeenCalledOnce();
    } finally {
        Object.defineProperty(window, 'location', { configurable: true, value: location });
    }
});
