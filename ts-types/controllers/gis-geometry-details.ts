import type { EditableGeometry, GeometryValidation } from '../domain/geometry-editor.ts';

export interface GISGeometryDetailsContext {
    formId: string;
    endpoint: string;
    revision: number;
    canWrite: boolean;
}
export interface GISGeometryDetailsResponse {
    revision: number;
    name: string;
    color: string;
    geojson: EditableGeometry;
}
/** Parse failures have no measurement; invalid parsed values retain their identity. */
export interface ParsedGeometryText extends Partial<GeometryValidation> {
    valid: boolean;
    error: string;
    geometry?: EditableGeometry;
}
