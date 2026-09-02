import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const mocks = vi.hoisted(() => ({
    visible: false,
    loading: false,
    layers: [],
    bounds: new Map(),
    fitBounds: vi.fn(),
    toggle: vi.fn(async (_id, visible) => {
        mocks.visible = visible;
        return true;
    }),
}));

vi.mock('../config.js', async () => {
    const actual = await vi.importActual('../config.js');
    return {
        DEFAULTS: actual.DEFAULTS,
        Config: {
            get gisLayers() { return mocks.layers; },
            getGISLayerById: id => mocks.layers.find(layer => layer.id === String(id)) || null,
        },
    };
});
vi.mock('../map/layers.js', () => ({
    Layers: {
        isGISLayerVisible: vi.fn(() => mocks.visible),
        isGISLayerLoading: vi.fn(() => mocks.loading),
        toggleGISLayerVisibility: mocks.toggle,
    },
}));
vi.mock('../state.js', () => ({
    State: {
        gisLayerBounds: mocks.bounds,
        map: { fitBounds: mocks.fitBounds },
    },
}));

import { GISLayersPanel } from './gis_layers_panel.js';

class ResizeObserverMock {
    observe() {}
    disconnect() {}
}

describe('GIS Layers panel', () => {
    beforeEach(() => {
        global.ResizeObserver = ResizeObserverMock;
        mocks.visible = false;
        mocks.loading = false;
        mocks.layers = [];
        mocks.bounds.clear();
        document.body.innerHTML = '<div id="map-container"><div id="map"></div></div>';
    });

    afterEach(() => {
        GISLayersPanel.destroy();
        vi.clearAllMocks();
    });

    it('uses one private left-stack panel with the 130px collapsed contract', () => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas', color: '#6366f1' }];
        GISLayersPanel.init();

        const minimized = document.getElementById('gis-layers-panel-minimized');
        expect(document.getElementById('gis-layers-panel').style.left).toBe('16px');
        expect(minimized.style.display).toBe('block');
        const css = readFileSync(resolve('frontend_private/static/private/css/map_viewer.css'), 'utf8');
        expect(css).toMatch(/#gis-layers-panel-minimized\s*\{[^}]*width:\s*130px/s);
        expect(document.getElementById('map-layers-mobile-drawer')).toBeNull();
    });

    it('activates a hidden layer and zooms only with its bounds', async () => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas', color: '#6366f1' }];
        const bounds = { bbox: true };
        mocks.bounds.set('layer-1', bounds);
        GISLayersPanel.init();

        document.querySelector('.gis-layer-button').click();

        await vi.waitFor(() => expect(mocks.toggle).toHaveBeenCalledWith('layer-1', true));
        expect(mocks.fitBounds).toHaveBeenCalledWith(bounds, { padding: 50, maxZoom: 16 });
    });

    it('keeps toggle clicks isolated from card zoom', async () => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas', color: '#6366f1' }];
        mocks.bounds.set('layer-1', { bbox: true });
        GISLayersPanel.init();
        const checkbox = document.querySelector('.gis-layer-button input');
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event('change', { bubbles: true }));

        await vi.waitFor(() => expect(mocks.toggle).toHaveBeenCalledWith('layer-1', true));
        expect(mocks.fitBounds).not.toHaveBeenCalled();
    });

    it('escapes API names in text and attributes', () => {
        mocks.layers = [{
            id: 'layer-1',
            name: '<img src=x onerror=alert(1)>',
            color: 'not-a-color',
        }];
        GISLayersPanel.init();

        const item = document.querySelector('.gis-layer-button');
        expect(item.querySelector('img')).toBeNull();
        expect(item.textContent).toContain('<img src=x');
        expect(item.querySelector('span[title]').getAttribute('title')).toBe('<img src=x onerror=alert(1)>');
    });
});
