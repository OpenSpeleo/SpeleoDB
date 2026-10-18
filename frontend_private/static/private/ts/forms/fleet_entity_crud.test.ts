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

import { attachFleetEntityCrud } from './fleet_entity_crud.ts';

function controls(): void {
    document.body.insertAdjacentHTML('beforeend', '<input name="csrfmiddlewaretoken" value="fleet-csrf"><button id="add">Add</button><button class="edit" data-entity-id="123">Edit</button><div id="entity_modal" class="hidden"><button id="save">Save</button></div>');
}

it('retains required-option errors and lets the collector cancel or throw before transport', () => {
    expect(() => attachFleetEntityCrud({} as never)).toThrow('modalSelector required');
    controls();
    const $ = jqueryHost.jQuery;
    const update = vi.fn(async () => ({}));
    const collect = vi.fn(() => null);
    attachFleetEntityCrud({ modalSelector: '#entity_modal', saveButtonSelector: '#save', update, collectPayload: collect });
    $('#save').trigger('click');
    expect(collect).toHaveBeenCalledWith(false);
    expect(update).not.toHaveBeenCalled();
    collect.mockImplementation(() => { throw new Error('Invalid fleet item'); });
    $('#save').trigger('click');
    expect($('#modal_error_txt').text()).toBe('Invalid fleet item');
});

it('keeps editing identity attachment-local and passes the original button into population', () => {
    controls();
    const $ = jqueryHost.jQuery;
    const update = vi.fn(async (_id: string | number, _payload: { name: string }) => ({}));
    const create = vi.fn(async (_payload: { name: string }) => ({}));
    const populate = vi.fn();
    const reset = vi.fn();
    const collect = vi.fn(() => ({ name: 'Item' }));
    attachFleetEntityCrud({ modalSelector: '#entity_modal', saveButtonSelector: '#save', update, collectPayload: collect,
        editButtonSelector: '.edit', populateForEdit: populate, addButtonSelector: '#add', resetForCreate: reset, create });
    $('.edit').trigger('click');
    $('#save').trigger('click');
    expect(collect).toHaveBeenLastCalledWith(true);
    expect(populate).toHaveBeenCalledWith(expect.objectContaining({ 0: document.querySelector('.edit') }));
    expect(update).toHaveBeenCalledWith(123, { name: 'Item' });
    $('#add').trigger('click');
    $('#save').trigger('click');
    expect(reset).toHaveBeenCalledOnce();
    expect(collect).toHaveBeenLastCalledWith(false);
    expect(create).toHaveBeenCalledWith({ name: 'Item' });
});
