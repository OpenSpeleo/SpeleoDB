import type { LandmarkGeoJSONCollection, StationGeoJSON, StationGeoJSONCollection } from '@speleodb/api';
import type { Feature, FeatureCollection, Point, Position } from 'geojson';
import type { EntityId } from './identifiers.ts';
import type { StationRecord, LeadRecord } from './station-records.ts';
import type { LandmarkRecord, LandmarkCollectionRecord } from './landmark-records.ts';

export type StationFeature = StationGeoJSON;
export type StationFeatureCollection = StationGeoJSONCollection;
export type LeadFeature = Feature<Point, Omit<LeadRecord, 'id' | 'latitude' | 'longitude'>>;
export type LeadFeatureCollection = FeatureCollection<Point, Omit<LeadRecord, 'id' | 'latitude' | 'longitude'>>;
export interface LandmarkFeatureProperties extends Omit<LandmarkRecord, 'id'> {
    collection_type?: string;
    is_personal_collection?: boolean;
}
export type LandmarkFeatureCollection = LandmarkGeoJSONCollection;
export interface ViewerLandmark extends Omit<LandmarkRecord, 'collection' | 'collection_name' | 'collection_color'> {
    coordinates?: Position;
    collection?: EntityId | null;
    collection_name?: string | null;
    collection_type?: string | null;
    collection_color?: string | null;
    is_personal_collection?: boolean;
}
export interface ViewerLandmarkCollection extends Partial<Omit<LandmarkCollectionRecord, 'id' | 'name' | 'color' | 'user_permission_level' | 'user_permission_level_label'>>, Pick<LandmarkCollectionRecord, 'id' | 'name'> {
    color: string | null;
    user_permission_level?: number | undefined;
    user_permission_level_label?: string | null | undefined;
    can_write?: boolean;
    can_admin?: boolean;
}
