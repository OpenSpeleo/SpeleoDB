import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { startDevelopmentReload } from './reload.ts';

describe('completed development generation reload', () => {
    const reload = vi.fn();
    const request = vi.fn<typeof fetch>();
    let script: HTMLScriptElement;
    let stop = () => {};
    beforeEach(() => {
        vi.useFakeTimers();
        sessionStorage.clear();
        reload.mockReset();
        request.mockReset();
        vi.stubGlobal('fetch', request);
        vi.stubGlobal('window', { location: { reload } });
        script = document.createElement('script');
        script.dataset.speleodbGeneration = 'session-a/1';
        script.dataset.speleodbReload = '/__assets__/generation/';
    });
    afterEach(() => {
        stop();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        vi.useRealTimers();
    });
    function respond(generation: unknown) {
        request.mockResolvedValue(new Response(JSON.stringify({ generation })));
    }
    async function begin() {
        stop = startDevelopmentReload(script);
        await vi.advanceTimersByTimeAsync(0);
    }
    it('compares the first response with the rendered generation and reloads once', async () => {
        respond('session-a/2');
        await begin();
        expect(reload).toHaveBeenCalledTimes(1);
        expect(sessionStorage.getItem('speleo_dev_reload_target')).toBe('session-a/2');
        await vi.advanceTimersByTimeAsync(5000);
        expect(request).toHaveBeenCalledTimes(1);
        expect(request).toHaveBeenCalledWith('/__assets__/generation/', { cache: 'no-store', credentials: 'same-origin' });
    });
    it('waits for publication and follows a later successful build', async () => {
        respond('session-a/1');
        await begin();
        expect(reload).not.toHaveBeenCalled();
        respond('session-a/3');
        await vi.advanceTimersByTimeAsync(1000);
        expect(reload).toHaveBeenCalledTimes(1);
    });
    it('does not loop on stale HTML but can follow another new generation', async () => {
        sessionStorage.setItem('speleo_dev_reload_target', 'session-a/2');
        respond('session-a/2');
        await begin();
        expect(reload).not.toHaveBeenCalled();
        respond('new-session/1');
        await vi.advanceTimersByTimeAsync(1000);
        expect(reload).toHaveBeenCalledTimes(1);
    });
    it('does not navigate when storage is unavailable', async () => {
        vi.spyOn(sessionStorage, 'setItem').mockImplementation(() => { throw new Error('denied'); });
        respond('session-a/2');
        await begin();
        await vi.advanceTimersByTimeAsync(1000);
        expect(reload).not.toHaveBeenCalled();
    });
    it.each([null, {}, '../unsafe/2', '', 5])('ignores malformed generation %j', async generation => {
        respond(generation);
        await begin();
        expect(reload).not.toHaveBeenCalled();
    });
    it('retries network and malformed JSON errors without navigating', async () => {
        request.mockRejectedValueOnce(new Error('offline'))
            .mockResolvedValueOnce(new Response('partial'))
            .mockResolvedValueOnce(new Response('{}', { status: 503 }));
        await begin();
        await vi.advanceTimersByTimeAsync(2000);
        expect(request).toHaveBeenCalledTimes(3);
        expect(reload).not.toHaveBeenCalled();
    });
    it('does not start for production markup or navigate after cancellation', async () => {
        startDevelopmentReload(null)();
        expect(request).not.toHaveBeenCalled();
        let finish!: (response: Response) => void;
        request.mockReturnValue(new Promise(resolve => { finish = resolve; }));
        stop = startDevelopmentReload(script);
        stop();
        finish(new Response(JSON.stringify({ generation: 'session-a/2' })));
        await vi.advanceTimersByTimeAsync(0);
        expect(reload).not.toHaveBeenCalled();
    });
});
