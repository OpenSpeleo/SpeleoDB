import type { Mock } from 'vitest';
import type { PublicGISContext } from '../../ts-types/controllers/public-gis.ts';
import { init as initialize } from './public-gis.ts';
import { configureRuntimeContext as importedconfigureRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';
import { initPublicGISViewer as importedinitPublicGISViewer } from '../../frontend_public/static/ts/gis_view_main.ts';

vi.mock('../../frontend_private/static/private/ts/map_viewer/runtime_context.ts', () => ({ configureRuntimeContext: vi.fn() }));
vi.mock('../../frontend_public/static/ts/gis_view_main.ts', () => ({ initPublicGISViewer: vi.fn() }));

beforeEach(() => {
    configureRuntimeContext.mockReset();
    initPublicGISViewer.mockReset();
});

afterEach(() => {
    vi.restoreAllMocks();
});

it('configures context synchronously and awaits the lazy viewer without a window-load wait', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    let finish!: (value: unknown) => void;
    initPublicGISViewer.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const context = { viewMode: 'public', gisToken: 'token' };
    let settled = false;
    const pending = init(context).then(result => { settled = true; return result; });
    expect(configureRuntimeContext).toHaveBeenCalledExactlyOnceWith(context);
    expect(configureRuntimeContext.mock.calls[0]![0]).toBe(context);
    expect(initPublicGISViewer).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(initPublicGISViewer).toHaveBeenCalledExactlyOnceWith());
    expect(settled).toBe(false);
    finish('viewer-result');
    await expect(pending).resolves.toBeUndefined();
});

it('repeats initialization and forwards missing context without controller validation', async () => {
    await init({ viewMode: 'public' });
    await init();
    expect(configureRuntimeContext.mock.calls[1]![0]).toBeUndefined();
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
    configureRuntimeContext.mockImplementation(() => { throw error; });
    await expect(init({})).rejects.toBe(error);
    expect(initPublicGISViewer).not.toHaveBeenCalled();
});

const configureRuntimeContext = importedconfigureRuntimeContext as unknown as Mock<(context: unknown) => unknown>;

const initPublicGISViewer = importedinitPublicGISViewer as unknown as Mock<() => unknown>;

function init(context?: unknown) { return initialize(context as PublicGISContext); }
