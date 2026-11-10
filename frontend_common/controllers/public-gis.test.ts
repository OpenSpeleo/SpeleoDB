import type { Mock } from 'vitest';
import type { PublicGISContext } from '../../ts-types/controllers/public-gis.ts';
import { init as initialize } from './public-gis.ts';
import { getRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';
import { initPublicGISViewer as importedinitPublicGISViewer } from '../../frontend_public/static/ts/gis_view_main.ts';

// JSDOM cannot provide MapLibre's WebGL renderer. Keep context handling real;
// isolate only the rendering entrypoint and its completion/failure boundary.
vi.mock('../../frontend_public/static/ts/gis_view_main.ts', () => ({ initPublicGISViewer: vi.fn() }));

beforeEach(() => {
    initPublicGISViewer.mockReset();
});

it('configures context synchronously and awaits the lazy viewer without a window-load wait', async () => {
    let finish!: (value: unknown) => void;
    initPublicGISViewer.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const context = { viewMode: 'public', gisToken: 'token' };
    let settled = false;
    const pending = init(context).then(result => { settled = true; return result; });
    expect(getRuntimeContext()).toMatchObject(context);
    expect(initPublicGISViewer).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(initPublicGISViewer).toHaveBeenCalledExactlyOnceWith());
    expect(settled).toBe(false);
    finish('viewer-result');
    await expect(pending).resolves.toBeUndefined();
});

it('repeats initialization and forwards missing context without controller validation', async () => {
    await init({ viewMode: 'public' });
    await init();
    expect(getRuntimeContext()).not.toHaveProperty('viewMode');
    expect(initPublicGISViewer).toHaveBeenCalledTimes(2);
});

it.each(['throw', 'reject'])('propagates a viewer %s', async kind => {
    const error = new Error('Public viewer failed');
    if (kind === 'throw') initPublicGISViewer.mockImplementation(() => { throw error; });
    else initPublicGISViewer.mockRejectedValue(error);
    await expect(init({})).rejects.toBe(error);
});

it('stops before the viewer when context configuration throws', async () => {
    const error = new Error('Context failed');
    const context = { get icons() { throw error; } };
    await expect(init(context)).rejects.toBe(error);
    expect(initPublicGISViewer).not.toHaveBeenCalled();
});

const initPublicGISViewer = importedinitPublicGISViewer as unknown as Mock<() => unknown>;

function init(context?: unknown) { return initialize(context as PublicGISContext); }
