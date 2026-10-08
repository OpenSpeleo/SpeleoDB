import { DEFAULTS } from '../config.ts';

/** Position one overlay panel below the first visible established stack anchor. */
export function positionOverlayPanel(elements: readonly (HTMLElement | null | undefined)[], anchorIds: readonly string[], container: HTMLElement | null | undefined) {
    if (!container) return;
    const anchor = anchorIds.map(id => document.getElementById(id))
        .find(element => element && element.style.display !== 'none');
    const top = anchor
        ? anchor.getBoundingClientRect().bottom - container.getBoundingClientRect().top + DEFAULTS.UI.MAP_PANEL_GAP_PX
        : DEFAULTS.UI.MAP_PANEL_EDGE_PX;
    for (const element of (elements.filter(Boolean) as HTMLElement[])) {
        element.style.left = `${DEFAULTS.UI.MAP_PANEL_EDGE_PX}px`;
        element.style.right = 'auto';
        element.style.top = `${top}px`;
    }
}
