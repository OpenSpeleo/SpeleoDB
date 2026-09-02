import { LazyOverlayManager } from './lazy_overlay_manager.js';

function deferred() { let resolve; let reject; const promise = new Promise((res, rej) => { resolve = res; reject = rej; }); return { promise, resolve, reject }; }

function manager(overrides = {}) {
    return new LazyOverlayManager({
        getVersion: entity => entity.version,
        fetchData: vi.fn(async entity => ({ id: entity.id })),
        attach: vi.fn(async (entity, data) => ({ id: entity.id, data })),
        setVisible: vi.fn(async () => {}),
        remove: vi.fn(async () => {}),
        onStateChange: vi.fn(),
        onError: vi.fn(),
        ...overrides,
    });
}

describe('LazyOverlayManager', () => {
    it('defaults every overlay off and deduplicates cached activations', async () => {
        const overlay = manager();
        const entity = { id: 'one', version: 'v1' };
        expect(overlay.isDesired('one')).toBe(false);
        await overlay.setDesired(entity, true);
        await overlay.setDesired(entity, false);
        await overlay.setDesired(entity, true);
        expect(overlay.options.fetchData).toHaveBeenCalledTimes(1);
        expect(overlay.options.setVisible).toHaveBeenLastCalledWith(expect.anything(), true, entity);
    });

    it('never attaches a slow response after the user switches off', async () => {
        const pending = deferred();
        const overlay = manager({ fetchData: vi.fn(() => pending.promise) });
        const entity = { id: 'one', version: 'v1' };
        const activation = overlay.setDesired(entity, true);
        await overlay.setDesired(entity, false);
        pending.resolve({});
        await activation;
        expect(overlay.options.attach).not.toHaveBeenCalled();
        expect(overlay.isDesired('one')).toBe(false);
    });

    it('shares one promise for concurrent intent until intent changes', async () => {
        const pending = deferred();
        const overlay = manager({ fetchData: vi.fn(() => pending.promise) });
        const entity = { id: 'one', version: 'v1' };
        const first = overlay.setDesired(entity, true);
        // A duplicate UI event is the same intent and may replace the request,
        // but only the current generation is allowed to attach.
        const second = overlay.setDesired(entity, true);
        pending.resolve({});
        await Promise.all([first, second]);
        expect(overlay.options.fetchData).toHaveBeenCalledTimes(1);
        expect(overlay.options.attach).toHaveBeenCalledTimes(1);
    });

    it('removes revoked overlays and invalidates changed revisions', async () => {
        const overlay = manager();
        await overlay.setDesired({ id: 'one', version: 'v1' }, true);
        await overlay.reconcile([{ id: 'one', version: 'v2' }]);
        expect(overlay.options.remove).toHaveBeenCalled();
        expect(overlay.options.fetchData).toHaveBeenCalledTimes(2);
        await overlay.reconcile([]);
        expect(overlay.isDesired('one')).toBe(false);
    });

    it('reverts desired state and reports safe load failures', async () => {
        const overlay = manager({ fetchData: vi.fn(async () => { throw new Error('failed'); }) });
        await overlay.setDesired({ id: 'one', version: 'v1' }, true);
        expect(overlay.isDesired('one')).toBe(false);
        expect(overlay.options.onError).toHaveBeenCalledTimes(1);
    });

    it('does not retain a removed registration when replacement attachment fails', async () => {
        const attach = vi.fn()
            .mockResolvedValueOnce({ id: 'one', version: 'v1' })
            .mockRejectedValueOnce(new Error('replacement failed'));
        const overlay = manager({ attach });
        await overlay.setDesired({ id: 'one', version: 'v1' }, true);

        await overlay.setDesired({ id: 'one', version: 'v2' }, true);

        expect(overlay.getRegistration('one')).toBeNull();
        expect(overlay.cache.has('one')).toBe(false);
        expect(overlay.isDesired('one')).toBe(false);
    });

    it('does not attach stale work after intent changes during previous-registration removal', async () => {
        const removal = deferred();
        const remove = vi.fn(() => removal.promise);
        const overlay = manager({ remove });
        await overlay.setDesired({ id: 'one', version: 'v1' }, true);

        const replacement = overlay.setDesired({ id: 'one', version: 'v2' }, true);
        await vi.waitFor(() => expect(remove).toHaveBeenCalledTimes(1));
        await overlay.setDesired({ id: 'one', version: 'v2' }, false);
        removal.resolve();
        await replacement;

        expect(overlay.options.attach).toHaveBeenCalledTimes(1);
        expect(overlay.getRegistration('one')).toBeNull();
        expect(overlay.isDesired('one')).toBe(false);
    });

    it('removes an attached overlay when activation itself fails', async () => {
        const overlay = manager({ setVisible: vi.fn(async () => { throw new Error('style changed'); }) });
        await overlay.setDesired({ id: 'one', version: 'v1' }, true);
        expect(overlay.options.remove).toHaveBeenCalledTimes(1);
        expect(overlay.getRegistration('one')).toBeNull();
        expect(overlay.isDesired('one')).toBe(false);
    });

    it('removes registrations before a map style rebuild clears them', async () => {
        const overlay = manager();
        const entity = { id: 'one', version: 'v1' };
        await overlay.setDesired(entity, true);
        const registration = overlay.getRegistration(entity.id);
        await overlay.markRegistrationsRemoved();
        expect(overlay.options.remove).toHaveBeenCalledWith(registration, entity);
        expect(overlay.getRegistration(entity.id)).toBeNull();
    });

    it('invalidates in-flight attachment work during a map style rebuild', async () => {
        const pending = deferred();
        const fetchData = vi.fn()
            .mockImplementationOnce(() => pending.promise)
            .mockResolvedValueOnce({ fresh: true });
        const overlay = manager({ fetchData });
        const entity = { id: 'one', version: 'v1' };
        const staleActivation = overlay.setDesired(entity, true);

        await overlay.markRegistrationsRemoved();
        pending.resolve({ stale: true });
        await staleActivation;
        expect(overlay.options.attach).not.toHaveBeenCalled();
        expect(overlay.isDesired('one')).toBe(true);
        expect(overlay.isLoading('one')).toBe(false);

        await overlay.restoreDesired();
        expect(fetchData).toHaveBeenCalledTimes(2);
        expect(overlay.options.attach).toHaveBeenCalledWith(
            entity,
            { fresh: true },
            expect.objectContaining({ generation: 3, version: 'v1' }),
        );
    });

    it('evicts a hidden overlay after visible overlays temporarily exceed the cache budget', async () => {
        const overlay = manager({ maxCacheEntries: 1 });
        const first = { id: 'one', version: 'v1' };
        const second = { id: 'two', version: 'v1' };
        await overlay.setDesired(first, true);
        await overlay.setDesired(second, true);
        expect(overlay.cache.size).toBe(2);

        await overlay.setDesired(first, false);

        expect(overlay.options.remove).toHaveBeenCalledWith(expect.objectContaining({ id: 'one' }), first);
        expect(overlay.getRegistration('one')).toBeNull();
        expect(overlay.getRegistration('two')).not.toBeNull();
        expect(overlay.cache.size).toBe(1);
    });
});
