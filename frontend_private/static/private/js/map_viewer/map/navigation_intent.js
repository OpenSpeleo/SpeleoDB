let activeMap = null;
let activeIntent = null;

function cancelOnGesture(event) {
    if (event.originalEvent) cancelMapNavigation();
}

/** Route teardown and map replacement invalidate every deferred camera action. */
export function resetMapNavigation(map = null) {
    activeMap?.off?.('movestart', cancelOnGesture);
    activeMap = map;
    activeIntent = null;
    activeMap?.on?.('movestart', cancelOnGesture);
}

export function cancelMapNavigation(entityKey) {
    if (entityKey === undefined || activeIntent?.entityKey === entityKey) activeIntent = null;
}

/** One camera intent spans project, GPS, GIS, station and landmark controls. */
export function beginMapNavigation(map, entityKey) {
    if (activeMap !== map) resetMapNavigation(map);
    const intent = { map, entityKey };
    activeIntent = intent;
    return { isCurrent: () => activeIntent === intent && activeMap === map && Boolean(map) };
}
