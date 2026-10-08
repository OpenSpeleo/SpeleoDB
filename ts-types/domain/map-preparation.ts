import type { BBox } from 'geojson';
import type { JSONValue } from './json.ts';
import type { DepthDomain } from './map-display.ts';
import type { Coordinate2D } from './map-geometry.ts';

import type { PreparationOptions } from '@speleodb/map-core/preparation';
export type { PreparationOptions } from '@speleodb/map-core/preparation';
export interface BoundsPreparationOptions extends PreparationOptions { wrapLongitude?: boolean }
export type PreparedBounds = [Coordinate2D, Coordinate2D];
export interface PreparationBounds {
    bbox: PreparedBounds | null;
    wrapLongitude: boolean;
    longitudes: number[];
    west: number;
    east: number;
    south: number;
    north: number;
}
export interface BoundedData { bbox?: BBox | undefined }
export interface PreparedSnapPoint {
    coordinates: [number, number];
    lineName: JSONValue;
    type: 'start' | 'end';
    lineIndex: number;
}
export interface PreparedProject<Data> {
    data: Data;
    domain: DepthDomain | null;
    snapPoints: PreparedSnapPoint[];
    boundsCoordinates: PreparedBounds | null;
}
