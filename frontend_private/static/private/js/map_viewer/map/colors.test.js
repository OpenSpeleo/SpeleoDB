import { Colors } from './colors.js';
import { Config, DEFAULTS } from '../config.js';

vi.mock('../config.js', () => ({
    Config: {
        getProjectById: vi.fn(),
        getGPSTrackById: vi.fn(),
    },
    DEFAULTS: Object.freeze({
        COLORS: {
            FALLBACK: '#94a3b8',
            DEPTH_NONE: '#999999',
            DEPTH_SHALLOW: '#4575b4',
            DEPTH_MID: '#e6f598',
            DEPTH_DEEP: '#d73027',
        },
    }),
}));

describe('Colors', () => {
    beforeEach(() => {
        Colors.resetColorMap();
        Colors.resetGPSTrackColorMap();
        vi.clearAllMocks();
    });

    describe('getProjectColor', () => {
        it('returns the stored color from the project model', () => {
            Config.getProjectById.mockReturnValue({ id: 'p-1', color: '#ff5500' });

            expect(Colors.getProjectColor('p-1')).toBe('#ff5500');
            expect(Config.getProjectById).toHaveBeenCalledWith('p-1');
        });

        it('returns FALLBACK_COLOR when project has no color', () => {
            Config.getProjectById.mockReturnValue({ id: 'p-1' });

            expect(Colors.getProjectColor('p-1')).toBe(Colors.FALLBACK_COLOR);
        });

        it('returns FALLBACK_COLOR when project is not found', () => {
            Config.getProjectById.mockReturnValue(null);

            expect(Colors.getProjectColor('unknown')).toBe(Colors.FALLBACK_COLOR);
        });

        it('caches the result when a real color is found', () => {
            Config.getProjectById.mockReturnValue({ id: 'p-1', color: '#ff5500' });

            Colors.getProjectColor('p-1');
            Colors.getProjectColor('p-1');

            expect(Config.getProjectById).toHaveBeenCalledTimes(1);
        });

        it('does NOT cache fallback — retries on next call', () => {
            // First call: project not found yet
            Config.getProjectById.mockReturnValue(null);
            expect(Colors.getProjectColor('p-1')).toBe(Colors.FALLBACK_COLOR);

            // Second call: project now available with color
            Config.getProjectById.mockReturnValue({ id: 'p-1', color: '#e41a1c' });
            expect(Colors.getProjectColor('p-1')).toBe('#e41a1c');

            // Should have queried Config twice (no stale cache)
            expect(Config.getProjectById).toHaveBeenCalledTimes(2);
        });

        it('does NOT cache when project exists but has no color field', () => {
            Config.getProjectById.mockReturnValue({ id: 'p-1' });
            expect(Colors.getProjectColor('p-1')).toBe(Colors.FALLBACK_COLOR);

            // Color becomes available later
            Config.getProjectById.mockReturnValue({ id: 'p-1', color: '#377eb8' });
            expect(Colors.getProjectColor('p-1')).toBe('#377eb8');

            expect(Config.getProjectById).toHaveBeenCalledTimes(2);
        });

        it('simulates public viewer timing: called before setPublicProjects, then after', () => {
            // Before Config is populated
            Config.getProjectById.mockReturnValue(null);
            expect(Colors.getProjectColor('pub-1')).toBe(Colors.FALLBACK_COLOR);

            // After setPublicProjects populates Config
            Config.getProjectById.mockReturnValue({ id: 'pub-1', color: '#4daf4a' });
            expect(Colors.getProjectColor('pub-1')).toBe('#4daf4a');

            // Third call hits the cache now
            Config.getProjectById.mockReturnValue(null); // wouldn't matter
            expect(Colors.getProjectColor('pub-1')).toBe('#4daf4a');

            expect(Config.getProjectById).toHaveBeenCalledTimes(2);
        });
    });

    describe('getGPSTrackColor', () => {
        it('returns the stored color from the track model', () => {
            Config.getGPSTrackById.mockReturnValue({ id: 't-1', color: '#377eb8' });

            expect(Colors.getGPSTrackColor('t-1')).toBe('#377eb8');
            expect(Config.getGPSTrackById).toHaveBeenCalledWith('t-1');
        });

        it('returns FALLBACK_COLOR when track has no color', () => {
            Config.getGPSTrackById.mockReturnValue({ id: 't-1' });

            expect(Colors.getGPSTrackColor('t-1')).toBe(Colors.FALLBACK_COLOR);
        });

        it('returns FALLBACK_COLOR when track is not found', () => {
            Config.getGPSTrackById.mockReturnValue(null);

            expect(Colors.getGPSTrackColor('unknown')).toBe(Colors.FALLBACK_COLOR);
        });

        it('caches the result when a real color is found', () => {
            Config.getGPSTrackById.mockReturnValue({ id: 't-1', color: '#377eb8' });

            Colors.getGPSTrackColor('t-1');
            Colors.getGPSTrackColor('t-1');

            expect(Config.getGPSTrackById).toHaveBeenCalledTimes(1);
        });

        it('does NOT cache fallback — retries on next call', () => {
            Config.getGPSTrackById.mockReturnValue(null);
            expect(Colors.getGPSTrackColor('t-1')).toBe(Colors.FALLBACK_COLOR);

            Config.getGPSTrackById.mockReturnValue({ id: 't-1', color: '#d95f02' });
            expect(Colors.getGPSTrackColor('t-1')).toBe('#d95f02');

            expect(Config.getGPSTrackById).toHaveBeenCalledTimes(2);
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
            const interpolation = result[2];
            expect(interpolation).toContain(DEFAULTS.COLORS.DEPTH_SHALLOW);
            expect(interpolation).toContain(DEFAULTS.COLORS.DEPTH_DEEP);
        });

        it('uses correct midpoint for interpolation', () => {
            const result = Colors.getDepthPaint({ max: 200 });
            const interpolation = result[2]; // the interpolation sub-expression
            expect(interpolation).toContain(100); // midDepth = 200/2
            expect(interpolation).toContain(200); // maxDepth
        });

        it('returns valid expression for negative max via floor', () => {
            // Negative max -> Math.max(1e-9, -5) = 1e-9 which IS truthy,
            // so this actually returns a valid expression (documenting current behavior)
            const result = Colors.getDepthPaint({ max: -5 });
            expect(Array.isArray(result)).toBe(true);
        });
    });
});
