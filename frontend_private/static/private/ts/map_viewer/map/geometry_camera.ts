import { computeCameraPadding, type Rectangle, type CameraPadding } from '@speleodb/map-viewer/camera-padding';
import { DEFAULTS } from '../config.ts';
import type { CameraBounds, FlatBounds, GeometryCameraMap } from '../../../../../../ts-types/domain/map-geometry.ts';

/** Web camera margins remain application policy; rectangle fitting is shared. */
export function geometryCameraPadding(map: Rectangle, viewport: Rectangle, obstacles: Rectangle[] = []): CameraPadding | number {
    return computeCameraPadding(map, viewport, {
        padding: DEFAULTS.MAP.FIT_BOUNDS_PADDING,
        marginRatio: DEFAULTS.GIS_GEOMETRY.FIT_MARGIN_RATIO,
        obstacles,
    });
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
