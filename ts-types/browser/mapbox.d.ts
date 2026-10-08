import type { MapboxGlobal } from '../domain/map-geometry.ts';

declare global {
    var mapboxgl: MapboxGlobal;
}
