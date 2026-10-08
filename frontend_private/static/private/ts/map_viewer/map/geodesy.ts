import { DEFAULTS } from '../config.ts';
import { calculateDistanceInMeters as distance } from '@speleodb/map-core/geo';

/** Direct spherical distance; ignores elevation and any rendered annotation. */
export function calculateDistanceInMeters(point1: readonly number[], point2: readonly number[]) {
    return distance(point1, point2, DEFAULTS.GEODESY.EARTH_RADIUS_METERS);
}
