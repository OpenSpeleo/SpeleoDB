import { init } from './station-tags.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

const tag = { id: 'tag', name: '<unsafe>', color: '#EF4444', station_count: 1, creation_date: '2026-01-01' };
beforeEach(() => {
    server.handle(request => request.method === 'GET' ? { json: [tag] } : { status: request.method === 'POST' ? 201 : 200, json: tag });
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="csrf"><button id="btn-create-tag">Create</button><table><tbody id="tags-table-body"></tbody></table><div id="tags-cards-container"></div><div id="edit-tag-modal"><form id="edit-tag-form"><input id="edit-tag-id"><input id="edit-tag-name"><input id="edit-tag-color"><input id="custom-color-input" type="color"><div id="edit-tag-color-picker"></div><button type="submit">Save</button></form></div><div id="delete-tag-modal"><input id="delete-tag-id"><div id="delete-tag-info"></div><span id="delete-tag-station-count"></span><button id="btn-confirm-delete">Delete</button></div><div id="modal_error"><span id="modal_error_txt"></span></div><div id="modal_success"><span id="modal_success_txt"></span></div>';
});
afterEach(() => { $(document).off(); document.body.innerHTML = ''; });
async function loaded() { init(); await vi.waitFor(() => expect($('#tags-table-body .btn-edit-tag')).toHaveLength(1)); }
function submit() { $('#edit-tag-form').trigger('submit'); }

it('renders generated tag data as inert text and opens the selected edit/delete modal', async () => {
    await loaded(); expect(server.requests[0]!.path).toBe('/api/v2/station_tags/');
    expect($('#tags-table-body').text()).toContain('<unsafe>'); expect($('unsafe')).toHaveLength(0);
    $('#tags-table-body .btn-edit-tag').trigger('click'); expect($('#edit-tag-id').val()).toBe('tag');
    expect($('.tag-color-picker-option')).toHaveLength(20); expect($('.tag-color-picker-option.selected')).toHaveLength(1);
    $('.tag-color-picker-option').eq(1).trigger('click'); expect($('#edit-tag-color').val()).toBe('#f97316');
    $('#custom-color-input').val('#abcdef').trigger('change'); expect($('#edit-tag-color').val()).toBe('#ABCDEF');
    $('#tags-cards-container .btn-delete-tag').trigger('click');
    expect($('#delete-tag-info').text()).toContain('<unsafe>'); expect($('#delete-tag-info unsafe')).toHaveLength(0);
    expect($('#delete-tag-station-count').text()).toBe('1');
});

it('validates name/color locally and creates a typed tag through generated JSON', async () => {
    await loaded(); $('#btn-create-tag').trigger('click'); $('#edit-tag-name').val(''); submit();
    expect($('#modal_error_txt').text()).toBe('Please enter a tag name');
    $('#edit-tag-name').val(' New '); $('#edit-tag-color').val('#abc'); submit();
    expect($('#modal_error_txt').text()).toContain('Invalid color format');
    expect(server.requests).toHaveLength(1);
    $('#edit-tag-color').val('#abcdef'); submit();
    await vi.waitFor(() => expect(server.requests.some(request => request.method === 'POST')).toBe(true));
    const request = server.requests.find(request => request.method === 'POST')!;
    expect(request.path).toBe('/api/v2/station_tags/'); expect(JSON.parse(request.body)).toEqual({ name: 'New', color: '#abcdef' });
    await vi.waitFor(() => expect(server.requests.filter(request => request.method === 'GET')).toHaveLength(2));
});

it('uses generated PUT and DELETE for the selected tag and reloads the list', async () => {
    await loaded(); $('#tags-table-body .btn-edit-tag').trigger('click'); $('#edit-tag-name').val('Updated'); submit();
    await vi.waitFor(() => expect(server.requests.filter(request => request.method === 'GET')).toHaveLength(2));
    expect(server.requests.find(request => request.method === 'PUT')).toMatchObject({ path: '/api/v2/station_tags/tag/' });
    $('#tags-table-body .btn-delete-tag').trigger('click'); $('#btn-confirm-delete').trigger('click');
    await vi.waitFor(() => expect(server.requests.some(request => request.method === 'DELETE')).toBe(true));
    expect(server.requests.find(request => request.method === 'DELETE')).toMatchObject({ path: '/api/v2/station_tags/tag/' });
});
