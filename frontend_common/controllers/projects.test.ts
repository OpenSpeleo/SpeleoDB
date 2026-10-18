import type { MockInstance } from 'vitest';
import { init } from './projects.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
import { showApiErrorModal } from '../../frontend_private/static/private/ts/forms/api_errors.ts';

vi.mock('../../frontend_private/static/private/ts/forms/api_errors.ts', () => ({ showApiErrorModal: vi.fn() }));

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
let timer: MockInstance<typeof window.setTimeout>;
const context = { projectsUrl: '#projects' };

beforeAll(async () => {
    originalUrl = window.location.href;
    loadJQuery();
    server = await startApiServer();
});
beforeEach(() => {
    vi.clearAllMocks();
    server.reset();
    server.reply({ json: [{ id: '7', commit_count: 0 }] });
    setBrowserUrl(`${server.origin}/private/projects/`);
    timer = vi.spyOn(window, 'setTimeout');
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
    localStorage.clear();
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="csrf"><button id="btn_release_all_locks"></button><button id="btn_confirmed_mass_unlock"></button><button class="btn-unlock" data-project_id="7"></button><button id="btn_confirmed_unlock"></button><div id="modal_confirmation_mass_unlock" style="display:none"></div><div id="modal_confirmation_unlock" style="display:none"></div><div id="modal_success"><span id="modal_success_txt"></span></div><span class="async_revision" data-id="revision-7" data-project_id="7"></span><span id="revision-7"></span><span class="async_revision" data-id="revision-8" data-project_id="8"></span><span id="revision-8"></span><div class="country-group" data-country-code="MX"><button class="country-group-header"></button></div>';
});
afterEach(() => {
    for (const [index, args] of timer.mock.calls.entries()) {
        if (args[1] === 2000) window.clearTimeout(timer.mock.results[index]?.value as ReturnType<typeof window.setTimeout>);
    }
    $('body').off('click');
    vi.restoreAllMocks();
    document.body.innerHTML = '';
});
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

async function initialize() {
    expect(init(context)).toBeUndefined();
    await vi.waitFor(() => expect($('#revision-8').text()).toBe('-'));
}

it('fetches revision counts immediately and renders missing records as a dash', async () => {
    await initialize();
    expect(server.requests[0]).toMatchObject({ method: 'GET', path: '/api/v2/projects/' });
    expect($('#revision-7').text()).toBe('0');
    expect($('#revision-8').text()).toBe('-');
});

it.each([
    { status: 200, json: { error: 'Unexpected response' } },
    { status: 503, json: { detail: 'Unavailable' } },
])('renders dashes when revision loading receives $status with no project list', async reply => {
    server.reply(reply);
    await initialize();
    expect($('#revision-7').text()).toBe('-');
});

it('opens mass confirmation and sends DELETE with CSRF, shared errors and delayed redirect', async () => {
    await initialize();
    $('#btn_release_all_locks').trigger('click');
    expect($('#modal_confirmation_mass_unlock')[0]!.style.display).toBe('flex');
    server.reply({ status: 403, json: { detail: 'Denied' } });
    $('#btn_confirmed_mass_unlock').trigger('click');
    await vi.waitFor(() => expect(showApiErrorModal).toHaveBeenCalledWith(expect.objectContaining({ status: 403, data: { detail: 'Denied' } })));
    expect(server.requests[1]).toMatchObject({ method: 'DELETE', path: '/api/v2/user/release_all_locks/', headers: { 'x-csrftoken': 'csrf' }, body: '' });

    server.reply({ json: {} });
    $('#btn_confirmed_mass_unlock').trigger('click');
    await vi.waitFor(() => expect($('#modal_success_txt').text()).toBe('All the projects have been unlocked.'));
    expect(timer).toHaveBeenCalledWith(expect.any(Function), 2000);
});

it('uses the clicked project ID in the subsequent single-project POST', async () => {
    await initialize();
    $('.btn-unlock').trigger('click');
    expect($('#btn_confirmed_unlock').data('project_id')).toBe(7);
    server.reply({ json: {} });
    $('#btn_confirmed_unlock').trigger('click');
    await vi.waitFor(() => expect($('#modal_success_txt').text()).toBe('The project has been unlocked for edition.'));
    expect(server.requests[1]).toMatchObject({ method: 'POST', path: '/api/v2/projects/7/release/', headers: { 'x-csrftoken': 'csrf', 'content-type': 'application/json' }, body: '{}' });
});

it('toggles country collapse using click and keyboard and writes the existing storage key', async () => {
    await initialize();
    $('.country-group-header').trigger('click');
    expect($('.country-group').hasClass('collapsed')).toBe(true);
    expect(JSON.parse(localStorage.getItem('speleo_projects_collapsed_countries')!) as unknown).toEqual(['MX']);
    const event = $.Event('keydown', { key: ' ' });
    $('.country-group-header').trigger(event);
    expect(event.isDefaultPrevented()).toBe(true);
    expect($('.country-group').hasClass('collapsed')).toBe(false);
    expect(JSON.parse(localStorage.getItem('speleo_projects_collapsed_countries')!) as unknown).toEqual([]);
});

it('tolerates invalid stored JSON and denied writes and repeats handlers when reinitialized', async () => {
    localStorage.setItem('speleo_projects_collapsed_countries', '{');
    await initialize();
    $('.country-group-header').trigger('click');
    expect($('.country-group').hasClass('collapsed')).toBe(true);
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('Unavailable'); });
    expect(() => $('.country-group-header').trigger('click')).not.toThrow();
    $('#revision-8').text('');
    await initialize();
    $('.country-group-header').trigger('click');
    expect($('.country-group').hasClass('collapsed')).toBe(false);
    expect(server.requests).toHaveLength(2);
});
