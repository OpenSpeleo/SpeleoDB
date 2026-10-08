import type { AuthFormOptions } from '../../ts-types/domain/auth.ts';
import type { Mock } from 'vitest';
import type { AuthFormContext } from '../../ts-types/controllers/auth-form.ts';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './auth-form.ts';
import { attachAuthForm, validateEmail } from '../../frontend_public/static/ts/auth_form.ts';

vi.mock('../../frontend_public/static/ts/auth_form.ts', async importOriginal => {
    const original = await importOriginal<typeof import('../../frontend_public/static/ts/auth_form.ts')>();
    return { ...original, attachAuthForm: vi.fn() };
});

const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');

beforeAll(() => {
    (0, eval)(jquery);
});

// The double deliberately returns values ignored by the real controller.
const attachment = vi.mocked(attachAuthForm) as unknown as Mock<(options: AuthFormOptions) => unknown>;
function init(context?: unknown) { return initialize(context as AuthFormContext); }

beforeEach(() => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    attachment.mockReset();
    document.body.innerHTML = '<div id="cave_diver_modal" style="display:none"><button id="cave_diver_modal_close">Close</button></div>';
});

afterEach(() => {
    $(window).off('click');
    vi.restoreAllMocks();
    document.body.innerHTML = '';
    window.history.replaceState(null, '', '/');
});

it.each(['login', 'signup', 'password-reset', 'password-reset-from-key'])('waits for load before attaching %s with the configured endpoint and form', async mode => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init({ mode, formId: 'auth-form', endpoint: '/auth/', successMessage: 'Done' });
    expect(attachment).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    expect(attachment).toHaveBeenCalledOnce();
    expect(attachment.mock.calls[0]![0]).toMatchObject({ formId: 'auth-form', endpoint: '/auth/' });
});

it('preserves login validation ordering and redirects on success', async () => {
    await init({ mode: 'login', successRedirect: '#signed-in' });
    const options = attachment.mock.calls[0]![0];
    const [validate] = options.validators! as Array<(payload: unknown) => unknown>;
    expect(validate!({})).toBe('The Email Address is not valid !');
    expect(validate!({ email: 'invalid', password: 'value' })).toBe('The Email Address is not valid !');
    expect(validateEmail('valid@example.com')).toBe(true);
    expect(validate!({ email: 'valid@example.com' })).toBe('The Password field is empty !');
    expect(validate!({ email: 'valid@example.com', password: 'value' })).toBeNull();
    options.onSuccess!();
    expect(window.location.hash).toBe('#signed-in');
});

it('distinguishes login verification and inactive errors while delegating other statuses', async () => {
    await init({ mode: 'login' });
    const { errorHandler } = attachment.mock.calls[0]![0];
    expect(errorHandler!({ status: 403, responseJSON: { data: {} } })).toBeNull();
    expect(errorHandler!({ status: 401 })).toBeNull();
    expect(errorHandler!({ status: 401, responseJSON: { data: { flows: [{ id: 'verify_email' }] } } }))
        .toBe('Your email is not verified. We just resent you an activation link on your email.');
    expect(errorHandler!({ status: 401, responseJSON: { data: {} } }))
        .toBe('Your account is inactive. If you believe this is an error, please contact us.');
});

it('checks the signup marker before submission and removes only a valid marker from both payloads', async () => {
    await init({ mode: 'signup', successMessage: 'Registered' });
    const options = attachment.mock.calls[0]![0];
    expect(options.treat401AsSuccess).toBe(true);
    expect(options.successMessage).toBe('Registered');
    const payload = { cave_marker: '  arrow  ', email: 'valid@example.com' };
    const formData = new FormData();
    formData.set('cave_marker', payload.cave_marker);
    formData.set('email', payload.email);
    expect(options.beforeAjax!({ cave_marker: 'line' }, formData)).toBe(false);
    expect(document.getElementById('cave_diver_modal')!.style.display).not.toBe('none');
    expect(formData.has('cave_marker')).toBe(true);
    document.getElementById('cave_diver_modal_close')!.click();
    expect(document.getElementById('cave_diver_modal')!.style.display).toBe('none');
    expect(options.beforeAjax!(payload, formData)).toBe(true);
    expect(payload).toEqual({ email: 'valid@example.com' });
    expect([...formData.entries()]).toEqual([['email', 'valid@example.com']]);
    options.beforeAjax!({}, formData);
    document.getElementById('cave_diver_modal')!.click();
    expect(document.getElementById('cave_diver_modal')!.style.display).toBe('none');
});

it('preserves signup name/email/password validation precedence', async () => {
    await init({ mode: 'signup' });
    const [validate] = attachment.mock.calls[0]![0].validators! as Array<(payload: unknown) => unknown>;
    expect(validate!({})).toBe('The `name` field is empty !');
    expect(validate!({ name: 'Diver' })).toBe('The Email Address is not valid !');
    const identity = { name: 'Diver', email: 'valid@example.com' };
    expect(validate!(identity)).toBe('One of the `password` fields is empty !');
    expect(validate!({ ...identity, password: 'first', password2: 'second' })).toBe('Password fields do not match !');
    expect(validate!({ ...identity, password: 'same', password2: 'same' })).toBeNull();
});

it('keeps reset modes separate and enables 401 success only for the key-based reset', async () => {
    await init({ mode: 'password-reset', successMessage: 'Sent' });
    const reset = attachment.mock.calls[0]![0];
    expect(reset).not.toHaveProperty('treat401AsSuccess');
    expect(reset.validators![0]!({ email: 'valid@example.com' }, new FormData())).toBeNull();
    expect(reset.validators![0]!({}, new FormData())).toBe('The Email Address is not valid !');
    await init({ mode: 'password-reset-from-key', successMessage: 'Updated' });
    const fromKey = attachment.mock.calls[1]![0];
    expect(fromKey.treat401AsSuccess).toBe(true);
    expect(fromKey.validators![0]!({ password: 'same', password2: 'same' }, new FormData())).toBeNull();
    expect(fromKey.validators![0]!({ password: 'same' }, new FormData())).toBe('One of the `password` fields is empty !');
});

it('rejects unsupported or missing context and propagates helper errors', async () => {
    await expect(init({ mode: 'absent' })).rejects.toThrow('Unsupported auth form mode: absent');
    await expect(init()).rejects.toThrow(TypeError);
    expect(attachment).not.toHaveBeenCalled();
    const error = new Error('Attachment failed');
    attachment.mockImplementation(() => { throw error; });
    await expect(init({ mode: 'login' })).rejects.toBe(error);
});

it('repeats attachments and ignores helper promise results', async () => {
    attachment.mockReturnValue(new Promise(() => {}));
    await expect(init({ mode: 'login' })).resolves.toBeUndefined();
    await expect(init({ mode: 'login' })).resolves.toBeUndefined();
    expect(attachment).toHaveBeenCalledTimes(2);
});
