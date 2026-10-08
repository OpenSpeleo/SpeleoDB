import type { LineString, Polygon } from 'geojson';

export type Position2D = [number, number];
export type EditableGeometryType = 'LineString' | 'Polygon';
export type EditableGeometry = LineString | Polygon;
export interface GeometryMeasurement {
    areaM2: number;
    areaKm2: number;
    vertexCount: number;
    bounds: [Position2D, Position2D] | null;
}
export interface GeometryValidation extends GeometryMeasurement {
    valid: boolean;
    error: string;
}
export interface GeometryDraftSnapshot {
    type: EditableGeometryType;
    vertices: Position2D[];
}
export interface GeometryDraft extends GeometryDraftSnapshot {
    undo: GeometryDraftSnapshot[];
    redo: GeometryDraftSnapshot[];
}
