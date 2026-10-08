import type { Feature, FeatureCollection, Point, Position } from 'geojson';
import type { EntityId } from './identifiers.ts';
import type { StationRecord, LeadRecord } from './station-records.ts';
import type { LandmarkRecord, LandmarkCollectionRecord } from './landmark-records.ts';

export type StationFeature = Feature<Point, Omit<StationRecord, 'id'>>;
export type StationFeatureCollection = FeatureCollection<Point, Omit<StationRecord, 'id'>>;
export type LeadFeature = Feature<Point, Omit<LeadRecord, 'id' | 'latitude' | 'longitude'>>;
export type LeadFeatureCollection = FeatureCollection<Point, Omit<LeadRecord, 'id' | 'latitude' | 'longitude'>>;
export interface LandmarkFeatureProperties extends Omit<LandmarkRecord, 'id'> {
    collection_type?: string;
    is_personal_collection?: boolean;
}
export type LandmarkFeatureCollection = FeatureCollection<Point, LandmarkFeatureProperties>;
export interface ViewerLandmark extends Omit<LandmarkRecord, 'collection' | 'collection_name' | 'collection_color'> {
    coordinates?: Position;
    collection?: EntityId | null;
    collection_name?: string | null;
    collection_type?: string | null;
    collection_color?: string | null;
    is_personal_collection?: boolean;
}
export interface ViewerLandmarkCollection extends Omit<LandmarkCollectionRecord, 'color' | 'user_permission_level' | 'user_permission_level_label'> {
    color: string | null;
    user_permission_level?: number | undefined;
    user_permission_level_label?: string | undefined;
    can_write?: boolean;
    can_admin?: boolean;
}
