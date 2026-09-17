import { readFileSync } from 'node:fs';
import { DEFAULTS } from '../config.js';
import {
    changeDraft, createGeometryDraft, geometryFromVertices, geometryVertices,
    measureGeometry, restoreDraft, validateGeometry,
} from './geometry.js';

function rectangle(width, height = 0.01) {
    return { type: 'Polygon', coordinates: [[[0, 0], [width, 0], [width, height], [0, height], [0, 0]]] };
}

describe('GIS geometry contract', () => {
    const sharedCases = JSON.parse(readFileSync('speleodb/gis/tests/fixtures/gis_geometry_cases.json', 'utf8'));
    it.each(sharedCases)('matches the shared backend geometry fixture: $id', sample => {
        const result = validateGeometry(sample.geojson);
        expect(result.valid).toBe(sample.valid);
        expect(result.vertexCount).toBe(sample.vertex_count);
        expect(Math.abs(result.areaM2 - sample.area_m2)).toBeLessThanOrEqual(0.000001);
    });
    it('accepts one line or simple polygon', () => {
        for (const geometry of [
            { type: 'LineString', coordinates: [[-87.3, 20.1], [-87.299, 20.101]] },
            rectangle(0.01),
        ]) expect(validateGeometry(geometry).valid).toBe(true);
    });

    it.each([
        null,
        { type: 'Feature', geometry: { type: 'Point', coordinates: [0, 0] } },
        { type: 'FeatureCollection', features: [] },
        { type: 'MultiPoint', coordinates: [[0, 0]] },
        { type: 'GeometryCollection', geometries: [] },
        { type: 'Point', coordinates: [0, 0] },
        { type: 'LineString', coordinates: [[0, 0, 1], [0.01, 0.01]] },
        { type: 'LineString', coordinates: [['0', 0], [0.01, 0.01]] },
        { type: 'LineString', coordinates: [[true, 0], [0.01, 0.01]] },
        { type: 'LineString', coordinates: [[Infinity, 0], [0.01, 0.01]] },
        { type: 'LineString', coordinates: [[0, NaN], [0.01, 0.01]] },
        { type: 'LineString', coordinates: [[181, 0], [0.01, 0.01]] },
        { type: 'LineString', coordinates: [[0, -91], [0.01, 0.01]] },
        { type: 'LineString', coordinates: [[], [0.01, 0.01]] },
        { type: 'LineString', coordinates: null },
        { type: 'LineString', coordinates: [[0, 0]] },
        { type: 'Polygon', coordinates: [null] },
        { type: 'Polygon', coordinates: [[]] },
        { type: 'Polygon', coordinates: [[[0, 0], [0.01, 0], [0, 0.01]]] },
        { type: 'Polygon', coordinates: [rectangle(0.01).coordinates[0], rectangle(0.001).coordinates[0]] },
    ])('rejects unsupported or malformed coordinates: %j', geometry => {
        expect(validateGeometry(geometry).valid).toBe(false);
    });

    it('computes coordinates rather than trusting a supplied bounding box', () => {
        const large = { ...rectangle(1, 1), bbox: [0, 0, 0.001, 0.001] };
        expect(validateGeometry(large).valid).toBe(false);
        expect(measureGeometry(large).areaKm2).toBeGreaterThan(DEFAULTS.GIS_GEOMETRY.MAX_AREA_M2 / 1_000_000);
    });

    it('uses spherical bbox area, including for lines, rather than polygon area', () => {
        const line = { type: 'LineString', coordinates: [[0, 0], [0.01, 0.01]] };
        const box = rectangle(0.01);
        expect(measureGeometry(line).areaM2).toBeCloseTo(measureGeometry(box).areaM2, 8);
        expect(measureGeometry(box).areaM2).toBeCloseTo(1236434.580536857, 4);
        expect(measureGeometry({ type: 'LineString', coordinates: [[0, 0], [1, 0]] }).areaM2).toBe(0);
    });

    it('accepts exactly the limit and rejects any computed excess', () => {
        const radians = Math.PI / 180;
        const height = 0.01;
        const width = DEFAULTS.GIS_GEOMETRY.MAX_AREA_M2
            / (DEFAULTS.GIS_GEOMETRY.EARTH_RADIUS_M ** 2 * radians * Math.sin(height * radians));
        expect(validateGeometry(rectangle(width * (1 - Number.EPSILON))).valid).toBe(true);
        expect(validateGeometry(rectangle(width * (1 + Number.EPSILON * 2))).valid).toBe(false);
    });

    it('counts a polygon closing coordinate only once and enforces 100 editable vertices', () => {
        const ring = Array.from({ length: 100 }, (_, index) => {
            const angle = index * Math.PI * 2 / 100;
            return [Math.cos(angle) * 0.001, Math.sin(angle) * 0.001];
        });
        const accepted = { type: 'Polygon', coordinates: [[...ring, ring[0]]] };
        expect(validateGeometry(accepted)).toMatchObject({ valid: true, vertexCount: 100 });
        const extra = [...ring, [0.001, -0.00001]];
        expect(validateGeometry({ type: 'Polygon', coordinates: [[...extra, extra[0]]] }).valid).toBe(false);
    });

    it('rejects dateline crossings for line segments and closing polygon edges', () => {
        expect(validateGeometry({ type: 'LineString', coordinates: [[179.999, 1], [-179.999, 1.001]] }).error).toMatch(/antimeridian/);
        expect(validateGeometry({ type: 'Polygon', coordinates: [[[179, 0], [0, 0], [-179, 0.001], [179, 0]]] }).error).toMatch(/antimeridian/);
    });

    it.each([
        [[0, 0], [0.01, 0.01], [0, 0.01], [0.01, 0], [0, 0]],
        [[0, 0], [0.01, 0], [0.02, 0], [0, 0]],
        [[0, 0], [0.01, 0], [0.01, 0.01], [0.01, 0], [0, 0]],
        [[0, 0], [0.02, 0], [0.01, 0], [0.01, 0.01], [0, 0]],
    ])('rejects degenerate/self-intersecting polygon %j', (...coordinates) => {
        expect(validateGeometry({ type: 'Polygon', coordinates: [coordinates] }).valid).toBe(false);
    });

    it('rejects repeated consecutive line coordinates', () => {
        expect(validateGeometry({ type: 'LineString', coordinates: [[1, 1], [1, 1]] }).valid).toBe(false);
    });
});

describe('geometry draft commands', () => {
    it('copies input, edits without changing it, and derives polygon closure', () => {
        const original = rectangle(0.01);
        const before = structuredClone(original);
        const draft = createGeometryDraft(original);
        expect(draft.vertices).toHaveLength(4);
        const vertices = geometryVertices(original);
        vertices[0] = [0.001, 0.001];
        changeDraft(draft, vertices);
        const result = geometryFromVertices('Polygon', draft.vertices);
        expect(result.coordinates[0][0]).toEqual(result.coordinates[0].at(-1));
        expect(original).toEqual(before);
    });

    it('supports undo/redo through incomplete draft geometry and clears a forked redo stack', () => {
        const draft = createGeometryDraft();
        changeDraft(draft, [[0, 0]]);
        changeDraft(draft, [[0, 0], [0.01, 0.01]]);
        expect(restoreDraft(draft, 'undo')).toBe(true);
        expect(draft.vertices).toEqual([[0, 0]]);
        expect(restoreDraft(draft, 'redo')).toBe(true);
        expect(draft.vertices).toHaveLength(2);
        restoreDraft(draft, 'undo');
        changeDraft(draft, [[0, 0], [0.02, 0.02]]);
        expect(draft.redo).toHaveLength(0);
        expect(changeDraft(draft, [[0, 0], [0.02, 0.02]])).toBe(false);
    });
});
