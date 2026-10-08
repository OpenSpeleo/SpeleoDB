import { sendPermissionRequest } from './permission_request.ts';

afterEach(() => vi.unstubAllGlobals());

it('preserves jQuery callback identities and validation receiver after installing the CSRF header', () => {
    const ajax = vi.fn<(settings: JQuery.AjaxSettings<unknown>) => void>();
    vi.stubGlobal('$', { ajax });
    const context = { url: '/context' };
    const trace: string[] = [];
    const xhr = { setRequestHeader: (name: string, value: string) => { trace.push(`${name}:${value}`); } } as unknown as JQuery.jqXHR<unknown>;
    const success = vi.fn();
    const error = vi.fn();
    sendPermissionRequest({
        endpoint: '/permissions', method: 'PUT', data: '{"level":"READ_ONLY"}', csrfToken: 'captured-token',
        validate: function (receivedXhr, settings) {
            expect(this).toBe(context);
            expect(receivedXhr).toBe(xhr);
            expect(settings).toBe(request);
            trace.push('validate');
            return false;
        },
        success, error,
    });
    const request = ajax.mock.calls[0]![0];
    expect(request.success).toBe(success);
    expect(request.error).toBe(error);
    expect(request.beforeSend!.call(context, xhr, request)).toBe(false);
    expect(trace).toEqual(['X-CSRFToken:captured-token', 'validate']);
    expect(request).toMatchObject({ url: '/permissions', method: 'PUT', cache: false, contentType: 'application/json; charset=utf-8' });
});
