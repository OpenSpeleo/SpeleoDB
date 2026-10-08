import type { GISPopupFeature } from '../../../../../../../ts-types/domain/map-layers.ts';
import type { ViewerMap } from '../../../../../../../ts-types/domain/map-state.ts';
import type { MapboxPopup, MapboxLngLat } from '../../../../../../../ts-types/domain/mapbox.ts';
import { DEFAULTS } from '../../config.ts';

const gisFeaturePopups = new WeakMap<ViewerMap, Set<MapboxPopup>>();

function boundedGISPopupText(value: unknown, maxLength: number) {
    // Keep legacy coercion of arbitrary imported property values, including objects.
    const coercedValue: unknown = value ?? '';
    const text = String(coercedValue).trim();
    if (text.length <= maxLength) return text;
    return `${text.slice(0, maxLength - 1).trimEnd()}…`;
}

function structuredGISPopupValue(value: unknown) {
    if (value && typeof value === 'object') return value;
    if (typeof value !== 'string') return null;
    try {
        const parsed: unknown = JSON.parse(value);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch {
        return null;
    }
}

function readableGISPopupLabel(value: unknown) {
    return String(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

function gisPopupMetadataRows(feature: GISPopupFeature | null | undefined) {
    const properties = feature?.properties || {};
    const rows: [string, unknown][] = [];
    const geometryType = feature?.geometry?.type;
    if (geometryType) rows.push(['Geometry', readableGISPopupLabel(geometryType)]);

    const folderPath = structuredGISPopupValue(properties.folder_path);
    if (Array.isArray(folderPath) && folderPath.length > 0) {
        rows.push(['Folder', folderPath.map(String).join(' / ')]);
    }

    const extendedData = structuredGISPopupValue(properties.extended_data);
    if (extendedData && !Array.isArray(extendedData)) {
        for (const [key, value] of Object.entries(extendedData)) {
            if (value === null || value === undefined || typeof value === 'object') continue;
            rows.push([readableGISPopupLabel(key), value]);
        }
    }
    return rows.slice(0, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_MAX_ROWS);
}

export function bindGISPopupScrollIsolation(container: HTMLElement) {
    const stopPropagation = (event: Event) => event.stopPropagation();
    container.addEventListener('wheel', stopPropagation, { passive: true });
    container.addEventListener('touchmove', stopPropagation, { passive: true });
    return () => {
        container.removeEventListener('wheel', stopPropagation);
        container.removeEventListener('touchmove', stopPropagation);
    };
}

export function updateGISPopupOverflowAffordance(card: HTMLElement) {
    const viewport = card.querySelector<HTMLElement>('.gis-layer-feature-card__scroll');
    if (!viewport) return false;
    const tolerance = DEFAULTS.GIS_LAYER_RENDER.POPUP_OVERFLOW_TOLERANCE_PX;
    const maxScrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    const isScrollable = maxScrollTop > tolerance;
    card.classList.toggle('is-scrollable', isScrollable);

    const rail = card.querySelector<HTMLElement>('.gis-layer-feature-card__scroll-rail');
    const thumb = rail?.querySelector<HTMLElement>('.gis-layer-feature-card__scroll-thumb');
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

export function bindGISPopupScrollBehavior(card: HTMLElement) {
    const viewport = card.querySelector<HTMLElement>('.gis-layer-feature-card__scroll');
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

export function buildGISFeaturePopup(feature: GISPopupFeature | null | undefined) {
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
    title.textContent = boundedGISPopupText(
        properties.name || properties.title || properties.render_label || 'Untitled feature',
        DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS,
    );
    header.append(eyebrow, title);
    card.appendChild(header);

    const description = boundedGISPopupText(
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

    const rows = gisPopupMetadataRows(feature);
    if (rows.length > 0) {
        const metadata = document.createElement('dl');
        metadata.className = 'gis-layer-feature-card__metadata';
        for (const [label, value] of rows) {
            const term = document.createElement('dt');
            term.textContent = boundedGISPopupText(label, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS);
            const detail = document.createElement('dd');
            detail.textContent = boundedGISPopupText(value, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS);
            metadata.append(term, detail);
        }
        card.appendChild(metadata);
    }
    return card;
}

export function openGISFeaturePopup(map: ViewerMap, feature: GISPopupFeature, lngLat: MapboxLngLat) {
    if (!globalThis.mapboxgl?.Popup) return;
    const content = buildGISFeaturePopup(feature);
    const cleanup = bindGISPopupScrollBehavior(content);
    const popup = new mapboxgl.Popup!({
        className: 'gis-layer-feature-popup',
        closeButton: true,
        closeOnClick: true,
        focusAfterOpen: true,
        maxWidth: `${DEFAULTS.GIS_LAYER_RENDER.POPUP_MAX_WIDTH_PX}px`,
    });
    if (!gisFeaturePopups.has(map)) gisFeaturePopups.set(map, new Set());
    const popups = gisFeaturePopups.get(map)!;
    popups.add(popup);
    popup.once?.('close', () => {
        popups.delete(popup);
        cleanup();
    });
    popup
        .setLngLat(lngLat)
        .setDOMContent(content)
        .addTo(map);
}

export function closeGISFeaturePopups(map: ViewerMap | null): void {
    const popups = gisFeaturePopups.get(map!);
    if (!popups) return;
    for (const popup of popups) popup.remove();
    popups.clear();
}
