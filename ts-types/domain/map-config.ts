import type {
    Project, ProjectWithGeoJson, PublicGISProjectView, SurfaceMonitoringNetworkWithPerm,
    GPSTrackWithFile, GISLayer, GISGeometry, GISGeometryList,
} from '@speleodb/api';
import type { EntityId } from './identifiers.ts';

export type PermissionAction = 'read' | 'write' | 'delete';
export interface ScopeAccess { read: boolean; write: boolean; delete: boolean }
export interface StationScopeRecord {
    project?: EntityId | null | undefined;
    network?: EntityId | null | undefined;
    station_type?: string | undefined;
}

/** Mutable, incrementally populated UI cache fields, derived from wire DTOs. */
type CacheFields<T> = { -readonly [Key in keyof T]?: T[Key] | undefined };

/** Config merges project metadata with display permissions and later GeoJSON reads. */
export interface ViewerProject extends CacheFields<Pick<Project, 'name' | 'description' | 'color' | 'visibility'>> {
    id: string;
    country?: string | undefined;
    permissions?: Project['permission'] | undefined;
    latitude?: Project['latitude'] | string | null | undefined;
    longitude?: Project['longitude'] | string | null | undefined;
    geojson_url?: PublicGISProjectView['geojson_file'] | undefined;
}
export interface ProjectMapInput extends Omit<ViewerProject, 'id' | 'permissions'>,
    CacheFields<Pick<ProjectWithGeoJson, 'geojson_file' | 'geojson_revision' | 'geojson_commit_sha'>> {
    id: EntityId;
    permission?: Project['permission'] | undefined;
}
export interface ViewerNetwork extends CacheFields<Omit<SurfaceMonitoringNetworkWithPerm, 'id' | 'user_permission_level' | 'user_permission_level_label'>> {
    id: string;
    permissions?: SurfaceMonitoringNetworkWithPerm['user_permission_level_label'] | undefined;
    permission_level?: SurfaceMonitoringNetworkWithPerm['user_permission_level'] | undefined;
}
export interface NetworkMapInput extends CacheFields<Omit<SurfaceMonitoringNetworkWithPerm, 'id'>> { id: EntityId }
export interface ViewerGPSTrack extends CacheFields<Omit<GPSTrackWithFile, 'id'>> { id: string }
export interface GPSTrackMapInput extends Omit<ViewerGPSTrack, 'id'> { id: EntityId }
export interface ViewerGISLayer extends CacheFields<Omit<GISLayer, 'id'>> { id: string }
export interface GISLayerMapInput extends Omit<ViewerGISLayer, 'id'> { id: EntityId }
export interface GISGeometryMetadata extends CacheFields<Omit<GISGeometryList, 'id' | 'revision'>>, Pick<GISGeometryList, 'id' | 'revision'> {}
export interface GISGeometryMapInput extends CacheFields<Omit<GISGeometry, 'id' | 'revision'>>, Pick<GISGeometry, 'revision'> { id: EntityId }
export interface LoadOverlayOptions { force?: boolean; throwOnError?: boolean }
