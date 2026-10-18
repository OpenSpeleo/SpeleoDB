import { init } from './danger-zone.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterEach(() => { $(document).off(); $('body').off(); document.body.innerHTML = ''; vi.useRealTimers(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

function page() { document.body.innerHTML = `<input name="csrfmiddlewaretoken" value="csrf-delete"><button id="btn_delete">Delete</button><div id="modal_confirmation" style="display:none"><button id="btn_confirmed_delete">Confirm</button></div><div id="error_div"></div><div id="success_div"></div><div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div>`; }

it.each([['project', 'projects'], ['team', 'teams']] as const)('deletes %s through its generated operation only after confirmation', async (resource, path) => {
    page();
    await init({ resource, entityId: 'entity/id', successMessage: 'Removed' });
    $('#btn_delete').trigger('click');
    expect($('#modal_confirmation').css('display')).toBe('flex');
    expect(server.requests).toHaveLength(0);
    $('#btn_confirmed_delete').trigger('click');
    await vi.waitFor(() => expect($('#modal_success_txt').text()).toBe('Removed'));
    expect(server.requests).toHaveLength(1);
    expect(server.requests[0]).toMatchObject({ method: 'DELETE', path: `/api/v2/${path}/entity%2Fid/`, headers: { 'x-csrftoken': 'csrf-delete' } });
});

it('presents rejected delete errors as inert text', async () => {
    page();
    server.reply({ status: 403, json: { detail: '<img src=x> denied' } });
    await init({ resource: 'project', entityId: 'project' });
    $('#btn_confirmed_delete').trigger('click');
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toBe('<img src=x> denied'));
    expect($('#modal_error_txt img')).toHaveLength(0);
    expect($('#modal_success').css('display')).toBe('none');
});
