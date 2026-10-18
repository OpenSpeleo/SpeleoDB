import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { attachAuthForm, validateEmail } from './auth_form.ts';
import type { AuthFormOptions, AuthPayload } from '../../../ts-types/domain/auth.ts';

const operation = vi.fn(async (_payload: AuthPayload): Promise<unknown> => ({}));

beforeAll(() => { (0, eval)(readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8')); });
beforeEach(() => {
    operation.mockReset().mockResolvedValue({});
    document.body.innerHTML = '<form id="auth"><input name="email" value="diver@example.com"><input name="csrfmiddlewaretoken" value="csrf"><button id="btn_submit" type="button">Submit</button></form><div id="error_div"></div><div id="success_div"></div>';
});
afterEach(() => { document.body.innerHTML = ''; });

function submit(options: Partial<AuthFormOptions> = {}) {
    attachAuthForm({ formId: 'auth', submit: operation, ...options });
    $('#btn_submit').triggerHandler('click');
}
async function settled() {
    await new Promise(resolve => setTimeout(resolve, 0));
}

it('requires form and callback in that order and tolerates an absent submit button', () => {
    expect(() => attachAuthForm({} as never)).toThrow('attachAuthForm: formId is required');
    expect(() => attachAuthForm({ formId: 'auth' } as never)).toThrow('attachAuthForm: submit is required');
    expect(attachAuthForm({ formId: 'auth', submit: operation, submitBtnId: 'absent' })).toBeUndefined();
    expect(operation).not.toHaveBeenCalled();
});

it('runs beforeSubmit before validators and passes the validated typed payload to submit', async () => {
    const order: string[] = [];
    let sharedPayload: AuthPayload;
    let sharedData: FormData;
    submit({
        beforeSubmit(payload, data) {
            order.push('before'); sharedPayload = payload; sharedData = data;
            payload.email = 'validated@example.com'; data.set('email', 'form-only@example.com');
            delete payload.csrfmiddlewaretoken;
        },
        validators: [(payload, data) => {
            order.push('validate'); expect(payload).toBe(sharedPayload); expect(data).toBe(sharedData);
            expect(payload.email).toBe('validated@example.com'); return null;
        }],
    });
    expect(order).toEqual(['before', 'validate']);
    await settled();
    expect(operation).toHaveBeenCalledWith({ email: 'validated@example.com' });
});

it('cancels only for explicit false beforeSubmit and stops after the first failing validator', async () => {
    const validate = vi.fn<NonNullable<AuthFormOptions['validators']>[number]>();
    submit({ beforeSubmit: () => false, validators: [validate] });
    expect(validate).not.toHaveBeenCalled();
    $('#btn_submit').off('click');
    submit({ beforeSubmit: () => undefined, validators: [() => '<b>Required</b>', validate] });
    await settled();
    expect(validate).not.toHaveBeenCalled(); expect(operation).not.toHaveBeenCalled();
    expect($('#error_div').text()).toBe('<b>Required</b>'); expect($('#error_div b')).toHaveLength(0);
});

it('uses an explicit success callback or the configured inline text', async () => {
    const onSuccess = vi.fn();
    submit({ onSuccess });
    await settled();
    expect(onSuccess).toHaveBeenCalledWith(); expect($('#success_div').text()).toBe('');
    $('#btn_submit').off('click');
    submit({ successMessage: '<b>Done</b>' });
    await settled();
    expect($('#success_div').text()).toBe('<b>Done</b>'); expect($('#success_div b')).toHaveLength(0);
});

it('handles 401 as success before custom errors without invoking onSuccess', async () => {
    const onSuccess = vi.fn(); const errorHandler = vi.fn();
    operation.mockRejectedValue({ status: 401 });
    submit({ treat401AsSuccess: true, onSuccess, errorHandler, successMessage: 'Sent' });
    await settled();
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
])('preserves default error precedence for %j', async (data, message) => {
    // These malformed wire bodies intentionally exercise the defensive catch path.
    operation.mockRejectedValue({ status: 400, data });
    submit();
    await settled();
    expect($('#error_div').text()).toBe(message);
});

it('retains custom error text, fallback and safe presentation if a handler throws', async () => {
    const handler = vi.fn<NonNullable<AuthFormOptions['errorHandler']>>(() => '<img src=x>');
    operation.mockRejectedValue({ status: 400, data: { error: 'fallback' } });
    submit({ errorHandler: handler });
    await settled();
    expect($('#error_div').text()).toBe('<img src=x>'); expect($('#error_div img')).toHaveLength(0);
    handler.mockReturnValue(null);
    $('#btn_submit').triggerHandler('click');
    await settled();
    expect($('#error_div').text()).toBe('fallback');
    handler.mockImplementation(() => { throw new Error('handler'); });
    $('#btn_submit').triggerHandler('click');
    await settled();
    expect($('#error_div').text()).toBe('There has been an error ...');
});

it('renders synchronous request-building failures through the error policy', async () => {
    submit({ submit: () => { throw new Error('Invalid payload'); }, errorHandler: () => 'Invalid request' });
    await settled();
    expect($('#error_div').text()).toBe('Invalid request');
});

it('repeated attachments retain duplicate requests and the click cancellation return', async () => {
    attachAuthForm({ formId: 'auth', submit: operation });
    attachAuthForm({ formId: 'auth', submit: operation });
    expect($('#btn_submit').triggerHandler('click')).toBe(false);
    await settled();
    expect(operation).toHaveBeenCalledTimes(2);
});

it('preserves email regular-expression coercion and invalid input behavior', () => {
    expect(validateEmail('diver@example.com')).toBe(true);
    expect(validateEmail(null)).toBe(false);
    expect(validateEmail({ toString: () => 'diver@example.com' })).toBe(true);
    expect(() => validateEmail(Symbol('email'))).toThrow(TypeError);
});
