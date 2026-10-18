import { init } from './fleet.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterEach(() => { $(document).off(); $(window).off('click'); $('body').off(); document.body.innerHTML = ''; vi.useRealTimers(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

function page() { document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="csrf"><input id="name" value=" Fleet "><input id="description" value=" Notes "><button id="btn_submit">Save</button><button class="toggle-sensor-btn" data-sensor-id="sensor /1">Toggle</button><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div> '; }

it.each(['cylinder', 'sensor'] as const)('saves %s fleet settings through its generated update operation', async kind => {
    page(); await init({ kind, mode: 'details', fleetId: 'fleet', settings: true, settingsMessage: 'Saved' });
    vi.useFakeTimers(); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect($('#modal_success_txt').text()).toBe('Saved'));
    expect(server.requests[0]).toMatchObject({ method: 'PUT', path: `/api/v2/${kind}-fleets/fleet/`, headers: { 'x-csrftoken': 'csrf' } });
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ name: 'Fleet', description: 'Notes' });
});

it('keeps missing fleet names local and enables retry after a server rejection', async () => {
    page(); server.reply({ status: 403, json: { detail: 'Denied' } });
    await init({ kind: 'sensor', mode: 'details', fleetId: 'fleet', settings: true });
    $('#name').val(' '); $('#btn_submit').trigger('click');
    expect($('#modal_error_txt').text()).toBe('Fleet name is required.'); expect(server.requests).toHaveLength(0);
    $('#name').val('Fleet'); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toBe('Denied'));
});

it('uses the generated functional-state operation for the selected sensor', async () => {
    page(); server.reply({ status: 403, json: { detail: 'Denied' } });
    await init({ kind: 'sensor', mode: 'details', fleetId: 'fleet' }); $('.toggle-sensor-btn').trigger('click');
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toBe('Denied'));
    expect(server.requests[0]).toMatchObject({ method: 'PATCH', path: '/api/v2/sensors/sensor%20%2F1/toggle-functional/' });
});
