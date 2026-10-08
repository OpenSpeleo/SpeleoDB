import { MAP_ICON_URLS } from '@speleodb/map-viewer/icons';
import type { Mock } from 'vitest';
import type { PrivateMapContext } from '../../ts-types/controllers/private-map.ts';
import { init as initialize } from './private-map.ts';
import { DataImport as importedDataImport } from '../../frontend_private/static/private/ts/data_import.ts';
import { configureRuntimeContext as importedconfigureRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';
import { initPrivateMapViewer as importedinitPrivateMapViewer } from '../../frontend_private/static/private/ts/map_viewer/main.ts';

vi.mock('../../frontend_private/static/private/ts/data_import.ts', () => ({ DataImport: { init: vi.fn() } }));
vi.mock('../../frontend_private/static/private/ts/map_viewer/runtime_context.ts', async importOriginal => {
    const actual = await importOriginal<typeof import('../../frontend_private/static/private/ts/map_viewer/runtime_context.ts')>();
    return { ...actual, configureRuntimeContext: vi.fn(actual.configureRuntimeContext) };
});
vi.mock('../../frontend_private/static/private/ts/map_viewer/main.ts', () => ({ initPrivateMapViewer: vi.fn() }));

beforeEach(() => {
    configureRuntimeContext.mockReset();
    initPrivateMapViewer.mockReset();
    DataImport.init.mockReset();
    document.body.innerHTML = '<img id="cylinder-modal-icon" src="/original.svg">';
});

afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
});

it('configures context immediately, updates the icon before viewer initialization and awaits it before imports', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    let finish!: () => void;
    const viewerReady = new Promise<void>(resolve => { finish = resolve; });
    const context = { csrfToken: 'csrf', icons: { cylinderOrange: '/orange.svg' } };
    initPrivateMapViewer.mockImplementation(() => {
        expect(document.getElementById('cylinder-modal-icon')!.getAttribute('src')).toBe('/orange.svg');
        return viewerReady;
    });
    const pending = init(context);
    expect(configureRuntimeContext).toHaveBeenCalledExactlyOnceWith(context);
    expect(configureRuntimeContext.mock.calls[0]![0]).toBe(context);
    expect(initPrivateMapViewer).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(initPrivateMapViewer).toHaveBeenCalledExactlyOnceWith());
    expect(DataImport.init).not.toHaveBeenCalled();
    finish();
    await expect(pending).resolves.toBeUndefined();
    expect(DataImport.init).toHaveBeenCalledExactlyOnceWith('csrf');
    expect(DataImport.init.mock.contexts[0]).toBe(DataImport);
});

it('uses the shared icon when context has no override and allows missing DOM', async () => {
    await init({ csrfToken: 'first' });
    expect(document.getElementById('cylinder-modal-icon')!.getAttribute('src')).toBe(MAP_ICON_URLS.cylinder);
    document.body.innerHTML = '';
    await init({ csrfToken: 'second', icons: { cylinderOrange: '/orange.svg' } });
    expect(initPrivateMapViewer).toHaveBeenCalledTimes(2);
    expect(DataImport.init.mock.calls).toEqual([['first'], ['second']]);
});

it.each(['throw', 'reject'])('propagates a viewer %s and does not initialize imports', async kind => {
    const error = new Error('Map failed');
    if (kind === 'throw') initPrivateMapViewer.mockImplementation(() => { throw error; });
    else initPrivateMapViewer.mockRejectedValue(error);
    await expect(init({})).rejects.toBe(error);
    expect(DataImport.init).not.toHaveBeenCalled();
});

it('stops before loading the viewer when context configuration throws', async () => {
    const error = new Error('Context failed');
    configureRuntimeContext.mockImplementation(() => { throw error; });
    await expect(init({})).rejects.toBe(error);
    expect(initPrivateMapViewer).not.toHaveBeenCalled();
});

it('propagates synchronous import initialization errors but ignores returned promises', async () => {
    DataImport.init.mockReturnValue(new Promise(() => {}));
    await expect(init({})).resolves.toBeUndefined();
    const error = new Error('Imports failed');
    DataImport.init.mockImplementation(() => { throw error; });
    await expect(init({})).rejects.toBe(error);
});

const configureRuntimeContext = importedconfigureRuntimeContext as unknown as Mock<(context: unknown) => unknown>;

const initPrivateMapViewer = importedinitPrivateMapViewer as unknown as Mock<() => unknown>;

const DataImport = importedDataImport as unknown as { init: Mock<(csrfToken: string) => unknown> };

function init(context?: unknown) { return initialize(context as PrivateMapContext); }
