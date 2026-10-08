import { initErrorPage } from './error.ts';
import type { ParticlesRuntime } from '../../../ts-types/domain/particles.ts';

afterEach(() => vi.unstubAllGlobals());

it('returns the original vendor result and preserves the vendor receiver', () => {
    const result = Promise.resolve({ id: 'tsparticles' });
    const load = vi.fn<ParticlesRuntime['load']>().mockReturnValue(result);
    const vendor = { load };
    vi.stubGlobal('tsParticles', vendor);
    expect(initErrorPage()).toBe(result);
    expect(load.mock.contexts[0]).toBe(vendor);
    expect(load).toHaveBeenCalledWith('tsparticles', expect.objectContaining({ fpsLimit: 60, detectRetina: true }));
});

it('reuses the mutable particle configuration on repeated initialization', () => {
    const load = vi.fn<ParticlesRuntime['load']>().mockResolvedValue(undefined);
    vi.stubGlobal('tsParticles', { load });
    void initErrorPage();
    void initErrorPage();
    expect(load.mock.calls[0]![1]).toBe(load.mock.calls[1]![1]);
    expect(Object.isFrozen(load.mock.calls[0]![1])).toBe(false);
});

it('throws vendor errors synchronously and returns rejecting promises unchanged', async () => {
    const error = new Error('Vendor failure');
    const load = vi.fn<ParticlesRuntime['load']>(() => { throw error; });
    vi.stubGlobal('tsParticles', { load });
    expect(() => initErrorPage()).toThrow(error);
    const rejected = Promise.reject(error);
    load.mockReturnValue(rejected);
    expect(initErrorPage()).toBe(rejected);
    await expect(rejected).rejects.toBe(error);
});

it('does not replace a missing vendor or validate its target element', () => {
    vi.stubGlobal('tsParticles', undefined);
    expect(() => initErrorPage()).toThrow(TypeError);
    const load = vi.fn();
    vi.stubGlobal('tsParticles', { load });
    document.body.innerHTML = '';
    expect(initErrorPage()).toBeUndefined();
    expect(load).toHaveBeenCalledOnce();
});
