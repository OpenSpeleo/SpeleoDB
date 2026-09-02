import { GISLayerClient } from './gis_layer_client.js';
import { LazyOverlayManager } from './lazy_overlay_manager.js';
import { GISLayerRenderer } from './map/gis_layers.js';
import { Utils } from './utils.js';
import { DEFAULTS } from './config.js';
import { Layers } from './map/layers.js';

let runtime = null;

export async function fetchGISLayerData(layer, signal) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    const currentLayer = await GISLayerClient.detail(layer.id, signal);
    if (!currentLayer?.file) throw new Error('The GIS Layer is no longer accessible.');
    return {
        url: currentLayer.file,
        direct_source: currentLayer.source_format === 'GEOJSON',
    };
}

export function getGISLayerRuntime() {
    if (runtime) return runtime;
    runtime = new LazyOverlayManager({
        getVersion: layer => [layer.modified_date, layer.color].join(':'),
        fetchData: fetchGISLayerData,
        attach: async (layer, data, activation) => {
            const registration = await GISLayerRenderer.attach(layer, data, activation);
            Layers.reorderLayers();
            return registration;
        },
        setVisible: async (registration, visible) => GISLayerRenderer.setVisible(registration, visible),
        remove: async registration => GISLayerRenderer.remove(registration),
        onStateChange: (layerId, lifecycle) => {
            window.dispatchEvent(new CustomEvent('speleo:gis-layer-state-changed', { detail: { layerId, ...lifecycle } }));
        },
        onError: (_layerId, error, layer) => {
            console.error(`Unable to display ${layer?.name || 'GIS Layer'}`, error);
            const reason = error?.message ? ` ${error.message}` : '';
            Utils.showNotification('error', `Unable to display ${layer?.name || 'GIS Layer'}.${reason}`);
        },
        maxCacheEntries: DEFAULTS.UI.OVERLAY_CACHE_MAX_ENTRIES,
    });
    return runtime;
}

export function resetGISLayerRuntime() {
    runtime = null;
}
