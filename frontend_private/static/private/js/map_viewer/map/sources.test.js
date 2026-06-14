import { DEFAULTS } from '../config.js';
import { MapSources } from './sources.js';

function arrayBufferFromHex(hex) {
    const bytes = new Uint8Array(hex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    return bytes.buffer;
}

function createMapMock() {
    const handlers = {};
    const layers = [
        { id: 'background', layout: {} },
        { id: 'satellite', layout: { visibility: 'visible' } },
        { id: 'hillshade-shadow', layout: { visibility: 'none' } },
        { id: 'project-layer-p1' },
        { id: 'project-labels-p1' },
        { id: 'project-points-p1' },
        { id: 'gps-track-line-1' },
        { id: 'gps-track-points-1' },
        { id: 'stations-p1-circles' },
        { id: 'surface-stations-1' },
        { id: 'landmarks-layer' },
        { id: 'cylinder-installs-layer' },
        { id: 'exploration-leads-layer' },
        { id: 'marker-drag-highlight' },
    ];
    const sources = new Set();
    return {
        handlers,
        layers,
        map: {
            addControl: vi.fn(),
            once: vi.fn((eventName, handler) => {
                handlers[eventName] = handler;
            }),
            off: vi.fn(),
            setStyle: vi.fn(),
            getStyle: vi.fn(() => ({ layers })),
            getLayer: vi.fn((layerId) => layers.some(layer => layer.id === layerId)),
            getSource: vi.fn((sourceId) => sources.has(sourceId)),
            addSource: vi.fn((sourceId) => sources.add(sourceId)),
            removeSource: vi.fn((sourceId) => sources.delete(sourceId)),
            addLayer: vi.fn((layer, beforeId) => {
                const nextLayer = { id: layer.id, beforeId };
                const beforeIndex = layers.findIndex(item => item.id === beforeId);
                if (beforeIndex >= 0) {
                    layers.splice(beforeIndex, 0, nextLayer);
                } else {
                    layers.push(nextLayer);
                }
            }),
            removeLayer: vi.fn((layerId) => {
                const index = layers.findIndex(layer => layer.id === layerId);
                if (index >= 0) layers.splice(index, 1);
            }),
            setLayoutProperty: vi.fn((layerId, property, value) => {
                const layer = layers.find(item => item.id === layerId);
                if (layer) {
                    layer.layout = layer.layout || {};
                    layer.layout[property] = value;
                }
            }),
        }
    };
}

describe('MapSources', () => {
    beforeEach(() => {
        localStorage.clear();
        document.body.innerHTML = '<div id="map-wrapper"><div id="map"></div></div>';
    });

    afterEach(() => {
        localStorage.clear();
        document.body.innerHTML = '';
        vi.restoreAllMocks();
    });

    it('uses Mapbox satellite as the default source when a token is available', () => {
        expect(MapSources.getCurrentMapSourceId('token')).toBe(DEFAULTS.MAP.DEFAULT_SOURCE_ID);
    });

    it('falls back to a tokenless source when the default requires a missing token', () => {
        expect(MapSources.getCurrentMapSourceId('')).toBe('esri-satellite');
    });

    it('includes all tokenless ESRI sources when no Mapbox token is available', () => {
        expect(MapSources.getAvailableMapSources('').map(source => source.id)).toEqual([
            'esri-satellite',
            'esri-world-hillshade',
            'esri-world-hillshade-dark',
        ]);
    });

    it('ignores invalid stored source ids', () => {
        localStorage.setItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE, 'unknown-source');

        expect(MapSources.getCurrentMapSourceId('token')).toBe(DEFAULTS.MAP.DEFAULT_SOURCE_ID);
    });

    it('persists valid source choices', () => {
        const sourceId = MapSources.setCurrentMapSourceId('esri-world-hillshade-dark', 'token');

        expect(sourceId).toBe('esri-world-hillshade-dark');
        expect(localStorage.getItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE)).toBe('esri-world-hillshade-dark');
        expect(MapSources.getCurrentMapSourceId('token')).toBe('esri-world-hillshade-dark');
    });

    it('builds a Mapbox style URL for style sources', () => {
        expect(MapSources.buildMapStyle('mapbox-satellite', 'token')).toBe(DEFAULTS.MAP.STYLE);
    });

    it('builds a raster style object for tile sources', () => {
        const style = MapSources.buildMapStyle('esri-world-hillshade', '');

        expect(style.version).toBe(8);
        expect(style.sources['speleo-base-raster-source']).toMatchObject({
            type: 'raster',
            tileSize: 256,
            maxzoom: 16,
        });
        expect(style.sources['speleo-base-raster-source'].tiles[0]).toContain('World_Hillshade');
        expect(style.layers[0]).toMatchObject({
            id: 'speleo-base-raster-layer',
            type: 'raster',
            source: 'speleo-base-raster-source',
        });
    });

    it('builds ESRI Satellite with the ESRI tile URL when checked protocol support is unavailable', () => {
        const originalInstalled = globalThis.__speleoCheckedTileProtocolInstalled;
        Object.defineProperty(globalThis, '__speleoCheckedTileProtocolInstalled', {
            configurable: true,
            writable: true,
            value: false,
        });

        const style = MapSources.buildMapStyle('esri-satellite', '');

        expect(style.sources['speleo-base-raster-source']).toMatchObject({
            type: 'raster',
            tileSize: 256,
            maxzoom: 18,
        });
        expect(style.sources['speleo-base-raster-source'].tiles[0]).toBe(
            'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        );
        expect(style.sources['speleo-base-raster-source'].tiles[0]).toContain('{z}/{y}/{x}');

        Object.defineProperty(globalThis, '__speleoCheckedTileProtocolInstalled', {
            configurable: true,
            value: originalInstalled,
        });
    });

    it('installs a JS fetch hash check that rejects known missing-data images for every raster source', async () => {
        const originalFetch = globalThis.fetch;
        const originalCrypto = globalThis.crypto;
        const tileResponse = new Response(new Uint8Array([1, 2, 3]), {
            status: 200,
            headers: { 'Content-Type': 'image/jpeg' },
        });

        globalThis.fetch = vi.fn(async () => tileResponse);
        Object.defineProperty(globalThis, 'crypto', {
            configurable: true,
            value: {
                subtle: {
                    digest: vi.fn(async () => arrayBufferFromHex(DEFAULTS.MAP.MISSING_TILE_SHA256_HASHES[0])),
                },
            },
        });

        MapSources.installCheckedTileFetch();
        const satelliteResponse = await fetch(
            'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/17/27064/17738'
        );
        const hillshadeResponse = await fetch(
            'https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade_Dark/MapServer/tile/17/27064/17738'
        );

        expect(satelliteResponse.status).toBe(404);
        expect(satelliteResponse.statusText).toBe('Tile matched known missing-data hash');
        expect(hillshadeResponse.status).toBe(404);
        expect(hillshadeResponse.statusText).toBe('Tile matched known missing-data hash');
        expect(globalThis.fetch.__speleoCheckedTileFetch).toBe(true);

        globalThis.fetch = originalFetch;
        Object.defineProperty(globalThis, 'crypto', {
            configurable: true,
            value: originalCrypto,
        });
    });

    it('installs a Mapbox checked tile protocol that fetches the real ESRI URL and rejects missing-data hashes', async () => {
        const originalMapboxgl = globalThis.mapboxgl;
        const originalFetch = globalThis.fetch;
        const originalCrypto = globalThis.crypto;
        const originalInstalled = globalThis.__speleoCheckedTileProtocolInstalled;
        const addProtocol = vi.fn();

        Object.defineProperty(globalThis, 'mapboxgl', {
            configurable: true,
            value: { addProtocol },
        });
        Object.defineProperty(globalThis, '__speleoCheckedTileProtocolInstalled', {
            configurable: true,
            writable: true,
            value: false,
        });
        globalThis.fetch = vi.fn(async () => new Response(new Uint8Array([1, 2, 3]), {
            status: 200,
            headers: { 'Content-Type': 'image/jpeg' },
        }));
        Object.defineProperty(globalThis, 'crypto', {
            configurable: true,
            value: {
                subtle: {
                    digest: vi.fn(async () => arrayBufferFromHex(DEFAULTS.MAP.MISSING_TILE_SHA256_HASHES[0])),
                },
            },
        });

        MapSources.installCheckedTileProtocol();

        expect(addProtocol).toHaveBeenCalledWith('speleo-checked-tile', expect.any(Function));
        const protocolHandler = addProtocol.mock.calls[0][1];
        const callback = vi.fn();
        protocolHandler({
            url: 'speleo-checked-tile://https/server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade_Dark/MapServer/tile/17/27064/17738',
        }, callback);

        await vi.waitFor(() => {
            expect(callback).toHaveBeenCalled();
        });

        expect(globalThis.fetch).toHaveBeenCalledWith(
            'https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade_Dark/MapServer/tile/17/27064/17738',
            expect.objectContaining({ signal: expect.any(AbortSignal) })
        );
        expect(callback.mock.calls[0][0]).toBeInstanceOf(Error);
        expect(callback.mock.calls[0][0].message).toBe('Tile matched known missing-data hash');

        const checkedStyle = MapSources.buildMapStyle('esri-world-hillshade-dark', '');
        expect(checkedStyle.sources['speleo-base-raster-source'].tiles[0]).toBe(
            'speleo-checked-tile://https/server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade_Dark/MapServer/tile/{z}/{y}/{x}'
        );

        Object.defineProperty(globalThis, 'mapboxgl', {
            configurable: true,
            value: originalMapboxgl,
        });
        Object.defineProperty(globalThis, '__speleoCheckedTileProtocolInstalled', {
            configurable: true,
            value: originalInstalled,
        });
        globalThis.fetch = originalFetch;
        Object.defineProperty(globalThis, 'crypto', {
            configurable: true,
            value: originalCrypto,
        });
    });

    it('uses the Mapbox style as the initial style when a token exists', () => {
        expect(MapSources.buildInitialMapStyle('esri-world-hillshade-dark', 'token')).toBe(DEFAULTS.MAP.STYLE);
    });

    it('treats reloadRequired false as the only non-destructive source event', () => {
        expect(MapSources.requiresDataReload(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'esri-world-hillshade', reloadRequired: false }
        }))).toBe(false);
        expect(MapSources.requiresDataReload(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'future-source', reloadRequired: true }
        }))).toBe(true);
        expect(MapSources.requiresDataReload(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: 'legacy-source' }
        }))).toBe(true);
    });

    it('switches ESRI sources by replacing one raster tile layer below overlays without setStyle', () => {
        const { map, layers } = createMapMock();
        const eventSpy = vi.fn();
        window.addEventListener('speleo:map-source-changed', eventSpy);

        MapSources.applyMapSource(map, 'esri-world-hillshade-dark', 'token');

        expect(map.setStyle).not.toHaveBeenCalled();
        expect(map.addSource).toHaveBeenCalledWith(
            'speleo-base-raster-source',
            expect.objectContaining({
                type: 'raster',
                maxzoom: 16,
                tiles: expect.arrayContaining([
                    expect.stringContaining('World_Hillshade_Dark')
                ]),
            })
        );
        expect(map.addLayer).toHaveBeenCalledWith(
            expect.objectContaining({
                id: 'speleo-base-raster-layer',
                type: 'raster',
                source: 'speleo-base-raster-source',
            }),
            'project-layer-p1'
        );
        expect(map.setLayoutProperty).toHaveBeenCalledWith('background', 'visibility', 'none');
        expect(map.setLayoutProperty).toHaveBeenCalledWith('satellite', 'visibility', 'none');
        expect(map.setLayoutProperty).toHaveBeenCalledWith('hillshade-shadow', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('project-layer-p1', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('project-labels-p1', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('project-points-p1', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('gps-track-line-1', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('gps-track-points-1', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('stations-p1-circles', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('surface-stations-1', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('landmarks-layer', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('cylinder-installs-layer', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('exploration-leads-layer', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('marker-drag-highlight', 'visibility', 'none');
        expect(layers.map(layer => layer.id).indexOf('speleo-base-raster-layer'))
            .toBeLessThan(layers.map(layer => layer.id).indexOf('project-layer-p1'));
        expect(eventSpy).toHaveBeenCalledWith(expect.objectContaining({
            detail: { sourceId: 'esri-world-hillshade-dark', reloadRequired: false }
        }));

        map.removeLayer.mockClear();
        map.removeSource.mockClear();
        map.addSource.mockClear();
        map.addLayer.mockClear();
        MapSources.applyMapSource(map, 'esri-world-hillshade', 'token');

        expect(map.removeLayer).toHaveBeenCalledWith('speleo-base-raster-layer');
        expect(map.removeSource).toHaveBeenCalledWith('speleo-base-raster-source');
        expect(map.addSource).toHaveBeenCalledTimes(1);
        expect(map.addLayer).toHaveBeenCalledTimes(1);
        expect(map.removeLayer.mock.invocationCallOrder[0])
            .toBeLessThan(map.addSource.mock.invocationCallOrder[0]);
        expect(map.removeSource.mock.invocationCallOrder[0])
            .toBeLessThan(map.addSource.mock.invocationCallOrder[0]);
        expect(map.setStyle).not.toHaveBeenCalled();

        window.removeEventListener('speleo:map-source-changed', eventSpy);
    });

    it('switches to ESRI Satellite as a non-destructive raster source', () => {
        const { map } = createMapMock();

        MapSources.applyMapSource(map, 'esri-satellite', 'token');

        expect(map.setStyle).not.toHaveBeenCalled();
        expect(map.addSource).toHaveBeenCalledWith(
            'speleo-base-raster-source',
            expect.objectContaining({
                type: 'raster',
                maxzoom: 18,
                tiles: expect.arrayContaining([
                    'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                ]),
            })
        );
        expect(localStorage.getItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE)).toBe('esri-satellite');
    });

    it('switches back to Mapbox by removing the raster tile layer without setStyle', () => {
        const { map } = createMapMock();

        MapSources.applyMapSource(map, 'esri-world-hillshade-dark', 'token');
        map.setLayoutProperty.mockClear();
        MapSources.applyMapSource(map, 'mapbox-satellite', 'token');

        expect(map.removeLayer).toHaveBeenCalledWith('speleo-base-raster-layer');
        expect(map.removeSource).toHaveBeenCalledWith('speleo-base-raster-source');
        expect(map.setLayoutProperty).toHaveBeenCalledWith('background', 'visibility', 'visible');
        expect(map.setLayoutProperty).toHaveBeenCalledWith('satellite', 'visibility', 'visible');
        expect(map.setLayoutProperty).toHaveBeenCalledWith('hillshade-shadow', 'visibility', 'none');
        expect(map.setLayoutProperty).not.toHaveBeenCalledWith('project-layer-p1', 'visibility', expect.anything());
        expect(map.setStyle).not.toHaveBeenCalled();
    });

    it('adds the map source selector through the Mapbox control API without duplicates', () => {
        const { map } = createMapMock();

        MapSources.renderControl(map, 'token');
        MapSources.renderControl(map, 'token');

        expect(map.addControl).toHaveBeenCalledTimes(1);
        expect(map.addControl).toHaveBeenCalledWith(
            expect.objectContaining({
                onAdd: expect.any(Function),
                onRemove: expect.any(Function),
            }),
            'top-right'
        );
    });

    it('renders a Mapbox icon button under controls with a menu that switches sources', () => {
        const { map } = createMapMock();
        const eventSpy = vi.fn();
        window.addEventListener('speleo:map-source-changed', eventSpy);

        const control = MapSources.createControl('token');
        const element = control.onAdd(map);
        document.body.appendChild(element);

        expect(element).toBeInstanceOf(HTMLElement);
        expect(element.id).toBe('map-source-control');
        expect(element.classList.contains('mapboxgl-ctrl')).toBe(true);
        expect(element.classList.contains('mapboxgl-ctrl-group')).toBe(true);

        const button = element.querySelector('#map-source-button');
        expect(button).not.toBeNull();
        expect(button.classList.contains('mapboxgl-ctrl-icon')).toBe(true);
        expect(button.getAttribute('aria-label')).toBe('Map Source');
        expect(button.getAttribute('aria-controls')).toBe('map-source-menu');

        const select = element.querySelector('#map-source-select');
        expect(select).toBeNull();

        const menu = element.querySelector('#map-source-menu');
        expect(menu).not.toBeNull();
        expect(menu.classList.contains('hidden')).toBe(true);
        expect(menu.getAttribute('role')).toBe('radiogroup');
        expect(menu.getAttribute('aria-hidden')).toBe('true');
        expect(menu.querySelector('.map-source-menu-title').textContent).toBe('Map Source');
        expect(menu.querySelectorAll('.map-source-option').length).toBe(4);
        expect(menu.querySelectorAll('.map-source-option input[type="radio"]').length).toBe(4);

        button.click();
        expect(menu.classList.contains('hidden')).toBe(false);
        expect(button.getAttribute('aria-expanded')).toBe('true');
        expect(menu.getAttribute('aria-hidden')).toBe('false');

        document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        expect(menu.classList.contains('hidden')).toBe(true);

        button.click();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        expect(menu.classList.contains('hidden')).toBe(true);

        button.click();
        const option = menu.querySelector('.map-source-option[data-source-id="esri-world-hillshade-dark"]');
        const radio = option.querySelector('input[type="radio"]');
        expect(radio.checked).toBe(false);
        radio.checked = true;
        radio.dispatchEvent(new Event('change', { bubbles: true }));

        expect(map.setStyle).not.toHaveBeenCalled();
        expect(localStorage.getItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE)).toBe('esri-world-hillshade-dark');
        expect(radio.checked).toBe(true);
        expect(menu.classList.contains('hidden')).toBe(true);
        expect(eventSpy).toHaveBeenCalledWith(expect.objectContaining({
            detail: { sourceId: 'esri-world-hillshade-dark', reloadRequired: false }
        }));

        window.removeEventListener('speleo:map-source-changed', eventSpy);
    });
});
