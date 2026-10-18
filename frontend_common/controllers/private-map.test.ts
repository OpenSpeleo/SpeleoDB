import { MAP_ICON_URLS } from '@speleodb/map-viewer/icons';
import { init } from './private-map.ts';
import { getRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';
import { initPrivateMapViewer } from '../../frontend_private/static/private/ts/map_viewer/main.ts';

// JSDOM cannot create the WebGL context required by MapLibre. Only the renderer
// entrypoint is replaced here; runtime context and the import UI remain real.
vi.mock('../../frontend_private/static/private/ts/map_viewer/main.ts', () => ({ initPrivateMapViewer: vi.fn() }));

beforeEach(() => {
    vi.mocked(initPrivateMapViewer).mockReset();
    document.body.innerHTML = '<img id="cylinder-modal-icon" src="/original.svg">';
});
afterEach(() => { document.body.replaceChildren(); });

it('configures the real runtime context and updates the icon before awaiting the renderer', async () => {
    let finish!: () => void;
    const ready = new Promise<void>(resolve => { finish = resolve; });
    vi.mocked(initPrivateMapViewer).mockImplementation(() => {
        expect(document.getElementById('cylinder-modal-icon')!.getAttribute('src')).toBe('/orange.svg');
        return ready;
    });
    const pending = init({ csrfToken: 'csrf', icons: { cylinderOrange: '/orange.svg' } });
    expect(getRuntimeContext().csrfToken).toBe('csrf');
    await vi.waitFor(() => { expect(initPrivateMapViewer).toHaveBeenCalledOnce(); });
    finish();
    await expect(pending).resolves.toBeUndefined();
});

it('uses the shared default icon and permits pages without the optional icon or import modal', async () => {
    await init({ csrfToken: 'first' });
    expect(document.getElementById('cylinder-modal-icon')!.getAttribute('src')).toBe(MAP_ICON_URLS.cylinder);
    document.body.replaceChildren();
    await expect(init({ csrfToken: 'second' })).resolves.toBeUndefined();
    expect(getRuntimeContext().csrfToken).toBe('second');
});

it('propagates renderer initialization failure', async () => {
    const error = new Error('Map failed');
    vi.mocked(initPrivateMapViewer).mockRejectedValue(error);
    await expect(init({ csrfToken: '' })).rejects.toBe(error);
});
