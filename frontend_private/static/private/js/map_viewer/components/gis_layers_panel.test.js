import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const mocks = vi.hoisted(() => ({
    visible: false,
    loading: false,
    layers: [],
    bounds: new Map(),
    geometryTypes: [],
    geometryVisibility: new Map(),
    fitBounds: vi.fn(),
    setGeometryVisibility: vi.fn((id, type, visible) => {
        mocks.geometryVisibility.set(`${id}/${type}`, visible);
    }),
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
        getGISLayerGeometryTypes: vi.fn(() => mocks.geometryTypes),
        isGISLayerGeometryTypeVisible: vi.fn((id, type) => mocks.geometryVisibility.get(`${id}/${type}`) !== false),
        setGISLayerGeometryTypeVisibility: mocks.setGeometryVisibility,
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
        mocks.geometryTypes = [];
        mocks.geometryVisibility.clear();
        mocks.bounds.clear();
        document.body.innerHTML = '<div id="map-container"><div id="map"></div></div>';
    });

    afterEach(() => {
        GISLayersPanel.destroy();
        vi.clearAllMocks();
    });

    it('uses the shared folded-card dimensions in the private left stack', () => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas', color: '#6366f1' }];
        GISLayersPanel.init();

        const minimized = document.getElementById('gis-layers-panel-minimized');
        expect(document.getElementById('gis-layers-panel').style.left).toBe('16px');
        expect(minimized.style.display).toBe('block');
        const css = readFileSync(resolve('frontend_private/static/private/css/map_viewer.css'), 'utf8');
        expect(css).toMatch(/#gis-layers-panel-minimized,\s*#gis-geometries-panel-minimized\s*\{[^}]*width:\s*160px;[^}]*height:\s*48px/s);
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
        mocks.geometryTypes = ['Point', 'Polygon'];
        GISLayersPanel.init();

        const item = document.querySelector('.gis-layer-button');
        expect(item.querySelector('img')).toBeNull();
        expect(item.textContent).toContain('<img src=x');
        expect(item.querySelector('span[title]').getAttribute('title')).toBe('<img src=x onerror=alert(1)>');
        expect(item.querySelector('[data-geometry-type="Point"] input').getAttribute('aria-label'))
            .toBe('Show Point in <img src=x onerror=alert(1)>');
    });

    it.each([{ types: [] }, { types: ['LineString'] }, { types: ['MultiPolygon'] }])('omits geometry subcontrols for unknown or single-type layers: %j', ({ types }) => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas' }];
        mocks.geometryTypes = types;
        GISLayersPanel.init();

        expect(document.querySelector('[data-geometry-type-controls]')).toBeNull();
        expect(document.querySelectorAll('.gis-layer-button input')).toHaveLength(1);
    });

    it('discovers actual mixed types after loading and labels each control with its type and layer', () => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas' }];
        GISLayersPanel.init();
        expect(document.querySelector('[data-geometry-type-controls]')).toBeNull();

        mocks.visible = true;
        mocks.geometryTypes = ['Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'];
        window.dispatchEvent(new CustomEvent('speleo:gis-layer-loading-changed', { detail: { layerId: 'layer-1' } }));

        const rows = [...document.querySelectorAll('[data-geometry-type]')];
        expect(rows.map(row => row.dataset.geometryType)).toEqual(mocks.geometryTypes);
        for (const row of rows) {
            expect(row.closest('.gis-layer-button').dataset.layerId).toBe('layer-1');
            const checkbox = row.querySelector('input');
            expect(checkbox.labels[0]).toBe(row);
            expect(checkbox.getAttribute('aria-label')).toBe(`Show ${row.dataset.geometryType} in Protected areas`);
            expect(checkbox.checked).toBe(true);
            expect(checkbox.disabled).toBe(false);
        }
    });

    it('changes only the selected subtype without zooming, toggling the master or replacing focused controls', () => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas' }];
        mocks.geometryTypes = ['Point', 'MultiLineString'];
        mocks.visible = true;
        mocks.bounds.set('layer-1', { bbox: true });
        GISLayersPanel.init();
        const master = document.querySelector('.gis-layer-button input');
        const row = document.querySelector('[data-geometry-type="MultiLineString"]');
        const checkbox = row.querySelector('input');
        checkbox.focus();
        checkbox.click();

        expect(mocks.setGeometryVisibility).toHaveBeenLastCalledWith('layer-1', 'MultiLineString', false);
        expect(document.activeElement).toBe(checkbox);
        expect(document.querySelector('[data-geometry-type="MultiLineString"] input')).toBe(checkbox);
        row.querySelector('span').click();
        expect(mocks.setGeometryVisibility).toHaveBeenLastCalledWith('layer-1', 'MultiLineString', true);
        expect(mocks.setGeometryVisibility).toHaveBeenCalledTimes(2);
        document.querySelector('[data-geometry-type-controls]').click();
        expect(master.checked).toBe(true);
        expect(mocks.toggle).not.toHaveBeenCalled();
        expect(mocks.fitBounds).not.toHaveBeenCalled();
    });

    it.each([
        { visible: false, loading: false },
        { visible: true, loading: true },
    ])('disables subcontrols while the parent is hidden or loading: %j', state => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas' }];
        mocks.geometryTypes = ['Point', 'Polygon'];
        mocks.visible = state.visible;
        mocks.loading = state.loading;
        mocks.geometryVisibility.set('layer-1/Polygon', false);
        GISLayersPanel.init();

        const checkboxes = [...document.querySelectorAll('[data-geometry-type] input')];
        expect(checkboxes.every(checkbox => checkbox.disabled)).toBe(true);
        expect(checkboxes.map(checkbox => checkbox.checked)).toEqual([true, false]);
        for (const checkbox of checkboxes) {
            checkbox.click();
            checkbox.closest('label').click();
        }
        expect(mocks.setGeometryVisibility).not.toHaveBeenCalled();
        expect(mocks.toggle).not.toHaveBeenCalled();
        expect(mocks.fitBounds).not.toHaveBeenCalled();
    });

    it('retains subtype preferences when the master is switched off and on', async () => {
        mocks.layers = [{ id: 'layer-1', name: 'Protected areas' }];
        mocks.geometryTypes = ['Point', 'Polygon'];
        mocks.visible = true;
        mocks.geometryVisibility.set('layer-1/Polygon', false);
        GISLayersPanel.init();

        document.querySelector('.gis-layer-button input').click();
        await vi.waitFor(() => expect(document.querySelector('[data-geometry-type="Point"] input').disabled).toBe(true));
        document.querySelector('.gis-layer-button input').click();
        await vi.waitFor(() => expect(document.querySelector('[data-geometry-type="Point"] input').disabled).toBe(false));
        expect(document.querySelector('[data-geometry-type="Point"] input').checked).toBe(true);
        expect(document.querySelector('[data-geometry-type="Polygon"] input').checked).toBe(false);
        expect(mocks.setGeometryVisibility).not.toHaveBeenCalled();
        expect(mocks.fitBounds).not.toHaveBeenCalled();
    });
});
