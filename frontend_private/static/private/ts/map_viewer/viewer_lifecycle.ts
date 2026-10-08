import type { ViewerState } from '../../../../../ts-types/domain/map-state.ts';
import { DEFAULTS } from './defaults.ts';

/** Register the roots' own callbacks without wrapping promises or moving startup work. */
export function registerViewerDataLifecycle(
    map: { on(event: 'load', callback: () => Promise<void>): unknown },
    callbacks: { load: () => Promise<void>; sourceChange: (event: Event) => Promise<void> },
): void {
    map.on('load', callbacks.load);
    // EventTarget ignores the existing async callback's return; retain its identity.
    window.addEventListener('speleo:map-source-changed', callbacks.sourceChange as unknown as EventListener);
}

/** Each viewer owns its listener lifetime and supplies its fullscreen policy. */
export function createMapHeightUpdater(isFullscreen: () => boolean = () => false): () => void {
    return function setMapHeight() {
        const mapElement = document.getElementById('map')!;
        const rect = mapElement.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const mapTop = rect.top;
        const isMobile = window.innerWidth <= DEFAULTS.UI.MOBILE_BREAKPOINT;
        const fullscreen = isFullscreen();
        const newHeight = isMobile || fullscreen ? (viewportHeight - mapTop) : Math.max(viewportHeight - mapTop - DEFAULTS.UI.MAP_PADDING_OFFSET, DEFAULTS.UI.MIN_MAP_HEIGHT);
        mapElement.style.height = newHeight + 'px';
    };
}

/** Clear only rendered survey state; preferences, source data, and private tools stay with their owners. */
export function clearRenderedSurveyState(state: Pick<ViewerState,
    'effectiveProjectVisibility' | 'allProjectLayers' | 'projectDepthDomains' | 'activeDepthDomain' | 'projectBounds'
>): void {
    state.effectiveProjectVisibility = new Map();
    state.allProjectLayers = new Map();
    state.projectDepthDomains = new Map();
    state.activeDepthDomain = null;
    state.projectBounds = new Map();
}
