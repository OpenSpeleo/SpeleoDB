import { v2ProjectsList } from '@speleodb/api';
import { setTimeout as delay } from 'node:timers/promises';
import { apiData, webApiOptions } from './client.ts';
import { setBrowserUrl, startApiServer } from '../test/api-server.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => {
    originalUrl = window.location.href;
    server = await startApiServer();
});
beforeEach(() => {
    server.reset();
    setBrowserUrl(`${server.origin}/private/map/`);
});
afterAll(async () => {
    setBrowserUrl(originalUrl);
    await server.close();
});

/** Hold a real HTTP response beyond the SDK's real ten-second default. */
function holdResponse() {
    let admit!: () => void;
    let release!: () => void;
    const admitted = new Promise<void>(resolve => { admit = resolve; });
    const response = new Promise<{ json: [] }>(resolve => { release = () => resolve({ json: [] }); });
    server.handle(() => { admit(); return response; });
    return { admitted, release };
}

describe.each(['fetch', 'xhr'] as const)('browser %s deadline policy', transport => {
    // Upload callbacks select the SDK's real XHR transport.
    const options = transport === 'xhr' ? { onUploadProgress: () => undefined } : {};

    it('completes requests after the SDK default deadline without timing out', async () => {
        const held = holdResponse();
        let outcome = 'pending';
        const pending = apiData(v2ProjectsList(webApiOptions(options)));
        void pending.then(() => { outcome = 'resolved'; }, () => { outcome = 'rejected'; });
        try {
            await held.admitted;
            await delay(11_000);
            expect(outcome).toBe('pending');
            held.release();
            await expect(pending).resolves.toEqual([]);
            expect(server.requests).toHaveLength(1);
        } finally {
            held.release();
            await pending.catch(() => undefined);
        }
    }, 30_000);

    it('still cancels an active request with no deadline and ignores its late response', async () => {
        const held = holdResponse();
        const controller = new AbortController();
        const pending = apiData(v2ProjectsList(webApiOptions({ ...options, signal: controller.signal })));
        // Consume a premature failure too, so regression output is the assertion
        // below rather than an unhandled rejection during the real delay.
        const outcome = pending.then(value => ({ value }), error => ({ error: error as Error }));
        try {
            await held.admitted;
            await delay(11_000);
            controller.abort();
            expect(await outcome).toMatchObject({ error: { name: 'AbortError' } });
            expect(server.requests).toHaveLength(1);
        } finally {
            controller.abort();
            held.release();
            await pending.catch(() => undefined);
        }
    }, 30_000);
});

it('retains an explicit finite deadline for a caller that supplies one', async () => {
    const held = holdResponse();
    const pending = apiData(v2ProjectsList(webApiOptions({ timeoutMs: 1_000 })));
    const rejected = expect(pending).rejects.toMatchObject({ name: 'TimeoutError' });
    try {
        await held.admitted;
        await rejected;
    } finally {
        held.release();
        await pending.catch(() => undefined);
    }
});
