import { Config, DEFAULTS } from '../config.js';

const FALLBACK_COLOR = DEFAULTS.COLORS.FALLBACK;

const projectColorMap = new Map();
const gpsTrackColorMap = new Map();

export const Colors = {
    FALLBACK_COLOR,

    isValidColorMode(mode) {
        return DEFAULTS.DISPLAY.COLOR_MODES.includes(mode);
    },

    // Resolve paint in one place for mode changes and newly loaded/rebuilt layers.
    getSurveyPaint(projectId, mode, depthDomain = null) {
        if (mode === 'depth') return this.getDepthPaint(depthDomain);
        const projectColor = this.getProjectColor(projectId);
        if (mode === 'shot') return ['to-color', ['get', 'color'], projectColor];
        return projectColor;
    },

    getProjectColor: function(projectId) {
        if (projectColorMap.has(projectId)) {
            return projectColorMap.get(projectId);
        }
        const project = Config.getProjectById(projectId);
        if (project && project.color) {
            projectColorMap.set(projectId, project.color);
            return project.color;
        }
        // Don't cache fallback — Config may not be populated yet.
        // Next call will retry and pick up the real color once available.
        return FALLBACK_COLOR;
    },

    getGPSTrackColor: function(trackId) {
        if (gpsTrackColorMap.has(trackId)) {
            return gpsTrackColorMap.get(trackId);
        }
        const track = Config.getGPSTrackById(trackId);
        if (track && track.color) {
            gpsTrackColorMap.set(trackId, track.color);
            return track.color;
        }
        return FALLBACK_COLOR;
    },

    resetColorMap: function() {
        projectColorMap.clear();
    },

    invalidateProjectColor: function(projectId) {
        projectColorMap.delete(String(projectId));
    },

    resetGPSTrackColorMap: function() {
        gpsTrackColorMap.clear();
    },

    invalidateGPSTrackColor: function(trackId) {
        gpsTrackColorMap.delete(String(trackId));
    },

    getDepthPaint: function(depthDomain = null) {
        const maxDepth = depthDomain && Number.isFinite(depthDomain.max)
            ? (depthDomain.max > 0 ? depthDomain.max : DEFAULTS.DEPTH.ZERO_DOMAIN_MAX_FEET)
            : null;
        if (!maxDepth) {
            return DEFAULTS.COLORS.DEPTH_NONE;
        }

        const midDepth = maxDepth / 2;
        const stops = midDepth > 0
            ? [0, DEFAULTS.COLORS.DEPTH_SHALLOW, midDepth, DEFAULTS.COLORS.DEPTH_MID, maxDepth, DEFAULTS.COLORS.DEPTH_DEEP]
            : [0, DEFAULTS.COLORS.DEPTH_SHALLOW, maxDepth, DEFAULTS.COLORS.DEPTH_DEEP];
        return [
            'case',
            ['has', 'depth_val'],
            ['interpolate', ['linear'], ['max', 0, ['coalesce', ['to-number', ['get', 'depth_val']], 0]],
                ...stops
            ],
            DEFAULTS.COLORS.DEPTH_NONE
        ];
    }
};
