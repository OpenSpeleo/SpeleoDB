import { calculateDistanceInMeters } from './geodesy.js';
import { DEFAULTS } from '../config.js';

describe('shared spherical distance', () => {
    it('preserves the established mean Earth radius and known equatorial distance', () => {
        expect(calculateDistanceInMeters([0, 0], [0, 0])).toBe(0);
        expect(calculateDistanceInMeters([0, 0], [1, 0])).toBeCloseTo(111194.9266, 3);
        expect(DEFAULTS.GEODESY.EARTH_RADIUS_METERS).toBe(6371000);
    });

    it('takes the short route over the date line and is symmetric', () => {
        const a = [179.9, 35];
        const b = [-179.9, 35];
        expect(calculateDistanceInMeters(a, b)).toBeCloseTo(calculateDistanceInMeters(b, a), 6);
        expect(calculateDistanceInMeters(a, b)).toBeGreaterThan(18000);
        expect(calculateDistanceInMeters(a, b)).toBeLessThan(19000);
    });

    it('remains finite at poles and numerically difficult antipodes', () => {
        for (const latitude of [0, 12.345, 45.00001, 89.9, 90]) {
            expect(calculateDistanceInMeters([0, latitude], [180, -latitude]))
                .toBeCloseTo(Math.PI * DEFAULTS.GEODESY.EARTH_RADIUS_METERS, 0);
        }
        expect(calculateDistanceInMeters([0, 90], [45, 90])).toBeLessThan(1e-8);
    });
});
