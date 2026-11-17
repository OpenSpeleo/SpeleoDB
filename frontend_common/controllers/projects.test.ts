import { init } from './projects.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
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
    localStorage.clear();
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="csrf"><button id="btn_release_all_locks"></button><button id="btn_confirmed_mass_unlock"></button><button class="btn-unlock" data-project_id="7"></button><div id="modal_confirmation_mass_unlock" style="display:none"></div><div id="modal_confirmation_unlock" style="display:none"><div><span id="project-unlock-modal-title"></span><strong id="project-unlock-editor-email"></strong><button id="cancel-unlock">Cancel</button><button id="btn_confirmed_unlock"></button></div></div><div id="modal_success"><span id="modal_success_txt"></span></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><span class="async_revision" data-id="revision-7" data-project_id="7"></span><span id="revision-7"></span><span class="async_revision" data-id="revision-8" data-project_id="8"></span><span id="revision-8"></span><div class="country-group" data-country-code="MX"><button class="country-group-header"></button></div>';
});
afterEach(() => {
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
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toBe('Denied'));
    expect(server.requests[1]).toMatchObject({ method: 'DELETE', path: '/api/v2/user/release_all_locks/', headers: { 'x-csrftoken': 'csrf' }, body: '' });

    server.reply({ json: {} });
    $('#btn_confirmed_mass_unlock').trigger('click');
    await vi.waitFor(() => expect($('#modal_success_txt').text()).toBe('All the projects have been unlocked.'));
    await vi.waitFor(() => expect(window.location.hash).toBe('#projects'), { timeout: 3000 });
});

it.each([false, true])('releases the clicked project with confirmation only for force unlock (%s)', async (forceUnlock) => {
    await initialize();
    server.reply({ json: {} });
    $('.btn-unlock').attr('data-force-unlock', String(forceUnlock)).trigger('click');
    if (forceUnlock) {
        expect($('#modal_confirmation_unlock').css('display')).toBe('flex');
        expect($('#btn_confirmed_unlock').data('project_id')).toBe(7);
        expect(server.requests).toHaveLength(1);
        $('#btn_confirmed_unlock').trigger('click');
    } else {
        expect($('#modal_confirmation_unlock').css('display')).toBe('none');
    }
    await vi.waitFor(() => expect($('#modal_success_txt').text()).toBe('The project has been unlocked for edition.'));
    expect(server.requests[1]).toMatchObject({ method: 'POST', path: '/api/v2/projects/7/release/', headers: { 'x-csrftoken': 'csrf', 'content-type': 'application/json' }, body: '{}' });
});

it('keeps force-unlock email readable and keyboard navigation inside the confirmation until dismissed', async () => {
    await initialize();
    const trigger = document.querySelector<HTMLButtonElement>('.btn-unlock')!;
    const modal = document.getElementById('modal_confirmation_unlock')!;
    const cancel = document.getElementById('cancel-unlock')!;
    const confirm = document.getElementById('btn_confirmed_unlock')!;
    trigger.dataset.forceUnlock = 'true';
    trigger.dataset.editorEmail = '<editor>&example.test';
    trigger.focus();
    trigger.click();
    expect(document.activeElement).toBe(cancel);
    expect(document.getElementById('project-unlock-editor-email')!.textContent).toBe('<editor>&example.test');
    expect(document.querySelector('#project-unlock-editor-email editor')).toBeNull();
    expect(modal.getAttribute('aria-modal')).toBe('true');
    confirm.focus();
    confirm.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(cancel);
    cancel.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(confirm);
    document.getElementById('project-unlock-editor-email')!.click();
    expect(modal.style.display).toBe('flex');
    confirm.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    expect(modal.style.display).toBe('none');
    expect(document.activeElement).toBe(trigger);
    expect(server.requests).toHaveLength(1);
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
    // Exercise browser storage denial, which JSDOM's in-memory storage cannot produce.
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('Unavailable'); });
    expect(() => $('.country-group-header').trigger('click')).not.toThrow();
    $('#revision-8').text('');
    await initialize();
    $('.country-group-header').trigger('click');
    expect($('.country-group').hasClass('collapsed')).toBe(false);
    expect(server.requests).toHaveLength(2);
});
