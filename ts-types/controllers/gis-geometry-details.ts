import type { EditableGeometry, GeometryValidation } from '../domain/geometry-editor.ts';

export interface GISGeometryDetailsContext {
    formId: string;
    geometryId: string;
    revision: number;
    canWrite: boolean;
}
/** Parse failures have no measurement; invalid parsed values retain their identity. */
export interface ParsedGeometryText extends Partial<GeometryValidation> {
    valid: boolean;
    error: string;
    geometry?: EditableGeometry;
}
