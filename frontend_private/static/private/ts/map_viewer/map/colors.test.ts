import type { DepthPaint } from '../../../../../../ts-types/domain/map-depth.ts';
import { Colors } from './colors.ts';
import { Config, DEFAULTS } from '../config.ts';

describe('Colors', () => {
    const originalProjects = Config._projects;
    const originalTracks = Config._gpsTracks;
    afterAll(() => {
        Config._projects = originalProjects;
        Config._gpsTracks = originalTracks;
        Colors.resetColorMap();
        Colors.resetGPSTrackColorMap();
    });
    beforeEach(() => {
        Colors.resetColorMap();
        Colors.resetGPSTrackColorMap();
        Config._projects = [];
        Config._gpsTracks = [];
    });

    describe('getProjectColor', () => {
        it('returns the stored color from the project model', () => {
            Config._projects = [{ id: 'p-1', color: '#ff5500' }];

            expect(Colors.getProjectColor('p-1')).toBe('#ff5500');
        });

        it('returns FALLBACK_COLOR when project has no color', () => {
            Config._projects = [{ id: 'p-1' }];

            expect(Colors.getProjectColor('p-1')).toBe(Colors.FALLBACK_COLOR);
        });

        it('returns FALLBACK_COLOR when project is not found', () => {
            Config._projects = [];

            expect(Colors.getProjectColor('unknown')).toBe(Colors.FALLBACK_COLOR);
        });

        it('caches the result when a real color is found', () => {
            Config._projects = [{ id: 'p-1', color: '#ff5500' }];

            expect(Colors.getProjectColor('p-1')).toBe('#ff5500');
            Config._projects = [{ id: 'p-1', color: '#123456' }];
            expect(Colors.getProjectColor('p-1')).toBe('#ff5500');
        });

        it('does NOT cache fallback — retries on next call', () => {
            // First call: project not found yet
            Config._projects = [];
            expect(Colors.getProjectColor('p-1')).toBe(Colors.FALLBACK_COLOR);

            // Second call: project now available with color
            Config._projects = [{ id: 'p-1', color: '#e41a1c' }];
            expect(Colors.getProjectColor('p-1')).toBe('#e41a1c');
        });

        it('does NOT cache when project exists but has no color field', () => {
            Config._projects = [{ id: 'p-1' }];
            expect(Colors.getProjectColor('p-1')).toBe(Colors.FALLBACK_COLOR);

            // Color becomes available later
            Config._projects = [{ id: 'p-1', color: '#377eb8' }];
            expect(Colors.getProjectColor('p-1')).toBe('#377eb8');
        });

        it('simulates public viewer timing: called before setPublicProjects, then after', () => {
            // Before Config is populated
            Config._projects = [];
            expect(Colors.getProjectColor('pub-1')).toBe(Colors.FALLBACK_COLOR);

            // After setPublicProjects populates Config
            Config._projects = [{ id: 'pub-1', color: '#4daf4a' }];
            expect(Colors.getProjectColor('pub-1')).toBe('#4daf4a');

            // Third call hits the cache now
            Config._projects = []; // wouldn't matter
            expect(Colors.getProjectColor('pub-1')).toBe('#4daf4a');
        });
    });

    describe('getSurveyPaint', () => {
        it('uses the model color as shot conversion fallback and preserves depth paint', () => {
            Config._projects = [{ id: 'p-1', color: '#ff5500' }];
            expect(Colors.getSurveyPaint('p-1', 'shot')).toEqual(['to-color', ['get', 'color'], '#ff5500']);
            expect(Colors.getSurveyPaint('p-1', 'project')).toBe('#ff5500');
            expect(Colors.getSurveyPaint('p-1', 'depth', { max: 200 })).toEqual(Colors.getDepthPaint({ max: 200 }));
        });

        it('retries the shot fallback when project metadata arrives later', () => {
            Config._projects = [];
            expect(Colors.getSurveyPaint('p-1', 'shot')[2]).toBe(Colors.FALLBACK_COLOR);
            Config._projects = [{ id: 'p-1', color: '#123456' }];
            expect(Colors.getSurveyPaint('p-1', 'shot')[2]).toBe('#123456');
        });

        it.each(['project', 'depth', 'shot'])('accepts the supported %s mode', mode => {
            expect(Colors.isValidColorMode(mode)).toBe(true);
        });

        it.each([null, undefined, 'unknown', {}, 1])('rejects unsupported mode %j', mode => {
            expect(Colors.isValidColorMode(mode)).toBe(false);
        });
    });

    describe('getGPSTrackColor', () => {
        it('returns the stored color from the track model', () => {
            Config._gpsTracks = [{ id: 't-1', color: '#377eb8' }];

            expect(Colors.getGPSTrackColor('t-1')).toBe('#377eb8');
        });

        it('returns FALLBACK_COLOR when track has no color', () => {
            Config._gpsTracks = [{ id: 't-1' }];

            expect(Colors.getGPSTrackColor('t-1')).toBe(Colors.FALLBACK_COLOR);
        });

        it('returns FALLBACK_COLOR when track is not found', () => {
            Config._gpsTracks = [];

            expect(Colors.getGPSTrackColor('unknown')).toBe(Colors.FALLBACK_COLOR);
        });

        it('caches the result when a real color is found', () => {
            Config._gpsTracks = [{ id: 't-1', color: '#377eb8' }];

            expect(Colors.getGPSTrackColor('t-1')).toBe('#377eb8');
            Config._gpsTracks = [{ id: 't-1', color: '#123456' }];
            expect(Colors.getGPSTrackColor('t-1')).toBe('#377eb8');
        });

        it('does NOT cache fallback — retries on next call', () => {
            Config._gpsTracks = [];
            expect(Colors.getGPSTrackColor('t-1')).toBe(Colors.FALLBACK_COLOR);

            Config._gpsTracks = [{ id: 't-1', color: '#d95f02' }];
            expect(Colors.getGPSTrackColor('t-1')).toBe('#d95f02');
        });
    });

    describe('getDepthPaint', () => {
        it('returns DEPTH_NONE for null domain', () => {
            expect(Colors.getDepthPaint(null)).toBe(DEFAULTS.COLORS.DEPTH_NONE);
        });

        it('returns DEPTH_NONE for undefined domain', () => {
            expect(Colors.getDepthPaint()).toBe(DEFAULTS.COLORS.DEPTH_NONE);
        });

        it('returns valid expression when max is zero (floored to 1e-9)', () => {
            // Math.max(1e-9, 0) = 1e-9, which is truthy, so it builds an expression
            const result = Colors.getDepthPaint({ max: 0 });
            expect(Array.isArray(result)).toBe(true);
            expect(result[0]).toBe('case');
        });

        it('returns interpolation expression for valid domain', () => {
            const result = Colors.getDepthPaint({ max: 100 });
            expect(Array.isArray(result)).toBe(true);
            expect(result[0]).toBe('case');
            const interpolation = (result as DepthPaint)[2];
            expect(interpolation).toContain(DEFAULTS.COLORS.DEPTH_SHALLOW);
            expect(interpolation).toContain(DEFAULTS.COLORS.DEPTH_DEEP);
        });

        it('uses correct midpoint for interpolation', () => {
            const result = Colors.getDepthPaint({ max: 200 });
            const interpolation = (result as DepthPaint)[2]; // the interpolation sub-expression
            expect(interpolation).toContain(0.5); // Midpoint of the normalized domain.
            expect(interpolation).toContain(1); // Maximum of the normalized domain.
        });

        it('returns valid expression for negative max via floor', () => {
            // Negative max -> Math.max(1e-9, -5) = 1e-9 which IS truthy,
            // so this actually returns a valid expression (documenting current behavior)
            const result = Colors.getDepthPaint({ max: -5 });
            expect(Array.isArray(result)).toBe(true);
        });

        it.each([10.06, 1e-12])('preserves a positive fixed maximum of %s in the gradient', maximum => {
            const interpolation = (Colors.getDepthPaint({ min: 0, max: maximum }) as DepthPaint)[2];
            expect(interpolation.slice(3)).toEqual([
                0, DEFAULTS.COLORS.DEPTH_SHALLOW,
                0.5, DEFAULTS.COLORS.DEPTH_MID,
                1, DEFAULTS.COLORS.DEPTH_DEEP,
            ]);
        });

        it('keeps interpolation stops distinct when a positive maximum has no representable midpoint', () => {
            const interpolation = (Colors.getDepthPaint({ min: 0, max: Number.MIN_VALUE }) as DepthPaint)[2];
            expect(interpolation.slice(3)).toEqual([
                0, DEFAULTS.COLORS.DEPTH_SHALLOW,
                0.5, DEFAULTS.COLORS.DEPTH_MID,
                1, DEFAULTS.COLORS.DEPTH_DEEP,
            ]);
        });
    });
});
