import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const mocks = vi.hoisted(() => ({
    getGISLayerDetails: vi.fn(),
    bounds: { isEmpty: vi.fn(() => false) },
}));

vi.mock('../api.js', () => ({
    API: { getGISLayerDetails: mocks.getGISLayerDetails },
}));
vi.mock('../config.js', async () => {
    const actual = await vi.importActual('../config.js');
    return {
        ...actual,
        Config: { getGISLayerById: vi.fn(() => ({ color: '#6366f1' })) },
    };
});
vi.mock('./colors.js', () => ({ Colors: {} }));
vi.mock('./geometry.js', () => ({ Geometry: {} }));


import { State } from '../state.js';
import { GIS_GEOMETRY_TYPE_PROPERTY, gisLayerGeometryFilter } from './gis_layer_geometry.js';
import {
    bindGISPopupScrollIsolation,
    buildGISFeaturePopup,
    Layers,
    updateGISPopupOverflowAffordance,
} from './layers.js';

describe('GIS Layer display', () => {
    beforeEach(() => {
        State.resetLayerState();
        State.gisLayerStates.clear();
        State.gisLayerLoadingStates.clear();
        State.gisLayerCache.clear();
        State.gisLayerGeometryTypeStates.clear();
        State.allGISLayerLayers.clear();
        State.gisLayerBounds.clear();
        State.gisLayerClickableLayerIds.clear();
        State.map = {
            addSource: vi.fn(),
            addLayer: vi.fn(),
            getLayer: vi.fn(),
            getSource: vi.fn(),
            getStyle: vi.fn(() => ({ layers: [] })),
            removeLayer: vi.fn(),
            removeSource: vi.fn(),
            setLayoutProperty: vi.fn(),
            setFilter: vi.fn(),
            moveLayer: vi.fn(),
        };
        mocks.getGISLayerDetails.mockReset();
        globalThis.fetch = vi.fn();
        globalThis.mapboxgl = { LngLatBounds: class { constructor() { return mocks.bounds; } } };
    });

    afterEach(() => {
        State.map = null;
        delete globalThis.mapboxgl;
        vi.restoreAllMocks();
    });

    it('refreshes detail, downloads once, and preserves the cached GeoJSON', async () => {
        const geojson = { type: 'FeatureCollection', features: [{
            type: 'Feature',
            properties: { untouched: true },
            geometry: { type: 'Point', coordinates: [-80, 25] },
        }] };
        mocks.getGISLayerDetails.mockResolvedValue({ file: '/fresh-signed-url' });
        fetch.mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue(geojson) });

        await expect(Layers.toggleGISLayerVisibility('layer-1', true)).resolves.toBe(true);

        expect(mocks.getGISLayerDetails).toHaveBeenCalledWith('layer-1', { signal: expect.any(AbortSignal) });
        expect(fetch).toHaveBeenCalledWith('/fresh-signed-url', { signal: expect.any(AbortSignal) });
        expect(State.map.addSource).toHaveBeenCalledWith('gis-layer-source-layer-1', {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [{
                ...geojson.features[0],
                properties: { untouched: true, [GIS_GEOMETRY_TYPE_PROPERTY]: 'Point' },
            }] },
            generateId: true,
            tolerance: 0,
        });
        expect(State.gisLayerCache.get('layer-1')).toBe(geojson);
        expect(geojson.features[0].properties).toEqual({ untouched: true });
        expect(State.gisLayerBounds.get('layer-1')).toBe(mocks.bounds);
    });

    it('never fetches an undefined URL when detail metadata has no file', async () => {
        mocks.getGISLayerDetails.mockResolvedValue({ id: 'layer-1' });

        await expect(Layers.toggleGISLayerVisibility('layer-1', true)).resolves.toBe(false);

        expect(fetch).not.toHaveBeenCalled();
        expect(State.gisLayerStates.get('layer-1')).toBe(false);
        expect(State.gisLayerLoadingStates.get('layer-1')).toBe(false);
        expect(State.gisLayerCache.has('layer-1')).toBe(false);
    });

    it('adds only the required polygon, line, and point rendering roles', async () => {
        await Layers.addGISLayer('layer-1', { type: 'FeatureCollection', features: [] });

        expect(State.map.addLayer.mock.calls.map(([layer]) => [layer.id, layer.type, layer.filter])).toEqual([
            ['gis-layer-layer-1-fill', 'fill', gisLayerGeometryFilter('Polygon', [])],
            ['gis-layer-layer-1-outline', 'line', gisLayerGeometryFilter('Polygon', [])],
            ['gis-layer-layer-1-line', 'line', gisLayerGeometryFilter('LineString', [])],
            ['gis-layer-layer-1-point', 'circle', gisLayerGeometryFilter('Point', [])],
        ]);
        const [, outline, line] = State.map.addLayer.mock.calls.map(([layer]) => layer);
        expect(outline.paint['line-width']).toEqual(['interpolate', ['linear'], ['zoom'],
            0, 1, 8, 1, 12, 1.5, 14, 1.5, 16, 1.5, 18, 1.5]);
        expect(line.paint['line-width']).toEqual(['interpolate', ['linear'], ['zoom'],
            0, 1, 8, 1, 12, 1.5, 14, 2, 16, 2.5, 18, 2.5]);
        expect(outline.minzoom ?? 0).toBe(0);
        expect(line.minzoom ?? 0).toBe(0);
        expect(line.paint['line-color']).toBe('#6366f1');
    });

    it('opens the exact safe feature card from polygon and point clicks', async () => {
        const popupContents = [];
        const popupOptions = [];
        class PopupMock {
            constructor(options) { popupOptions.push(options); }
            once() { return this; }
            setLngLat() { return this; }
            setDOMContent(content) { popupContents.push(content); return this; }
            addTo() { return this; }
        }
        globalThis.mapboxgl.Popup = PopupMock;
        for (const geometryType of ['Polygon', 'Point']) {
            Layers.openGISFeaturePopup({
                geometry: { type: geometryType },
                properties: {
                    name: '<img src=x onerror=alert(1)>',
                    description: '<script>alert(1)</script>',
                    folder_path: JSON.stringify(['Protected areas', 'North']),
                    extended_data: JSON.stringify({ owner: '<svg/onload=alert(1)>' }),
                },
            }, { lng: 0, lat: 0 });
        }

        expect(popupContents).toHaveLength(2);
        expect(popupOptions[0]).toEqual(expect.objectContaining({
            className: 'gis-layer-feature-popup',
            closeButton: true,
            closeOnClick: true,
            focusAfterOpen: true,
            maxWidth: '360px',
        }));
        const card = popupContents[0];
        expect(card.tagName).toBe('ARTICLE');
        expect(card.getAttribute('aria-label')).toBe('GIS feature details');
        expect(card.querySelector('img,script,svg')).toBeNull();
        expect(card.textContent).toContain('<img src=x onerror=alert(1)>');
        expect(card.textContent).toContain('<script>alert(1)</script>');
        expect(card.textContent).toContain('Polygon');
        expect(card.textContent).toContain('Protected areas / North');
        expect(card.textContent).toContain('<svg/onload=alert(1)>');
        expect(card.querySelector('.gis-layer-feature-card__header').parentElement).toBe(card);
        expect(card.querySelector('.gis-layer-feature-card__metadata').parentElement).toBe(card);
        const body = card.querySelector('.gis-layer-feature-card__body');
        const viewport = card.querySelector('.gis-layer-feature-card__scroll');
        expect(viewport.parentElement).toBe(body);
        expect(body.querySelector('.gis-layer-feature-card__scroll-rail').getAttribute('aria-hidden')).toBe('true');
    });

    it('closes map-owned GIS popups through their native lifecycle', async () => {
        const closed = [];
        class Popup {
            once(name, handler) { if (name === 'close') this.onClose = handler; return this; }
            setLngLat() { return this; }
            setDOMContent() { return this; }
            addTo() { return this; }
            remove() { closed.push(this); this.onClose(); }
        }
        globalThis.mapboxgl.Popup = Popup;
        Layers.openGISFeaturePopup({ properties: { name: 'First' } }, { lng: 0, lat: 0 });
        Layers.openGISFeaturePopup({ properties: { name: 'Second' } }, { lng: 1, lat: 1 });
        Layers.closeGISFeaturePopups();
        expect(closed).toHaveLength(2);
        Layers.closeGISFeaturePopups();
        expect(closed).toHaveLength(2);
    });

    it('renders missing properties safely with the prior fallback card', async () => {
        const setDOMContent = vi.fn().mockReturnThis();
        class PopupMock {
            once() { return this; }
            setLngLat() { return this; }
            setDOMContent(content) { setDOMContent(content); return this; }
            addTo() { return this; }
        }
        globalThis.mapboxgl.Popup = PopupMock;
        expect(() => Layers.openGISFeaturePopup({ geometry: { type: 'Point' } }, {})).not.toThrow();
        const card = setDOMContent.mock.calls[0][0];
        expect(card.querySelector('.gis-layer-feature-card__title').textContent).toBe('Untitled feature');
        expect(card.querySelector('.gis-layer-feature-card__description')).toBeNull();
        expect(card.textContent).toContain('Point');
    });

    it('keeps one stable clickable-layer registry when replacing a GIS Layer', async () => {
        const data = { type: 'FeatureCollection', features: [] };
        await Layers.addGISLayer('layer-1', data);
        await Layers.addGISLayer('layer-1', data);

        expect([...State.gisLayerClickableLayerIds]).toEqual([
            'gis-layer-layer-1-fill',
            'gis-layer-layer-1-point',
        ]);
    });

    it('preserves bounded metadata and the exact scoped popup CSS', async () => {
        const popup = buildGISFeaturePopup({
            geometry: { type: 'Point' },
            properties: {
                title: 'Feature title',
                description: 'x'.repeat(2000),
                extended_data: Object.fromEntries(
                    Array.from({ length: 10 }, (_, index) => [`field_${index}`, 'value']),
                ),
            },
        });
        expect(popup.querySelector('.gis-layer-feature-card__title').textContent).toBe('Feature title');
        expect(popup.querySelector('.gis-layer-feature-card__description').textContent.length).toBe(1200);
        expect(popup.querySelectorAll('.gis-layer-feature-card__metadata dt')).toHaveLength(4);

        const css = readFileSync(resolve('frontend_private/static/private/css/map_viewer.css'), 'utf8');
        expect(css).toContain('.mapboxgl-popup.gis-layer-feature-popup .mapboxgl-popup-content');
        expect(css).toContain('.mapboxgl-popup.gis-layer-feature-popup .mapboxgl-popup-close-button');
        expect(css).toMatch(/\.gis-layer-feature-card__scroll\s*\{[^}]*overscroll-behavior:\s*contain;/s);
        expect(css).toContain('.gis-layer-feature-card.is-scrollable .gis-layer-feature-card__scroll-rail');
        expect(css).toContain('.gis-layer-feature-card__scroll-thumb');
    });

    it('preserves the custom overflow affordance and scroll isolation', async () => {
        const card = buildGISFeaturePopup({ properties: { description: 'Description' } });
        const viewport = card.querySelector('.gis-layer-feature-card__scroll');
        const rail = card.querySelector('.gis-layer-feature-card__scroll-rail');
        const thumb = card.querySelector('.gis-layer-feature-card__scroll-thumb');
        Object.defineProperties(viewport, {
            clientHeight: { configurable: true, value: 100 },
            scrollHeight: { configurable: true, value: 400 },
            scrollTop: { configurable: true, value: 150, writable: true },
        });
        Object.defineProperty(rail, 'clientHeight', { configurable: true, value: 100 });

        expect(updateGISPopupOverflowAffordance(card)).toBe(true);
        expect(card.classList).toContain('is-scrollable');
        expect(viewport.tabIndex).toBe(0);
        expect(viewport.getAttribute('aria-label')).toBe('Scrollable feature description');
        expect(thumb.style.height).toBe('28px');
        expect(thumb.style.transform).toBe('translateY(36px)');

        const parent = document.createElement('div');
        parent.appendChild(viewport);
        const parentWheel = vi.fn();
        parent.addEventListener('wheel', parentWheel);
        const cleanup = bindGISPopupScrollIsolation(viewport);
        viewport.dispatchEvent(new WheelEvent('wheel', { bubbles: true, deltaY: 100 }));
        expect(parentWheel).not.toHaveBeenCalled();
        cleanup();
    });

    it('reuses cached data and only changes visibility on later toggles', async () => {
        State.gisLayerCache.set('layer-1', { type: 'FeatureCollection', features: [] });
        State.allGISLayerLayers.set('layer-1', ['gis-layer-layer-1-line']);
        State.map.getLayer.mockReturnValue({});

        await Layers.toggleGISLayerVisibility('layer-1', true);
        await Layers.toggleGISLayerVisibility('layer-1', false);

        expect(mocks.getGISLayerDetails).not.toHaveBeenCalled();
        expect(fetch).not.toHaveBeenCalled();
        expect(State.map.setLayoutProperty).toHaveBeenLastCalledWith(
            'gis-layer-layer-1-line',
            'visibility',
            'none',
        );
    });

    it('re-registers a visible cached layer after a map style rebuild', async () => {
        const geojson = { type: 'FeatureCollection', features: [] };
        State.gisLayerCache.set('layer-1', geojson);

        await Layers.toggleGISLayerVisibility('layer-1', true);

        expect(mocks.getGISLayerDetails).not.toHaveBeenCalled();
        expect(fetch).not.toHaveBeenCalled();
        expect(State.map.addSource).toHaveBeenCalledWith(
            'gis-layer-source-layer-1',
            expect.objectContaining({ data: geojson, tolerance: 0 }),
        );
    });

    it('reverts visibility after a failed display request', async () => {
        mocks.getGISLayerDetails.mockRejectedValue(new Error('revoked'));
        vi.spyOn(console, 'error').mockImplementation(() => {});

        await expect(Layers.toggleGISLayerVisibility('layer-1', true)).resolves.toBe(false);

        expect(Layers.isGISLayerVisible('layer-1')).toBe(false);
        expect(Layers.isGISLayerLoading('layer-1')).toBe(false);
    });

    it('filters exact geometry types without downloading or replacing the source', async () => {
        const types = ['Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'];
        const geojson = { type: 'FeatureCollection', features: types.map(type => ({
            type: 'Feature', properties: {}, geometry: { type, coordinates: [] }
        })) };
        State.gisLayerCache.set('layer-1', geojson);
        await Layers.toggleGISLayerVisibility('layer-1', true);
        State.map.getLayer.mockReturnValue({});

        await Layers.setGISLayerGeometryTypeVisibility('layer-1', 'Polygon', false);

        expect(Layers.getGISLayerGeometryTypes('layer-1')).toEqual(types);
        expect(Layers.isGISLayerGeometryTypeVisible('layer-1', 'Polygon')).toBe(false);
        expect(Layers.isGISLayerVisible('layer-1')).toBe(true);
        const enabledTypes = types.filter(type => type !== 'Polygon');
        const roles = [['fill', 'Polygon'], ['outline', 'Polygon'], ['line', 'LineString'], ['point', 'Point']];
        expect(State.map.setFilter.mock.calls).toEqual(roles.map(([role, family]) => [
            `gis-layer-layer-1-${role}`, gisLayerGeometryFilter(family, enabledTypes)
        ]));
        expect(State.map.addSource).toHaveBeenCalledTimes(1);
        expect(fetch).not.toHaveBeenCalled();

        // Master visibility is a separate gate and keeps the chosen type filters.
        await Layers.toggleGISLayerVisibility('layer-1', false);
        await Layers.toggleGISLayerVisibility('layer-1', true);
        expect(Layers.isGISLayerGeometryTypeVisible('layer-1', 'Polygon')).toBe(false);
        expect(State.map.setFilter).toHaveBeenCalledTimes(4);

        // A style rebuild recreates the four roles with those same preferences.
        State.allGISLayerLayers.clear();
        State.map.addLayer.mockClear();
        await Layers.toggleGISLayerVisibility('layer-1', true);
        expect(State.map.addLayer.mock.calls.map(([layer]) => layer.filter)).toEqual(
            roles.map(([, family]) => gisLayerGeometryFilter(family, enabledTypes))
        );
        expect(fetch).not.toHaveBeenCalled();
    });

    it('allows all types to be hidden and restored, independently for each layer', async () => {
        const geojson = { type: 'GeometryCollection', geometries: [
            { type: 'Point', coordinates: [1, 2] },
            { type: 'LineString', coordinates: [[1, 2], [3, 4]] }
        ] };
        await Layers.addGISLayer('layer-1', geojson);
        await Layers.addGISLayer('layer-2', geojson);
        State.map.getLayer.mockReturnValue({});
        await Layers.setGISLayerGeometryTypeVisibility('layer-1', 'Point', false);
        await Layers.setGISLayerGeometryTypeVisibility('layer-1', 'LineString', false);
        expect(State.map.setFilter).toHaveBeenLastCalledWith(
            'gis-layer-layer-1-point', gisLayerGeometryFilter('Point', [])
        );
        expect(Layers.isGISLayerGeometryTypeVisible('layer-2', 'Point')).toBe(true);
        await Layers.setGISLayerGeometryTypeVisibility('layer-1', 'Point', true);
        expect(State.map.setFilter).toHaveBeenLastCalledWith(
            'gis-layer-layer-1-point', gisLayerGeometryFilter('Point', ['Point'])
        );
    });
});
