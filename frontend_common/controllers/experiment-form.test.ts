import { readFileSync } from 'node:fs';
import type { ExperimentFormContext } from '../../ts-types/controllers/experiment-form.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

let init: typeof import('./experiment-form.ts').init;
beforeAll(async () => {
    (0, eval)(readFileSync('frontend_private/static/private/ts/vendors/Sortable.min.js', 'utf8'));
    ({ init } = await import('./experiment-form.ts'));
});
beforeEach(() => {
    server.reply({ status: 201, json: { id: 'experiment' } });
    document.body.innerHTML = '<form id="experiment"><input name="name" value="Experiment"><input name="code" value="EXP"><input name="description" value="Notes"><input name="csrfmiddlewaretoken" value="csrf"></form><button id="btn_submit"></button><div id="all_fields_container"></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div>';
});
afterEach(() => { $(document).off(); document.body.innerHTML = ''; vi.useRealTimers(); });
const context: ExperimentFormContext = { mode: 'create', formId: 'experiment', successMessage: 'Saved' };
const mandatory = '<div class="mandatory-field-item" data-field-name="Date" data-field-type="date" data-field-required="true"></div><div class="mandatory-field-item" data-field-name="Email" data-field-type="text" data-field-required="true"></div>';
function choice(name = 'Choice') { return `<div class="field-item"><input class="field-name" value=" ${name} "><select class="field-type"><option value="select">Select</option></select><input type="checkbox" class="field-required" checked><div class="field-tags-container"><span class="tag-text">Low</span><span class="tag-text">High</span></div></div>`; }

it('rejects incomplete, duplicate and missing custom fields before HTTP', async () => {
    $('#all_fields_container').html(mandatory); await init(context);
    $('#btn_submit').trigger('click'); expect($('#modal_error_txt').text()).toContain('at least one custom field');
    $('#all_fields_container').append(choice('')); $('#btn_submit').trigger('click');
    expect($('#modal_error_txt').text()).toContain('name');
    $('.field-name').val('Choice'); $('#all_fields_container').append(choice()); $('#btn_submit').trigger('click');
    expect($('#modal_error_txt').text()).toContain('Duplicate'); expect(server.requests).toHaveLength(0);
});

it('sends ordered mandatory and custom fields as generated JSON with request-time CSRF', async () => {
    $('#all_fields_container').html(mandatory + choice()); await init(context);
    vi.useFakeTimers(); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect($('#modal_success_txt').text()).toBe('Saved'));
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/experiments/', headers: { 'x-csrftoken': 'csrf' } });
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ name: 'Experiment', code: 'EXP', description: 'Notes', start_date: null, end_date: null, experiment_fields: [{ name: 'Date', type: 'date', required: true }, { name: 'Email', type: 'text', required: true }, { name: 'Choice', type: 'select', required: true, options: ['Low', 'High'] }] });
});

it('preserves existing field identifiers and omits fields when editing an empty list', async () => {
    server.reply({ json: { id: 'experiment' } });
    $('#all_fields_container').html('<div class="existing-field-item" data-field-id="field" data-field-type="select" data-field-required="true"><input class="existing-field-name" value=" Existing "></div>');
    $('.existing-field-item').data('field-options', '["A","B"]');
    await init({ ...context, mode: 'edit', experimentId: 'experiment' });
    vi.useFakeTimers(); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    expect(server.requests[0]).toMatchObject({ method: 'PUT', path: '/api/v2/experiments/experiment/' });
    expect(JSON.parse(server.requests[0]!.body)).toMatchObject({ experiment_fields: [{ id: 'field', name: 'Existing', type: 'select', required: true, options: ['A', 'B'] }] });
    $('#all_fields_container').empty(); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect(server.requests).toHaveLength(2));
    expect(JSON.parse(server.requests[1]!.body)).not.toHaveProperty('experiment_fields');
});
