import { DEFAULTS } from '../config.js';
import { applyGeoJSONNodes } from './geojson_transport.js';

function assertCurrent(isCurrent) {
    if (!isCurrent()) throw new DOMException('Viewer load superseded', 'AbortError');
}

async function parseWithoutSourceExcerpts(parse) {
    try { return await parse(); }
    catch (error) {
        if (error instanceof SyntaxError) throw new Error('Unable to parse viewer GeoJSON');
        throw error;
    }
}

/** Parse large downloaded GeoJSON off-thread with bounded main-thread delivery. */
export async function readViewerGeoJSON(response, {
    isCurrent = () => true,
    yieldWork = () => new Promise(resolve => setTimeout(resolve, 0)),
} = {}) {
    assertCurrent(isCurrent);
    // Existing response doubles and browsers without workers retain native parsing.
    if (typeof Worker === 'undefined' || typeof response.arrayBuffer !== 'function') {
        const data = await parseWithoutSourceExcerpts(() => response.json());
        assertCurrent(isCurrent);
        return data;
    }
    const buffer = await response.arrayBuffer();
    assertCurrent(isCurrent);
    if (buffer.byteLength < DEFAULTS.VIEWER_WORK.WORKER_PARSE_BYTES) {
        const data = await parseWithoutSourceExcerpts(() => JSON.parse(new TextDecoder().decode(buffer)));
        assertCurrent(isCurrent);
        return data;
    }
    // Construction errors, including CSP failures, remain visible load errors.
    const worker = new Worker(new URL('./geojson_worker.js', import.meta.url), { type: 'module' });
    try {
        return await new Promise((resolve, reject) => {
            let data;
            const containers = new Map();
            worker.onerror = () => reject(new Error('Unable to parse viewer GeoJSON in worker'));
            worker.onmessageerror = () => reject(new Error('Unable to receive viewer GeoJSON'));
            worker.onmessage = async ({ data: message }) => {
                try {
                    assertCurrent(isCurrent);
                    switch (message.type) {
                        case 'start':
                            data = message.array ? [] : {};
                            containers.set(0, data);
                            break;
                        case 'nodes':
                            applyGeoJSONNodes(containers, message.nodes);
                            break;
                        case 'complete':
                            resolve(data);
                            return;
                        case 'result':
                            resolve(message.data);
                            return;
                        default:
                            throw new Error('Unable to parse viewer GeoJSON');
                    }
                    await yieldWork();
                    assertCurrent(isCurrent);
                    worker.postMessage({ type: 'next' });
                } catch (error) {
                    reject(error);
                }
            };
            worker.postMessage({
                type: 'parse', buffer,
                batchSize: DEFAULTS.VIEWER_WORK.WORKER_NODE_BATCH_SIZE,
            }, [buffer]);
        });
    } finally {
        worker.terminate();
    }
}
