import { TextEncoder, TextDecoder } from 'node:util';
import { geoJSONMessages } from '@speleodb/map-core/geojson-transport';
import { readViewerGeoJSON } from './read_geojson.ts';
import type { JSONValue } from '../../../../../../ts-types/domain/json.ts';
import type { GeoJSONWorkerRequest, GeoJSONWorkerResponse } from '../../../../../../ts-types/worker/geojson.ts';

vi.mock('../config.ts', () => ({ DEFAULTS: { VIEWER_WORK: { WORKER_PARSE_BYTES: 100, WORKER_NODE_BATCH_SIZE: 2 } } }));

class WorkerDouble {
    static instances: WorkerDouble[] = [];
    sent: Array<{ message: GeoJSONWorkerRequest; transfer: Transferable[] | undefined }> = [];
    terminated = false;
    declare url: URL;
    declare options: WorkerOptions;
    declare steps: ReturnType<typeof geoJSONMessages>;
    declare onmessage: (event: { data: GeoJSONWorkerResponse | void }) => Promise<void>;
    constructor(url: URL, options: WorkerOptions) {
        this.url = url;
        this.options = options;
        WorkerDouble.instances.push(this);
    }
    postMessage(message: GeoJSONWorkerRequest, transfer?: Transferable[]) {
        this.sent.push({ message, transfer });
        if (message.type === 'parse') this.steps = geoJSONMessages(message.buffer, message.batchSize);
        queueMicrotask(() => {
            if (this.terminated) return;
            try {
                void this.onmessage({ data: this.steps.next().value });
            } catch {
                void this.onmessage({ data: { type: 'error' } });
            }
        });
    }
    terminate() { this.terminated = true; }
}

function responseFor(data: JSONValue) {
    const buffer = new TextEncoder().encode(JSON.stringify(data)).buffer;
    return { arrayBuffer: vi.fn(async () => buffer), json: vi.fn(async () => data) };
}

const large = {
    type: 'FeatureCollection',
    name: 'Private survey',
    features: Array.from({ length: 7 }, (_, id) => ({
        type: 'Feature', id, properties: { name: 'Station' }, geometry: { type: 'Point', coordinates: [id, 2] },
    })),
};

beforeEach(() => {
    vi.stubGlobal('TextEncoder', TextEncoder);
    vi.stubGlobal('TextDecoder', TextDecoder);
    vi.stubGlobal('Worker', WorkerDouble);
    WorkerDouble.instances = [];
});

afterEach(() => vi.unstubAllGlobals());

it('parses large collections in a worker and acknowledges batches after yielding', async () => {
    const response = responseFor(large);
    const yieldWork = vi.fn(async () => {});
    const result = await readViewerGeoJSON(response, { yieldWork });
    expect(result).toEqual(large);
    expect(response.json).not.toHaveBeenCalled();
    expect(yieldWork.mock.calls.length).toBeGreaterThan(5);
    const worker = WorkerDouble.instances[0]!;
    expect(worker.options).toEqual({ type: 'module' });
    expect(worker.sent[0]!.transfer).toEqual([(worker.sent[0]!.message as Extract<GeoJSONWorkerRequest, { type: 'parse' }>).buffer]);
    expect(worker.terminated).toBe(true);
});

it('preserves arbitrary single-feature GeoJSON', async () => {
    const data = large.features[0]!;
    expect(await readViewerGeoJSON(responseFor(data))).toEqual(data);
    expect(WorkerDouble.instances[0]!.terminated).toBe(true);
});

it('avoids worker setup for small payloads', async () => {
    const data = { type: 'Point', coordinates: [1, 2] };
    expect(await readViewerGeoJSON(responseFor(data))).toEqual(data);
    expect(WorkerDouble.instances).toHaveLength(0);
});

it('retains native parsing when workers or arrayBuffer are unavailable', async () => {
    const response = { json: vi.fn(async () => large) };
    expect(await readViewerGeoJSON(response)).toBe(large);
    vi.stubGlobal('Worker', undefined);
    expect(await readViewerGeoJSON(responseFor(large))).toBe(large);
    expect(WorkerDouble.instances).toHaveLength(0);
});

it('cancels between batches, terminates the worker and returns no partial data', async () => {
    let current = true;
    const yieldWork = vi.fn(async () => { current = false; });
    await expect(readViewerGeoJSON(responseFor(large), { isCurrent: () => current, yieldWork }))
        .rejects.toMatchObject({ name: 'AbortError' });
    expect(WorkerDouble.instances[0]!.terminated).toBe(true);
    expect(WorkerDouble.instances[0]!.sent).toHaveLength(1);
});

it('rejects stale responses before parsing', async () => {
    let current = true;
    const response = responseFor(large);
    response.arrayBuffer.mockImplementation(async () => {
        current = false;
        return new ArrayBuffer(1000);
    });
    await expect(readViewerGeoJSON(response, { isCurrent: () => current })).rejects.toMatchObject({ name: 'AbortError' });
    expect(WorkerDouble.instances).toHaveLength(0);
});

it('forwards a yielding rejection unchanged and still terminates the worker', async () => {
    const failure: unknown = 'scheduler stopped';
    await expect(readViewerGeoJSON(responseFor(large), { yieldWork: () => Promise.reject(failure) }))
        .rejects.toBe(failure);
    expect(WorkerDouble.instances[0]!.terminated).toBe(true);
});

it('reports parser failure without exposing private data and cleans up the worker', async () => {
    const response = { arrayBuffer: async () => new TextEncoder().encode('private malformed survey'.repeat(10)).buffer };
    await expect(readViewerGeoJSON(response)).rejects.toThrow('Unable to parse viewer GeoJSON');
    expect(WorkerDouble.instances[0]!.terminated).toBe(true);
});

it('also omits private parser excerpts on small and native-fallback responses', async () => {
    const privateText = 'private source excerpt';
    await expect(readViewerGeoJSON({ arrayBuffer: async () => new TextEncoder().encode(privateText).buffer }))
        .rejects.toThrow('Unable to parse viewer GeoJSON');
    await expect(readViewerGeoJSON({ json: async () => { throw new SyntaxError(privateText); } }))
        .rejects.toThrow('Unable to parse viewer GeoJSON');
});
