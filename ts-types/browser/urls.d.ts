import type { EntityId } from '../domain/identifiers.ts';

/** Django-generated reversal functions consumed by application modules/context. */
export interface ApplicationUrls {
    'private:cylinder_fleet_details'(this: void, fleetId: EntityId): string;
    'private:experiment_details'(this: void, experimentId: EntityId): string;
    'private:gis_geometry_details'(this: void, geometryId: EntityId): string;
    'private:gis_layer_details'(this: void, layerId: EntityId): string;
    'private:gis_view_details'(this: void, viewId: EntityId): string;
    'private:gps_track_details'(this: void, trackId: EntityId): string;
    'private:landmark_collection_details'(this: void, collectionId: EntityId): string;
    'private:landmark_collection_new'(this: void): string;
    'private:project_details'(this: void, projectId: EntityId): string;
    'private:project_revision_explorer'(this: void, projectId: EntityId, commitId: string): string;
    'private:sensor_fleet_details'(this: void, fleetId: EntityId): string;
    'private:surface_network_details'(this: void, networkId: EntityId): string;
}

declare global {
    var Urls: ApplicationUrls;

    interface Window {
        Urls: ApplicationUrls;
    }
}
