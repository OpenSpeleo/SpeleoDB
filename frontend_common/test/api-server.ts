import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import type { IncomingHttpHeaders } from 'node:http';
import type { AddressInfo } from 'node:net';
import type { JSDOM } from 'jsdom';

export interface RecordedApiRequest {
    method: string;
    path: string;
    headers: IncomingHttpHeaders;
    body: string;
}
export interface ApiTestReply {
    status?: number;
    json?: unknown;
    text?: string;
    bytes?: Uint8Array;
    headers?: Record<string, string>;
}
type ReplyHandler = (request: RecordedApiRequest) => ApiTestReply | Promise<ApiTestReply>;

/** Exercise the generated client through real HTTP; no transport or SDK replacement. */
export async function startApiServer() {
    const requests: RecordedApiRequest[] = [];
    let handler: ReplyHandler = () => ({ json: {} });
    const server = createServer((incoming, outgoing) => {
        void (async () => {
        try {
            // JSDOM keeps its initial XHR origin after reconfigure. Exercise real
            // CORS negotiation rather than replacing its transport or internals.
            const cors = {
                'Access-Control-Allow-Origin': incoming.headers.origin ?? '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD',
                'Access-Control-Allow-Headers': incoming.headers['access-control-request-headers'] ?? 'content-type, x-csrftoken',
                'Access-Control-Allow-Credentials': 'true',
            };
            if (incoming.method === 'OPTIONS') {
                outgoing.writeHead(204, cors);
                outgoing.end();
                return;
            }
            const chunks: Uint8Array[] = [];
            for await (const chunk of incoming) chunks.push(Buffer.from(chunk as Uint8Array));
            const request: RecordedApiRequest = {
                method: incoming.method ?? 'GET', path: incoming.url ?? '/',
                headers: incoming.headers, body: Buffer.concat(chunks).toString('utf8'),
            };
            requests.push(request);
            const reply = await handler(request);
            const headers = { 'Content-Type': 'application/json', ...cors, ...reply.headers };
            outgoing.writeHead(reply.status ?? 200, headers);
            outgoing.end(reply.bytes ?? reply.text ?? (reply.json === undefined ? '' : JSON.stringify(reply.json)));
        } catch {
            outgoing.writeHead(500, { 'Content-Type': 'text/plain' });
            outgoing.end('Test HTTP handler failed.');
        }
        })();
    });
    server.listen(0, '127.0.0.1');
    await once(server, 'listening');
    const origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
    return {
        origin, requests,
        reply(value: ApiTestReply) { handler = () => value; },
        handle(value: ReplyHandler) { handler = value; },
        reset() { requests.length = 0; handler = () => ({ json: {} }); },
        async close() {
            await new Promise<void>((resolve, reject) => {
                server.close(error => error ? reject(error) : resolve());
                server.closeAllConnections();
            });
        },
    };
}

/** Vitest exposes JSDOM's supported URL configuration API in this environment. */
export function setBrowserUrl(url: string): void {
    const host = globalThis as typeof globalThis & { jsdom: JSDOM };
    host.jsdom.reconfigure({ url });
}

export function loadJQuery(): void {
    const source = readFileSync('frontend_public/static/ts/vendors/jquery-3.7.1.js', 'utf8');
    // Run the checked-in vendor exactly as a browser script.
    (0, eval)(source);
}

/** Select real matching body constructors when testing Bun fetch multipart. */
export function useNativeFetchBodyConstructors(): () => void {
    const current = { FormData, File, Blob, URL };
    const runtime = globalThis as typeof globalThis & {
        __nativeFetchBodyConstructors: typeof current;
    };
    Object.assign(globalThis, runtime.__nativeFetchBodyConstructors);
    return () => { Object.assign(globalThis, current); };
}
