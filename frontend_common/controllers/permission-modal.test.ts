import { init } from './permission-modal.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterEach(() => { $(document).off(); $('body').off(); document.body.innerHTML = ''; vi.useRealTimers(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

function page() { document.body.innerHTML = `<input name="csrfmiddlewaretoken" value="csrf-permission"><button id="btn_open_add_user">Add</button><button class="btn_delete_perm" data-user="person@example.test">Delete</button><div id="permission_modal" style="display:none"><h2 id="permission_modal_title"></h2><h3 id="permission_modal_header"></h3><form id="permission_form"><input id="user" name="user"><div id="user_suggestions"></div><select id="level" name="level"><option value="READ_ONLY">Read</option></select><button id="btn_submit_add">Save</button></form></div><div id="error_div"></div><div id="success_div"></div><div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div>`; }

it('creates a user permission through generated JSON with current CSRF', async () => {
    page(); server.reply({ status: 201, json: {} });
    await init({ resource: 'project', entityId: 'project' });
    vi.useFakeTimers();
    $('#btn_open_add_user').trigger('click');
    $('#user').val('person@example.test');
    $('#btn_submit_add').trigger('click');
    await vi.waitFor(() => expect($('#modal_success').css('display')).toBe('flex'));
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/projects/project/permission/user/detail/', headers: { 'x-csrftoken': 'csrf-permission' } });
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ user: 'person@example.test', level: 'READ_ONLY' });
});

it('revokes the selected user and preserves rejected responses for retry', async () => {
    page(); server.reply({ status: 403, json: { detail: 'Denied' } });
    await init({ resource: 'project', entityId: 'project' });
    $('.btn_delete_perm').trigger('click');
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toBe('Denied'));
    expect(server.requests[0]).toMatchObject({ method: 'DELETE', path: '/api/v2/projects/project/permission/user/detail/' });
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ user: 'person@example.test' });
    expect($('.btn_delete_perm').hasClass('disabled')).toBe(false);
});
