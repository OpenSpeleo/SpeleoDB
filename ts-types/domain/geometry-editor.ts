import type { LineString, Polygon } from 'geojson';

import type { Position2D } from '@speleodb/map-core/geometry';
export type { Position2D, GeometryMeasurement, GeometryValidation } from '@speleodb/map-core/geometry';

export type EditableGeometryType = 'LineString' | 'Polygon';
export type EditableGeometry = LineString | Polygon;
export interface GeometryDraftSnapshot {
    type: EditableGeometryType;
    vertices: Position2D[];
}
export interface GeometryDraft extends GeometryDraftSnapshot {
    undo: GeometryDraftSnapshot[];
    redo: GeometryDraftSnapshot[];
}
