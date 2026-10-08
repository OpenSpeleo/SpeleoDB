import type { DepthFeature } from '../../../../../../ts-types/domain/map-depth.ts';
import { DepthUtils, buildSectionDepthAverageMap, computeProjectDepthDomain, resolveLineDepthValue, applyDepthLimit, depthFromFeet, depthToFeet, isValidDepthLimit, mergeDepthDomains } from './depth.ts';

describe('mergeDepthDomains', () => {
    it('returns null for empty array', () => {
        expect(mergeDepthDomains([])).toBeNull();
    });

    it('returns null when all entries are null', () => {
        expect(mergeDepthDomains([null, null])).toBeNull();
    });

    it('returns single domain when only one is non-null', () => {
        expect(mergeDepthDomains([{ min: 0, max: 50 }, null])).toEqual({ min: 0, max: 50 });
    });

    it('merges multiple domains taking max of maxes', () => {
        expect(mergeDepthDomains([{ min: 0, max: 30 }, { min: 0, max: 80 }])).toEqual({ min: 0, max: 80 });
    });

    it('always returns min 0 regardless of input mins', () => {
        expect(mergeDepthDomains([{ min: -20, max: 10 }, { min: 5, max: 40 }])).toEqual({ min: 0, max: 40 });
    });
});

describe('depth limits and display units', () => {
    it.each([null, 1, 0.01, Number.MIN_VALUE, Number.MAX_VALUE])('accepts canonical limit %s', value => {
        expect(isValidDepthLimit(value)).toBe(true);
    });

    it.each([undefined, '', '10', 0, -1, NaN, Infinity, -Infinity, true, {}, []])('rejects invalid limit %s', value => {
        expect(isValidDepthLimit(value)).toBe(false);
    });

    it('converts only at the unit boundary and preserves the unlimited sentinel', () => {
        expect(depthToFeet(30.48, 'm')).toBeCloseTo(100, 12);
        expect(depthFromFeet(100, 'm')).toBe(30.48);
        expect(depthToFeet(100, 'ft')).toBe(100);
        expect(depthFromFeet(100, 'ft')).toBe(100);
        expect(depthToFeet(null, 'm')).toBeNull();
        expect(depthFromFeet(null, 'ft')).toBeNull();
        expect(depthFromFeet(-10, 'm')).toBe(-3.048);
        expect(depthToFeet(10, 'yd')).toBeNaN();
        expect(depthFromFeet('10', 'm')).toBeNaN();
    });

    it('keeps a fixed maximum even when it exceeds the observed depth', () => {
        const measured = Object.freeze({ min: 0, max: 25 });
        expect(applyDepthLimit(measured, 100)).toEqual({ min: 0, max: 100 });
        expect(applyDepthLimit(measured, 10)).toEqual({ min: 0, max: 10 });
        expect(measured.max).toBe(25);
        expect(applyDepthLimit(measured, null)).toBe(measured);
    });

    it('does not invent depth data, while preserving a measured zero-depth domain', () => {
        expect(applyDepthLimit(null, 100)).toBeNull();
        expect(applyDepthLimit({ min: 0, max: 0 }, 100)).toEqual({ min: 0, max: 100 });
    });
});

describe('depth metadata coercion and cached domains', () => {
    it('preserves numeric coercion and unit-labelled parsing', () => {
        expect(DepthUtils.parseDepthValue('')).toBe(0);
        expect(DepthUtils.parseDepthValue(false)).toBe(0);
        expect(DepthUtils.parseDepthValue('depth -12.5 ft')).toBe(-12.5);
        expect(DepthUtils.parseDepthValue(null)).toBeUndefined();
        expect(DepthUtils.parseDepthValue('missing')).toBeUndefined();
        expect(() => DepthUtils.parseDepthValue(Symbol('depth'))).toThrow(TypeError);
    });

    it('preserves section key identity and fallback order', () => {
        const section = { toString: () => 'section' };
        expect(DepthUtils.getFeatureSectionName({ section_name: section, name: 'fallback' })).toBe(section);
        expect(DepthUtils.getFeatureSectionName({ section_name: ' ', Name: 'fallback' })).toBe('fallback');
        expect(DepthUtils.getFeatureDepthValue({ depth: 'missing', Depth: '12 ft', depth_ft: 99 })).toBe(12);
        expect(resolveLineDepthValue({ name: 0 }, new Map([[0, 22]]))).toBeUndefined();
        expect(resolveLineDepthValue({ name: 'section', depth: 7 }, new Map([['section', 22]]))).toBe(7);
    });

    it('averages point depths only and reuses the supplied section map', () => {
        const features: DepthFeature[] = [
            { type: 'Feature', geometry: { type: 'Point', coordinates: [0, 0] }, properties: { name: 'a', depth: 10 } },
            { type: 'Feature', geometry: { type: 'Point', coordinates: [0, 0] }, properties: { name: 'a', depth: 30 } },
            { type: 'Feature', geometry: { type: 'LineString', coordinates: [] }, properties: { name: 'a', depth: 100 } },
        ];
        expect(buildSectionDepthAverageMap(features)).toEqual(new Map([['a', 20]]));
        const cached = new Map([['a', 70]]);
        const collection = { type: 'FeatureCollection' as const, features: [features[0]] };
        expect(computeProjectDepthDomain(collection, cached)).toEqual({ min: 0, max: 70 });
        expect(cached).toEqual(new Map([['a', 70]]));
        expect(computeProjectDepthDomain({ type: 'FeatureCollection', features })).toEqual({ min: 0, max: 100 });
        expect(computeProjectDepthDomain(null)).toBeNull();
        expect(computeProjectDepthDomain({ type: 'FeatureCollection', features: [] })).toBeNull();
    });
});
