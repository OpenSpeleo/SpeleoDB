import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { attachAuthForm, validateEmail } from './auth_form.ts';
import type { AuthFailure, AuthFormOptions, AuthPayload } from '../../../ts-types/domain/auth.ts';
import type { MockInstance } from 'vitest';

interface AuthRequest {
    beforeSend(xhr: { setRequestHeader(name: string, value: string): void }): boolean;
    success(): void;
    error(xhr: AuthFailure): void;
}
let request: AuthRequest;
let ajax: MockInstance<JQueryStatic['ajax']>;

beforeAll(() => { (0, eval)(readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8')); });
beforeEach(() => {
    document.body.innerHTML = '<form id="auth"><input name="email" value="diver@example.com"><input name="csrfmiddlewaretoken" value="csrf"><button id="btn_submit" type="button">Submit</button></form><div id="error_div"></div><div id="success_div"></div>';
    ajax = vi.spyOn($, 'ajax').mockImplementation(settings => {
        request = settings as unknown as AuthRequest;
        return {} as JQuery.jqXHR<unknown>;
    });
});
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });

function submit(options: AuthFormOptions = {}) {
    attachAuthForm({ formId: 'auth', endpoint: '/auth/', ...options });
    $('#btn_submit').triggerHandler('click');
    return request;
}

it('requires form and endpoint in that order and tolerates an absent submit button', () => {
    expect(() => attachAuthForm({})).toThrow('attachAuthForm: formId is required');
    expect(() => attachAuthForm({ formId: 'auth' })).toThrow('attachAuthForm: endpoint is required');
    expect(attachAuthForm({ formId: 'auth', endpoint: '/auth/', submitBtnId: 'absent' })).toBeUndefined();
    expect(ajax).not.toHaveBeenCalled();
});

it('runs beforeAjax before validators and serializes the mutated FormData, not payload', () => {
    const order: string[] = [];
    let sharedPayload: AuthPayload;
    let sharedData: FormData;
    const settings = submit({
        beforeAjax(payload, data) {
            order.push('before'); sharedPayload = payload; sharedData = data;
            payload.email = 'payload-only@example.com'; data.set('email', 'wire@example.com');
            data.delete('csrfmiddlewaretoken');
        },
        validators: [(payload, data) => {
            order.push('validate'); expect(payload).toBe(sharedPayload); expect(data).toBe(sharedData);
            expect(payload.email).toBe('payload-only@example.com'); return null;
        }],
    });
    expect(order).toEqual(['before', 'validate']);
    expect(settings).toMatchObject({ url: '/auth/', method: 'POST', cache: false, contentType: 'application/json; charset=utf-8', data: '{"email":"wire@example.com"}' });
    const xhr = { setRequestHeader: vi.fn() };
    expect(settings.beforeSend(xhr)).toBe(true);
    expect(xhr.setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'csrf');
});

it('cancels only for explicit false beforeAjax and stops after the first failing validator', () => {
    const validate = vi.fn<NonNullable<AuthFormOptions['validators']>[number]>();
    submit({ beforeAjax: () => false, validators: [validate] });
    expect(validate).not.toHaveBeenCalled(); expect(ajax).not.toHaveBeenCalled();
    $('#btn_submit').off('click');
    submit({ beforeAjax: () => undefined, validators: [() => '<b>Required</b>', validate] });
    expect(validate).not.toHaveBeenCalled(); expect(ajax).not.toHaveBeenCalled();
    expect($('#error_div').text()).toBe('<b>Required</b>'); expect($('#error_div b')).toHaveLength(0);
});

it('uses an explicit success callback or the configured inline text', () => {
    const onSuccess = vi.fn();
    submit({ onSuccess }).success();
    expect(onSuccess).toHaveBeenCalledWith(); expect($('#success_div').text()).toBe('');
    $('#btn_submit').off('click');
    submit({ successMessage: '<b>Done</b>' }).success();
    expect($('#success_div').text()).toBe('<b>Done</b>'); expect($('#success_div b')).toHaveLength(0);
});

it('handles 401 as success before custom errors without invoking onSuccess', () => {
    const onSuccess = vi.fn(); const errorHandler = vi.fn();
    submit({ treat401AsSuccess: true, onSuccess, errorHandler, successMessage: 'Sent' }).error({ status: 401 });
    expect(onSuccess).not.toHaveBeenCalled(); expect(errorHandler).not.toHaveBeenCalled();
    expect($('#success_div').text()).toBe('Sent');
});

it.each([
    [undefined, 'An error occurred. Please try again.'],
    [{ error: 'Primary', errors: [{ message: 'Secondary' }] }, 'Primary'],
    [{ errors: [{ message: 'First' }, { message: 'Second' }] }, 'First'],
    [{ errors: [{}] }, 'An error occurred.'],
    [{ errors: [] }, 'An error occurred. Please try again.'],
    ['invalid', 'There has been an error ...'],
    [{ errors: [null] }, 'There has been an error ...'],
])('preserves default error precedence for %j', (responseJSON, message) => {
    // These malformed wire bodies intentionally exercise the legacy catch path.
    submit().error({ status: 400, responseJSON } as AuthFailure);
    expect($('#error_div').text()).toBe(message);
});

it('retains custom error text, fallback and thrown error behavior', () => {
    const handler = vi.fn<NonNullable<AuthFormOptions['errorHandler']>>(() => '<img src=x>');
    const settings = submit({ errorHandler: handler });
    settings.error({ status: 400, responseJSON: { error: 'fallback' } });
    expect($('#error_div').text()).toBe('<img src=x>'); expect($('#error_div img')).toHaveLength(0);
    handler.mockReturnValue(null); settings.error({ responseJSON: { error: 'fallback' } });
    expect($('#error_div').text()).toBe('fallback');
    const error = new Error('handler'); handler.mockImplementation(() => { throw error; });
    expect(() => settings.error({})).toThrow(error);
});

it('repeated attachments retain duplicate requests and the click cancellation return', () => {
    attachAuthForm({ formId: 'auth', endpoint: '/auth/' });
    attachAuthForm({ formId: 'auth', endpoint: '/auth/' });
    expect($('#btn_submit').triggerHandler('click')).toBe(false);
    expect(ajax).toHaveBeenCalledTimes(2);
});

it('preserves email regular-expression coercion and invalid input behavior', () => {
    expect(validateEmail('diver@example.com')).toBe(true);
    expect(validateEmail(null)).toBe(false);
    expect(validateEmail({ toString: () => 'diver@example.com' })).toBe(true);
    expect(() => validateEmail(Symbol('email'))).toThrow(TypeError);
});
