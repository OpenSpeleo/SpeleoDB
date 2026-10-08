import { applyGeoJSONNodes, geoJSONMessages } from './geojson_transport.ts';
import type { JSONContainer, JSONObject, JSONValue } from '../../../../../../ts-types/domain/json.ts';
import type { GeoJSONMessage } from '../../../../../../ts-types/worker/geojson.ts';

function encode(value: JSONValue): ArrayBuffer {
    return new TextEncoder().encode(JSON.stringify(value)).buffer;
}

function decode(messages: GeoJSONMessage[]): JSONValue | undefined {
    let root: JSONValue | undefined;
    const containers = new Map<number, JSONContainer>();
    for (const message of messages) {
        if (message.type === 'result') root = message.data;
        if (message.type === 'start') {
            root = message.array ? [] : {};
            containers.set(0, root);
        }
        if (message.type === 'nodes') applyGeoJSONNodes(containers, message.nodes);
    }
    return root;
}

describe('GeoJSON transport translation contract', () => {
    it.each([null, false, 0, 'text'])('returns primitive JSON directly for %s', value => {
        expect([...geoJSONMessages(encode(value), 1)]).toEqual([{ type: 'result', data: value }]);
    });

    it('round-trips nested objects, arrays, empty containers and numerical positions in bounded batches', () => {
        const original = {
            type: 'FeatureCollection',
            features: [{ type: 'Feature', properties: { name: 'Station', tags: [], extra: {} },
                geometry: { type: 'LineString', coordinates: [[1, 2, 3], [4, 5, 6]] } }],
        };
        const messages = [...geoJSONMessages(encode(original), 2)];
        expect(messages[0]).toEqual({ type: 'start', array: false });
        expect(messages.at(-1)).toEqual({ type: 'complete' });
        const batches = messages.filter(message => message.type === 'nodes');
        expect(batches.every(message => message.nodes.length <= 2)).toBe(true);
        expect(decode(messages)).toEqual(original);
        expect(batches.flatMap(message => message.nodes).some(node => Array.isArray(node.value))).toBe(true);
    });

    it('preserves root arrays and objects with no children', () => {
        for (const value of [[], {}, [[], {}, [1, 2, 3, 4, 5]]]) {
            expect(decode([...geoJSONMessages(encode(value), 1)])).toEqual(value);
        }
    });

    it('defines __proto__ as an own data property without mutating the receiving prototype', () => {
        const original = JSON.parse('{"__proto__":{"polluted":true},"constructor":"ordinary"}') as JSONValue;
        const result = decode([...geoJSONMessages(encode(original), 1)]) as JSONObject;
        expect(Object.getPrototypeOf(result)).toBe(Object.prototype);
        expect(Object.hasOwn(result, '__proto__')).toBe(true);
        expect(Object.getOwnPropertyDescriptor(result, '__proto__')).toEqual({
            value: { polluted: true }, enumerable: true, writable: true, configurable: true,
        });
        expect(result.constructor).toBe('ordinary');
        expect(({} as { polluted?: boolean }).polluted).toBeUndefined();
    });

    it.each([0, -1, 1.5, Number.NaN])('throws the existing batch-size error lazily for %s', size => {
        const generator = geoJSONMessages(encode({}), size);
        expect(() => generator.next()).toThrow('Invalid transport batch size');
    });

    it('parses before validating batch size and preserves the parse exception', () => {
        const generator = geoJSONMessages(new TextEncoder().encode('{').buffer, 0);
        expect(() => generator.next()).toThrow(SyntaxError);
    });

    it('retains supplied container identity and the undefined mutation return', () => {
        const root = {};
        const containers = new Map<number, JSONContainer>([[0, root]]);
        expect(applyGeoJSONNodes(containers, [{ parent: 0, key: 'name', value: 'Station' }])).toBeUndefined();
        expect(containers.get(0)).toBe(root);
        expect(root).toEqual({ name: 'Station' });
    });
});
