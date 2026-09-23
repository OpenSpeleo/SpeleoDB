import { TextEncoder, TextDecoder } from 'node:util';
import { geoJSONMessages, applyGeoJSONNodes } from './geojson_transport.js';
import { readViewerGeoJSON } from './read_geojson.js';

vi.mock('../config.js', () => ({ DEFAULTS: { VIEWER_WORK: { WORKER_PARSE_BYTES: 100, WORKER_NODE_BATCH_SIZE: 2 } } }));

class WorkerDouble {
    static instances = [];
    sent = [];
    terminated = false;
    constructor(url, options) {
        this.url = url;
        this.options = options;
        WorkerDouble.instances.push(this);
    }
    postMessage(message, transfer) {
        this.sent.push({ message, transfer });
        if (message.type === 'parse') this.steps = geoJSONMessages(message.buffer, message.batchSize);
        queueMicrotask(() => {
            if (this.terminated) return;
            try {
                this.onmessage({ data: this.steps.next().value });
            } catch {
                this.onmessage({ data: { type: 'error' } });
            }
        });
    }
    terminate() { this.terminated = true; }
}

function responseFor(data) {
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
    const worker = WorkerDouble.instances[0];
    expect(worker.options).toEqual({ type: 'module' });
    expect(worker.sent[0].transfer).toEqual([worker.sent[0].message.buffer]);
    expect(worker.terminated).toBe(true);
});

it('preserves arbitrary single-feature GeoJSON', async () => {
    const data = large.features[0];
    expect(await readViewerGeoJSON(responseFor(data))).toEqual(data);
    expect(WorkerDouble.instances[0].terminated).toBe(true);
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
    expect(WorkerDouble.instances[0].terminated).toBe(true);
    expect(WorkerDouble.instances[0].sent).toHaveLength(1);
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

it('reports parser failure without exposing private data and cleans up the worker', async () => {
    const response = { arrayBuffer: async () => new TextEncoder().encode('private malformed survey'.repeat(10)).buffer };
    await expect(readViewerGeoJSON(response)).rejects.toThrow('Unable to parse viewer GeoJSON');
    expect(WorkerDouble.instances[0].terminated).toBe(true);
});

it('bounds transport batches and preserves all JSON metadata without prototype mutation', () => {
    const input = JSON.parse(JSON.stringify(large).replace('"name":"Private survey"', '"__proto__":{"testMarker":true},"name":"Private survey"'));
    const buffer = new TextEncoder().encode(JSON.stringify(input)).buffer;
    const messages = [...geoJSONMessages(buffer, 2)];
    const restored = {};
    const containers = new Map([[0, restored]]);
    expect(messages[0]).toEqual({ type: 'start', array: false });
    for (const message of messages.filter(message => message.type === 'nodes')) {
        expect(message.nodes.length).toBeLessThanOrEqual(2);
        applyGeoJSONNodes(containers, message.nodes);
    }
    expect(restored).toEqual(input);
    expect(Object.getPrototypeOf(restored)).toBe(Object.prototype);
    expect({}.testMarker).toBeUndefined();
    expect(messages.at(-1)).toEqual({ type: 'complete' });
});

it('splits a single huge coordinate array into bounded messages', () => {
    const input = { type: 'Feature', geometry: { type: 'LineString',
        coordinates: Array.from({ length: 100_000 }, (_, index) => [index, 1, 2]),
    }, properties: { name: 'Long line' } };
    const restored = {};
    const containers = new Map([[0, restored]]);
    let batches = 0;
    let maximumLeafLength = 0;
    const buffer = new TextEncoder().encode(JSON.stringify(input)).buffer;
    for (const message of geoJSONMessages(buffer, 1000)) {
        if (message.type !== 'nodes') continue;
        expect(message.nodes.length).toBeLessThanOrEqual(1000);
        for (const node of message.nodes) {
            if (Array.isArray(node.value)) maximumLeafLength = Math.max(maximumLeafLength, node.value.length);
        }
        applyGeoJSONNodes(containers, message.nodes);
        batches++;
    }
    expect(batches).toBeGreaterThan(100);
    expect(maximumLeafLength).toBeLessThanOrEqual(4);
    expect(restored).toEqual(input);
});

it('also omits private parser excerpts on small and native-fallback responses', async () => {
    const privateText = 'private source excerpt';
    await expect(readViewerGeoJSON({ arrayBuffer: async () => new TextEncoder().encode(privateText).buffer }))
        .rejects.toThrow('Unable to parse viewer GeoJSON');
    await expect(readViewerGeoJSON({ json: async () => { throw new SyntaxError(privateText); } }))
        .rejects.toThrow('Unable to parse viewer GeoJSON');
});
