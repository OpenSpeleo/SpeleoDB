import type { EntityId } from './identifiers.ts';
import type { JSONValue } from './json.ts';
import type { ViewerFeature } from './map-geometry.ts';
import type { PreparedSnapPoint } from './map-preparation.ts';

export interface SnapIndicatorMap {
    getContainer(): HTMLElement;
    project(coordinates: readonly number[]): { x: number; y: number };
}
export interface SnapResult {
    coordinates: [number, number];
    lineName: JSONValue;
    pointType: 'start' | 'end' | null;
    distance: number;
    snapped: boolean;
    projectId: string | null;
}
export type NearestSnapResult =
    | { snapped: false; coordinates: [number, number]; distance: number }
    | (Omit<SnapResult, 'coordinates' | 'snapped'> & { snapped: true; coordinates: [number, number] | null });
export interface SnapInfo {
    snapRadius: number;
    totalSnapPoints: number;
    projectsWithSnapPoints: number;
    snapPointsPerProject: Record<string, number>;
}
export interface GeometryFacade {
    calculateDistanceInMeters(coordinates1: readonly number[], coordinates2: readonly number[]): number;
    cachePreparedSnapPoints(projectId: EntityId, snapPoints: PreparedSnapPoint[]): void;
    cacheLineFeatures(projectId: EntityId, geojsonData: { features?: ViewerFeature[] } | null | undefined): void;
    findMagneticSnapPoint(coordinates: readonly number[], projectId?: EntityId | null): SnapResult;
    findProjectForFeature(feature: { layer?: { id?: string } }, map: unknown, allProjectLayers: Map<EntityId, string[]>): EntityId | null;
    snapIndicatorEl: HTMLDivElement | null;
    showSnapIndicator(coordinates: readonly number[], map: SnapIndicatorMap, isSnapped?: boolean): void;
    hideSnapIndicator(): void;
    getSnapRadius(): number;
    findNearestSnapPointWithinRadius(coordinates: readonly number[], radiusMeters?: number): NearestSnapResult;
    getSnapInfo(): SnapInfo;
    setSnapRadius(radiusInMeters: unknown): number;
}
