import { init } from './entity-crud.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterEach(() => { $(document).off(); $(window).off('click'); $('body').off(); document.body.innerHTML = ''; vi.useRealTimers(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

function page() { document.body.innerHTML = '<form id="entity"><input name="csrfmiddlewaretoken" value="csrf"><input name="name" value="Fleet"><input name="description" value="Description"><input type="checkbox" name="email_on_projects_updates" checked><input type="checkbox" name="email_on_speleodb_updates"><button id="btn_submit" type="button">Save</button></form><button id="add_sensor_btn">Add</button><div id="sensors_container"></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div> '; }

it('collects trimmed sensor rows after required-name validation and posts the generated fleet DTO', async () => {
    page(); server.reply({ status: 201, json: { id: 'fleet' } });
    await init({ resource: 'sensor-fleet', formId: 'entity', sensorRows: true, requiredField: 'name', requiredMessage: 'Name required' });
    $('#add_sensor_btn').trigger('click'); $('#add_sensor_btn').trigger('click');
    $('.sensor-name').first().val(' Sensor A '); $('.sensor-notes').first().val(' Notes ');
    $('[name=name]').val(' '); $('#btn_submit').trigger('click');
    expect($('#modal_error_txt').text()).toBe('Name required'); expect(server.requests).toHaveLength(0);
    $('[name=name]').val('Fleet'); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect($('#modal_success').css('display')).toBe('flex'));
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/sensor-fleets/' });
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ name: 'Fleet', description: 'Description', sensors: [{ name: 'Sensor A', notes: 'Notes' }] });
    $('.remove-sensor-btn').first().trigger('click'); expect($('.sensor-item')).toHaveLength(1);
});

it('serializes checked and unchecked preferences as JSON booleans', async () => {
    page(); await init({ resource: 'preferences', formId: 'entity', serializeCheckboxes: true });
    $('#btn_submit').trigger('click'); await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    expect(server.requests[0]).toMatchObject({ method: 'PATCH', path: '/api/v2/user/' });
    expect(server.requests[0]!.headers['x-csrftoken']).toBe('csrf');
    expect(server.requests[0]!.headers['content-type']).toContain('application/json');
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ email_on_projects_updates: true, email_on_speleodb_updates: false });
});

it('selects the generated update operation from resource and entity identifier', async () => {
    page(); await init({ resource: 'surface-network', entityId: 'network /1', formId: 'entity' });
    $('#btn_submit').trigger('click'); await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    expect(server.requests[0]).toMatchObject({ method: 'PUT', path: '/api/v2/surface-networks/network%20%2F1/' });
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ name: 'Fleet', description: 'Description' });
});
