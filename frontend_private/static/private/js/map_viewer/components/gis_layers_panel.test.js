const mocks = vi.hoisted(() => ({
    desired: false,
    loading: false,
    runtime: {
        isDesired: vi.fn(() => mocks.desired),
        isLoading: vi.fn(() => mocks.loading),
        setDesired: vi.fn(async (_layer, desired) => {
            mocks.desired = desired;
            return desired;
        }),
    },
    store: { layers: [] },
}));

vi.mock('../gis_layers_runtime.js', () => ({
    getGISLayerRuntime: () => mocks.runtime,
}));
vi.mock('../gis_layer_store.js', () => ({ GISLayerStore: mocks.store }));
import { GISLayersPanel } from './gis_layers_panel.js';

class ResizeObserverMock {
    observe() {}
    disconnect() {}
}

describe('GIS Layers panel', () => {
    beforeEach(() => {
        global.ResizeObserver = ResizeObserverMock;
        mocks.desired = false;
        mocks.loading = false;
        mocks.store.layers = [];
        document.body.innerHTML = '<div id="map-container"><div id="map"></div></div>';
    });

    afterEach(() => {
        GISLayersPanel.destroy();
        vi.clearAllMocks();
    });

    it('uses one isolated left-stack panel without duplicating project or GPS controls', () => {
        mocks.store.layers = [{ id: 'layer-1', name: 'Protected areas', color: '#6366f1' }];
        GISLayersPanel.init();

        const panel = document.getElementById('gis-layers-panel');
        expect(panel.style.left).toBe('16px');
        expect(panel.style.display).toBe('none');
        expect(document.getElementById('gis-layers-panel-minimized').style.display).toBe('block');
        expect(document.getElementById('map-layers-mobile-drawer')).toBeNull();
        expect(document.getElementById('mobile-project-list')).toBeNull();
        expect(document.getElementById('mobile-gps-list')).toBeNull();
    });

    it('defaults OFF and activates from a card-body click', async () => {
        const layer = { id: 'layer-1', name: 'Protected areas', color: '#6366f1' };
        mocks.store.layers = [layer];
        GISLayersPanel.init();

        const item = document.querySelector('.gis-layer-button');
        expect(item.classList).toContain('opacity-50');
        expect(item.querySelector('input').checked).toBe(false);
        item.click();
        await vi.waitFor(() => expect(mocks.runtime.setDesired).toHaveBeenCalledWith(layer, true));
    });

    it('escapes API names in both text and attributes', () => {
        mocks.store.layers = [{
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

    it('allows a loading activation to be switched off immediately', async () => {
        const layer = { id: 'layer-1', name: 'Protected areas', color: '#6366f1' };
        mocks.store.layers = [layer];
        mocks.desired = true;
        mocks.loading = true;
        GISLayersPanel.init();

        const checkbox = document.querySelector('.gis-layer-button input');
        expect(checkbox.disabled).toBe(false);
        checkbox.checked = false;
        checkbox.dispatchEvent(new Event('change', { bubbles: true }));

        await vi.waitFor(() => expect(mocks.runtime.setDesired).toHaveBeenCalledWith(layer, false));
    });
});
