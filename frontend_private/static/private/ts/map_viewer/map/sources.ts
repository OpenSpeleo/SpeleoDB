import { GLOBE_ATMOSPHERE_LAYER_ID } from '@speleodb/map-viewer';
import { Renderer } from './renderer.ts';
import type { MapSourceDefinition, MapSourceMap, MapSourceControl, MapSourceChangeEvent, RasterStyle, RasterSourceOptions, BackgroundLayer, CheckedTileProtocol } from '../../../../../../ts-types/domain/map-sources.ts';
import type { ViewerUpdateContext } from '../../../../../../ts-types/domain/viewer-updates.ts';
import { DEFAULTS, MAP_SOURCES } from '../config.ts';
import { Utils } from '../utils.ts';
import { ViewerUpdates } from '../viewer_updates.ts';

const RASTER_SOURCE_ID = 'speleo-base-raster-source';
const RASTER_LAYER_ID = 'speleo-base-raster-layer';
const BASE_ANCHOR_ID = 'speleo-base-anchor';
const baseStyles = new WeakMap<MapSourceMap, { id: string; visibility: 'visible' | 'none' }[]>();
const CHECKED_TILE_PROTOCOL = 'speleo-checked-tile';
const protocolRenderers = new WeakSet<object>();
const OVERLAY_LAYER_PREFIXES = Object.freeze([
    'project-layer-',
    'project-labels-',
    'project-points-',
    'gps-track-line-',
    'gps-track-points-',
    'gis-layer-',
    'gis-geometry-',
    'stations-',
    'surface-stations-',
    'landmarks-',
    'cylinder-installs',
    'exploration-leads',
    'marker-drag-highlight',
    DEFAULTS.MEASUREMENT.LAYER_PREFIX,
]);

const MAP_SOURCE_ICON_SVG = `
    <svg fill="currentColor" xmlns="http://www.w3.org/2000/svg" viewBox="0 -0.01 512.01 512.01">
        <path d="M12.41 148.02l232.94 105.67c6.8 3.09 14.49 3.09 21.29 0l232.94-105.67c16.55-7.51 16.55-32.52 0-40.03L266.65 2.31a25.607 25.607 0 0 0-21.29 0L12.41 107.98c-16.55 7.51-16.55 32.53 0 40.04zm487.18 88.28l-58.09-26.33-161.64 73.27c-7.56 3.43-15.59 5.17-23.86 5.17s-16.29-1.74-23.86-5.17L70.51 209.97l-58.1 26.33c-16.55 7.5-16.55 32.5 0 40l232.94 105.59c6.8 3.08 14.49 3.08 21.29 0L499.59 276.3c16.55-7.5 16.55-32.5 0-40zm0 127.8l-57.87-26.23-161.86 73.37c-7.56 3.43-15.59 5.17-23.86 5.17s-16.29-1.74-23.86-5.17L70.29 337.87 12.41 364.1c-16.55 7.5-16.55 32.5 0 40l232.94 105.59c6.8 3.08 14.49 3.08 21.29 0L499.59 404.1c16.55-7.5 16.55-32.5 0-40z"></path>
    </svg>
`;

function getMapSourceById(sourceId: string | null): MapSourceDefinition | null {
    return MAP_SOURCES.find(source => source.id === sourceId) || null;
}

function hasRequiredToken(source: MapSourceDefinition, accessToken: string) {
    return !source.requiresToken || Boolean(accessToken);
}

function getFirstUsableSource(accessToken: string): MapSourceDefinition {
    return MAP_SOURCES.find(source => hasRequiredToken(source, accessToken)) || MAP_SOURCES[0]!;
}

function hasGlobalMissingTileHashChecks() {
    return DEFAULTS.MAP.MISSING_TILE_SHA256_HASHES.length > 0;
}

function isRasterTileSource(source: MapSourceDefinition | null | undefined) {
    return source?.type === 'raster' && Array.isArray(source.tiles) && source.tiles.length > 0;
}

function encodeCheckedTileUrl(tileUrl: string) {
    const match = tileUrl.match(/^(https?):\/\/(.+)$/);
    if (!match) return tileUrl;
    return `${CHECKED_TILE_PROTOCOL}://${match[1]}/${match[2]}`;
}

function decodeCheckedTileUrl(tileUrl: string) {
    const prefix = `${CHECKED_TILE_PROTOCOL}://`;
    if (!tileUrl.startsWith(prefix)) return tileUrl;

    const encodedUrl = tileUrl.slice(prefix.length);
    const firstSlashIndex = encodedUrl.indexOf('/');
    if (firstSlashIndex < 0) return tileUrl;

    const scheme = encodedUrl.slice(0, firstSlashIndex);
    const rest = encodedUrl.slice(firstSlashIndex + 1);
    if (scheme !== 'https' && scheme !== 'http') return tileUrl;

    return `${scheme}://${rest}`;
}

function resolveTileUrls(source: MapSourceDefinition, accessToken = '') {
    return (source.tiles || []).map(tileUrl => {
        const resolvedUrl = tileUrl.replaceAll('{accessToken}', encodeURIComponent(accessToken));
        return isRasterTileSource(source)
            && hasGlobalMissingTileHashChecks()
            && Boolean(Renderer && protocolRenderers.has(Renderer))
            ? encodeCheckedTileUrl(resolvedUrl)
            : resolvedUrl;
    });
}

function buildRasterSourceConfig(source: MapSourceDefinition, accessToken = ''): RasterSourceOptions {
    return {
        type: 'raster',
        tiles: resolveTileUrls(source, accessToken),
        tileSize: source.tileSize,
        maxzoom: source.maxzoom,
        attribution: source.attribution,
    };
}

function buildRasterStyle(source: MapSourceDefinition, accessToken = ''): RasterStyle {
    return {
        version: 8,
        glyphs: DEFAULTS.MAP.RASTER_GLYPHS,
        sources: {
            [RASTER_SOURCE_ID]: buildRasterSourceConfig(source, accessToken)
        },
        layers: [
            {
                id: RASTER_LAYER_ID,
                type: 'raster',
                source: RASTER_SOURCE_ID,
            }
        ],
    };
}

function isSpeleoOverlayLayer(layerId: string) {
    return layerId === GLOBE_ATMOSPHERE_LAYER_ID || OVERLAY_LAYER_PREFIXES.some(prefix => layerId.startsWith(prefix));
}

/** Capture before survey sources are installed: getStyle serializes their data. */
function captureBaseStyle(map: MapSourceMap) {
    if (baseStyles.has(map)) return baseStyles.get(map)!;
    const layers = (map.getStyle()?.layers || [])
        .filter(layer => layer.id !== RASTER_LAYER_ID && !isSpeleoOverlayLayer(layer.id));
    // Tokenless raster styles otherwise have no permanent insertion point. The
    // transparent anchor keeps replacement raster layers below every overlay.
    if (!layers.length) {
        const anchor: BackgroundLayer = { id: BASE_ANCHOR_ID, type: 'background', paint: { 'background-opacity': 0 } };
        map.addLayer(anchor, map.getLayer(RASTER_LAYER_ID) ? RASTER_LAYER_ID : undefined);
        layers.push(anchor);
    }
    const base = layers.map(layer => ({ id: layer.id, visibility: layer.layout?.visibility ?? 'visible' }));
    baseStyles.set(map, base);
    return base;
}

function removeRasterLayer(map: MapSourceMap) {
    if (map.getLayer?.(RASTER_LAYER_ID)) map.removeLayer(RASTER_LAYER_ID);
    if (map.getSource?.(RASTER_SOURCE_ID)) map.removeSource(RASTER_SOURCE_ID);
}

function* mapSourceChanges(map: MapSourceMap, source: MapSourceDefinition, accessToken: string) {
    const base = captureBaseStyle(map);
    removeRasterLayer(map);
    for (const layer of base) {
        if (map.getLayer(layer.id)) {
            map.setLayoutProperty(layer.id, 'visibility', source.type === 'raster' ? 'none' : layer.visibility);
            yield;
        }
    }
    if (source.type === 'raster') {
        map.addSource(RASTER_SOURCE_ID, buildRasterSourceConfig(source, accessToken));
        map.addLayer({ id: RASTER_LAYER_ID, type: 'raster', source: RASTER_SOURCE_ID },
            base.find(layer => map.getLayer(layer.id))?.id);
    }
}

function hexFromArrayBuffer(buffer: ArrayBuffer) {
    return Array.from(new Uint8Array(buffer))
        .map(byte => byte.toString(16).padStart(2, '0'))
        .join('');
}

async function sha256Hex(buffer: ArrayBuffer) {
    if (!globalThis.crypto?.subtle) return null;
    const hashBuffer = await globalThis.crypto.subtle.digest('SHA-256', buffer);
    return hexFromArrayBuffer(hashBuffer);
}

function tileUrlMatchesTemplate(tileUrl: string, tileTemplate: string) {
    const normalizedTileUrl = decodeCheckedTileUrl(tileUrl);
    const prefix = tileTemplate.split('{z}')[0]!;
    return normalizedTileUrl.startsWith(prefix);
}

function getHashCheckedSourceForTileUrl(tileUrl: string) {
    return MAP_SOURCES.find((source: MapSourceDefinition) => (
        isRasterTileSource(source)
        && (source.tiles || []).some(tileTemplate => tileUrlMatchesTemplate(tileUrl, tileTemplate))
    )) || null;
}

function tileRequestError(status: number, message: string) {
    // MapLibre retries parent/child tiles only when a failed tile has status 404.
    return Object.assign(new Error(message), { status });
}

/** Only ESRI raster requests use this protocol; application fetch is untouched. */
export function createCheckedTileProtocolHandler(): CheckedTileProtocol {
    return async (params, controller) => {
        const tileUrl = decodeCheckedTileUrl(params.url);
        if (!getHashCheckedSourceForTileUrl(tileUrl)) throw new Error('Unknown checked tile source');
        const response = await fetch(tileUrl, { signal: controller.signal });
        if (!response.ok) throw tileRequestError(response.status, `Tile request failed with HTTP ${response.status}`);
        const data = await response.arrayBuffer();
        const tileHash = await sha256Hex(data);
        if (tileHash && DEFAULTS.MAP.MISSING_TILE_SHA256_HASHES.includes(tileHash)) {
            throw tileRequestError(404, 'Tile matched known missing-data hash');
        }
        return { data, cacheControl: response.headers.get('cache-control'), expires: response.headers.get('expires') };
    };
}

export const MapSources = {
    getAvailableMapSources: function (accessToken = '') {
        return MAP_SOURCES.filter(source => hasRequiredToken(source, accessToken));
    },

    getMapSourceById,

    installCheckedTileProtocol: function () {
        if (!hasGlobalMissingTileHashChecks()) return;
        if (!MAP_SOURCES.some(isRasterTileSource)) return;
        if (Boolean(Renderer && protocolRenderers.has(Renderer))) return;
        if (typeof Renderer?.addProtocol !== 'function') return;

        Renderer.addProtocol(CHECKED_TILE_PROTOCOL, createCheckedTileProtocolHandler());
        protocolRenderers.add(Renderer);
    },

    getCurrentMapSourceId: function (accessToken = '') {
        let storedSourceId = null;

        try {
            storedSourceId = localStorage.getItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE);
        } catch (e) {
            storedSourceId = null;
        }

        const storedSource = getMapSourceById(storedSourceId);
        if (storedSource && hasRequiredToken(storedSource, accessToken)) {
            return storedSource.id;
        }

        const defaultSource = getMapSourceById(DEFAULTS.MAP.DEFAULT_SOURCE_ID);
        if (defaultSource && hasRequiredToken(defaultSource, accessToken)) {
            return defaultSource.id;
        }

        return getFirstUsableSource(accessToken).id;
    },

    setCurrentMapSourceId: function (sourceId: string | null, accessToken = '') {
        const source = getMapSourceById(sourceId);
        if (!source || !hasRequiredToken(source, accessToken)) {
            return this.getCurrentMapSourceId(accessToken);
        }

        try {
            localStorage.setItem(DEFAULTS.STORAGE_KEYS.MAP_SOURCE, source.id);
        } catch (e) {
            // localStorage unavailable
        }

        return source.id;
    },

    buildMapStyle: function (sourceId: string | null, accessToken = ''): string | RasterStyle {
        const source = getMapSourceById(sourceId) || getFirstUsableSource(accessToken);

        if (!hasRequiredToken(source, accessToken)) {
            return this.buildMapStyle(getFirstUsableSource(accessToken).id, accessToken);
        }

        if (source.type === 'mapbox-style') {
            return source.style!;
        }

        if (source.type === 'raster') {
            return buildRasterStyle(source, accessToken);
        }

        return DEFAULTS.MAP.STYLE;
    },

    buildInitialMapStyle: function (sourceId: string | null, accessToken = '') {
        if (accessToken) {
            return DEFAULTS.MAP.STYLE;
        }

        return this.buildMapStyle(sourceId, accessToken);
    },

    applyInitialMapSource: function (map: MapSourceMap, sourceId: string | null, accessToken = '') {
        captureBaseStyle(map);
        const source = getMapSourceById(sourceId) || getFirstUsableSource(accessToken);
        if (source.type === 'raster' && accessToken) {
            const changes = mapSourceChanges(map, source, accessToken);
            while (!changes.next().done) { /* Initial base style precedes viewer data. */ }
        }
    },

    applyMapSource: async function (map: MapSourceMap, sourceId: string | null, accessToken = '', context: ViewerUpdateContext | null = null) {
        const source = getMapSourceById(sourceId) || getFirstUsableSource(accessToken);
        const selectedSourceId = hasRequiredToken(source, accessToken) ? source.id : getFirstUsableSource(accessToken).id;
        const changes = mapSourceChanges(map, getMapSourceById(selectedSourceId)!, accessToken);
        while (!context || context.isCurrent()) {
            if (changes.next().done) {
                this.setCurrentMapSourceId(selectedSourceId, accessToken);
                window.dispatchEvent(new CustomEvent('speleo:map-source-changed', {
                    detail: { sourceId: selectedSourceId, reloadRequired: false }
                }));
                return selectedSourceId;
            }
            if (context?.shouldYield()) await context.yield();
        }
        return null;
    },

    requiresDataReload: function (event: MapSourceChangeEvent) {
        return event.detail?.reloadRequired !== false;
    },

    createControl: function (accessToken = ''): MapSourceControl {
        const sources = this.getAvailableMapSources(accessToken);
        const selectedSourceId = this.getCurrentMapSourceId(accessToken);
        // eslint-disable-next-line @typescript-eslint/no-this-alias -- Preserve the enclosing source facade receiver in control callbacks.
        const sourceApi = this;

        return {
            _container: null,
            _onDocumentClick: null,
            _onDocumentKeyDown: null,
            _updateKey: {},
            _appliedSourceId: selectedSourceId,

            onAdd: function (map) {
                const control = document.createElement('div');
                control.id = 'map-source-control';
                control.className = 'maplibregl-ctrl maplibregl-ctrl-group map-source-control';

                const button = document.createElement('button');
                button.id = 'map-source-button';
                button.className = 'maplibregl-ctrl-icon map-source-button';
                button.type = 'button';
                button.title = 'Map Source';
                button.setAttribute('aria-label', 'Map Source');
                button.setAttribute('aria-expanded', 'false');
                button.setAttribute('aria-controls', 'map-source-menu');
                // Trusted static SVG placeholder; do not interpolate user/API data here.
                button.innerHTML = MAP_SOURCE_ICON_SVG;

                const menu = document.createElement('div');
                menu.id = 'map-source-menu';
                menu.className = 'map-source-menu hidden';
                menu.setAttribute('role', 'radiogroup');
                menu.setAttribute('aria-hidden', 'true');
                menu.setAttribute('aria-labelledby', 'map-source-menu-title');

                const heading = document.createElement('div');
                heading.id = 'map-source-menu-title';
                heading.className = 'map-source-menu-title';
                heading.textContent = 'Map Source';
                menu.appendChild(heading);

                sources.forEach(source => {
                    const option = document.createElement('label');
                    option.className = 'map-source-option';
                    option.dataset.sourceId = source.id;
                    const radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.name = 'map-source';
                    radio.value = source.id;
                    radio.checked = source.id === selectedSourceId;
                    const labelText = document.createElement('span');
                    labelText.textContent = source.label;
                    option.appendChild(radio);
                    option.appendChild(labelText);
                    if (source.id === selectedSourceId) {
                        option.classList.add('active');
                    }
                    menu.appendChild(option);
                });

                const closeMenu = () => {
                    menu.classList.add('hidden');
                    button.setAttribute('aria-expanded', 'false');
                    menu.setAttribute('aria-hidden', 'true');
                };

                const openMenu = () => {
                    menu.classList.remove('hidden');
                    button.setAttribute('aria-expanded', 'true');
                    menu.setAttribute('aria-hidden', 'false');
                };

                const toggleMenu = () => {
                    if (menu.classList.contains('hidden')) {
                        openMenu();
                    } else {
                        closeMenu();
                    }
                };

                button.addEventListener('click', (event) => {
                    event.stopPropagation();
                    toggleMenu();
                });

                const showSelection = (sourceId: string) => {
                    menu.querySelectorAll<HTMLElement>('.map-source-option').forEach(item => {
                        const isActive = item.dataset.sourceId === sourceId;
                        item.classList.toggle('active', isActive);
                        item.querySelector('input')!.checked = isActive;
                    });
                };

                menu.addEventListener('change', (event) => {
                    if (!(event.target as HTMLInputElement).matches('input[type="radio"][name="map-source"]')) return;
                    const option = (event.target as HTMLInputElement).closest('.map-source-option');
                    if (!option) return;
                    const nextSourceId = (event.target as HTMLInputElement).value;
                    showSelection(nextSourceId);
                    closeMenu();
                    button.setAttribute('aria-busy', 'true');
                    void ViewerUpdates.schedule(this._updateKey, async context => {
                        if (!context.isCurrent() || this._container !== control) return;
                        const applied = await sourceApi.applyMapSource(map, nextSourceId, accessToken, context);
                        if (!context.isCurrent() || this._container !== control || !applied) return;
                        this._appliedSourceId = applied;
                        button.removeAttribute('aria-busy');
                    }, { onError: error => {
                        if (this._container !== control) return;
                        showSelection(this._appliedSourceId);
                        button.removeAttribute('aria-busy');
                        void ViewerUpdates.schedule(this._updateKey, context => sourceApi.applyMapSource(map, this._appliedSourceId, accessToken, context));
                        console.error('Error switching map source:', error);
                        Utils.showNotification('error', 'Failed to switch map source');
                    } });
                });

                this._onDocumentClick = (event) => {
                    if (!control.contains(event.target as Node | null)) {
                        closeMenu();
                    }
                };
                document.addEventListener('click', this._onDocumentClick);

                this._onDocumentKeyDown = (event) => {
                    if (event.key === 'Escape' && !menu.classList.contains('hidden')) {
                        event.preventDefault();
                        closeMenu();
                        button.focus();
                    }
                };
                document.addEventListener('keydown', this._onDocumentKeyDown);

                control.appendChild(button);
                control.appendChild(menu);
                this._container = control;
                return control;
            },

            onRemove: function () {
                ViewerUpdates.cancel(this._updateKey);
                if (this._onDocumentClick) {
                    document.removeEventListener('click', this._onDocumentClick);
                    this._onDocumentClick = null;
                }
                if (this._onDocumentKeyDown) {
                    document.removeEventListener('keydown', this._onDocumentKeyDown);
                    this._onDocumentKeyDown = null;
                }
                if (this._container?.parentNode) {
                    this._container.parentNode.removeChild(this._container);
                }
                this._container = null;
            },
        };
    },

    renderControl: function (map: MapSourceMap | null | undefined, accessToken = '') {
        if (!map || typeof map.addControl !== 'function') return;
        if (map.__speleoMapSourceControl) return;

        map.__speleoMapSourceControl = this.createControl(accessToken);
        map.addControl(map.__speleoMapSourceControl, 'top-right');
    },
};
