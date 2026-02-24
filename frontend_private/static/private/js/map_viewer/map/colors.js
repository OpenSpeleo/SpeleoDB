// Maximally distinguishable color palette based on perceptual color theory
// These 20 colors are optimized for maximum visual distinction
const PALETTE = [
    '#e41a1c', // Red
    '#377eb8', // Blue  
    '#4daf4a', // Green
    '#984ea3', // Purple
    '#ff7f00', // Orange
    '#ffff33', // Yellow
    '#a65628', // Brown
    '#f781bf', // Pink
    '#999999', // Gray
    '#66c2a5', // Teal
    '#fc8d62', // Salmon
    '#8da0cb', // Lavender
    '#e78ac3', // Rose
    '#a6d854', // Lime
    '#ffd92f', // Gold
    '#e5c494', // Tan
    '#b3b3b3', // Light Gray
    '#1b9e77', // Dark Teal
    '#d95f02', // Dark Orange
    '#7570b3'  // Slate Blue
];

// Persistent per-project color assignment to avoid reusing first color
const projectColorMap = new Map();

// Persistent per-GPS-track color assignment (separate from projects)
const gpsTrackColorMap = new Map();

export const Colors = {
    PALETTE,

    // Helper to get consistent project color (using index-based assignment like old implementation)
    getProjectColor: function(projectId, fallbackIndex = 0) {
        if (projectColorMap.has(projectId)) {
            return projectColorMap.get(projectId);
        }
        // Use the next available color based on how many projects we have
        const index = projectColorMap.size;
        const color = PALETTE[index % PALETTE.length];
        projectColorMap.set(projectId, color);
        return color;
    },

    // Helper to get consistent GPS track color (separate color space from projects)
    // Uses reversed palette to maximize visual distinction from project colors
    getGPSTrackColor: function(trackId) {
        if (gpsTrackColorMap.has(trackId)) {
            return gpsTrackColorMap.get(trackId);
        }
        // Use the next available color, offset and reversed to differ from projects
        const index = gpsTrackColorMap.size;
        // Start from a different part of the palette (offset by 10) and reverse order
        const reversedPalette = [...PALETTE].reverse();
        const offsetIndex = (index + 5) % reversedPalette.length;
        const color = reversedPalette[offsetIndex];
        gpsTrackColorMap.set(trackId, color);
        return color;
    },

    // Reset color assignments (useful for testing)
    resetColorMap: function() {
        projectColorMap.clear();
    },

    // Reset GPS track color assignments
    resetGPSTrackColorMap: function() {
        gpsTrackColorMap.clear();
    },

    // Interpolation expression for depth using active merged domain.
    // Falls back to gray when no active depth domain is available.
    getDepthPaint: function(depthDomain = null) {
        const maxDepth = depthDomain && Number.isFinite(depthDomain.max)
            ? Math.max(1e-9, depthDomain.max)
            : null;
        if (!maxDepth) {
            return '#999999';
        }

        const midDepth = maxDepth / 2;
        return [
            'case',
            ['has', 'depth_val'],
            ['interpolate', ['linear'], ['max', 0, ['coalesce', ['to-number', ['get', 'depth_val']], 0]],
                0, '#4575b4',
                midDepth, '#e6f598',
                maxDepth, '#d73027'
            ],
            '#999999' // Fallback color if no depth
        ];
    }
};

