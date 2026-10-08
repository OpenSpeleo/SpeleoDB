import { DEFAULTS } from '../config.ts';
import type { CameraBounds, CameraPadding, FlatBounds, GeometryCameraMap, Rectangle } from '../../../../../../ts-types/domain/map-geometry.ts';

const area = (rectangle: Rectangle) => Math.max(0, rectangle.right - rectangle.left)
    * Math.max(0, rectangle.bottom - rectangle.top);

/** Fit into the visible, unobstructed map instead of the whole canvas. */
export function geometryCameraPadding(map: Rectangle, viewport: Rectangle, obstacles: Rectangle[] = []): CameraPadding | number {
    let free = {
        left: Math.max(map.left, viewport.left), right: Math.min(map.right, viewport.right),
        top: Math.max(map.top, viewport.top), bottom: Math.min(map.bottom, viewport.bottom),
    };
    if (!area(free)) return DEFAULTS.MAP.FIT_BOUNDS_PADDING;
    for (const obstacle of obstacles) {
        if (!area(obstacle) || obstacle.right <= free.left || obstacle.left >= free.right
            || obstacle.bottom <= free.top || obstacle.top >= free.bottom) continue;
        // Keep the largest remaining rectangle. Each cut preserves clearance
        // from all previously considered panels, with constant work per panel.
        const choices = [
            { ...free, right: Math.max(free.left, obstacle.left) },
            { ...free, left: Math.min(free.right, obstacle.right) },
            { ...free, bottom: Math.max(free.top, obstacle.top) },
            { ...free, top: Math.min(free.bottom, obstacle.bottom) },
        ];
        const next = choices.reduce((best, choice) => area(choice) > area(best) ? choice : best);
        if (area(next)) free = next;
    }
    const margin = Math.min(DEFAULTS.MAP.FIT_BOUNDS_PADDING,
        (free.right - free.left) * DEFAULTS.GIS_GEOMETRY.FIT_MARGIN_RATIO,
        (free.bottom - free.top) * DEFAULTS.GIS_GEOMETRY.FIT_MARGIN_RATIO);
    return {
        left: free.left - map.left + margin, right: map.right - free.right + margin,
        top: free.top - map.top + margin, bottom: map.bottom - free.bottom + margin,
    };
}

export function fitGISGeometry(map: GeometryCameraMap, bounds: CameraBounds | null | undefined) {
    if (!bounds) return;
    // RFC 7946 crossing bounds use west > east. MapLibre fits projected corners
    // directly, so unwrap east to keep the camera on the short longitude span.
    const cameraBounds: CameraBounds = Array.isArray(bounds) && bounds.length === 4 && bounds[0] > bounds[2]
        ? [(bounds as FlatBounds)[0], (bounds as FlatBounds)[1], (bounds as FlatBounds)[2] + DEFAULTS.MAP.ANTIMERIDIAN_WRAP_DEGREES, (bounds as FlatBounds)[3]]
        : bounds;
    const container = map.getContainer?.() || document.getElementById('map');
    const rectangle = container?.getBoundingClientRect();
    const viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0;
    const top = viewport?.offsetTop || 0;
    const visible = { left, top, right: left + (viewport?.width || window.innerWidth),
        bottom: top + (viewport?.height || window.innerHeight) };
    const selectors = ['.gis-geometry-editor', '#project-panel', '#project-panel-minimized',
        '#gps-tracks-panel', '#gps-tracks-panel-minimized', '#gis-layers-panel',
        '#gis-layers-panel-minimized', '#gis-geometries-panel', '#gis-geometries-panel-minimized',
        '.maplibregl-ctrl-top-right'];
    const obstacles = selectors.flatMap(selector => [...document.querySelectorAll<HTMLElement>(selector)])
        .filter(element => !element.hidden && getComputedStyle(element).display !== 'none')
        .map(element => element.getBoundingClientRect());
    map.fitBounds(cameraBounds, {
        padding: rectangle?.width && rectangle?.height
            ? geometryCameraPadding(rectangle, visible, obstacles) : DEFAULTS.MAP.FIT_BOUNDS_PADDING,
        maxZoom: DEFAULTS.MAP.FIT_BOUNDS_MAX_ZOOM,
        bearing: 0, pitch: 0, retainPadding: false,
    });
}
