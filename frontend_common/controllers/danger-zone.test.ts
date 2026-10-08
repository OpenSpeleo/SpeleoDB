import type { Mock } from 'vitest';
import type { DangerZoneContext } from '../../ts-types/controllers/danger-zone.ts';
import { init as initialize } from './danger-zone.ts';
import { attachDangerZone } from '../../frontend_private/static/private/ts/forms/danger_zone.ts';

vi.mock('../../frontend_private/static/private/ts/forms/danger_zone.ts', () => ({
    attachDangerZone: vi.fn(),
}));

// The double intentionally returns values that the real attachment does not.
const attachment = vi.mocked(attachDangerZone) as unknown as Mock<(context?: unknown) => unknown>;
function init(context?: unknown) { return initialize(context as DangerZoneContext); }

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
