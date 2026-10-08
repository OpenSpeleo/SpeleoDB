import type { StyleSpecification } from 'maplibre-gl';
import type { MapControl } from '../../../../../../ts-types/domain/map-core.ts';

/**
 * Keep Mapbox's classic satellite/vector-label provider on the MapLibre engine.
 * Only mapbox:// resources receive credentials; application and ESRI URLs pass
 * through untouched. MapLibre calls this for styles, TileJSON, glyphs and sprites
 * (including the .json/.png and @2x suffixes it appends before requesting them).
 */
export function normalizeMapboxRequest(url: string, accessToken: string): { url: string } {
    if (!url.startsWith('mapbox://')) return { url };
    const resource = new URL(url);
    const path = resource.pathname.slice(1);
    let apiPath: string;
    switch (resource.hostname) {
        case 'styles':
            apiPath = `/styles/v1/${path}`;
            break;
        case 'fonts':
            apiPath = `/fonts/v1/${path}`;
            break;
        case 'sprites': {
            const match = path.match(/^([^/]+)\/([^/]+?)(@2x)?(\.json|\.png)?$/);
            if (!match) throw new Error('Invalid Mapbox sprite resource');
            apiPath = `/styles/v1/${match[1]}/${match[2]}/sprite${match[3] || ''}${match[4] || ''}`;
            break;
        }
        default:
            apiPath = `/v4/${resource.hostname}${resource.pathname}.json`;
            resource.searchParams.set('secure', 'true');
    }
    const normalized = new URL(apiPath, 'https://api.mapbox.com');
    normalized.search = resource.search;
    normalized.searchParams.set('access_token', accessToken);
    return { url: normalized.toString() };
}

/** Mapbox classic styles use projection.name; MapLibre uses projection.type. */
export function normalizeProviderStyle(_previous: StyleSpecification | undefined, next: StyleSpecification): StyleSpecification {
    const normalized: StyleSpecification = { ...next, projection: { type: 'globe' } };
    // Provider styles own imagery, not the application's camera. MapLibre can
    // apply their saved camera even when explicit constructor options are zero.
    delete normalized.center;
    delete normalized.zoom;
    delete normalized.bearing;
    delete normalized.pitch;
    delete normalized.roll;
    return normalized;
}

/** Keep native source credits while excluding the provider's feedback action. */
export function withoutMapboxFeedback(control: Required<MapControl>): Required<MapControl> {
    let observer: MutationObserver | null = null;
    return {
        onAdd(map) {
            const container = control.onAdd(map);
            const removeFeedback = () => {
                container.querySelectorAll('a.mapbox-improve-map[href="https://www.mapbox.com/contribute/"]')
                    .forEach(link => link.remove());
            };
            removeFeedback();
            // Native attribution replaces its contents when source credits change.
            // Observe only this control, retaining its compact toggle and credits.
            observer = new MutationObserver(removeFeedback);
            observer.observe(container, { childList: true, subtree: true });
            return container;
        },
        onRemove() {
            observer?.disconnect();
            observer = null;
            control.onRemove();
        },
    };
}

/** Retain the provider logo formerly supplied by the Mapbox renderer itself. */
export function createMapboxAttributionControl() {
    let container: HTMLDivElement | null = null;
    return {
        onAdd() {
            container = document.createElement('div');
            container.className = 'maplibregl-ctrl map-provider-attribution';
            const link = document.createElement('a');
            link.href = 'https://www.mapbox.com/about/maps/';
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            const logo = document.createElement('img');
            logo.src = new URL('../../../media/mapbox-provider-logo.svg', import.meta.url).href;
            logo.alt = 'Mapbox';
            logo.width = 88;
            logo.height = 23;
            link.appendChild(logo);
            container.appendChild(link);
            return container;
        },
        onRemove() {
            container?.remove();
            container = null;
        },
    };
}
