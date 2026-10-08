import type { ParticlesRuntime } from '../../ts-types/domain/particles.ts';
import { init } from './error-page.ts';
import { initErrorPage } from '../../frontend_errors/static/ts/error.ts';

const load = vi.fn<ParticlesRuntime['load']>();
beforeEach(() => {
    load.mockReset().mockResolvedValue({ id: 'particles-instance' });
    document.body.innerHTML = '<div id="tsparticles"></div>';
    vi.stubGlobal('tsParticles', { load });
});

afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
});

it('starts immediately without context or load readiness and retains the vendor receiver', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init();
    expect(load).toHaveBeenCalledOnce();
    expect(load.mock.contexts[0]).toBe(tsParticles);
    expect(load).toHaveBeenCalledWith('tsparticles', expect.objectContaining({ fpsLimit: 60, detectRetina: true }));
    await expect(pending).resolves.toBeUndefined();
});

it('waits for vendor completion while the helper returns the original promise', async () => {
    let finish!: (value: unknown) => void;
    const vendorResult = new Promise(resolve => { finish = resolve; });
    load.mockReturnValue(vendorResult);
    expect(initErrorPage()).toBe(vendorResult);
    let settled = false;
    const pending = init().then(() => { settled = true; });
    await Promise.resolve();
    expect(settled).toBe(false);
    finish({ id: 'particles-instance' });
    await pending;
    expect(settled).toBe(true);
});

it('reuses the same configuration object and invokes the vendor on every initialization', async () => {
    await init();
    await init();
    expect(load).toHaveBeenCalledTimes(2);
    expect(load.mock.calls[0]![1]).toBe(load.mock.calls[1]![1]);
});

it.each(['throw', 'reject'])('propagates vendor %s failures through the controller promise', async kind => {
    const error = new Error('Particles unavailable');
    if (kind === 'throw') load.mockImplementation(() => { throw error; });
    else load.mockRejectedValue(error);
    await expect(init()).rejects.toBe(error);
});

it('still delegates without a target element, leaving target validation to the vendor', async () => {
    document.body.innerHTML = '';
    await init();
    expect(load).toHaveBeenCalledOnce();
});

it('rejects when the required vendor global is missing', async () => {
    vi.stubGlobal('tsParticles', undefined);
    await expect(init()).rejects.toThrow(TypeError);
});
