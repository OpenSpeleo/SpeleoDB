import { DEFAULTS } from '../config.js';
import { State } from '../state.js';

const FALLBACK_COLOR = DEFAULTS.COLORS.FALLBACK;

function safeIdPart(value) {
    return String(value).replace(/[^a-zA-Z0-9_-]/g, '_');
}

function addGeoJSONRoles(map, sourceId, prefix, fallbackColor, layerIds, sourceLayer, directSource) {
    const common = { source: sourceId };
    if (sourceLayer) common['source-layer'] = sourceLayer;
    const render = DEFAULTS.GIS_LAYER_RENDER;
    const color = directSource
        ? fallbackColor
        : ['coalesce', ['get', 'render_color'], fallbackColor];
    const fillOpacity = directSource
        ? render.FILL_OPACITY
        : ['coalesce', ['get', 'render_fill_opacity'], render.FILL_OPACITY];
    const outlineOpacity = directSource
        ? render.LINE_OPACITY
        : ['coalesce', ['get', 'render_outline_opacity'], render.LINE_OPACITY];
    const lineWidth = directSource
        ? render.LINE_WIDTH
        : ['coalesce', ['get', 'render_line_width'], render.LINE_WIDTH];
    const labelProperty = directSource ? 'name' : 'render_label';
    const definitions = [
        { suffix: 'fill', type: 'fill', filter: ['==', '$type', 'Polygon'], paint: { 'fill-color': color, 'fill-opacity': fillOpacity } },
        { suffix: 'outline', type: 'line', filter: ['==', '$type', 'Polygon'], paint: { 'line-color': color, 'line-width': directSource ? render.OUTLINE_WIDTH : ['coalesce', ['get', 'render_line_width'], render.OUTLINE_WIDTH], 'line-opacity': outlineOpacity } },
        { suffix: 'line', type: 'line', filter: ['==', '$type', 'LineString'], paint: { 'line-color': color, 'line-width': lineWidth, 'line-opacity': render.LINE_OPACITY }, layout: { 'line-join': 'round', 'line-cap': 'round' } },
        { suffix: 'point', type: 'circle', filter: ['==', '$type', 'Point'], paint: { 'circle-color': color, 'circle-radius': ['interpolate', ['linear'], ['zoom'], render.POINT_RADIUS_ZOOM_MIN, render.POINT_RADIUS_MIN, render.POINT_RADIUS_ZOOM_MAX, render.POINT_RADIUS_MAX], 'circle-stroke-color': render.POINT_STROKE_COLOR, 'circle-stroke-width': render.POINT_STROKE_WIDTH } },
        { suffix: 'label', type: 'symbol', filter: ['all', ['has', labelProperty], ['!=', ['get', labelProperty], '']], minzoom: DEFAULTS.ZOOM_LEVELS.GIS_LAYER_LABEL, layout: { 'text-field': ['get', labelProperty], 'text-size': render.LABEL_SIZE, 'text-offset': render.LABEL_OFFSET, 'text-anchor': 'top', 'text-optional': true }, paint: { 'text-color': render.LABEL_COLOR, 'text-halo-color': render.LABEL_HALO_COLOR, 'text-halo-width': render.LABEL_HALO_WIDTH } },
    ];
    for (const definition of definitions) {
        const id = `${prefix}-${definition.suffix}`;
        map.addLayer({
            id,
            ...common,
            ...definition,
            layout: { visibility: 'none', ...(definition.layout || {}) },
        });
        layerIds.push(id);
    }
}

function abortError() {
    const error = new Error('GIS Layer activation was cancelled.');
    error.name = 'AbortError';
    return error;
}

function waitForSources(map, sourceIds, signal) {
    if (signal?.aborted) return Promise.reject(abortError());
    const pending = new Set(sourceIds.filter(id => !map.isSourceLoaded?.(id)));
    if (pending.size === 0 || typeof map.on !== 'function') return Promise.resolve();
    return new Promise((resolve, reject) => {
        const cleanup = () => {
            window.clearTimeout(timer);
            map.off?.('sourcedata', onSourceData);
            map.off?.('error', onError);
            signal?.removeEventListener('abort', onAbort);
        };
        const onSourceData = event => {
            if (event.sourceId && pending.has(event.sourceId) && map.isSourceLoaded?.(event.sourceId)) pending.delete(event.sourceId);
            if (pending.size === 0) { cleanup(); resolve(); }
        };
        const onError = event => {
            if (!event.sourceId || !pending.has(event.sourceId)) return;
            cleanup();
            reject(new Error('The GIS Layer display file could not be loaded.'));
        };
        const onAbort = () => {
            cleanup();
            reject(abortError());
        };
        const timer = window.setTimeout(() => {
            cleanup();
            reject(new Error('Timed out while loading GIS Layer display data.'));
        }, DEFAULTS.UI.OVERLAY_SOURCE_LOAD_TIMEOUT_MS);
        map.on('sourcedata', onSourceData);
        map.on('error', onError);
        signal?.addEventListener('abort', onAbort, { once: true });
    });
}

function boundedText(value, maxLength) {
    const text = String(value ?? '').trim();
    if (text.length <= maxLength) return text;
    return `${text.slice(0, maxLength - 1).trimEnd()}…`;
}

function structuredValue(value) {
    if (value && typeof value === 'object') return value;
    if (typeof value !== 'string') return null;
    try {
        const parsed = JSON.parse(value);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch {
        return null;
    }
}

function readableLabel(value) {
    return String(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

function metadataRows(feature) {
    const properties = feature?.properties || {};
    const rows = [];
    const geometryType = feature?.geometry?.type;
    if (geometryType) rows.push(['Geometry', readableLabel(geometryType)]);

    const folderPath = structuredValue(properties.folder_path);
    if (Array.isArray(folderPath) && folderPath.length > 0) {
        rows.push(['Folder', folderPath.map(String).join(' / ')]);
    }

    const extendedData = structuredValue(properties.extended_data);
    if (extendedData && !Array.isArray(extendedData)) {
        for (const [key, value] of Object.entries(extendedData)) {
            if (value === null || value === undefined || typeof value === 'object') continue;
            rows.push([readableLabel(key), value]);
        }
    }
    return rows.slice(0, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_MAX_ROWS);
}

export function bindGISPopupScrollIsolation(container) {
    const stopPropagation = event => event.stopPropagation();
    container.addEventListener('wheel', stopPropagation, { passive: true });
    container.addEventListener('touchmove', stopPropagation, { passive: true });
    return () => {
        container.removeEventListener('wheel', stopPropagation);
        container.removeEventListener('touchmove', stopPropagation);
    };
}

export function updateGISPopupOverflowAffordance(card) {
    const viewport = card.querySelector('.gis-layer-feature-card__scroll');
    if (!viewport) return false;
    const tolerance = DEFAULTS.GIS_LAYER_RENDER.POPUP_OVERFLOW_TOLERANCE_PX;
    const maxScrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    const isScrollable = maxScrollTop > tolerance;
    card.classList.toggle('is-scrollable', isScrollable);

    const rail = card.querySelector('.gis-layer-feature-card__scroll-rail');
    const thumb = rail?.querySelector('.gis-layer-feature-card__scroll-thumb');
    if (!isScrollable) {
        viewport.removeAttribute('tabindex');
        viewport.removeAttribute('aria-label');
        thumb?.style.removeProperty('height');
        thumb?.style.removeProperty('transform');
        return false;
    }

    viewport.tabIndex = 0;
    viewport.setAttribute('aria-label', 'Scrollable feature description');
    if (rail && thumb && rail.clientHeight > 0) {
        const render = DEFAULTS.GIS_LAYER_RENDER;
        const proportionalHeight = rail.clientHeight * (viewport.clientHeight / viewport.scrollHeight);
        const thumbHeight = Math.min(
            rail.clientHeight,
            Math.max(render.POPUP_SCROLL_THUMB_MIN_PX, proportionalHeight),
        );
        const availableTravel = Math.max(0, rail.clientHeight - thumbHeight);
        const scrollProgress = Math.min(1, Math.max(0, viewport.scrollTop / maxScrollTop));
        thumb.style.height = `${thumbHeight}px`;
        thumb.style.transform = `translateY(${availableTravel * scrollProgress}px)`;
    } else {
        thumb?.style.removeProperty('height');
        thumb?.style.removeProperty('transform');
    }
    return isScrollable;
}

export function bindGISPopupScrollBehavior(card) {
    const viewport = card.querySelector('.gis-layer-feature-card__scroll');
    if (!viewport) return () => {};

    const stopIsolation = bindGISPopupScrollIsolation(viewport);
    const update = () => updateGISPopupOverflowAffordance(card);
    const frame = window.requestAnimationFrame(update);
    viewport.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update, { passive: true });

    const resizeObserver = globalThis.ResizeObserver ? new ResizeObserver(update) : null;
    resizeObserver?.observe(viewport);
    if (viewport.firstElementChild) resizeObserver?.observe(viewport.firstElementChild);

    return () => {
        window.cancelAnimationFrame(frame);
        viewport.removeEventListener('scroll', update);
        window.removeEventListener('resize', update);
        resizeObserver?.disconnect();
        stopIsolation();
    };
}

export function buildGISFeaturePopup(feature) {
    const properties = feature?.properties || {};
    const card = document.createElement('article');
    card.className = 'gis-layer-feature-card';
    card.setAttribute('aria-label', 'GIS feature details');

    const header = document.createElement('header');
    header.className = 'gis-layer-feature-card__header';
    const eyebrow = document.createElement('span');
    eyebrow.className = 'gis-layer-feature-card__eyebrow';
    eyebrow.textContent = 'GIS feature';
    const title = document.createElement('h3');
    title.className = 'gis-layer-feature-card__title';
    title.textContent = boundedText(
        properties.name || properties.render_label || 'Untitled feature',
        DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS,
    );
    header.append(eyebrow, title);
    card.appendChild(header);

    const description = boundedText(
        properties.description,
        DEFAULTS.GIS_LAYER_RENDER.POPUP_DESCRIPTION_MAX_CHARS,
    );
    if (description) {
        const body = document.createElement('div');
        body.className = 'gis-layer-feature-card__body';
        const viewport = document.createElement('div');
        viewport.className = 'gis-layer-feature-card__scroll';
        const descriptionElement = document.createElement('p');
        descriptionElement.className = 'gis-layer-feature-card__description';
        descriptionElement.textContent = description;
        viewport.appendChild(descriptionElement);

        const rail = document.createElement('span');
        rail.className = 'gis-layer-feature-card__scroll-rail';
        rail.setAttribute('aria-hidden', 'true');
        const thumb = document.createElement('span');
        thumb.className = 'gis-layer-feature-card__scroll-thumb';
        rail.appendChild(thumb);
        body.append(viewport, rail);
        card.appendChild(body);
    }

    const rows = metadataRows(feature);
    if (rows.length > 0) {
        const metadata = document.createElement('dl');
        metadata.className = 'gis-layer-feature-card__metadata';
        for (const [label, value] of rows) {
            const term = document.createElement('dt');
            term.textContent = boundedText(label, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS);
            const detail = document.createElement('dd');
            detail.textContent = boundedText(value, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS);
            metadata.append(term, detail);
        }
        card.appendChild(metadata);
    }
    return card;
}

function bindSafePopup(map, layerId) {
    if (typeof map.on !== 'function') return null;
    const handler = event => {
        const feature = event.features?.[0] || {};
        if (globalThis.mapboxgl?.Popup) {
            const content = buildGISFeaturePopup(feature);
            const cleanup = bindGISPopupScrollBehavior(content);
            const popup = new mapboxgl.Popup({
                className: 'gis-layer-feature-popup',
                closeButton: true,
                closeOnClick: true,
                focusAfterOpen: true,
                maxWidth: `${DEFAULTS.GIS_LAYER_RENDER.POPUP_MAX_WIDTH_PX}px`,
            });
            popup.once?.('close', cleanup);
            popup
                .setLngLat(event.lngLat)
                .setDOMContent(content)
                .addTo(map);
        }
    };
    map.on('click', layerId, handler);
    return { layerId, handler };
}

export const GISLayerRenderer = {
    async attach(layer, data, activation = {}) {
        const map = State.map;
        if (!map) throw new Error('Map is not ready');
        const logicalId = safeIdPart(layer.id);
        const generationSuffix = activation.generation == null
            ? ''
            : `-g${safeIdPart(activation.generation)}`;
        const sourceIds = [];
        const layerIds = [];
        const popupHandlers = [];
        if (!data.url) throw new Error('The GIS Layer has no display file.');
        const registration = { sourceIds, layerIds, popupHandlers };
        try {
            const sourceId = `gis-layer-source-${logicalId}${generationSuffix}`;
            const prefix = `gis-layer-${logicalId}${generationSuffix}`;
            map.addSource(sourceId, { type: 'geojson', data: data.url, generateId: true });
            sourceIds.push(sourceId);
            addGeoJSONRoles(
                map,
                sourceId,
                prefix,
                layer.color || FALLBACK_COLOR,
                layerIds,
                null,
                data.direct_source === true,
            );
            layerIds.filter(id => /-(fill|line|point)$/.test(id)).forEach(id => {
                const binding = bindSafePopup(map, id);
                if (binding) popupHandlers.push(binding);
            });
            await waitForSources(map, sourceIds, activation.signal);
        } catch (error) {
            this.remove(registration);
            throw error;
        }
        return registration;
    },

    setVisible(registration, visible) {
        const map = State.map;
        if (!map || !registration) return;
        registration.layerIds.forEach(id => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none'); });
    },

    remove(registration) {
        const map = State.map;
        if (!map || !registration) return;
        (registration.popupHandlers || []).forEach(({ layerId, handler }) => map.off?.('click', layerId, handler));
        [...registration.layerIds].reverse().forEach(id => { if (map.getLayer(id)) map.removeLayer(id); });
        [...registration.sourceIds].reverse().forEach(id => { if (map.getSource(id)) map.removeSource(id); });
    },
};
