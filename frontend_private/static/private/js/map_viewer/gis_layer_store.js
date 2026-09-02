import { GISLayerClient } from './gis_layer_client.js';

let layers = null;

export const GISLayerStore = {
    get layers() { return layers || []; },
    getById(id) { return this.layers.find(layer => layer.id === String(id)) || null; },
    async load() {
        if (layers) return layers;
        try {
            const response = await GISLayerClient.list();
            layers = Array.isArray(response) ? response.map(layer => ({
                ...layer,
                id: String(layer.id),
            })) : [];
        } catch (error) {
            console.error('Failed to load private GIS Layers:', error);
            layers = [];
        }
        return layers;
    },
    async refresh() {
        layers = null;
        return this.load();
    },
    invalidate() { layers = null; },
};
