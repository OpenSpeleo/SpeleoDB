import type { EntityId } from '../domain/identifiers.ts';

/** Django-generated reversal functions consumed by application modules/context. */
export interface ApplicationUrls {
    'api:v2:all-projects-geojson'(this: void): string;
    'api:v2:cylinder-detail'(this: void, cylinderId: EntityId): string;
    'api:v2:cylinder-fleet-cylinders'(this: void, fleetId: EntityId): string;
    'api:v2:cylinder-fleet-detail'(this: void, fleetId: EntityId): string;
    'api:v2:cylinder-fleet-watchlist-export'(this: void, fleetId: EntityId): string;
    'api:v2:cylinder-fleets'(this: void): string;
    'api:v2:cylinder-install-detail'(this: void, installId: EntityId): string;
    'api:v2:cylinder-install-pressure-checks'(this: void, installId: EntityId): string;
    'api:v2:cylinder-installs'(this: void): string;
    'api:v2:cylinder-installs-geojson'(this: void): string;
    'api:v2:cylinder-pressure-check-detail'(this: void, installId: EntityId, checkId: EntityId): string;
    'api:v2:experiment-detail'(this: void, experimentId: EntityId): string;
    'api:v2:experiment-export-excel'(this: void, experimentId: EntityId): string;
    'api:v2:experiment-records'(this: void, stationId: EntityId, experimentId: EntityId): string;
    'api:v2:experiment-records-detail'(this: void, recordId: EntityId): string;
    'api:v2:experiments'(this: void): string;
    'api:v2:exploration-lead-all-geojson'(this: void): string;
    'api:v2:exploration-lead-detail'(this: void, leadId: EntityId): string;
    'api:v2:gis-geometry-detail'(this: void, geometryId: EntityId): string;
    'api:v2:gis-geometry-list'(this: void): string;
    'api:v2:gis-layer-detail'(this: void, layerId: EntityId): string;
    'api:v2:gis-layer-source'(this: void, layerId: EntityId): string;
    'api:v2:gis-layers'(this: void): string;
    'api:v2:gis-ogc:view-geojson'(this: void, token: string): string;
    'api:v2:gps-track-detail'(this: void, trackId: EntityId): string;
    'api:v2:gps-track-export-gpx'(this: void, trackId: EntityId): string;
    'api:v2:gps-tracks'(this: void): string;
    'api:v2:gpx-import'(this: void): string;
    'api:v2:kml-kmz-import'(this: void): string;
    'api:v2:kml-kmz-inspect'(this: void): string;
    'api:v2:landmark-collection-landmarks-bulk-delete'(this: void, collectionId: EntityId): string;
    'api:v2:landmark-collection-landmarks-transfer'(this: void, collectionId: EntityId): string;
    'api:v2:landmark-collections'(this: void): string;
    'api:v2:landmark-detail'(this: void, landmarkId: EntityId): string;
    'api:v2:landmarks'(this: void): string;
    'api:v2:landmarks-geojson'(this: void): string;
    'api:v2:log-detail'(this: void, logId: EntityId): string;
    'api:v2:network-stations'(this: void, networkId: EntityId): string;
    'api:v2:network-stations-geojson'(this: void, networkId: EntityId): string;
    'api:v2:project-exploration-leads'(this: void, projectId: EntityId): string;
    'api:v2:project-exploration-leads-geojson'(this: void, projectId: EntityId): string;
    'api:v2:project-geojson-commits'(this: void, projectId: EntityId): string;
    'api:v2:project-release'(this: void, projectId: EntityId): string;
    'api:v2:project-stations'(this: void, projectId: EntityId): string;
    'api:v2:projects'(this: void): string;
    'api:v2:resource-detail'(this: void, resourceId: EntityId): string;
    'api:v2:sensor-detail'(this: void, sensorId: EntityId): string;
    'api:v2:sensor-fleet-detail'(this: void, fleetId: EntityId): string;
    'api:v2:sensor-fleet-sensors'(this: void, fleetId: EntityId): string;
    'api:v2:sensor-fleet-watchlist-export'(this: void, fleetId: EntityId): string;
    'api:v2:sensor-fleets'(this: void): string;
    'api:v2:sensor-toggle-functional'(this: void, sensorId: EntityId): string;
    'api:v2:station-detail'(this: void, stationId: EntityId): string;
    'api:v2:station-logs'(this: void, stationId: EntityId): string;
    'api:v2:station-resources'(this: void, stationId: EntityId): string;
    'api:v2:station-sensor-install-detail'(this: void, stationId: EntityId, installId: EntityId): string;
    'api:v2:station-sensor-installs'(this: void, stationId: EntityId): string;
    'api:v2:station-sensor-installs-export'(this: void, stationId: EntityId): string;
    'api:v2:station-tag-colors'(this: void): string;
    'api:v2:station-tag-detail'(this: void, tagId: EntityId): string;
    'api:v2:station-tags'(this: void): string;
    'api:v2:station-tags-manage'(this: void, stationId: EntityId): string;
    'api:v2:subsurface-stations-geojson'(this: void): string;
    'api:v2:surface-networks'(this: void): string;
    'api:v2:surface-stations'(this: void): string;
    'api:v2:surface-stations-geojson'(this: void): string;
    'api:v2:user-dashboard-stats'(this: void): string;
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
