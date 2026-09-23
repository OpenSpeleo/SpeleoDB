/**
 * Stream bounded JSON-tree fragments, including within one enormous geometry.
 * No postMessage recursively clones an unbounded coordinate array or feature.
 */
export function* geoJSONMessages(buffer, batchSize) {
    const data = JSON.parse(new TextDecoder().decode(buffer));
    if (!Number.isInteger(batchSize) || batchSize < 1) throw new Error('Invalid transport batch size');
    if (data === null || typeof data !== 'object') {
        yield { type: 'result', data };
        return;
    }
    yield { type: 'start', array: Array.isArray(data) };
    let nextId = 1;
    let nodes = [];
    // Iterators avoid copying the keys of a huge coordinate array in one step.
    function* entries(value) {
        if (Array.isArray(value)) {
            for (let index = 0; index < value.length; index++) yield [index, value[index]];
        } else {
            for (const key in value) if (Object.hasOwn(value, key)) yield [key, value[key]];
        }
    }
    const stack = [{ id: 0, entries: entries(data) }];
    while (stack.length) {
        const current = stack.at(-1);
        const entry = current.entries.next();
        if (entry.done) {
            stack.pop();
            continue;
        }
        const [key, value] = entry.value;
        // GeoJSON positions are tiny and safe to clone as a single leaf.
        const position = Array.isArray(value) && value.length <= 4 && value.every(item => typeof item === 'number');
        if (value === null || typeof value !== 'object' || position) {
            nodes.push({ parent: current.id, key, value });
        } else {
            const id = nextId++;
            nodes.push({ parent: current.id, key, id, array: Array.isArray(value) });
            stack.push({ id, entries: entries(value) });
        }
        if (nodes.length >= batchSize) {
            yield { type: 'nodes', nodes };
            nodes = [];
        }
    }
    if (nodes.length) yield { type: 'nodes', nodes };
    yield { type: 'complete' };
}

/** Apply one bounded worker batch without invoking prototype setters. */
export function applyGeoJSONNodes(containers, nodes) {
    for (const node of nodes) {
        const parent = containers.get(node.parent);
        const value = Object.hasOwn(node, 'id') ? (node.array ? [] : {}) : node.value;
        if (Object.hasOwn(node, 'id')) containers.set(node.id, value);
        if (node.key === '__proto__') {
            Object.defineProperty(parent, node.key, { value, enumerable: true, writable: true, configurable: true });
        } else {
            parent[node.key] = value;
        }
    }
}
