import type { Polygon } from 'geojson';
import { readFileSync } from 'node:fs';
import {
    changeDraft, createGeometryDraft, geometryFromVertices, geometryVertices,
    restoreDraft, validateGeometry,
} from './geometry.ts';

function rectangle(width: number, height = 0.01): Polygon {
    return { type: 'Polygon', coordinates: [[[0, 0], [width, 0], [width, height], [0, height], [0, 0]]] };
}

describe('GIS geometry contract', () => {
    const sharedCases = JSON.parse(readFileSync('speleodb/gis/tests/fixtures/gis_geometry_cases.json', 'utf8')) as { id: string; geojson: unknown; valid: boolean; vertex_count: number; area_m2: number }[];
    it.each(sharedCases)('matches the shared backend geometry fixture: $id', sample => {
        const result = validateGeometry(sample.geojson);
        expect(result.valid).toBe(sample.valid);
        expect(result.vertexCount).toBe(sample.vertex_count);
        expect(Math.abs(result.areaM2 - sample.area_m2)).toBeLessThanOrEqual(0.000001);
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
        expect(result.coordinates[0]![0]).toEqual((result as Polygon).coordinates[0]!.at(-1));
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
