import { DEFAULTS, MAP_SOURCES } from '../config.js';
import { Utils } from '../utils.js';

const RASTER_SOURCE_ID = 'speleo-base-raster-source';
const RASTER_LAYER_ID = 'speleo-base-raster-layer';
const CHECKED_TILE_PROTOCOL = 'speleo-checked-tile';
const OVERLAY_LAYER_PREFIXES = Object.freeze([
    'project-layer-',
    'project-labels-',
    'project-points-',
    'gps-track-line-',
    'gps-track-points-',
    'stations-',
    'surface-stations-',
    'landmarks-',
    'cylinder-installs',
    'exploration-leads',
    'marker-drag-highlight',
]);

const MAP_SOURCE_ICON_SVG = `
    <svg fill="currentColor" xmlns="http://www.w3.org/2000/svg" viewBox="0 -0.01 512.01 512.01">
        <path d="M12.41 148.02l232.94 105.67c6.8 3.09 14.49 3.09 21.29 0l232.94-105.67c16.55-7.51 16.55-32.52 0-40.03L266.65 2.31a25.607 25.607 0 0 0-21.29 0L12.41 107.98c-16.55 7.51-16.55 32.53 0 40.04zm487.18 88.28l-58.09-26.33-161.64 73.27c-7.56 3.43-15.59 5.17-23.86 5.17s-16.29-1.74-23.86-5.17L70.51 209.97l-58.1 26.33c-16.55 7.5-16.55 32.5 0 40l232.94 105.59c6.8 3.08 14.49 3.08 21.29 0L499.59 276.3c16.55-7.5 16.55-32.5 0-40zm0 127.8l-57.87-26.23-161.86 73.37c-7.56 3.43-15.59 5.17-23.86 5.17s-16.29-1.74-23.86-5.17L70.29 337.87 12.41 364.1c-16.55 7.5-16.55 32.5 0 40l232.94 105.59c6.8 3.08 14.49 3.08 21.29 0L499.59 404.1c16.55-7.5 16.55-32.5 0-40z"></path>
    </svg>
`;

function getMapSourceById(sourceId) {
    return MAP_SOURCES.find(source => source.id === sourceId) || null;
}

function hasRequiredToken(source, accessToken) {
    return !source.requiresToken || Boolean(accessToken);
}

function getFirstUsableSource(accessToken) {
    return MAP_SOURCES.find(source => hasRequiredToken(source, accessToken)) || MAP_SOURCES[0];
}

function hasGlobalMissingTileHashChecks() {
    return DEFAULTS.MAP.MISSING_TILE_SHA256_HASHES.length > 0;
}

function isRasterTileSource(source) {
    return source?.type === 'raster' && Array.isArray(source.tiles) && source.tiles.length > 0;
}

function encodeCheckedTileUrl(tileUrl) {
    const match = tileUrl.match(/^(https?):\/\/(.+)$/);
    if (!match) return tileUrl;
    return `${CHECKED_TILE_PROTOCOL}://${match[1]}/${match[2]}`;
}

function decodeCheckedTileUrl(tileUrl) {
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

function resolveTileUrls(source, accessToken = '') {
    return (source.tiles || []).map(tileUrl => {
        const resolvedUrl = tileUrl.replaceAll('{accessToken}', encodeURIComponent(accessToken));
        return isRasterTileSource(source)
            && hasGlobalMissingTileHashChecks()
            && globalThis.__speleoCheckedTileProtocolInstalled === true
            ? encodeCheckedTileUrl(resolvedUrl)
            : resolvedUrl;
    });
}

function buildRasterSourceConfig(source, accessToken = '') {
    return {
        type: 'raster',
        tiles: resolveTileUrls(source, accessToken),
        tileSize: source.tileSize,
        maxzoom: source.maxzoom,
        attribution: source.attribution,
    };
}

function buildRasterStyle(source, accessToken = '') {
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

function isSpeleoOverlayLayer(layerId) {
    return OVERLAY_LAYER_PREFIXES.some(prefix => layerId.startsWith(prefix));
}

function getFirstOverlayLayerId(map) {
    const layers = map.getStyle()?.layers || [];
    const firstOverlay = layers.find(layer => isSpeleoOverlayLayer(layer.id));
    return firstOverlay?.id;
}

function hideBaseStyleLayers(map) {
    const layers = map.getStyle()?.layers || [];
    if (!map.__speleoBaseLayerVisibility) {
        map.__speleoBaseLayerVisibility = new Map();
    }

    layers.forEach(layer => {
        if (layer.id === RASTER_LAYER_ID || isSpeleoOverlayLayer(layer.id)) return;
        if (!map.__speleoBaseLayerVisibility.has(layer.id)) {
            map.__speleoBaseLayerVisibility.set(layer.id, layer.layout?.visibility ?? 'visible');
        }
        map.setLayoutProperty(layer.id, 'visibility', 'none');
    });
}

function restoreBaseStyleLayers(map) {
    if (!map.__speleoBaseLayerVisibility) return;

    map.__speleoBaseLayerVisibility.forEach((visibility, layerId) => {
        if (map.getLayer?.(layerId)) {
            map.setLayoutProperty(layerId, 'visibility', visibility);
        }
    });
    map.__speleoBaseLayerVisibility.clear();
}

function removeRasterLayer(map) {
    if (map.getLayer?.(RASTER_LAYER_ID)) {
        map.removeLayer(RASTER_LAYER_ID);
    }
    if (map.getSource?.(RASTER_SOURCE_ID)) {
        map.removeSource(RASTER_SOURCE_ID);
    }
}

function addRasterLayer(map, source, accessToken = '') {
    removeRasterLayer(map);
    hideBaseStyleLayers(map);

    map.addSource(RASTER_SOURCE_ID, buildRasterSourceConfig(source, accessToken));

    const layerConfig = {
        id: RASTER_LAYER_ID,
        type: 'raster',
        source: RASTER_SOURCE_ID,
    };
    const beforeId = getFirstOverlayLayerId(map);
    if (beforeId) {
        map.addLayer(layerConfig, beforeId);
    } else {
        map.addLayer(layerConfig);
    }
}

function hexFromArrayBuffer(buffer) {
    return Array.from(new Uint8Array(buffer))
        .map(byte => byte.toString(16).padStart(2, '0'))
        .join('');
}

async function sha256Hex(buffer) {
    if (!globalThis.crypto?.subtle) return null;
    const hashBuffer = await globalThis.crypto.subtle.digest('SHA-256', buffer);
    return hexFromArrayBuffer(hashBuffer);
}

function tileUrlMatchesTemplate(tileUrl, tileTemplate) {
    const normalizedTileUrl = decodeCheckedTileUrl(tileUrl);
    const prefix = tileTemplate.split('{z}')[0];
    return normalizedTileUrl.startsWith(prefix);
}

function getHashCheckedSourceForTileUrl(tileUrl) {
    return MAP_SOURCES.find(source => (
        isRasterTileSource(source)
        && (source.tiles || []).some(tileTemplate => tileUrlMatchesTemplate(tileUrl, tileTemplate))
    )) || null;
}

async function fetchWithTileHashCheck(originalFetch, thisArg, input, init) {
    const response = await originalFetch.call(thisArg, input, init);
    let tileUrl = null;
    if (typeof input === 'string') {
        tileUrl = input;
    } else if (input instanceof URL) {
        tileUrl = input.toString();
    } else {
        tileUrl = input?.url;
    }
    const source = tileUrl ? getHashCheckedSourceForTileUrl(tileUrl) : null;

    if (!source || !response?.ok) {
        return response;
    }

    const tileBuffer = await response.clone().arrayBuffer();
    const tileHash = await sha256Hex(tileBuffer);
    if (tileHash && DEFAULTS.MAP.MISSING_TILE_SHA256_HASHES.includes(tileHash)) {
        return new Response('', {
            status: 404,
            statusText: 'Tile matched known missing-data hash',
            headers: { 'Content-Type': 'text/plain' },
        });
    }

    return response;
}

function createCheckedTileProtocolHandler() {
    return (params, callback) => {
        const controller = new AbortController();
        const tileUrl = decodeCheckedTileUrl(params.url);
        const source = getHashCheckedSourceForTileUrl(tileUrl);

        if (!source) {
            callback(new Error('Unknown checked tile source'));
            return { cancel: () => controller.abort() };
        }

        fetch(tileUrl, { signal: controller.signal })
            .then(async response => {
                if (!response.ok) {
                    callback(new Error(`Tile request failed with HTTP ${response.status}`));
                    return;
                }

                const tileBuffer = await response.arrayBuffer();
                const tileHash = await sha256Hex(tileBuffer);
                if (tileHash && DEFAULTS.MAP.MISSING_TILE_SHA256_HASHES.includes(tileHash)) {
                    callback(new Error('Tile matched known missing-data hash'));
                    return;
                }

                callback(null, tileBuffer, response.headers.get('cache-control'), response.headers.get('expires'));
            })
            .catch(error => {
                if (error?.name === 'AbortError') return;
                callback(error);
            });

        return { cancel: () => controller.abort() };
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
        if (globalThis.__speleoCheckedTileProtocolInstalled === true) return;
        if (typeof globalThis.mapboxgl?.addProtocol !== 'function') return;

        mapboxgl.addProtocol(CHECKED_TILE_PROTOCOL, createCheckedTileProtocolHandler());
        globalThis.__speleoCheckedTileProtocolInstalled = true;
    },

    installCheckedTileFetch: function () {
        if (typeof globalThis.fetch !== 'function') return;
        if (globalThis.fetch.__speleoCheckedTileFetch === true) return;

        const originalFetch = globalThis.fetch;
        const checkedFetch = function (input, init) {
            return fetchWithTileHashCheck(originalFetch, this, input, init);
        };
        checkedFetch.__speleoCheckedTileFetch = true;
        checkedFetch.__speleoOriginalFetch = originalFetch;
        globalThis.fetch = checkedFetch;
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

    setCurrentMapSourceId: function (sourceId, accessToken = '') {
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

    buildMapStyle: function (sourceId, accessToken = '') {
        const source = getMapSourceById(sourceId) || getFirstUsableSource(accessToken);

        if (!hasRequiredToken(source, accessToken)) {
            return this.buildMapStyle(getFirstUsableSource(accessToken).id, accessToken);
        }

        if (source.type === 'mapbox-style') {
            return source.style;
        }

        if (source.type === 'raster') {
            return buildRasterStyle(source, accessToken);
        }

        return DEFAULTS.MAP.STYLE;
    },

    buildInitialMapStyle: function (sourceId, accessToken = '') {
        if (accessToken) {
            return DEFAULTS.MAP.STYLE;
        }

        return this.buildMapStyle(sourceId, accessToken);
    },

    applyInitialMapSource: function (map, sourceId, accessToken = '') {
        const source = getMapSourceById(sourceId) || getFirstUsableSource(accessToken);
        if (source.type === 'raster' && accessToken) {
            addRasterLayer(map, source, accessToken);
        }
    },

    applyMapSource: function (map, sourceId, accessToken = '') {
        const selectedSourceId = this.setCurrentMapSourceId(sourceId, accessToken);
        const source = getMapSourceById(selectedSourceId) || getFirstUsableSource(accessToken);

        if (source.type === 'raster') {
            addRasterLayer(map, source, accessToken);
            window.dispatchEvent(new CustomEvent('speleo:map-source-changed', {
                detail: { sourceId: selectedSourceId, reloadRequired: false }
            }));
            return selectedSourceId;
        }

        removeRasterLayer(map);
        restoreBaseStyleLayers(map);
        window.dispatchEvent(new CustomEvent('speleo:map-source-changed', {
            detail: { sourceId: selectedSourceId, reloadRequired: false }
        }));
        return selectedSourceId;
    },

    requiresDataReload: function (event) {
        return event.detail?.reloadRequired !== false;
    },

    createControl: function (accessToken = '') {
        const sources = this.getAvailableMapSources(accessToken);
        const selectedSourceId = this.getCurrentMapSourceId(accessToken);
        const sourceApi = this;

        return {
            _container: null,
            _onDocumentClick: null,
            _onDocumentKeyDown: null,

            onAdd: function (map) {
                const control = document.createElement('div');
                control.id = 'map-source-control';
                control.className = 'mapboxgl-ctrl mapboxgl-ctrl-group map-source-control';

                const button = document.createElement('button');
                button.id = 'map-source-button';
                button.className = 'mapboxgl-ctrl-icon map-source-button';
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

                menu.addEventListener('change', (event) => {
                    if (!event.target.matches('input[type="radio"][name="map-source"]')) return;
                    const option = event.target.closest('.map-source-option');
                    if (!option) return;
                    const nextSourceId = event.target.value;
                    try {
                        sourceApi.applyMapSource(map, nextSourceId, accessToken);
                        menu.querySelectorAll('.map-source-option').forEach(item => {
                            const isActive = item.dataset.sourceId === nextSourceId;
                            item.classList.toggle('active', isActive);
                            const radio = item.querySelector('input[type="radio"]');
                            if (radio) radio.checked = isActive;
                        });
                        closeMenu();
                    } catch (error) {
                        console.error('Error switching map source:', error);
                        Utils.showNotification('error', 'Failed to switch map source');
                    }
                });

                this._onDocumentClick = (event) => {
                    if (!control.contains(event.target)) {
                        closeMenu();
                    }
                };
                document.addEventListener('click', this._onDocumentClick);

                this._onDocumentKeyDown = (event) => {
                    if (event.key === 'Escape') {
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

    renderControl: function (map, accessToken = '') {
        if (!map || typeof map.addControl !== 'function') return;
        if (map.__speleoMapSourceControl) return;

        map.__speleoMapSourceControl = this.createControl(accessToken);
        map.addControl(map.__speleoMapSourceControl, 'top-right');
    },
};
