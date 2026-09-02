import { Utils } from './utils.js';

async function request(url, options = {}) {
    const response = await fetch(url, {
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': Utils.getCSRFToken() },
        ...options,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

export const GISLayerClient = {
    list: () => request(Urls['api:v2:gis-layers']()),
    detail: (id, signal) => request(Urls['api:v2:gis-layer-detail'](id), { signal }),
};
