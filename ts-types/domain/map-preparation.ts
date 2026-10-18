import type { JSONValue } from './json.ts';
import type { DepthDomain } from './map-display.ts';
import type { CoordinateBounds } from '@speleodb/map-core/coordinate-bounds';

import type { PreparationOptions } from '@speleodb/map-core/preparation';
export type { PreparationOptions } from '@speleodb/map-core/preparation';
export interface BoundsPreparationOptions extends PreparationOptions { wrapLongitude?: boolean }
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
    boundsCoordinates: CoordinateBounds | null;
}
