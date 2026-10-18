import { sendPermissionRequest } from './permission_request.ts';

it('validates before starting the supplied generated-operation callback', () => {
    const request = vi.fn(async () => ({})); const success = vi.fn(); const error = vi.fn();
    sendPermissionRequest({ request, validate: () => false, success, error });
    expect(request).not.toHaveBeenCalled(); expect(success).not.toHaveBeenCalled(); expect(error).not.toHaveBeenCalled();
});

it('settles successful requests through the configured success callback', async () => {
    const request = vi.fn(async () => ({ id: 'permission' })); const success = vi.fn(); const error = vi.fn();
    sendPermissionRequest({ request, validate: () => true, success, error });
    await Promise.resolve(); expect(request).toHaveBeenCalledOnce(); expect(success).toHaveBeenCalledOnce(); expect(error).not.toHaveBeenCalled();
});

it('forwards the original rejection to the error callback', async () => {
    const rejected = Object.assign(new Error('Denied'), { status: 403, data: { detail: 'Denied' } });
    const success = vi.fn(); const error = vi.fn();
    sendPermissionRequest({ request: async () => { throw rejected; }, success, error });
    await Promise.resolve(); expect(error).toHaveBeenCalledWith(rejected); expect(success).not.toHaveBeenCalled();
});
