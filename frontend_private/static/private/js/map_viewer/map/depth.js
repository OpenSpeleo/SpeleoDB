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


