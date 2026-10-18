import { init } from './auth-form.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterEach(() => { $(document).off(); $(window).off('click'); $('body').off(); document.body.innerHTML = ''; vi.useRealTimers(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

function page(fields: Record<string, string>) {
    document.body.innerHTML = '<form id="auth"><button id="btn_submit" type="button">Submit</button></form><div id="error_div"></div><div id="success_div"></div><div id="cave_diver_modal" style="display:none"><button id="cave_diver_modal_close">Close</button></div>';
    for (const [name, value] of Object.entries({ csrfmiddlewaretoken: 'csrf', ...fields })) {
        const input = document.createElement('input'); input.name = name; input.value = value;
        document.querySelector('form')!.append(input);
    }
}

it('validates login before sending generated JSON and redirects on success', async () => {
    page({ email: 'invalid', password: '' });
    await init({ mode: 'login', formId: 'auth', successRedirect: '#signed-in' });
    $('#btn_submit').trigger('click');
    expect($('#error_div').text()).toBe('The Email Address is not valid !');
    $('[name=email]').val('diver@example.test'); $('#btn_submit').trigger('click');
    expect($('#error_div').text()).toBe('The Password field is empty !');
    expect(server.requests).toHaveLength(0);
    $('[name=password]').val('secret'); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect(window.location.hash).toBe('#signed-in'));
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/_allauth/browser/v1/auth/login', headers: { 'x-csrftoken': 'csrf' } });
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ email: 'diver@example.test', password: 'secret' });
});

it.each([
    [{ flows: [{ id: 'verify_email' }] }, 'Your email is not verified.'],
    [{}, 'Your account is inactive.'],
])('presents login 401 flow details', async (data, message) => {
    page({ email: 'diver@example.test', password: 'secret' });
    server.reply({ status: 401, json: { data } });
    await init({ mode: 'login', formId: 'auth' }); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect($('#error_div').text()).toContain(message));
});

it('gates signup on the cave marker and sends only the allauth signup fields', async () => {
    page({ name: 'Diver', email: 'diver@example.test', password: 'secret', password2: 'secret', country: 'US', cave_marker: 'line' });
    server.reply({ status: 401, json: { data: { flows: [{ id: 'verify_email' }] } } });
    await init({ mode: 'signup', formId: 'auth', successMessage: 'Check your email' });
    $('#btn_submit').trigger('click');
    expect($('#cave_diver_modal').css('display')).not.toBe('none'); expect(server.requests).toHaveLength(0);
    $('#cave_diver_modal_close').trigger('click'); expect($('#cave_diver_modal').css('display')).toBe('none');
    $('[name=cave_marker]').val(' arrow '); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect($('#success_div').text()).toBe('Check your email'));
    expect(server.requests[0]!.path).toBe('/_allauth/browser/v1/auth/signup');
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ name: 'Diver', email: 'diver@example.test', password: 'secret', country: 'US' });
});

it.each([
    { mode: 'password-reset' as const, fields: { email: 'diver@example.test' }, path: 'request', status: 200, body: { email: 'diver@example.test' } },
    { mode: 'password-reset-from-key' as const, fields: { key: 'reset-key', password: 'new-password', password2: 'new-password' }, path: 'reset', status: 401, body: { key: 'reset-key', password: 'new-password' } },
])('uses the generated $mode operation', async ({ mode, fields, path, status, body }) => {
    page(fields); server.reply({ status, json: {} });
    await init({ mode, formId: 'auth', successMessage: 'Done' }); $('#btn_submit').trigger('click');
    await vi.waitFor(() => expect($('#success_div').text()).toBe('Done'));
    expect(server.requests[0]!.path).toBe(`/_allauth/browser/v1/auth/password/${path}`);
    expect(JSON.parse(server.requests[0]!.body)).toEqual(body);
});
