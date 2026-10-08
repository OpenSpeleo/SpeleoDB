import type { NavigationGesture, NavigationMap } from '../../../../../../ts-types/domain/map-runtime.ts';

let activeMap: NavigationMap | null = null;
let activeIntent: { map: NavigationMap | null; entityKey: string } | null = null;

function cancelOnGesture(event: NavigationGesture) {
    if (event.originalEvent) cancelMapNavigation();
}

/** Route teardown and map replacement invalidate every deferred camera action. */
export function resetMapNavigation(map: NavigationMap | null = null) {
    activeMap?.off?.('movestart', cancelOnGesture);
    activeMap = map;
    activeIntent = null;
    activeMap?.on?.('movestart', cancelOnGesture);
}

export function cancelMapNavigation(entityKey?: string) {
    if (entityKey === undefined || activeIntent?.entityKey === entityKey) activeIntent = null;
}

/** One camera intent spans project, GPS, GIS, station and landmark controls. */
export function beginMapNavigation(map: NavigationMap | null, entityKey: string) {
    if (activeMap !== map) resetMapNavigation(map);
    const intent = { map, entityKey };
    activeIntent = intent;
    return { isCurrent: () => activeIntent === intent && activeMap === map && Boolean(map) };
}
