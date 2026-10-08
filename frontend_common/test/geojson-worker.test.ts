// @vitest-environment node

import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'vite';
import { applyGeoJSONNodes } from '../../frontend_private/static/private/ts/map_viewer/map/geojson_transport.ts';
import type { JSONContainer } from '../../ts-types/domain/json.ts';
import type { GeoJSONWorkerRequest, GeoJSONWorkerResponse } from '../../ts-types/worker/geojson.ts';

let output: string;
let workerURL: URL;
const workers: Worker[] = [];
beforeAll(async () => {
    output = await mkdtemp(join(tmpdir(), 'speleodb-emitted-worker-'));
    const result = await build({ configFile: './vite.config.ts', logLevel: 'silent', build: { outDir: output } });
    const records = Array.isArray(result) ? result.flatMap(item => item.output) : (result as { output: Array<{ fileName: string }> }).output;
    const worker = records.find(item => /geojson_worker-[^/]+\.js$/.test(item.fileName));
    expect(worker).toBeDefined();
    workerURL = pathToFileURL(join(output, worker!.fileName));
    expect(await readFile(workerURL, 'utf8')).not.toContain('sourceMappingURL');
});
afterEach(() => { for (const worker of workers.splice(0)) worker.terminate(); });
afterAll(async () => { if (output) await rm(output, { recursive: true, force: true }); });

function emittedWorker() {
    const worker = new Worker(workerURL, { type: 'module' });
    workers.push(worker);
    return worker;
}

function exchange(worker: Worker, message: GeoJSONWorkerRequest, transfer: Transferable[] = []) {
    return new Promise<GeoJSONWorkerResponse>((resolve, reject) => {
        worker.onmessage = (event: MessageEvent<GeoJSONWorkerResponse>) => resolve(event.data);
        worker.onerror = reject;
        worker.postMessage(message, transfer);
    });
}

it('executes the emitted worker, transfers the input and reconstructs acknowledged bounded batches', async () => {
    const worker = emittedWorker();
    const source = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { name: 'Private' }, geometry: { type: 'LineString', coordinates: Array.from({ length: 40 }, (_, i) => [i, 2, 3]) } }] };
    const buffer = new TextEncoder().encode(JSON.stringify(source)).buffer;
    const first = await exchange(worker, { type: 'parse', buffer, batchSize: 3 }, [buffer]);
    expect(buffer.byteLength).toBe(0);
    expect(first).toEqual({ type: 'start', array: false });
    const received: GeoJSONWorkerResponse[] = [];
    worker.onmessage = (event: MessageEvent<GeoJSONWorkerResponse>) => { received.push(event.data); };
    await new Promise(resolve => setTimeout(resolve, 30));
    expect(received).toEqual([]);
    const restored = {};
    const containers = new Map<number, JSONContainer>([[0, restored]]);
    let batches = 0;
    for (;;) {
        const message = await exchange(worker, { type: 'next' });
        if (message.type === 'complete') break;
        expect(message.type).toBe('nodes');
        if (message.type !== 'nodes') throw new Error('Expected the emitted worker to send a node batch');
        expect(message.nodes.length).toBeLessThanOrEqual(3);
        applyGeoJSONNodes(containers, message.nodes);
        batches++;
    }
    expect(batches).toBeGreaterThan(10);
    expect(restored).toEqual(source);
});

it.each([null, 7, 'text', true])('returns primitive JSON %j through the actual entry', async value => {
    const worker = emittedWorker();
    const buffer = new TextEncoder().encode(JSON.stringify(value)).buffer;
    expect(await exchange(worker, { type: 'parse', buffer, batchSize: 2 }, [buffer])).toEqual({ type: 'result', data: value });
});

it('redacts malformed input and invalid lifecycle errors and permits a later fresh parse', async () => {
    const worker = emittedWorker();
    expect(await exchange(worker, { type: 'next' })).toEqual({ type: 'error' });
    const buffer = new TextEncoder().encode('private source fragment').buffer;
    expect(await exchange(worker, { type: 'parse', buffer, batchSize: 2 }, [buffer])).toEqual({ type: 'error' });
    const valid = new TextEncoder().encode('[]').buffer;
    expect(await exchange(worker, { type: 'parse', buffer: valid, batchSize: 2 }, [valid])).toEqual({ type: 'start', array: true });
    expect(await exchange(worker, { type: 'next' })).toEqual({ type: 'complete' });
});
