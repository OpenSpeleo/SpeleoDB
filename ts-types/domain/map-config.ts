import type { EntityId } from './identifiers.ts';
import type { Geometry } from 'geojson';

export type PermissionAction = 'read' | 'write' | 'delete';
export interface ScopeAccess { read: boolean; write: boolean; delete: boolean }
export interface StationScopeRecord {
    project?: EntityId | null | undefined;
    network?: EntityId | null | undefined;
    station_type?: string | undefined;
}

/** Config stores the fields selected from private and public project responses. */
export interface ViewerProject {
    id: string;
    name?: string | undefined;
    permissions?: string | null | undefined;
    description?: string | undefined;
    country?: string | undefined;
    color?: string | undefined;
    latitude?: string | number | null | undefined;
    longitude?: string | number | null | undefined;
    visibility?: string | undefined;
    geojson_url?: string | null | undefined;
}
export interface ProjectResponse extends Omit<ViewerProject, 'id' | 'permissions'> {
    id: EntityId;
    permission?: string | undefined;
    geojson_file?: string | null | undefined;
    geojson_revision?: string | null | undefined;
    geojson_commit_sha?: string | null | undefined;
}
export interface ViewerNetwork {
    id: string;
    name?: string | undefined;
    description?: string | undefined;
    is_active?: boolean | undefined;
    created_by?: string | undefined;
    creation_date?: string | undefined;
    modified_date?: string | undefined;
    permissions?: string | null | undefined;
    permission_level?: number | undefined;
}
export interface NetworkResponse extends Omit<ViewerNetwork, 'id' | 'permissions' | 'permission_level'> {
    id: EntityId;
    user_permission_level?: number | undefined;
    user_permission_level_label?: string | null | undefined;
}
export interface ViewerGPSTrack {
    id: string;
    name?: string | undefined;
    color?: string | undefined;
    file?: string | undefined;
    creation_date?: string | undefined;
    modified_date?: string | undefined;
}
export interface GPSTrackResponse extends Omit<ViewerGPSTrack, 'id'> { id: EntityId }
export interface ViewerGISLayer extends ViewerGPSTrack {
    description?: string | undefined;
    created_by?: string | undefined;
    source_format?: string | undefined;
    user_permission_level?: number | undefined;
    user_permission_level_label?: string | null | undefined;
    can_write?: boolean | undefined;
    can_delete?: boolean | undefined;
    can_manage_permissions?: boolean | undefined;
}
export interface GISLayerResponse extends Omit<ViewerGISLayer, 'id'> { id: EntityId }
export interface GISGeometryMetadata extends Omit<ViewerGISLayer, 'file' | 'source_format'> {
    revision: number;
    geometry_type?: string | undefined;
    bbox_area_m2?: number | undefined;
    vertex_count?: number | undefined;
}
export interface GISGeometryResponse extends Omit<GISGeometryMetadata, 'id'> {
    id: EntityId;
    geojson?: Geometry | undefined;
}
export interface LoadOverlayOptions { force?: boolean; throwOnError?: boolean }
