import { DEFAULTS } from '../config.ts';

/** Direct spherical distance; ignores elevation and any rendered annotation. */
export function calculateDistanceInMeters(point1: readonly number[], point2: readonly number[]) {
    const radians = Math.PI / DEFAULTS.GEODESY.DEGREES_PER_HALF_TURN;
    const [lng1, lat1] = point1 as readonly [number, number];
    const [lng2, lat2] = point2 as readonly [number, number];
    const latitudeTerm = Math.sin((lat2 - lat1) * radians / 2);
    const longitudeTerm = Math.sin((lng2 - lng1) * radians / 2);
    const haversine = latitudeTerm ** 2
        + Math.cos(lat1 * radians) * Math.cos(lat2 * radians) * longitudeTerm ** 2;
    // Floating point error near antipodes can otherwise put sqrt outside its domain.
    const clamped = Math.max(0, Math.min(1, haversine));
    return DEFAULTS.GEODESY.EARTH_RADIUS_METERS
        * 2 * Math.atan2(Math.sqrt(clamped), Math.sqrt(1 - clamped));
}
