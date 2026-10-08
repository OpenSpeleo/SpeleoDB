import type { Mock } from 'vitest';
import type { PermissionModalContext } from '../../ts-types/controllers/permission-modal.ts';
import { init as initialize } from './permission-modal.ts';
import { attachPermissionModal } from '../../frontend_private/static/private/ts/forms/permission_modal.ts';

vi.mock('../../frontend_private/static/private/ts/forms/permission_modal.ts', () => ({
    attachPermissionModal: vi.fn(),
}));

// The double deliberately returns values ignored by the real controller.
const attachment = vi.mocked(attachPermissionModal) as unknown as Mock<(options: unknown) => unknown>;
function init(context?: unknown) { return initialize(context as PermissionModalContext); }

beforeEach(() => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    attachment.mockReset();
});

afterEach(() => {
    vi.restoreAllMocks();
});

it('waits for load before forwarding the original context once', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const context = { endpoint: '/fixture/' };
    const pending = init(context);
    expect(attachment).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    expect(attachment).toHaveBeenCalledExactlyOnceWith(context);
    expect(attachment.mock.calls[0]![0]).toBe(context);
});

it('repeats initialization and forwards missing context without controller validation', async () => {
    const context = { endpoint: '/fixture/' };
    await init(context);
    await init(context);
    await init();
    expect(attachment.mock.calls.map(([argument]) => argument)).toEqual([context, context, undefined]);
});

it('rejects when the owned helper throws', async () => {
    const error = new Error('Attachment failed');
    attachment.mockImplementation(() => { throw error; });
    await expect(init({})).rejects.toBe(error);
});

it('ignores helper return values and does not await a returned promise', async () => {
    attachment.mockReturnValue(new Promise(() => {}));
    await expect(init({})).resolves.toBeUndefined();
});
