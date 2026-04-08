import { Config, DEFAULTS } from '../config.js';

const FALLBACK_COLOR = DEFAULTS.COLORS.FALLBACK;

const projectColorMap = new Map();
const gpsTrackColorMap = new Map();

export const Colors = {
    FALLBACK_COLOR,

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
            ? Math.max(1e-9, depthDomain.max)
            : null;
        if (!maxDepth) {
            return DEFAULTS.COLORS.DEPTH_NONE;
        }

        const midDepth = maxDepth / 2;
        return [
            'case',
            ['has', 'depth_val'],
            ['interpolate', ['linear'], ['max', 0, ['coalesce', ['to-number', ['get', 'depth_val']], 0]],
                0, DEFAULTS.COLORS.DEPTH_SHALLOW,
                midDepth, DEFAULTS.COLORS.DEPTH_MID,
                maxDepth, DEFAULTS.COLORS.DEPTH_DEEP
            ],
            DEFAULTS.COLORS.DEPTH_NONE
        ];
    }
};
