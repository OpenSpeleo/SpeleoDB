import { readFileSync } from 'node:fs';
import path from 'node:path';
import { attachTeamPermissionModal } from './team_permission_modal.ts';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };

const operations = {
    create: vi.fn(async (_payload: Record<string, unknown>) => ({})),
    update: vi.fn(async (_payload: Record<string, unknown>) => ({})),
    remove: vi.fn(async (_payload: Record<string, unknown>) => ({})),
};

beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    document.body.innerHTML = `
        <input name="csrfmiddlewaretoken" value="csrf-team">
        <button id="btn_open_add_team">Add</button>
        <button class="btn_open_edit_perm" data-team="assigned" data-team-name="Assigned &lt;Team&gt;" data-level="READ_ONLY">Edit</button>
        <button class="btn_delete_perm" data-team="assigned">Delete</button>
        <button class="btn_close">Close</button>
        <div id="permission_modal" style="display:none">
            <h2 id="permission_modal_title"></h2><h3 id="permission_modal_header"></h3>
            <form id="permission_form"><select id="team" name="team"><option value="">Choose</option><option value="available">Available</option></select>
            <select id="level" name="level"><option value="">Choose</option><option value="READ_ONLY">Read only</option></select>
            <button id="btn_submit_add">Save</button></form>
        </div>
        <div id="modal_success"><span id="modal_success_txt"></span></div>
        <div id="modal_error"><span id="modal_error_txt"></span></div>`;
});
afterEach(() => {
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
    vi.useRealTimers();
});

it('requires operations and returns undefined after wiring', () => {
    expect(() => attachTeamPermissionModal({} as never)).toThrow('Permission operations are required');
    expect(attachTeamPermissionModal({ operations })).toBeUndefined();
});

it('adds the assigned team as inert option text, locks edit selection, and unlocks add mode', () => {
    attachTeamPermissionModal({ operations });
    jqueryHost.jQuery('.btn_open_edit_perm').trigger('click');
    const team = document.getElementById('team') as HTMLSelectElement;
    expect(team.value).toBe('assigned');
    expect(team.options[2]?.text).toBe('Assigned <Team>');
    const blocked = new MouseEvent('mousedown', { cancelable: true });
    team.dispatchEvent(blocked);
    expect(blocked.defaultPrevented).toBe(true);
    expect(jqueryHost.jQuery('#permission_form').data('method')).toBe('PUT');
    jqueryHost.jQuery('#btn_open_add_team').trigger('click');
    expect(jqueryHost.jQuery('#permission_form').data('method')).toBe('POST');
    const allowed = new MouseEvent('mousedown', { cancelable: true });
    team.dispatchEvent(allowed);
    expect(allowed.defaultPrevented).toBe(false);
});

it('validates fields and supplies the update operation with form values', () => {
    const $ = jqueryHost.jQuery;
    attachTeamPermissionModal({ operations });
    $('.btn_open_edit_perm').trigger('click');
    $('#btn_submit_add').trigger('click');
    expect(operations.update).toHaveBeenCalledWith({ team: 'assigned', level: 'READ_ONLY' });
    expect(operations.create).not.toHaveBeenCalled();
});

it('guards duplicate deletion and permits retry after operation rejection', async () => {
    const $ = jqueryHost.jQuery;
    let reject!: (error: unknown) => void;
    const remove = vi.fn((_payload: Record<string, unknown>) => new Promise((_resolve, fail) => { reject = fail; }));
    attachTeamPermissionModal({ operations: { ...operations, remove } });
    $('.btn_delete_perm').trigger('click').trigger('click');
    expect(remove).toHaveBeenCalledOnce();
    expect(remove).toHaveBeenCalledWith({ team: 'assigned' });
    reject(Object.assign(new Error('Denied'), { data: { detail: 'Denied' }, status: 403 }));
    await vi.advanceTimersByTimeAsync(0);
    expect($('#modal_error_txt').text()).toBe('Denied');
    $('.btn_delete_perm').trigger('click');
    expect(remove).toHaveBeenCalledTimes(2);
});

it.each([
    ['', 'READ_ONLY', 'The team is empty!'],
    ['available', '', 'The Access Level field is empty!'],
])('rejects team=%s and level=%s before invoking an operation', (team, level, message) => {
    const $ = jqueryHost.jQuery;
    attachTeamPermissionModal({ operations });
    $('#btn_open_add_team').trigger('click');
    $('#team').val(team);
    $('#level').val(level);
    $('#btn_submit_add').trigger('click');
    expect(operations.create).not.toHaveBeenCalled();
    expect(operations.update).not.toHaveBeenCalled();
    expect(document.getElementById('modal_error_txt')!.textContent).toBe(message);
});

it('captures selected fields at click time independently of later edits', () => {
    const $ = jqueryHost.jQuery;
    attachTeamPermissionModal({ operations });
    $('.btn_open_edit_perm').trigger('click');
    $('#btn_submit_add').trigger('click');
    $('#level').val('');
    expect(operations.update).toHaveBeenCalledWith({ team: 'assigned', level: 'READ_ONLY' });
});
