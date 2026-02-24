export const DepthUtils = {
    // Robust depth parser: supports numbers and numeric prefixes like "123 ft"
    parseDepthValue(raw) {
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
    getFeatureSectionName(props) {
        if (!props) return undefined;
        const candidates = ['section_name', 'SECTION_NAME', 'section', 'Section', 'name', 'Name'];
        for (const key of candidates) {
            if (props[key] != null && String(props[key]).trim() !== '') return props[key];
        }
        return undefined;
    },

    // Try multiple property candidates for depth
    getFeatureDepthValue(props) {
        if (!props) return undefined;
        const candidates = ['depth', 'Depth', 'depth_m', 'depth_ft', 'DEPTH'];
        for (const key of candidates) {
            const v = this.parseDepthValue(props[key]);
            if (v != null) return v;
        }
        return undefined;
    }
};

function isFiniteNumber(value) {
    return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Build average depth by section name from Point features.
 */
export function buildSectionDepthAverageMap(features = []) {
    const sectionDepthAccumulator = new Map();

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

    const sectionDepthAvgMap = new Map();
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
export function resolveLineDepthValue(properties, sectionDepthAvgMap) {
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
export function computeProjectDepthDomain(featureCollection, precomputedSectionDepthAvgMap = null) {
    if (!featureCollection || !Array.isArray(featureCollection.features)) {
        return null;
    }

    const features = featureCollection.features;
    const sectionDepthAvgMap = precomputedSectionDepthAvgMap instanceof Map
        ? precomputedSectionDepthAvgMap
        : buildSectionDepthAverageMap(features);

    let maxDepth = -Infinity;

    sectionDepthAvgMap.forEach((avgDepth) => {
        if (isFiniteNumber(avgDepth)) {
            maxDepth = Math.max(maxDepth, avgDepth);
        }
    });

    features.forEach((feature) => {
        if (feature?.geometry?.type !== 'LineString') return;
        const depthValue = resolveLineDepthValue(feature?.properties, sectionDepthAvgMap);
        if (isFiniteNumber(depthValue)) {
            maxDepth = Math.max(maxDepth, depthValue);
        }
    });

    if (!isFiniteNumber(maxDepth)) {
        return null;
    }

    return { min: 0, max: Math.max(0, maxDepth) };
}

/**
 * Merge multiple depth domains into one (O(projects)).
 */
export function mergeDepthDomains(domains) {
    let max = 0;
    let hasDepth = false;

    (domains || []).forEach((domain) => {
        if (!domain || !isFiniteNumber(domain.max)) return;
        hasDepth = true;
        if (domain.max > max) max = domain.max;
    });

    if (!hasDepth) return null;
    return { min: 0, max: Math.max(0, max) };
}




