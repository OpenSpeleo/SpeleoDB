import type { StationFeatureCollection, LeadFeatureCollection, LandmarkFeatureCollection } from '../../../../../ts-types/domain/map-entities.ts';
import type { GPXImportResult } from '../../../../../ts-types/domain/map-import.ts';
import type { EntityId } from '../../../../../ts-types/domain/identifiers.ts';
import type { ProjectResponse, NetworkResponse, GPSTrackResponse, GISLayerResponse, GISGeometryResponse } from '../../../../../ts-types/domain/map-config.ts';
import type { ApiRequestOptions, ApiNoContent } from '../../../../../ts-types/domain/map-transport.ts';
import type { StationWrite, StationRecord, StationTagRecord, StationLogRecord, StationResourceRecord, LeadWrite, LeadRecord } from '../../../../../ts-types/domain/station-records.ts';
import type { LandmarkWrite, LandmarkRecord, LandmarkCollectionRecord } from '../../../../../ts-types/domain/landmark-records.ts';
import type { ExperimentValues, ExperimentRecord, ExperimentDefinition } from '../../../../../ts-types/domain/experiment-records.ts';
import type { SensorFleetRecord, SensorRecord, SensorInstallRecord, CylinderFleetRecord, CylinderRecord, CylinderInstallRecord, CylinderInstallDetails, CylinderInstallWrite, PressureCheckRecord, PressureCheckWrite, CylinderInstallQuery } from '../../../../../ts-types/domain/fleet-records.ts';
import type { FeatureCollection, Geometry } from 'geojson';

type GeometryWrite = { name?: string; color?: string; geojson?: Geometry; expected_revision?: number };
import { Utils } from './utils.ts';
import { createMapTransport } from './transport.ts';

// Keep callback-time lookup and its Utils receiver when callers replace the facade.
const apiRequest = createMapTransport(() => Utils.getCSRFToken());

export const API = {
    getGISGeometries: () => apiRequest<GISGeometryResponse[]>(Urls['api:v2:gis-geometry-list']()),
    getGISGeometryDetails: (id: EntityId, options?: ApiRequestOptions) => apiRequest<GISGeometryResponse>(Urls['api:v2:gis-geometry-detail'](id), 'GET', null, false, options),
    createGISGeometry: (data: GeometryWrite) => apiRequest<GISGeometryResponse>(Urls['api:v2:gis-geometry-list'](), 'POST', data),
    updateGISGeometry: (id: EntityId, data: GeometryWrite) => apiRequest<GISGeometryResponse>(Urls['api:v2:gis-geometry-detail'](id), 'PATCH', data),

    // Stations
    createStation: (projectId: EntityId, stationData: StationWrite) =>
        apiRequest<StationRecord>(Urls['api:v2:project-stations'](projectId), 'POST', stationData),

    updateStation: (stationId: EntityId, stationData: StationWrite) =>
        apiRequest<StationRecord>(Urls['api:v2:station-detail'](stationId), 'PATCH', stationData),

    deleteStation: (stationId: EntityId) =>
        apiRequest<{ id: EntityId; message?: string } | ApiNoContent>(Urls['api:v2:station-detail'](stationId), 'DELETE'),

    getProjectStations: (projectId: EntityId) =>
        apiRequest<StationRecord[]>(Urls['api:v2:project-stations'](projectId)),

    getStationDetails: (stationId: EntityId) =>
        apiRequest<StationRecord>(Urls['api:v2:station-detail'](stationId)),

    // All Stations GeoJSON (single API call for all stations)
    getAllStationsGeoJSON: () =>
        apiRequest<StationFeatureCollection>(Urls['api:v2:subsurface-stations-geojson']()),

    // Surface Networks
    getAllSurfaceNetworks: () =>
        apiRequest<NetworkResponse[]>(Urls['api:v2:surface-networks']()),

    // Surface Stations
    createSurfaceStation: (networkId: EntityId, stationData: StationWrite) =>
        apiRequest<StationRecord>(Urls['api:v2:network-stations'](networkId), 'POST', stationData),

    getNetworkStations: (networkId: EntityId) =>
        apiRequest<StationRecord[]>(Urls['api:v2:network-stations'](networkId)),

    getNetworkStationsGeoJSON: (networkId: EntityId) =>
        apiRequest<StationFeatureCollection>(Urls['api:v2:network-stations-geojson'](networkId)),

    getAllSurfaceStations: () =>
        apiRequest<StationRecord[]>(Urls['api:v2:surface-stations']()),

    getAllSurfaceStationsGeoJSON: () =>
        apiRequest<StationFeatureCollection>(Urls['api:v2:surface-stations-geojson']()),

    // Landmarks
    createLandmark: (landmarkData: LandmarkWrite) =>
        apiRequest<{ landmark: LandmarkRecord }>(Urls['api:v2:landmarks'](), 'POST', landmarkData),

    updateLandmark: (landmarkId: EntityId, landmarkData: LandmarkWrite) =>
        apiRequest<{ landmark: LandmarkRecord }>(Urls['api:v2:landmark-detail'](landmarkId), 'PATCH', landmarkData),

    deleteLandmark: (landmarkId: EntityId) =>
        apiRequest<{ message: string } | ApiNoContent>(Urls['api:v2:landmark-detail'](landmarkId), 'DELETE'),

    getAllLandmarks: () =>
        apiRequest<{ landmarks: LandmarkRecord[] }>(Urls['api:v2:landmarks']()),

    getLandmarkCollections: () =>
        apiRequest<LandmarkCollectionRecord[]>(Urls['api:v2:landmark-collections']()),

    // All Landmarks GeoJSON (single API call)
    getAllLandmarksGeoJSON: () =>
        apiRequest<LandmarkFeatureCollection>(Urls['api:v2:landmarks-geojson']()),

    // Tags
    getUserTags: () =>
        apiRequest<StationTagRecord[]>(Urls['api:v2:station-tags']()),

    getTagColors: () =>
        apiRequest<{ colors: string[] }>(Urls['api:v2:station-tag-colors']()),

    createTag: (name: string, color: string) =>
        apiRequest<StationTagRecord>(Urls['api:v2:station-tags'](), 'POST', { name, color }),

    setStationTag: (stationId: EntityId, tagId: EntityId) =>
        apiRequest<StationTagRecord>(Urls['api:v2:station-tags-manage'](stationId), 'POST', { tag_id: tagId }),

    removeStationTag: (stationId: EntityId) =>
        apiRequest<null>(Urls['api:v2:station-tags-manage'](stationId), 'DELETE'),

    // Station Logs
    getStationLogs: (stationId: EntityId) =>
        apiRequest<StationLogRecord[]>(Urls['api:v2:station-logs'](stationId)),

    createStationLog: (stationId: EntityId, formData: FormData) =>
        apiRequest<StationLogRecord>(Urls['api:v2:station-logs'](stationId), 'POST', formData, true),

    updateStationLog: (logId: EntityId, formData: FormData) =>
        apiRequest<StationLogRecord>(Urls['api:v2:log-detail'](logId), 'PATCH', formData, true),

    deleteStationLog: (logId: EntityId) =>
        apiRequest<{ id: EntityId; message?: string } | ApiNoContent>(Urls['api:v2:log-detail'](logId), 'DELETE'),

    // Experiments
    getExperiments: () =>
        apiRequest<ExperimentDefinition[]>(Urls['api:v2:experiments']()),

    getExperimentData: (stationId: EntityId, experimentId: EntityId) =>
        apiRequest<ExperimentRecord[]>(Urls['api:v2:experiment-records'](stationId, experimentId)),

    createExperimentRecord: (stationId: EntityId, experimentId: EntityId, recordData: ExperimentValues) =>
        apiRequest<ExperimentRecord>(Urls['api:v2:experiment-records'](stationId, experimentId), 'POST', recordData),

    updateExperimentRecord: (recordId: EntityId, recordData: ExperimentValues) =>
        apiRequest<ExperimentRecord>(Urls['api:v2:experiment-records-detail'](recordId), 'PUT', recordData),

    deleteExperimentRecord: (recordId: EntityId) =>
        apiRequest<{ id: EntityId; message?: string } | ApiNoContent>(Urls['api:v2:experiment-records-detail'](recordId), 'DELETE'),

    // Resources
    getStationResources: (stationId: EntityId) =>
        apiRequest<StationResourceRecord[]>(Urls['api:v2:station-resources'](stationId)),

    createStationResource: (stationId: EntityId, formData: FormData) =>
        apiRequest<StationResourceRecord>(Urls['api:v2:station-resources'](stationId), 'POST', formData, true),

    updateStationResource: (resourceId: EntityId, formData: FormData) =>
        apiRequest<StationResourceRecord>(Urls['api:v2:resource-detail'](resourceId), 'PATCH', formData, true),

    deleteStationResource: (resourceId: EntityId) =>
        apiRequest<{ id: EntityId; message?: string } | ApiNoContent>(Urls['api:v2:resource-detail'](resourceId), 'DELETE'),

    // Projects
    getAllProjects: () =>
        apiRequest<ProjectResponse[]>(Urls['api:v2:projects']()),

    getAllProjectsGeoJSON: () =>
        apiRequest<ProjectResponse[]>(Urls['api:v2:all-projects-geojson']()),

    // Exploration Leads
    getProjectExplorationLeadsGeoJSON: (projectId: EntityId) =>
        apiRequest<LeadFeatureCollection>(Urls['api:v2:project-exploration-leads-geojson'](projectId)),

    getAllProjectExplorationLeadsGeoJSON: () =>
        apiRequest<LeadFeatureCollection>(Urls['api:v2:exploration-lead-all-geojson']()),

    getProjectExplorationLeads: (projectId: EntityId) =>
        apiRequest<LeadRecord[]>(Urls['api:v2:project-exploration-leads'](projectId)),

    createExplorationLead: (projectId: EntityId, leadData: LeadWrite) =>
        apiRequest<LeadRecord>(Urls['api:v2:project-exploration-leads'](projectId), 'POST', leadData),

    updateExplorationLead: (leadId: EntityId, leadData: LeadWrite) =>
        apiRequest<LeadRecord>(Urls['api:v2:exploration-lead-detail'](leadId), 'PATCH', leadData),

    deleteExplorationLead: (leadId: EntityId) =>
        apiRequest<{ id: EntityId; message?: string } | ApiNoContent>(Urls['api:v2:exploration-lead-detail'](leadId), 'DELETE'),

    // Sensor-Fleets
    getSensorFleets: () =>
        apiRequest<SensorFleetRecord[]>(Urls['api:v2:sensor-fleets']()),

    getSensorFleetDetails: (fleetId: EntityId) =>
        apiRequest<SensorFleetRecord>(Urls['api:v2:sensor-fleet-detail'](fleetId)),

    getSensorFleetSensors: (fleetId: EntityId) =>
        apiRequest<SensorRecord[]>(Urls['api:v2:sensor-fleet-sensors'](fleetId)),

    // Sensor Installs
    getStationSensorInstalls: (stationId: EntityId) =>
        apiRequest<SensorInstallRecord[]>(Urls['api:v2:station-sensor-installs'](stationId)),

    getStationSensorInstallsWithStatus: (stationId: EntityId, status: string) =>
        apiRequest<SensorInstallRecord[]>(Urls['api:v2:station-sensor-installs'](stationId) + "?status=" + status),

    // Returns raw Response object for blob download (not parsed JSON)
    getStationSensorInstallsAsExcel: async (stationId: EntityId) => {
        const response = await fetch(Urls['api:v2:station-sensor-installs-export'](stationId), {
            method: 'GET',
            headers: {
                'X-CSRFToken': Utils.getCSRFToken()
            },
            credentials: 'same-origin'
        });
        return response;  // Return raw Response for blob handling
    },

    getStationSensorInstallDetails: (stationId: EntityId, installId: EntityId) =>
        apiRequest<SensorInstallRecord>(Urls['api:v2:station-sensor-install-detail'](stationId, installId)),

    createStationSensorInstalls: (stationId: EntityId, formData: FormData) =>
        apiRequest<SensorInstallRecord>(Urls['api:v2:station-sensor-installs'](stationId), 'POST', formData, true),

    updateStationSensorInstalls: (stationId: EntityId, installId: EntityId, formData: FormData) =>
        apiRequest<SensorInstallRecord>(Urls['api:v2:station-sensor-install-detail'](stationId, installId), 'PATCH', formData, true),

    // GPS Tracks
    getGPSTracks: () =>
        apiRequest<GPSTrackResponse[]>(Urls['api:v2:gps-tracks']()),

    getGPSTrackDetails: (trackId: EntityId, options?: ApiRequestOptions) =>
        apiRequest<GPSTrackResponse>(Urls['api:v2:gps-track-detail'](trackId), 'GET', null, false, options),

    // GIS Layers (private viewer only)
    getGISLayers: () =>
        apiRequest<GISLayerResponse[]>(Urls['api:v2:gis-layers']()),

    getGISLayerDetails: (layerId: EntityId, options?: ApiRequestOptions) =>
        apiRequest<GISLayerResponse>(Urls['api:v2:gis-layer-detail'](layerId), 'GET', null, false, options),

    // GPX Import
    importGPX: (formData: FormData) =>
        apiRequest<GPXImportResult>(Urls['api:v2:gpx-import'](), 'PUT', formData, true),

    // ================== CYLINDER FLEETS ================== //

    // Cylinder Fleets
    getCylinderFleets: () =>
        apiRequest<CylinderFleetRecord[]>(Urls['api:v2:cylinder-fleets']()),

    getCylinderFleetDetails: (fleetId: EntityId) =>
        apiRequest<CylinderFleetRecord>(Urls['api:v2:cylinder-fleet-detail'](fleetId)),

    getCylinderFleetCylinders: (fleetId: EntityId) =>
        apiRequest<CylinderRecord[]>(Urls['api:v2:cylinder-fleet-cylinders'](fleetId)),

    // Cylinder Installs
    getCylinderInstalls: (params: CylinderInstallQuery = {}) => {
        let url = Urls['api:v2:cylinder-installs']();
        const queryParams = [];
        if (params.cylinder_id) queryParams.push(`cylinder_id=${params.cylinder_id}`);
        if (params.fleet_id) queryParams.push(`fleet_id=${params.fleet_id}`);
        if (params.status) queryParams.push(`status=${params.status}`);
        if (queryParams.length > 0) url += '?' + queryParams.join('&');
        return apiRequest<CylinderInstallRecord[]>(url);
    },

    getCylinderInstallsGeoJSON: () =>
        apiRequest<FeatureCollection<Geometry, CylinderInstallRecord>>(Urls['api:v2:cylinder-installs-geojson']()),

    getAllCylinderInstallsGeoJSON: () =>
        apiRequest<FeatureCollection<Geometry, CylinderInstallRecord>>(Urls['api:v2:cylinder-installs-geojson']()),

    createCylinderInstall: (installData: CylinderInstallWrite) =>
        apiRequest<CylinderInstallRecord>(Urls['api:v2:cylinder-installs'](), 'POST', installData),

    getCylinderInstallDetails: (installId: EntityId) =>
        apiRequest<CylinderInstallDetails>(Urls['api:v2:cylinder-install-detail'](installId)),

    updateCylinderInstall: (installId: EntityId, installData: CylinderInstallWrite) =>
        apiRequest<CylinderInstallRecord>(Urls['api:v2:cylinder-install-detail'](installId), 'PATCH', installData),

    deleteCylinderInstall: (installId: EntityId) =>
        apiRequest<{ id: EntityId; message?: string } | ApiNoContent>(Urls['api:v2:cylinder-install-detail'](installId), 'DELETE'),

    // Cylinder Pressure Checks
    getCylinderPressureChecks: (installId: EntityId) =>
        apiRequest<PressureCheckRecord[]>(Urls['api:v2:cylinder-install-pressure-checks'](installId)),

    createCylinderPressureCheck: (installId: EntityId, checkData: PressureCheckWrite) =>
        apiRequest<PressureCheckRecord>(Urls['api:v2:cylinder-install-pressure-checks'](installId), 'POST', checkData),

    getCylinderPressureCheckDetails: (installId: EntityId, checkId: EntityId) =>
        apiRequest<PressureCheckRecord>(Urls['api:v2:cylinder-pressure-check-detail'](installId, checkId)),

    updateCylinderPressureCheck: (installId: EntityId, checkId: EntityId, checkData: PressureCheckWrite) =>
        apiRequest<PressureCheckRecord>(Urls['api:v2:cylinder-pressure-check-detail'](installId, checkId), 'PATCH', checkData),

    deleteCylinderPressureCheck: (installId: EntityId, checkId: EntityId) =>
        apiRequest<{ id: EntityId; message?: string } | ApiNoContent>(Urls['api:v2:cylinder-pressure-check-detail'](installId, checkId), 'DELETE'),
};
