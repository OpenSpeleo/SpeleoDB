import { firstPropertyDepth, depthDomainFromValues } from '@speleodb/map-core/depth';
import type { DepthDomain } from '../../../../../../ts-types/domain/map-display.ts';
import type { DepthFeature, DepthProperties, SectionDepthMap } from '../../../../../../ts-types/domain/map-depth.ts';
import { DEFAULTS } from '../config.ts';

export { isValidDepthLimit, applyDepthLimit, mergeDepthDomains } from '@speleodb/map-core/depth';

export function depthToFeet(value: unknown, unit: string) {
    if (unit !== 'ft' && unit !== 'm') return NaN;
    if (value === null) return null;
    if (typeof value !== 'number' || !Number.isFinite(value)) return NaN;
    return unit === 'm' ? value / DEFAULTS.MEASUREMENT.METERS_PER_FOOT : value;
}

export function depthFromFeet(value: unknown, unit: string) {
    if (unit !== 'ft' && unit !== 'm') return NaN;
    if (value === null) return null;
    if (typeof value !== 'number' || !Number.isFinite(value)) return NaN;
    return unit === 'm' ? value * DEFAULTS.MEASUREMENT.METERS_PER_FOOT : value;
}

export const DepthUtils = {
    // Robust depth parser: supports numbers and numeric prefixes like "123 ft"
    parseDepthValue(raw: unknown) {
        if (raw == null) return undefined;
        const num = Number(raw);
        if (Number.isFinite(num)) return num;
        if (typeof raw === 'string') {
            const m = raw.match(/-?\d+(?:\.\d+)?/);
            if (m) {
                const v = Number(m[0]);
                if (Number.isFinite(v)) return v;
            }
        }
        return undefined;
    },

    // Try multiple property candidates for section name
    getFeatureSectionName(props: DepthProperties | null | undefined) {
        if (!props) return undefined;
        const candidates = ['section_name', 'SECTION_NAME', 'section', 'Section', 'name', 'Name'] as const;
        for (const key of candidates) {
            if (props[key] != null && String(props[key]).trim() !== '') return props[key];
        }
        return undefined;
    },

    // Try multiple property candidates for depth
    getFeatureDepthValue(props: DepthProperties | null | undefined) {
        if (!props) return undefined;
        const candidates = ['depth', 'Depth', 'depth_m', 'depth_ft', 'DEPTH'] as const;
        return firstPropertyDepth(props, candidates, value => this.parseDepthValue(value)) ?? undefined;
    }
};

function isFiniteNumber(value: unknown): value is number {
    return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Build average depth by section name from Point features.
 */
export function buildSectionDepthAverageMap(features: readonly (DepthFeature | null | undefined)[] = []): SectionDepthMap {
    const sectionDepthAccumulator = new Map<unknown, number[]>();

    features.forEach((feature) => {
        const props = feature?.properties;
        const sectionName = DepthUtils.getFeatureSectionName(props);
        const pointDepth = DepthUtils.getFeatureDepthValue(props);

        if (
            feature?.geometry?.type === 'Point' &&
            sectionName != null &&
            isFiniteNumber(pointDepth)
        ) {
            const values = sectionDepthAccumulator.get(sectionName) || [];
            values.push(pointDepth);
            sectionDepthAccumulator.set(sectionName, values);
        }
    });

    const sectionDepthAvgMap: SectionDepthMap = new Map();
    sectionDepthAccumulator.forEach((values, sectionName) => {
        if (values.length > 0) {
            const avg = values.reduce((a, b) => a + b, 0) / values.length;
            sectionDepthAvgMap.set(sectionName, avg);
        }
    });

    return sectionDepthAvgMap;
}

/**
 * Resolve effective depth value for a LineString from direct depth or section average.
 */
export function resolveLineDepthValue(properties: DepthProperties | null | undefined, sectionDepthAvgMap: SectionDepthMap | null | undefined) {
    const lineDepth = DepthUtils.getFeatureDepthValue(properties);
    if (isFiniteNumber(lineDepth)) {
        return lineDepth;
    }

    const sectionName = DepthUtils.getFeatureSectionName(properties);
    if (!sectionName || !(sectionDepthAvgMap instanceof Map)) {
        return undefined;
    }

    const sectionDepth = sectionDepthAvgMap.get(sectionName);
    return isFiniteNumber(sectionDepth) ? sectionDepth : undefined;
}

/**
 * Compute depth domain for one project feature collection.
 * Domain min remains pinned to 0 to match current depth-gauge contract.
 */
export function computeProjectDepthDomain(featureCollection: { type?: 'FeatureCollection'; features?: readonly (DepthFeature | null | undefined)[] } | null | undefined, precomputedSectionDepthAvgMap: SectionDepthMap | null = null): DepthDomain | null {
    if (!featureCollection || !Array.isArray(featureCollection.features)) {
        return null;
    }

    const features = featureCollection.features as readonly (DepthFeature | null | undefined)[];
    const sectionDepthAvgMap = precomputedSectionDepthAvgMap instanceof Map
        ? precomputedSectionDepthAvgMap
        : buildSectionDepthAverageMap(features);

    function* values() {
        for (const depth of sectionDepthAvgMap.values()) {
            if (isFiniteNumber(depth)) yield depth;
        }
        for (const feature of features) {
            if (feature?.geometry?.type !== 'LineString') continue;
            const depth = resolveLineDepthValue(feature.properties, sectionDepthAvgMap);
            if (isFiniteNumber(depth)) yield depth;
        }
    }
    return depthDomainFromValues(values());
}
