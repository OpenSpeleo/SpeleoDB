import type { EditableGeometry, EditableGeometryType, GeometryDraft, Position2D } from '../../../../../../ts-types/domain/geometry-editor.ts';
import { DEFAULTS } from '../config.ts';
import { geometryVertices } from '@speleodb/map-core/geometry';
export { geometryVertices, measureGeometry, validateGeometry } from '@speleodb/map-core/geometry';

export function geometryFromVertices(type: EditableGeometryType, vertices: readonly Position2D[]): EditableGeometry {
    const coordinates = vertices.map(coordinate => [...coordinate] as Position2D);
    if (type === 'Polygon') return { type, coordinates: [coordinates.length ? [...coordinates, [...coordinates[0]!]] : []] };
    return { type, coordinates };
}

/** Pure bounded draft history; callers group a drag into a single replaceVertices command. */
export function createGeometryDraft(geometry: EditableGeometry | null = null): GeometryDraft {
    return {
        type: geometry?.type || 'LineString',
        vertices: geometryVertices(geometry),
        undo: [],
        redo: [],
    };
}

export function changeDraft(draft: GeometryDraft, vertices: readonly Position2D[], type = draft.type) {
    if (JSON.stringify([draft.type, draft.vertices]) === JSON.stringify([type, vertices])) return false;
    draft.undo.push({ type: draft.type, vertices: draft.vertices.map(coordinate => [...coordinate]) });
    if (draft.undo.length > DEFAULTS.GIS_GEOMETRY.MAX_HISTORY) draft.undo.shift();
    draft.redo = [];
    draft.type = type;
    draft.vertices = vertices.map(coordinate => [...coordinate]);
    return true;
}

export function restoreDraft(draft: GeometryDraft, direction: 'undo' | 'redo') {
    const source = direction === 'undo' ? draft.undo : draft.redo;
    const target = direction === 'undo' ? draft.redo : draft.undo;
    const previous = source.pop();
    if (!previous) return false;
    target.push({ type: draft.type, vertices: draft.vertices.map(coordinate => [...coordinate]) });
    draft.type = previous.type;
    draft.vertices = previous.vertices.map(coordinate => [...coordinate]);
    return true;
}
