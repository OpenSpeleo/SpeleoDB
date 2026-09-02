import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
    bindGISPopupScrollBehavior,
    bindGISPopupScrollIsolation,
    buildGISFeaturePopup,
    GISLayerRenderer,
    updateGISPopupOverflowAffordance,
} from './gis_layers.js';
import { State } from '../state.js';

const GEOJSON_URL = 'https://storage.test/layer.geojson?signed=1';

describe('GISLayerRenderer', () => {
    beforeEach(() => {
        globalThis.mapboxgl = {};
        State.map = { addSource: vi.fn(), addLayer: vi.fn(), getLayer: vi.fn(() => true), getSource: vi.fn(() => true), isSourceLoaded: vi.fn(() => true), on: vi.fn(), off: vi.fn(), setLayoutProperty: vi.fn(), removeLayer: vi.fn(), removeSource: vi.fn() };
    });
    afterEach(() => {
        State.map = null;
        delete globalThis.mapboxgl;
    });

    it('registers polygon fill/outline, line, point and label as one logical overlay', async () => {
        const registration = await GISLayerRenderer.attach({ id: 'layer-1', color: '#377eb8' }, { url: GEOJSON_URL });
        expect(State.map.addSource).toHaveBeenCalledWith('gis-layer-source-layer-1', expect.objectContaining({ type: 'geojson', data: GEOJSON_URL }));
        expect(registration.layerIds).toHaveLength(5);
        expect(State.map.addLayer.mock.calls.map(call => call[0].type)).toEqual(['fill', 'line', 'line', 'circle', 'symbol']);
        expect(State.map.addLayer.mock.calls[0][0].paint['fill-color']).toEqual(['coalesce', ['get', 'render_color'], '#377eb8']);
        expect(State.map.addLayer.mock.calls[0][0].paint['fill-opacity']).toEqual(['coalesce', ['get', 'render_fill_opacity'], 0.35]);
        expect(State.map.addLayer.mock.calls[1][0].paint['line-opacity']).toEqual(['coalesce', ['get', 'render_outline_opacity'], 0.95]);
        expect(State.map.addLayer.mock.calls[2][0].paint['line-width']).toEqual(['coalesce', ['get', 'render_line_width'], 2.5]);
        expect(State.map.addLayer.mock.calls[4][0].layout['text-field']).toEqual(['get', 'render_label']);
        expect(State.map.addLayer.mock.calls.every(call => call[0].layout.visibility === 'none')).toBe(true);
    });

    it('renders direct GeoJSON with layer-owned styles instead of source render properties', async () => {
        await GISLayerRenderer.attach(
            { id: 'layer-1', color: '#377eb8' },
            { direct_source: true, url: GEOJSON_URL },
        );

        const [fill, outline, line, point, label] = State.map.addLayer.mock.calls
            .map(call => call[0]);
        expect(fill.paint['fill-color']).toBe('#377eb8');
        expect(fill.paint['fill-opacity']).toBe(0.35);
        expect(outline.paint['line-width']).toBe(1.5);
        expect(outline.paint['line-opacity']).toBe(0.95);
        expect(line.paint['line-width']).toBe(2.5);
        expect(point.paint['circle-color']).toBe('#377eb8');
        expect(label.layout['text-field']).toEqual(['get', 'name']);
        expect(JSON.stringify(State.map.addLayer.mock.calls)).not.toContain('render_');
    });

    it('rejects missing display data', async () => {
        const attachment = GISLayerRenderer.attach(
            { id: 'layer-1' },
            {},
        );
        await expect(attachment).rejects.toThrow('no display file');
    });

    it('keeps popup handlers while hidden and removes them with every child layer and source', () => {
        const popupHandler = vi.fn();
        const registration = { layerIds: ['fill', 'line'], sourceIds: ['source'], popupHandlers: [{ layerId: 'line', handler: popupHandler }] };
        GISLayerRenderer.setVisible(registration, false);
        expect(State.map.setLayoutProperty).toHaveBeenCalledTimes(2);
        expect(State.map.off).not.toHaveBeenCalledWith('click', 'line', popupHandler);
        GISLayerRenderer.remove(registration);
        expect(State.map.off).toHaveBeenCalledWith('click', 'line', popupHandler);
        expect(State.map.removeLayer).toHaveBeenCalledTimes(2);
        expect(State.map.removeSource).toHaveBeenCalledWith('source');
    });

    it('rejects Mapbox source errors and cleans partial map objects', async () => {
        State.map.isSourceLoaded.mockReturnValue(false);
        const attachment = GISLayerRenderer.attach(
            { id: 'layer-1' },
            { url: GEOJSON_URL },
        );
        const errorHandler = State.map.on.mock.calls.find(([event]) => event === 'error')[1];
        errorHandler({ sourceId: 'gis-layer-source-layer-1' });
        await expect(attachment).rejects.toThrow('could not be loaded');
        expect(State.map.removeSource).toHaveBeenCalledWith('gis-layer-source-layer-1');
    });

    it('uses generation-unique IDs and aborts source waiting without touching a newer generation', async () => {
        State.map.isSourceLoaded.mockReturnValue(false);
        const firstController = new AbortController();
        const firstAttachment = GISLayerRenderer.attach(
            { id: 'layer-1' },
            { url: GEOJSON_URL },
            { generation: 1, signal: firstController.signal },
        );
        const secondController = new AbortController();
        const secondAttachment = GISLayerRenderer.attach(
            { id: 'layer-1' },
            { url: GEOJSON_URL },
            { generation: 2, signal: secondController.signal },
        );

        firstController.abort();
        await expect(firstAttachment).rejects.toMatchObject({ name: 'AbortError' });
        expect(State.map.removeSource).toHaveBeenCalledWith('gis-layer-source-layer-1-g1');
        expect(State.map.removeSource).not.toHaveBeenCalledWith('gis-layer-source-layer-1-g2');

        const sourcedataHandlers = State.map.on.mock.calls
            .filter(([event]) => event === 'sourcedata')
            .map(call => call[1]);
        State.map.isSourceLoaded.mockReturnValue(true);
        sourcedataHandlers.at(-1)({ sourceId: 'gis-layer-source-layer-1-g2' });
        await expect(secondAttachment).resolves.toEqual(expect.objectContaining({
            sourceIds: ['gis-layer-source-layer-1-g2'],
        }));
    });

    it('rolls back every child created before a synchronous Mapbox setup failure', async () => {
        State.map.addLayer.mockImplementationOnce(() => {}).mockImplementationOnce(() => {
            throw new Error('style changed');
        });

        const attachment = GISLayerRenderer.attach(
            { id: 'layer-1' },
            { url: GEOJSON_URL },
            { generation: 3 },
        );

        await expect(attachment).rejects.toThrow('style changed');
        expect(State.map.removeLayer).toHaveBeenCalledWith('gis-layer-layer-1-g3-fill');
        expect(State.map.removeSource).toHaveBeenCalledWith('gis-layer-source-layer-1-g3');
    });

    it('renders a scoped, accessible popup with safe bounded feature content', async () => {
        const setDOMContent = vi.fn().mockReturnThis();
        let popupOptions;
        let closePopup;
        class PopupMock {
            constructor(options) { popupOptions = options; }
            once(event, handler) { if (event === 'close') closePopup = handler; return this; }
            setLngLat() { return this; }
            setDOMContent(element) { setDOMContent(element); return this; }
            addTo() { return this; }
        }
        globalThis.mapboxgl.Popup = PopupMock;
        await GISLayerRenderer.attach({ id: 'layer-1' }, { url: GEOJSON_URL });
        const clickBinding = State.map.on.mock.calls.find(([event, layerId]) => event === 'click' && layerId.endsWith('-point'));
        clickBinding[2]({
            lngLat: { lng: 0, lat: 0 },
            features: [{
                geometry: { type: 'Polygon' },
                properties: {
                    name: '<img src=x onerror=alert(1)>',
                    description: '<script>alert(1)</script>',
                    folder_path: JSON.stringify(['Protected areas', 'North']),
                    extended_data: JSON.stringify({ owner: '<svg/onload=alert(1)>', empty: null }),
                },
            }],
        });
        const container = setDOMContent.mock.calls[0][0];
        expect(popupOptions).toEqual(expect.objectContaining({
            className: 'gis-layer-feature-popup',
            closeButton: true,
            focusAfterOpen: true,
            maxWidth: '360px',
        }));
        expect(container.tagName).toBe('ARTICLE');
        expect(container.getAttribute('aria-label')).toBe('GIS feature details');
        expect(container.querySelector('img,script,svg')).toBeNull();
        expect(container.textContent).toContain('<img src=x onerror=alert(1)>');
        expect(container.textContent).toContain('<script>alert(1)</script>');
        expect(container.textContent).toContain('Polygon');
        expect(container.textContent).toContain('Protected areas / North');
        expect(container.textContent).toContain('<svg/onload=alert(1)>');
        expect(container.querySelector('.gis-layer-feature-card__header').parentElement).toBe(container);
        expect(container.querySelector('.gis-layer-feature-card__metadata').parentElement).toBe(container);
        const body = container.querySelector('.gis-layer-feature-card__body');
        const viewport = container.querySelector('.gis-layer-feature-card__scroll');
        expect(body.parentElement).toBe(container);
        expect(viewport.parentElement).toBe(body);
        expect(viewport.querySelector('.gis-layer-feature-card__description')).not.toBeNull();
        expect(viewport.querySelector('.gis-layer-feature-card__header')).toBeNull();
        expect(viewport.querySelector('.gis-layer-feature-card__metadata')).toBeNull();
        expect(body.querySelector('.gis-layer-feature-card__scroll-rail').getAttribute('aria-hidden')).toBe('true');
        closePopup();
    });

    it('bounds description and metadata volume', () => {
        const popup = buildGISFeaturePopup({
            geometry: { type: 'Point' },
            properties: {
                name: 'Feature',
                description: 'x'.repeat(2000),
                extended_data: Object.fromEntries(Array.from({ length: 10 }, (_, index) => [`field_${index}`, 'value'])),
            },
        });
        expect(popup.querySelector('.gis-layer-feature-card__description').textContent.length).toBe(1200);
        expect(popup.querySelectorAll('.gis-layer-feature-card__metadata dt')).toHaveLength(4);
    });

    it('keeps Mapbox shell overrides scoped to GIS feature popups', () => {
        const css = readFileSync(resolve('frontend_private/static/private/css/map_viewer.css'), 'utf8');
        expect(css).toContain('.mapboxgl-popup.gis-layer-feature-popup .mapboxgl-popup-content');
        expect(css).toContain('.mapboxgl-popup.gis-layer-feature-popup .mapboxgl-popup-close-button');
        expect(css).toContain('.mapboxgl-popup.gis-layer-feature-popup.mapboxgl-popup-anchor-bottom .mapboxgl-popup-tip');
        expect(css).toMatch(/\.gis-layer-feature-card__scroll\s*\{[^}]*overscroll-behavior:\s*contain;/s);
        expect(css).toMatch(/\.gis-layer-feature-card__scroll\s*\{[^}]*touch-action:\s*pan-y;/s);
        expect(css).toMatch(/\.gis-layer-feature-card__scroll\s*\{[^}]*scrollbar-width:\s*none;/s);
        expect(css).toContain('.gis-layer-feature-card.is-scrollable .gis-layer-feature-card__scroll-rail');
        expect(css).toMatch(/\.gis-layer-feature-card__scroll-rail\s*\{[^}]*pointer-events:\s*none;/s);
        expect(css).toContain('.gis-layer-feature-card__scroll-thumb');
        expect(css).toMatch(/\.gis-layer-feature-card__header\s*\{[^}]*flex:\s*0 0 auto;/s);
        expect(css).toMatch(/\.gis-layer-feature-card__metadata\s*\{[^}]*flex:\s*0 0 auto;/s);
        expect(css).toMatch(/\.gis-layer-feature-card__metadata dd\s*\{[^}]*text-overflow:\s*ellipsis;/s);
        expect(css).toMatch(/\.gis-layer-feature-card__metadata dd\s*\{[^}]*white-space:\s*nowrap;/s);
        expect(css).not.toMatch(/(^|\n)\.mapboxgl-popup-content\b/);
    });

    it('shows and positions the persistent GIS scroll thumb only when the middle body overflows', () => {
        const card = buildGISFeaturePopup({ properties: { name: 'Feature', description: 'Description' } });
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

        Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 100 });
        expect(updateGISPopupOverflowAffordance(card)).toBe(false);
        expect(card.classList).not.toContain('is-scrollable');
        expect(viewport.hasAttribute('tabindex')).toBe(false);
        expect(thumb.style.height).toBe('');
        expect(thumb.style.transform).toBe('');
    });

    it('updates the GIS scroll thumb on scroll and resize and removes external handlers on cleanup', () => {
        const requestAnimationFrame = vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => {
            callback();
            return 1;
        });
        const cancelAnimationFrame = vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
        const card = buildGISFeaturePopup({ properties: { description: 'Description' } });
        const viewport = card.querySelector('.gis-layer-feature-card__scroll');
        const rail = card.querySelector('.gis-layer-feature-card__scroll-rail');
        const thumb = card.querySelector('.gis-layer-feature-card__scroll-thumb');
        Object.defineProperties(viewport, {
            clientHeight: { configurable: true, value: 100 },
            scrollHeight: { configurable: true, value: 100, writable: true },
            scrollTop: { configurable: true, value: 0, writable: true },
        });
        Object.defineProperty(rail, 'clientHeight', { configurable: true, value: 100 });
        const cleanup = bindGISPopupScrollBehavior(card);

        Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 500, writable: true });
        window.dispatchEvent(new Event('resize'));
        expect(card.classList).toContain('is-scrollable');
        viewport.scrollTop = 200;
        viewport.dispatchEvent(new Event('scroll'));
        expect(thumb.style.transform).toBe('translateY(36px)');

        cleanup();
        Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 100, writable: true });
        window.dispatchEvent(new Event('resize'));
        expect(card.classList).toContain('is-scrollable');
        expect(cancelAnimationFrame).toHaveBeenCalledWith(1);
        requestAnimationFrame.mockRestore();
        cancelAnimationFrame.mockRestore();
    });

    it('isolates popup wheel and touch scrolling from Mapbox and the page', () => {
        const parent = document.createElement('div');
        const card = document.createElement('article');
        parent.appendChild(card);
        const parentWheel = vi.fn();
        const parentTouchMove = vi.fn();
        parent.addEventListener('wheel', parentWheel);
        parent.addEventListener('touchmove', parentTouchMove);
        const cleanup = bindGISPopupScrollIsolation(card);

        card.dispatchEvent(new WheelEvent('wheel', { bubbles: true, deltaY: 100 }));
        card.dispatchEvent(new Event('touchmove', { bubbles: true }));

        expect(parentWheel).not.toHaveBeenCalled();
        expect(parentTouchMove).not.toHaveBeenCalled();
        cleanup();
        card.dispatchEvent(new WheelEvent('wheel', { bubbles: true, deltaY: 100 }));
        expect(parentWheel).toHaveBeenCalledOnce();
    });
});
