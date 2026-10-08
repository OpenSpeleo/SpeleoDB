import type { Feature, MultiLineString, Point } from 'geojson';
import type { EntityId } from './identifiers.ts';
import type { Coordinate2D } from './map-geometry.ts';
import type { Position2D } from './geometry-editor.ts';

export interface ScreenPoint { x: number; y: number }
export interface LongitudeLatitude { lng: number; lat: number }
export interface MeasurementPickingMap {
    isPointOnSurface?(point: ScreenPoint): boolean;
    unproject(point: ScreenPoint): LongitudeLatitude | null;
    project(coordinate: LongitudeLatitude): ScreenPoint | null;
}
export interface MeasurementRecord {
    id: EntityId;
    start: Position2D;
    end: Position2D;
    distanceMeters: number;
}
export interface MeasurementDraft {
    id?: EntityId;
    start: Coordinate2D;
    end: null;
}
export interface MeasurementProperties {
    measurementId: EntityId | undefined;
    priority: number;
    role: 'endpoint' | 'line' | 'label';
    label?: string;
}
export type MeasurementFeature = Feature<Point | MultiLineString, MeasurementProperties>;
