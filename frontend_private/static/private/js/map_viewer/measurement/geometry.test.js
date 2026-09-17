import { DEFAULTS } from '../config.js';
import { coordinateFromPoint, createMeasurement, curveLineParts, formatDistance, measurementFeatures, sampleCurve } from './geometry.js';

describe('measurement distances and formatting', () => {
    it('copies exact endpoints and measures the shortest geographic distance', () => {
        const start = [0, 0];
        const record = createMeasurement(start, [1, 0], 'one');
        start[0] = 20;
        expect(record.start).toEqual([0, 0]);
        expect(record.id).toBe('one');
        expect(record.distanceMeters).toBeCloseTo(111194.9266, 3);
        const originalOffset = DEFAULTS.MEASUREMENT.CURVE_OFFSET_RATIO;
        try {
            DEFAULTS.MEASUREMENT.CURVE_OFFSET_RATIO = 0.5;
            sampleCurve(record.start, record.end);
            expect(createMeasurement(record.start, record.end, 'two').distanceMeters).toBe(record.distanceMeters);
        } finally {
            DEFAULTS.MEASUREMENT.CURVE_OFFSET_RATIO = originalOffset;
        }
    });

    it.each([
        [0, '0 m', '0 ft'], [0.01, '<0.1 m', '<1 ft'], [128.4, '128.4 m', '421 ft'],
        [999.96, '1 km', '3281 ft'], [1609.2, '1.61 km', '1 mi'],
        [1609.344, '1.61 km', '1 mi'], [10000, '10 km', '6.21 mi'],
    ])('formats %s meters without false zeroes or unit-boundary artifacts', (meters, metric, imperial) => {
        expect(formatDistance(meters)).toEqual({ metric, imperial, label: `${metric} · ${imperial}` });
    });
});

describe('decorative geographic curves', () => {
    it('bends a short curve while keeping both endpoints exact', () => {
        const points = sampleCurve([0, 0], [1, 0]);
        expect(points[0]).toEqual([0, 0]);
        expect(points.at(-1)).toEqual([1, 0]);
        expect(points).toHaveLength(DEFAULTS.MEASUREMENT.MIN_CURVE_SEGMENTS + 1);
        expect(points[Math.floor(points.length / 2)][1]).toBeGreaterThan(0);
    });

    it.each([
        [[0, 0], [180, 0]], [[12, 80], [-168, -80]],
        [[0, 84], [180, 84]], [[179.9, 0], [-179.9, 0]],
        [[180, 0], [-179, 1]], [[-180, 0], [179, 1]],
    ])('keeps antipodal, polar, and date-line geometry finite: %s to %s', (start, end) => {
        const samples = sampleCurve(start, end);
        expect(samples).toEqual(sampleCurve(start, end));
        expect(samples.length).toBeLessThanOrEqual(DEFAULTS.MEASUREMENT.MAX_CURVE_SEGMENTS + 1);
        expect(samples[0]).toEqual(start);
        expect(samples.at(-1)).toEqual(end);
        for (const line of curveLineParts(samples)) {
            for (const [longitude, latitude] of line) {
                expect(Number.isFinite(longitude)).toBe(true);
                expect(Math.abs(longitude)).toBeLessThanOrEqual(180);
                expect(Math.abs(latitude)).toBeLessThanOrEqual(DEFAULTS.MEASUREMENT.MAX_LATITUDE);
            }
            for (let index = 1; index < line.length; index++) {
                expect(Math.abs(line[index][0] - line[index - 1][0])).toBeLessThanOrEqual(180);
            }
        }
    });

    it('splits date-line crossings into matching boundary points', () => {
        const parts = curveLineParts(sampleCurve([179, 0], [-179, 0]));
        expect(parts).toHaveLength(2);
        expect(parts[0].at(-1)[0]).toBe(180);
        expect(parts[1][0][0]).toBe(-180);
        expect(parts[0].at(-1)[1]).toBe(parts[1][0][1]);
    });

    it('clips polar curve sections without changing distance or endpoint positions', () => {
        const record = createMeasurement([0, 84], [180, 84], 'polar');
        const features = measurementFeatures(record);
        expect(features.filter(feature => feature.properties.role === 'endpoint').map(feature => feature.geometry.coordinates))
            .toEqual([record.start, record.end]);
        expect(features.find(feature => feature.properties.role === 'label').geometry.coordinates).toEqual(record.start);
        expect(features.find(feature => feature.properties.role === 'line').geometry.coordinates.length).toBeGreaterThan(1);
    });

    it('allows a first endpoint without a line or result', () => {
        expect(measurementFeatures({ start: [1, 2], end: null })).toEqual([
            expect.objectContaining({ properties: expect.objectContaining({ role: 'endpoint' }) }),
        ]);
    });
});

describe('surface coordinate picking', () => {
    let map;
    beforeEach(() => {
        map = { isPointOnSurface: vi.fn(() => true), unproject: vi.fn(() => ({ lng: 181, lat: 20 })), project: vi.fn(() => ({ x: 10, y: 20 })) };
    });
    it('normalizes longitudes after checking a valid screen round-trip', () => {
        expect(coordinateFromPoint(map, { x: 10, y: 20 })).toEqual([-179, 20]);
        expect(map.project).toHaveBeenCalledWith({ lng: 181, lat: 20 });
    });
    it('rejects sky points even when unproject would clamp to the horizon', () => {
        map.isPointOnSurface.mockReturnValue(false);
        expect(coordinateFromPoint(map, { x: 10, y: 20 })).toBeNull();
        expect(map.unproject).not.toHaveBeenCalled();
        map.isPointOnSurface.mockReturnValue(true);
        map.project.mockReturnValue({ x: 40, y: 20 });
        expect(coordinateFromPoint(map, { x: 10, y: 20 })).toBeNull();
    });
    it('rejects nonfinite and polar positions', () => {
        expect(coordinateFromPoint(map, { x: NaN, y: 20 })).toBeNull();
        for (const lat of [NaN, 86, -86]) {
            map.unproject.mockReturnValue({ lng: 0, lat });
            expect(coordinateFromPoint(map, { x: 10, y: 20 })).toBeNull();
        }
    });
});
