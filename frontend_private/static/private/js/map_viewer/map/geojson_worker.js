import { geoJSONMessages } from './geojson_transport.js';

let messages;
self.onmessage = ({ data }) => {
    try {
        if (data.type === 'parse') messages = geoJSONMessages(data.buffer, data.batchSize);
        const next = messages.next();
        if (!next.done) self.postMessage(next.value);
    } catch {
        // Never send parser excerpts: they can contain private survey data.
        self.postMessage({ type: 'error' });
    }
};
