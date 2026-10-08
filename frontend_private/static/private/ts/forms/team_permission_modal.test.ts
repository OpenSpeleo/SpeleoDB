import { readFileSync } from 'node:fs';
import path from 'node:path';
import { attachTeamPermissionModal } from './team_permission_modal.ts';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
let originalAjax: FormTestJQuery['ajax'];

beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    vi.useFakeTimers();
    originalAjax = jqueryHost.jQuery.ajax;
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
    jqueryHost.jQuery.ajax = originalAjax;
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
    vi.useRealTimers();
});

it('requires an endpoint and returns undefined after wiring', () => {
    expect(() => attachTeamPermissionModal({})).toThrow('attachTeamPermissionModal: endpoint is required');
    expect(attachTeamPermissionModal({ endpoint: '/teams/' })).toBeUndefined();
});

it('adds the assigned team as inert option text, locks edit selection, and unlocks add mode', () => {
    attachTeamPermissionModal({ endpoint: '/teams/' });
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

it('preserves beforeSend field validation and CSRF while serializing PUT', () => {
    const $ = jqueryHost.jQuery;
    $.ajax = vi.fn(options => {
        const setRequestHeader = vi.fn();
        expect(options.beforeSend({ setRequestHeader })).toBe(true);
        expect(setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'csrf-team');
        return {};
    });
    attachTeamPermissionModal({ endpoint: '/teams/' });
    $('.btn_open_edit_perm').trigger('click');
    $('#btn_submit_add').trigger('click');
    const request = $.ajax.mock.calls[0]![0];
    expect(request.method).toBe('PUT');
    expect(JSON.parse(request.data!) as unknown).toEqual({ team: 'assigned', level: 'READ_ONLY' });
});

it('guards duplicate deletion and permits retry after the original error callback', () => {
    const $ = jqueryHost.jQuery;
    $.ajax = vi.fn(() => ({}));
    attachTeamPermissionModal({ endpoint: '/teams/' });
    $('.btn_delete_perm').trigger('click').trigger('click');
    expect($.ajax).toHaveBeenCalledTimes(1);
    const request = $.ajax.mock.calls[0]![0];
    expect(request.method).toBe('DELETE');
    request.error({ responseJSON: { detail: 'Denied' }, status: 403 });
    $('.btn_delete_perm').trigger('click');
    expect($.ajax).toHaveBeenCalledTimes(2);
});

it.each([
    ['', 'READ_ONLY', 'The team is empty!'],
    ['available', '', 'The Access Level field is empty!'],
])('sets CSRF before rejecting team=%s and level=%s', (team, level, message) => {
    const $ = jqueryHost.jQuery;
    $.ajax = vi.fn(() => ({}));
    attachTeamPermissionModal({ endpoint: '/teams/' });
    $('#btn_open_add_team').trigger('click');
    $('#team').val(team);
    $('#level').val(level);
    $('#btn_submit_add').trigger('click');
    const request = $.ajax.mock.calls[0]![0];
    const header = vi.fn();
    expect(request.beforeSend({ setRequestHeader: header })).toBe(false);
    expect(header).toHaveBeenCalledWith('X-CSRFToken', 'csrf-team');
    expect(document.getElementById('modal_error_txt')!.textContent).toBe(message);
});

it('captures CSRF and serialized fields at click time but validates fields at beforeSend time', () => {
    const $ = jqueryHost.jQuery;
    $.ajax = vi.fn(() => ({}));
    attachTeamPermissionModal({ endpoint: '/teams/' });
    $('.btn_open_edit_perm').trigger('click');
    $('#btn_submit_add').trigger('click');
    $('input[name=csrfmiddlewaretoken]').val('changed');
    $('#level').val('');
    const request = $.ajax.mock.calls[0]![0];
    const header = vi.fn();
    expect(request.beforeSend({ setRequestHeader: header })).toBe(false);
    expect(header).toHaveBeenCalledWith('X-CSRFToken', 'csrf-team');
    expect(JSON.parse(request.data!) as unknown).toEqual({ team: 'assigned', level: 'READ_ONLY' });
});
