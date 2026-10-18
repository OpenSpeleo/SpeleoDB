import { init } from './gis-view-form.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterEach(() => { $(document).off(); $(window).off('click'); $('body').off(); document.body.innerHTML = ''; vi.useRealTimers(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

function page() { document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="csrf"><input id="name" value=" GIS "><input id="description" value=" Desc "><input type="checkbox" id="allow_precise_zoom" checked><button id="add_project_btn">Add</button><div id="projects_container"></div><div id="no_projects_message"></div><button id="btn_submit">Save</button><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div> '; }

it.each([undefined, 'view'])('loads projects and selects create/update from view ID %s', async viewId => {
    page();
    server.handle(request => request.method === 'GET' ? { json: [{ id: 'project', name: '<Cave>' }] } : { status: viewId ? 200 : 201, json: { id: 'view' } });
    await init(viewId ? { viewId } : {});
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    // Wait for the list response to populate the control, without replacing its request.
    await vi.waitFor(() => { $('#add_project_btn').trigger('click'); expect($('.project-select option[value=project]')).not.toHaveLength(0); });
    $('.project-select').first().val('project').trigger('change');
    expect($('.project-select option[value=project]').first().text()).toBe('<Cave>');
    expect($('.project-select cave')).toHaveLength(0);
    vi.useFakeTimers(); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect($('#modal_success').css('display')).toBe('flex'));
    expect(server.requests[0]!.path).toBe('/api/v2/projects/');
    const save = server.requests.find(request => request.method !== 'GET')!;
    expect(save).toMatchObject({ method: viewId ? 'PATCH' : 'POST', path: `/api/v2/user/gis_views/${viewId ? 'view/' : ''}` });
    expect(JSON.parse(save.body)).toEqual({ name: 'GIS', description: 'Desc', allow_precise_zoom: true, projects: [{ project_id: 'project', use_latest: true, commit_sha: '' }] });
});
