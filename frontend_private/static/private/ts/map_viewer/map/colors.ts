import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { DepthDomain } from '../../../../../../ts-types/domain/map-display.ts';
import type { DepthPaint, SurveyPaint } from '../../../../../../ts-types/domain/map-depth.ts';
import { Config, DEFAULTS } from '../config.ts';

const FALLBACK_COLOR = DEFAULTS.COLORS.FALLBACK;

const projectColorMap = new Map<EntityId, string>();
const gpsTrackColorMap = new Map<EntityId, string>();

export const Colors = {
    FALLBACK_COLOR,

    isValidColorMode(mode: unknown) {
        return DEFAULTS.DISPLAY.COLOR_MODES.includes(mode as string);
    },

    // Resolve paint in one place for mode changes and newly loaded/rebuilt layers.
    getSurveyPaint(projectId: EntityId, mode: string, depthDomain: Pick<DepthDomain, 'max'> & Partial<Pick<DepthDomain, 'min'>> | null = null): SurveyPaint {
        if (mode === 'depth') return this.getDepthPaint(depthDomain);
        const projectColor = this.getProjectColor(projectId);
        if (mode === 'shot') return ['to-color', ['get', 'color'], projectColor];
        return projectColor;
    },

    getProjectColor: function(projectId: EntityId) {
        if (projectColorMap.has(projectId)) {
            return projectColorMap.get(projectId)!;
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

    getGPSTrackColor: function(trackId: EntityId) {
        if (gpsTrackColorMap.has(trackId)) {
            return gpsTrackColorMap.get(trackId)!;
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

    invalidateProjectColor: function(projectId: EntityId) {
        projectColorMap.delete(String(projectId));
    },

    resetGPSTrackColorMap: function() {
        gpsTrackColorMap.clear();
    },

    invalidateGPSTrackColor: function(trackId: EntityId) {
        gpsTrackColorMap.delete(String(trackId));
    },

    getDepthPaint: function(depthDomain: Pick<DepthDomain, 'max'> & Partial<Pick<DepthDomain, 'min'>> | null = null): string | DepthPaint {
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
