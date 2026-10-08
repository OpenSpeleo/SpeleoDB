import { captureInitialControllerState, initializeController, initializeControllers, readControllerContext } from './app.ts';

const controller = vi.hoisted(() => ({ init: vi.fn<(context: unknown, element: HTMLElement) => unknown>() }));
vi.mock('./controllers/private-navigation.ts', () => controller);
vi.mock('./controllers/projects.ts', () => ({ init: 'not callable' }));

function declaration(name = 'private-navigation', context = '{}') {
    const element = document.createElement('script');
    element.type = 'application/json';
    element.dataset.speleodbController = name;
    element.textContent = context;
    document.body.append(element);
    return element;
}

beforeEach(() => {
    document.body.innerHTML = '';
    controller.init.mockReset();
});

afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
});

describe('Vite application bootstrap', () => {
    it('parses inert JSON controller context', () => {
        const element = document.createElement('script');
        element.dataset.speleodbController = 'example';
        element.textContent = '{"enabled":true,"count":2}';
        expect(readControllerContext(element)).toEqual({ enabled: true, count: 2 });
    });

    it('rejects executable or malformed controller context', () => {
        const element = document.createElement('script');
        element.dataset.speleodbController = 'example';
        element.textContent = 'window.alert(1)';
        expect(() => readControllerContext(element)).toThrow(
            'Invalid JSON context for controller "example"'
        );
    });

    it('captures parser-time particle dimensions before lazy controllers load', () => {
        const container = document.createElement('div');
        const canvas = document.createElement('canvas');
        canvas.dataset.particleAnimation = '';
        Object.defineProperties(container, {
            offsetWidth: { value: 640 },
            offsetHeight: { value: 480 },
        });
        container.append(canvas);
        document.body.append(container);

        captureInitialControllerState(document);

        expect(canvas.dataset.initialParticleWidth).toBe('640');
        expect(canvas.dataset.initialParticleHeight).toBe('480');
    });

    it('uses text context before data context and preserves JSON primitive results', () => {
        const element = declaration();
        element.dataset.speleodbContext = '{"source":"attribute"}';
        element.textContent = '  ';
        expect(readControllerContext(element)).toEqual({ source: 'attribute' });
        element.textContent = 'null';
        expect(readControllerContext(element)).toBeNull();
        element.textContent = 'false';
        expect(readControllerContext(element)).toBe(false);
    });

    it('retains malformed JSON as the context error cause', () => {
        const element = declaration('private-navigation', '{');
        expect(() => readControllerContext(element)).toThrow(expect.objectContaining({
            message: 'Invalid JSON context for controller "private-navigation"',
            cause: expect.any(SyntaxError) as unknown,
        }));
    });

    it('marks success before dispatch, bubbles readiness from the element, and ignores returned cleanup', async () => {
        const element = declaration('private-navigation', '{"value":1}');
        const cleanup = vi.fn();
        controller.init.mockReturnValue(cleanup);
        const ready = vi.fn((event: Event) => {
            expect(event.target).toBe(element);
            expect((event as CustomEvent<unknown>).detail).toEqual({ name: 'private-navigation' });
            void initializeController(element);
        });
        document.body.addEventListener('speleodb:controller-ready', ready, { once: true });
        await expect(initializeController(element)).resolves.toBeUndefined();
        await initializeController(element);
        expect(controller.init).toHaveBeenCalledExactlyOnceWith({ value: 1 }, element);
        expect(ready).toHaveBeenCalledOnce();
        expect(cleanup).not.toHaveBeenCalled();
    });

    it('allows overlapping initialization until the first call succeeds', async () => {
        const element = declaration();
        let finish!: () => void;
        const pending = new Promise<void>(resolve => { finish = resolve; });
        controller.init.mockReturnValue(pending);
        const first = initializeController(element);
        await vi.waitFor(() => expect(controller.init).toHaveBeenCalledOnce());
        const second = initializeController(element);
        await vi.waitFor(() => expect(controller.init).toHaveBeenCalledTimes(2));
        const ready = vi.fn();
        element.addEventListener('speleodb:controller-ready', ready);
        finish();
        await Promise.all([first, second]);
        expect(ready).toHaveBeenCalledTimes(2);
    });

    it('propagates direct failures, keeps failed elements retryable, and isolates discovery failures', async () => {
        const error = new Error('Initialization failed');
        const element = declaration();
        controller.init.mockRejectedValueOnce(error);
        await expect(initializeController(element)).rejects.toBe(error);
        controller.init.mockResolvedValue(undefined);
        await initializeController(element);
        expect(controller.init).toHaveBeenCalledTimes(2);

        const missing = declaration('unknown');
        const valid = declaration();
        const failure = vi.fn();
        missing.addEventListener('speleodb:controller-error', failure);
        const logged = vi.spyOn(console, 'error').mockImplementation(() => {});
        await expect(initializeControllers()).resolves.toBeUndefined();
        expect(logged).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({
            message: 'Unknown SpeleoDB controller: "unknown"',
        }));
        expect(failure).toHaveBeenCalledWith(expect.objectContaining({
            target: missing, bubbles: true,
            detail: { name: 'unknown', error: logged.mock.calls[0]![0] as unknown },
        }));
        expect(controller.init).toHaveBeenLastCalledWith({}, valid);
    });

    it('awaits each controller before starting the next declaration', async () => {
        const first = declaration('private-navigation', '{"order":1}');
        const second = declaration('private-navigation', '{"order":2}');
        let finish!: () => void;
        controller.init.mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve; }));
        const pending = initializeControllers();
        await vi.waitFor(() => expect(controller.init).toHaveBeenCalledExactlyOnceWith({ order: 1 }, first));
        finish();
        await pending;
        expect(controller.init).toHaveBeenNthCalledWith(2, { order: 2 }, second);
    });
});

it('retains the missing-init module error without marking its element ready', async () => {
    const element = declaration('projects');
    const ready = vi.fn();
    element.addEventListener('speleodb:controller-ready', ready);
    await expect(initializeController(element)).rejects.toThrow('SpeleoDB controller "projects" does not export init()');
    await expect(initializeController(element)).rejects.toThrow('SpeleoDB controller "projects" does not export init()');
    expect(ready).not.toHaveBeenCalled();
});
