import { init } from './mutex-lock.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterEach(() => { $(document).off(); $('body').off(); document.body.innerHTML = ''; vi.useRealTimers(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

function page() { document.body.innerHTML = `<input name="csrfmiddlewaretoken" value="csrf-lock"><button id="btn_lock_project">Lock</button><button class="btn_unlock">Unlock</button><div id="error_div"></div><div id="success_div"></div><div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div>`; }

it('wires only allowed actions and blocks duplicates while the generated request is pending', async () => {
    page();
    server.reply({ status: 403, json: { detail: 'Denied' } });
    await init({ projectId: 'project/id', canAcquire: true });
    $('.btn_unlock').trigger('click');
    expect(server.requests).toHaveLength(0);
    $('#btn_lock_project').trigger('click').trigger('click');
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toBe('Denied'));
    expect(server.requests).toHaveLength(1);
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/projects/project%2Fid/acquire/', headers: { 'x-csrftoken': 'csrf-lock' } });
    expect($('#btn_lock_project').prop('disabled')).toBe(false);
});

it('uses the generated release request and preserves the success message', async () => {
    page();
    await init({ projectId: 'project', canRelease: true, reloadDelayMs: 2000 });
    vi.useFakeTimers();
    $('.btn_unlock').trigger('click');
    await vi.waitFor(() => expect($('#modal_success').css('display')).toBe('flex'));
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/projects/project/release/', body: '{}' });
    expect($('#modal_success_txt').text()).toContain('unlocked');
});
