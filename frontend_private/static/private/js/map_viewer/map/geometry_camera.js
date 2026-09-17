import { DEFAULTS } from '../config.js';

const area = rectangle => Math.max(0, rectangle.right - rectangle.left)
    * Math.max(0, rectangle.bottom - rectangle.top);

/** Fit into the visible, unobstructed map instead of the whole canvas. */
export function geometryCameraPadding(map, viewport, obstacles = []) {
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

export function fitGISGeometry(map, bounds) {
    if (!bounds) return;
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
        '.mapboxgl-ctrl-top-right'];
    const obstacles = selectors.flatMap(selector => [...document.querySelectorAll(selector)])
        .filter(element => !element.hidden && getComputedStyle(element).display !== 'none')
        .map(element => element.getBoundingClientRect());
    map.fitBounds(bounds, {
        padding: rectangle?.width && rectangle?.height
            ? geometryCameraPadding(rectangle, visible, obstacles) : DEFAULTS.MAP.FIT_BOUNDS_PADDING,
        maxZoom: DEFAULTS.MAP.FIT_BOUNDS_MAX_ZOOM,
        bearing: 0, pitch: 0, retainPadding: false,
    });
}
