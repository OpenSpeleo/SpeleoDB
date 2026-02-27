vi.mock('../state.js', () => ({ State: {} }));
vi.mock('./layers.js', () => ({
    Layers: { isProjectVisible: vi.fn(() => true) }
}));

function makeLineGeoJSON(lines) {
    return {
        features: lines.map((line) => ({
            type: 'Feature',
            geometry: { type: 'LineString', coordinates: line.coords },
            properties: line.name ? { section_name: line.name } : {}
        }))
    };
}

describe('Geometry', () => {
    let Geo;
    let mockLayers;

    beforeEach(async () => {
        vi.resetModules();
        const mod = await import('./geometry.js');
        Geo = mod.Geometry;
        const layersMod = await import('./layers.js');
        mockLayers = layersMod.Layers;
        // Ensure visibility mock is reset to default after tests that override it
        mockLayers.isProjectVisible.mockImplementation(() => true);
    });

    afterEach(() => {
        const el = document.getElementById('snap-indicator');
        if (el) el.remove();
        vi.restoreAllMocks();
    });

    // ── calculateDistanceInMeters ──────────────────────────────────────

    describe('calculateDistanceInMeters', () => {
        it('returns 0 for identical points', () => {
            expect(Geo.calculateDistanceInMeters([0, 0], [0, 0])).toBe(0);
        });

        it('computes ~111 km per degree of latitude at the equator', () => {
            const d = Geo.calculateDistanceInMeters([0, 0], [0, 1]);
            expect(d).toBeCloseTo(111_195, -2);
        });

        it('is symmetric', () => {
            const berlin = [13.405, 52.52];
            const paris = [2.3522, 48.8566];
            expect(Geo.calculateDistanceInMeters(berlin, paris))
                .toBeCloseTo(Geo.calculateDistanceInMeters(paris, berlin), 6);
        });

        it('returns roughly correct distance for NYC to London (~5570 km)', () => {
            const nyc = [-74.006, 40.7128];
            const london = [-0.1278, 51.5074];
            const d = Geo.calculateDistanceInMeters(nyc, london);
            expect(d).toBeGreaterThan(5_500_000);
            expect(d).toBeLessThan(5_600_000);
        });
    });

    // ── cacheLineFeatures ──────────────────────────────────────────────

    describe('cacheLineFeatures', () => {
        it('caches start and end points from LineString features', () => {
            Geo.cacheLineFeatures('proj-1', makeLineGeoJSON([
                { coords: [[0, 0], [1, 1]], name: 'TestLine' }
            ]));
            const info = Geo.getSnapInfo();
            expect(info.totalSnapPoints).toBe(2);
            expect(info.snapPointsPerProject['proj-1']).toBe(2);
        });

        it('ignores null, undefined, and empty geojsonData', () => {
            Geo.cacheLineFeatures('p-null', null);
            Geo.cacheLineFeatures('p-undef', undefined);
            Geo.cacheLineFeatures('p-empty', {});
            expect(Geo.getSnapInfo().totalSnapPoints).toBe(0);
        });

        it('skips lines with fewer than 2 coordinates', () => {
            Geo.cacheLineFeatures('p-short', makeLineGeoJSON([
                { coords: [[5, 5]], name: 'Short' }
            ]));
            expect(Geo.getSnapInfo().snapPointsPerProject['p-short']).toBe(0);
        });

        it('ignores non-LineString features', () => {
            Geo.cacheLineFeatures('p-point', {
                features: [{
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: [0, 0] },
                    properties: {}
                }]
            });
            expect(Geo.getSnapInfo().projectsWithSnapPoints).toBe(0);
        });

        it('extracts endpoints from multiple LineStrings', () => {
            Geo.cacheLineFeatures('p-multi', makeLineGeoJSON([
                { coords: [[0, 0], [1, 1]], name: 'A' },
                { coords: [[2, 2], [3, 3], [4, 4]], name: 'B' }
            ]));
            expect(Geo.getSnapInfo().totalSnapPoints).toBe(4);
        });

        it('falls back to properties.name when section_name is absent', () => {
            Geo.cacheLineFeatures('p-fb', {
                features: [{
                    type: 'Feature',
                    geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] },
                    properties: { name: 'Fallback' }
                }]
            });
            const snap = Geo.findMagneticSnapPoint([0, 0], 'p-fb');
            expect(snap.lineName).toBe('Fallback');
        });

        it('converts projectId to string for cache key', () => {
            Geo.cacheLineFeatures(42, makeLineGeoJSON([
                { coords: [[0, 0], [1, 1]] }
            ]));
            expect(Geo.getSnapInfo().snapPointsPerProject['42']).toBe(2);
        });
    });

    // ── findMagneticSnapPoint ──────────────────────────────────────────

    describe('findMagneticSnapPoint', () => {
        beforeEach(() => {
            Geo.cacheLineFeatures('snap-proj', makeLineGeoJSON([
                { coords: [[10, 20], [10.01, 20.01]], name: 'Line A' }
            ]));
        });

        it('snaps to exact start point with zero distance', () => {
            const result = Geo.findMagneticSnapPoint([10, 20], 'snap-proj');
            expect(result.snapped).toBe(true);
            expect(result.coordinates).toEqual([10, 20]);
            expect(result.distance).toBe(0);
            expect(result.lineName).toBe('Line A');
            expect(result.pointType).toBe('start');
            expect(result.projectId).toBe('snap-proj');
        });

        it('does not snap when far from all points', () => {
            const result = Geo.findMagneticSnapPoint([50, 50], 'snap-proj');
            expect(result.snapped).toBe(false);
            expect(result.lineName).toBeNull();
            expect(result.projectId).toBeNull();
        });

        it('filters by projectId when provided', () => {
            Geo.cacheLineFeatures('other-proj', makeLineGeoJSON([
                { coords: [[10, 20], [10.001, 20.001]], name: 'Other' }
            ]));
            const result = Geo.findMagneticSnapPoint([10, 20], 'other-proj');
            expect(result.snapped).toBe(true);
            expect(result.projectId).toBe('other-proj');
        });

        it('skips hidden projects', () => {
            mockLayers.isProjectVisible.mockReturnValue(false);
            const result = Geo.findMagneticSnapPoint([10, 20]);
            expect(result.snapped).toBe(false);
        });

        it('returns unsnapped with target coordinates for non-existent project', () => {
            const result = Geo.findMagneticSnapPoint([10, 20], 'nonexistent');
            expect(result.snapped).toBe(false);
            expect(result.coordinates).toEqual([10, 20]);
        });

        it('searches all projects when projectId is null', () => {
            const result = Geo.findMagneticSnapPoint([10, 20]);
            expect(result.snapped).toBe(true);
            expect(result.projectId).toBe('snap-proj');
        });
    });

    // ── findNearestSnapPointWithinRadius ────────────────────────────────

    describe('findNearestSnapPointWithinRadius', () => {
        beforeEach(() => {
            Geo.cacheLineFeatures('near-proj', makeLineGeoJSON([
                { coords: [[0, 0], [0.001, 0.001]], name: 'Near' }
            ]));
        });

        it('snaps to exact point within radius', () => {
            const result = Geo.findNearestSnapPointWithinRadius([0, 0], 100);
            expect(result.snapped).toBe(true);
            expect(result.coordinates).toEqual([0, 0]);
            expect(result.distance).toBe(0);
        });

        it('does not snap when outside given radius', () => {
            const result = Geo.findNearestSnapPointWithinRadius([1, 1], 10);
            expect(result.snapped).toBe(false);
        });

        it('snaps with sufficiently large custom radius', () => {
            const result = Geo.findNearestSnapPointWithinRadius([0.001, 0], 200);
            expect(result.snapped).toBe(true);
        });

        it('skips hidden projects', () => {
            mockLayers.isProjectVisible.mockReturnValue(false);
            const result = Geo.findNearestSnapPointWithinRadius([0, 0], 100);
            expect(result.snapped).toBe(false);
        });

        it('returns target coordinates when not snapped', () => {
            const result = Geo.findNearestSnapPointWithinRadius([99, 99], 1);
            expect(result.snapped).toBe(false);
            expect(result.coordinates).toEqual([99, 99]);
        });

        it('includes lineName, pointType, and projectId when snapped', () => {
            const result = Geo.findNearestSnapPointWithinRadius([0, 0], 100);
            expect(result.lineName).toBe('Near');
            expect(result.pointType).toBe('start');
            expect(result.projectId).toBe('near-proj');
        });
    });

    // ── showSnapIndicator ──────────────────────────────────────────────

    describe('showSnapIndicator', () => {
        let mockMap;
        let mapContainer;

        beforeEach(() => {
            mapContainer = document.createElement('div');
            mapContainer.id = 'map';
            document.body.appendChild(mapContainer);
            mockMap = {
                project: vi.fn(() => ({ x: 100, y: 200 })),
                getContainer: vi.fn(() => mapContainer),
            };
        });

        afterEach(() => {
            mapContainer.remove();
        });

        it('creates and appends indicator element to map container', () => {
            Geo.showSnapIndicator([0, 0], mockMap);
            expect(Geo.snapIndicatorEl).not.toBeNull();
            expect(Geo.snapIndicatorEl.id).toBe('snap-indicator');
            expect(mapContainer.contains(Geo.snapIndicatorEl)).toBe(true);
        });

        it('never appends indicator to document.body (would cause offset bug)', () => {
            Geo.showSnapIndicator([0, 0], mockMap);
            const bodyChildren = Array.from(document.body.children);
            const directlyOnBody = bodyChildren.some(el => el.id === 'snap-indicator');
            expect(directlyOnBody).toBe(false);
        });

        it('projects coordinates via the map', () => {
            mockMap.project.mockReturnValue({ x: 150, y: 250 });
            Geo.showSnapIndicator([5, 10], mockMap);
            expect(mockMap.project).toHaveBeenCalledWith([5, 10]);
        });

        // jsdom's cssstyle cannot parse the full cssText (box-shadow + rgba
        // combination causes it to discard everything). Bypass by pre-setting
        // snapIndicatorEl to a stub so we capture the raw cssText string.

        it('uses larger size and green border when snapped', () => {
            let captured = '';
            Geo.snapIndicatorEl = { style: { set cssText(v) { captured = v; } } };
            Geo.showSnapIndicator([0, 0], mockMap, true);
            expect(captured).toContain('width: 20px');
            expect(captured).toContain('height: 20px');
            expect(captured).toContain('#10b981');
        });

        it('uses smaller size and red border when not snapped', () => {
            let captured = '';
            Geo.snapIndicatorEl = { style: { set cssText(v) { captured = v; } } };
            Geo.showSnapIndicator([0, 0], mockMap, false);
            expect(captured).toContain('width: 16px');
            expect(captured).toContain('height: 16px');
            expect(captured).toContain('#ef4444');
        });

        it('positions indicator at projected coordinates', () => {
            let captured = '';
            Geo.snapIndicatorEl = { style: { set cssText(v) { captured = v; } } };
            mockMap.project.mockReturnValue({ x: 150, y: 250 });
            Geo.showSnapIndicator([5, 10], mockMap);
            expect(captured).toContain('left: 150px');
            expect(captured).toContain('top: 250px');
        });

        it('reuses existing element on subsequent calls', () => {
            Geo.showSnapIndicator([0, 0], mockMap);
            Geo.showSnapIndicator([1, 1], mockMap);
            expect(document.querySelectorAll('#snap-indicator').length).toBe(1);
        });
    });

    // ── hideSnapIndicator ──────────────────────────────────────────────

    describe('hideSnapIndicator', () => {
        it('sets display:none on existing indicator', () => {
            const container = document.createElement('div');
            document.body.appendChild(container);
            const mockMap = { project: vi.fn(() => ({ x: 0, y: 0 })), getContainer: () => container };
            Geo.showSnapIndicator([0, 0], mockMap);
            Geo.hideSnapIndicator();
            expect(Geo.snapIndicatorEl.style.display).toBe('none');
        });

        it('does not throw when no indicator exists', () => {
            expect(() => Geo.hideSnapIndicator()).not.toThrow();
        });
    });

    // ── setSnapRadius / getSnapRadius ──────────────────────────────────

    describe('setSnapRadius / getSnapRadius', () => {
        it('returns default radius of 10', () => {
            expect(Geo.getSnapRadius()).toBe(10);
        });

        it('sets and returns new radius', () => {
            expect(Geo.setSnapRadius(25)).toBe(25);
            expect(Geo.getSnapRadius()).toBe(25);
        });

        it('clamps to minimum of 1', () => {
            expect(Geo.setSnapRadius(0.5)).toBe(1);
            expect(Geo.setSnapRadius(-5)).toBe(1);
        });

        it('defaults to 10 for NaN input', () => {
            expect(Geo.setSnapRadius('abc')).toBe(10);
            expect(Geo.setSnapRadius(NaN)).toBe(10);
        });

        it('defaults to 10 for null, undefined, and zero', () => {
            expect(Geo.setSnapRadius(null)).toBe(10);
            expect(Geo.setSnapRadius(undefined)).toBe(10);
            expect(Geo.setSnapRadius(0)).toBe(10);
        });
    });

    // ── getSnapInfo ────────────────────────────────────────────────────

    describe('getSnapInfo', () => {
        it('returns empty info when no data is cached', () => {
            expect(Geo.getSnapInfo()).toEqual({
                snapRadius: 10,
                totalSnapPoints: 0,
                projectsWithSnapPoints: 0,
                snapPointsPerProject: {}
            });
        });

        it('reflects cached data after cacheLineFeatures', () => {
            Geo.cacheLineFeatures('info-proj', makeLineGeoJSON([
                { coords: [[0, 0], [1, 1]] }
            ]));
            const info = Geo.getSnapInfo();
            expect(info.totalSnapPoints).toBe(2);
            expect(info.projectsWithSnapPoints).toBe(1);
            expect(info.snapPointsPerProject['info-proj']).toBe(2);
        });

        it('reflects updated snap radius', () => {
            Geo.setSnapRadius(50);
            expect(Geo.getSnapInfo().snapRadius).toBe(50);
        });
    });

    // ── findProjectForFeature ──────────────────────────────────────────

    describe('findProjectForFeature', () => {
        it('extracts UUID from station layer ID', () => {
            const feature = { layer: { id: 'stations-abc-12345678-1234-1234-1234-123456789012' } };
            expect(Geo.findProjectForFeature(feature, null, new Map()))
                .toBe('12345678-1234-1234-1234-123456789012');
        });

        it('returns null when station layer has no UUID', () => {
            const feature = { layer: { id: 'stations-no-uuid' } };
            expect(Geo.findProjectForFeature(feature, null, new Map())).toBeNull();
        });

        it('matches feature to project via allProjectLayers map', () => {
            const feature = { layer: { id: 'line-layer-1' } };
            const layers = new Map([['proj-1', ['line-layer-1', 'fill-layer-1']]]);
            expect(Geo.findProjectForFeature(feature, null, layers)).toBe('proj-1');
        });

        it('returns null for unrecognized layer', () => {
            const feature = { layer: { id: 'unknown' } };
            expect(Geo.findProjectForFeature(feature, null, new Map())).toBeNull();
        });

        it('returns null when feature has no layer', () => {
            expect(Geo.findProjectForFeature({}, null, new Map())).toBeNull();
        });

        it('returns null when layer.id is missing', () => {
            expect(Geo.findProjectForFeature({ layer: {} }, null, new Map())).toBeNull();
        });
    });
});
