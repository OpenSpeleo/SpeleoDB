/** Keep private map overlays inside the element used for fullscreen. */
export function getMapOverlayHost() {
    return document.getElementById('map-viewer-shell') || document.body;
}

export function isVisibleMapElement(element) {
    if (!element?.isConnected || element.closest('[hidden], .hidden')) return false;
    for (let current = element; current instanceof Element; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.display === 'none' || style.visibility === 'hidden') return false;
    }
    return true;
}

/** Includes legacy overlays so an open child never sends keys to the editor. */
export function getActiveMapDialog() {
    const dialogs = [...document.querySelectorAll('dialog[open], [role="dialog"], #map-managers-menu, .fixed.inset-0')]
        .filter(element => !element.matches('dialog:not([open])') && isVisibleMapElement(element))
        .filter(element => element.matches('dialog, [role="dialog"], #map-managers-menu') || /modal|lightbox/.test(element.id));
    return dialogs.findLast(element => element.matches('dialog[open]')) || dialogs.at(-1) || null;
}

export function isMapDialogOpen() {
    return Boolean(getActiveMapDialog());
}
