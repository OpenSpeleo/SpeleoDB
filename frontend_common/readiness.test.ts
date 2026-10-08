import { afterWindowLoad } from './readiness.ts';

afterEach(() => {
    vi.restoreAllMocks();
});

it('resolves undefined without registering a listener when load already completed', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    const listen = vi.spyOn(window, 'addEventListener');
    await expect(afterWindowLoad()).resolves.toBeUndefined();
    expect(listen).not.toHaveBeenCalled();
});

it.each(['loading', 'interactive'] as const)('resolves the original future load event from %s state', async state => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue(state);
    const listen = vi.spyOn(window, 'addEventListener');
    const pending = afterWindowLoad();
    let settled = false;
    void pending.then(() => { settled = true; });
    await Promise.resolve();
    expect(settled).toBe(false);
    expect(listen).toHaveBeenCalledWith('load', expect.any(Function), { once: true });
    const event = new Event('load');
    window.dispatchEvent(event);
    await expect(pending).resolves.toBe(event);
});
