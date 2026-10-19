import * as sdk from '@speleodb/api';
import type { EntityId } from '../../../../../ts-types/domain/identifiers.ts';
import type { ApiRequestOptions } from '../../../../../ts-types/domain/map-transport.ts';
import type { StationWrite, LeadWrite } from '../../../../../ts-types/domain/station-records.ts';
import type { LandmarkWrite } from '../../../../../ts-types/domain/landmark-records.ts';
import type { ExperimentValues } from '../../../../../ts-types/domain/experiment-records.ts';
import type { CylinderInstallWrite, PressureCheckWrite, CylinderInstallQuery } from '../../../../../ts-types/domain/fleet-records.ts';
import { apiData, webApiOptions } from '../../../../../frontend_common/api/client.ts';
import { formText, logBody, resourceBody, resourceUpdateBody, sensorBody, gpxBody } from '../../../../../frontend_common/api/form-values.ts';
import { Utils } from './utils.ts';
import { MANDATORY_FIELD_UUIDS } from '../../../../../frontend_common/api/experiment-values.ts';

type GeometryWrite = sdk.GISGeometryRequest;
/** The map owns its CSRF source; all transport and contracts are shared. */
function mapApiOptions(options: Omit<sdk.ApiRequestOptions, 'client'> = {}) {
    return webApiOptions({ ...options, headers: { 'X-CSRFToken': Utils.getCSRFToken(), ...options.headers } });
}

/** Full record writes require the measurement date as well as dynamic field values. */
function experimentRecordBody(values: ExperimentValues): sdk.V2StationsExperimentRecordsCreateBodyOne {
    const measurementDate = values[MANDATORY_FIELD_UUIDS.MEASUREMENT_DATE];
    if (typeof measurementDate !== 'string' || !measurementDate.trim()) {
        throw new Error('Enter a measurement date.');
    }
    return { ...values, [MANDATORY_FIELD_UUIDS.MEASUREMENT_DATE]: measurementDate };
}

export const API = {
    getGISGeometries: () => apiData(sdk.v2GisGeometriesList(undefined, mapApiOptions())),
    getGISGeometryDetails: (id: EntityId, options?: ApiRequestOptions) => apiData(sdk.v2GisGeometriesRetrieve(String(id), undefined, mapApiOptions(options))),
    createGISGeometry: (data: GeometryWrite) => apiData(sdk.v2GisGeometriesCreateWithJson(data, undefined, mapApiOptions())),
    updateGISGeometry: (id: EntityId, data: sdk.PatchedGISGeometryUpdateRequest) => apiData(sdk.v2GisGeometriesPartialUpdateWithJson(String(id), data, undefined, mapApiOptions())),

    // Stations
    createStation: (projectId: EntityId, stationData: sdk.SubSurfaceStationRequest) =>
        apiData(sdk.v2ProjectsStationsCreateWithJson(String(projectId), stationData, undefined, mapApiOptions())),

    updateStation: (stationId: EntityId, stationData: sdk.PatchedStationUpdateRequest) =>
        apiData(sdk.v2StationsPartialUpdateWithJson(String(stationId), stationData, undefined, mapApiOptions())),

    deleteStation: (stationId: EntityId) =>
        apiData(sdk.v2StationsDestroy(String(stationId), undefined, mapApiOptions())),

    getProjectStations: (projectId: EntityId) =>
        apiData(sdk.v2ProjectsStationsRetrieve(String(projectId), undefined, mapApiOptions())),

    getStationDetails: (stationId: EntityId) =>
        apiData(sdk.v2StationsRetrieve(String(stationId), undefined, mapApiOptions())),

    // All Stations GeoJSON (single API call for all stations)
    getAllStationsGeoJSON: () =>
        apiData(sdk.v2StationsSubsurfaceGeojsonRetrieve(undefined, mapApiOptions())),

    // Surface Networks
    getAllSurfaceNetworks: () =>
        apiData(sdk.v2SurfaceNetworksList(undefined, mapApiOptions())),

    // Surface Stations
    createSurfaceStation: (networkId: EntityId, stationData: sdk.SurfaceStationRequest) =>
        apiData(sdk.v2SurfaceNetworksStationsCreateWithJson(String(networkId), stationData, undefined, mapApiOptions())),

    getNetworkStations: (networkId: EntityId) =>
        apiData(sdk.v2SurfaceNetworksStationsRetrieve(String(networkId), undefined, mapApiOptions())),

    getNetworkStationsGeoJSON: (networkId: EntityId) =>
        apiData(sdk.v2SurfaceNetworksStationsGeojsonRetrieve(String(networkId), undefined, mapApiOptions())),

    getAllSurfaceStations: () =>
        apiData(sdk.v2StationsSurfaceRetrieve(undefined, mapApiOptions())),

    getAllSurfaceStationsGeoJSON: () =>
        apiData(sdk.v2StationsSurfaceGeojsonRetrieve(undefined, mapApiOptions())),

    // Landmarks
    createLandmark: (landmarkData: sdk.LandmarkRequest) =>
        apiData(sdk.v2LandmarksCreateWithJson(landmarkData, undefined, mapApiOptions())),

    updateLandmark: (landmarkId: EntityId, landmarkData: sdk.PatchedLandmarkRequest) =>
        apiData(sdk.v2LandmarksPartialUpdateWithJson(String(landmarkId), landmarkData, undefined, mapApiOptions())),

    deleteLandmark: (landmarkId: EntityId) =>
        apiData(sdk.v2LandmarksDestroy(String(landmarkId), undefined, mapApiOptions())),

    getAllLandmarks: () =>
        apiData(sdk.v2LandmarksList(undefined, mapApiOptions())),

    getLandmarkCollections: () =>
        apiData(sdk.v2LandmarkCollectionsList(undefined, mapApiOptions())),

    // All Landmarks GeoJSON (single API call)
    getAllLandmarksGeoJSON: () =>
        apiData(sdk.v2LandmarksGeojsonRetrieve(undefined, mapApiOptions())),

    // Tags
    getUserTags: () =>
        apiData(sdk.v2StationTagsList(undefined, mapApiOptions())),

    getTagColors: () =>
        apiData(sdk.v2StationTagsColorsRetrieve(undefined, mapApiOptions())),

    createTag: (name: string, color: string) =>
        apiData(sdk.v2StationTagsCreateWithJson({ name, color }, undefined, mapApiOptions())),

    setStationTag: (stationId: EntityId, tagId: EntityId) =>
        apiData(sdk.v2StationsTagsCreateWithJson(String(stationId), { tag_id: String(tagId) }, undefined, mapApiOptions())),

    removeStationTag: (stationId: EntityId) =>
        apiData(sdk.v2StationsTagsDestroy(String(stationId), undefined, mapApiOptions())),

    // Station Logs
    getStationLogs: (stationId: EntityId) =>
        apiData(sdk.v2StationsLogsRetrieve(String(stationId), undefined, mapApiOptions())),

    createStationLog: (stationId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2StationsLogsCreateWithFormData(String(stationId), logBody(formData), undefined, mapApiOptions(options))),

    updateStationLog: (logId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2LogsPartialUpdateWithFormData(String(logId), logBody(formData), undefined, mapApiOptions(options))),

    deleteStationLog: (logId: EntityId) =>
        apiData(sdk.v2LogsDestroy(String(logId), undefined, mapApiOptions())),

    // Experiments
    getExperiments: () =>
        apiData(sdk.v2ExperimentsList(undefined, mapApiOptions())),

    getExperimentData: (stationId: EntityId, experimentId: EntityId) =>
        apiData(sdk.v2StationsExperimentRecordsRetrieve(String(stationId), String(experimentId), undefined, mapApiOptions())),

    createExperimentRecord: (stationId: EntityId, experimentId: EntityId, recordData: ExperimentValues) =>
        apiData(sdk.v2StationsExperimentRecordsCreateWithJson(String(stationId), String(experimentId), experimentRecordBody(recordData), undefined, mapApiOptions())),

    updateExperimentRecord: (recordId: EntityId, recordData: ExperimentValues) =>
        apiData(sdk.v2ExperimentRecordsUpdate(String(recordId), experimentRecordBody(recordData), undefined, mapApiOptions())),

    deleteExperimentRecord: (recordId: EntityId) =>
        apiData(sdk.v2ExperimentRecordsDestroy(String(recordId), undefined, mapApiOptions())),

    // Resources
    getStationResources: (stationId: EntityId) =>
        apiData(sdk.v2StationsResourcesRetrieve(String(stationId), undefined, mapApiOptions())),

    createStationResource: (stationId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2StationsResourcesCreateWithFormData(String(stationId), resourceBody(formData), undefined, mapApiOptions(options))),

    updateStationResource: (resourceId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2ResourcesPartialUpdateWithFormData(String(resourceId), resourceUpdateBody(formData), undefined, mapApiOptions(options))),

    deleteStationResource: (resourceId: EntityId) =>
        apiData(sdk.v2ResourcesDestroy(String(resourceId), undefined, mapApiOptions())),

    // Projects
    getAllProjects: () =>
        apiData(sdk.v2ProjectsList(undefined, mapApiOptions())),

    getAllProjectsGeoJSON: () =>
        apiData(sdk.v2ProjectsGeojsonList(undefined, mapApiOptions())),

    // Exploration Leads
    getProjectExplorationLeadsGeoJSON: (projectId: EntityId) =>
        apiData(sdk.v2ProjectsExplorationLeadsGeojsonRetrieve(String(projectId), undefined, mapApiOptions())),

    getAllProjectExplorationLeadsGeoJSON: () =>
        apiData(sdk.v2ExplorationLeadsGeojsonRetrieve(undefined, mapApiOptions())),

    getProjectExplorationLeads: (projectId: EntityId) =>
        apiData(sdk.v2ProjectsExplorationLeadsRetrieve(String(projectId), undefined, mapApiOptions())),

    createExplorationLead: (projectId: EntityId, leadData: sdk.ExplorationLeadRequest) =>
        apiData(sdk.v2ProjectsExplorationLeadsCreateWithJson(String(projectId), leadData, undefined, mapApiOptions())),

    updateExplorationLead: (leadId: EntityId, leadData: sdk.PatchedExplorationLeadRequest) =>
        apiData(sdk.v2ExplorationLeadsPartialUpdateWithJson(String(leadId), leadData, undefined, mapApiOptions())),

    deleteExplorationLead: (leadId: EntityId) =>
        apiData(sdk.v2ExplorationLeadsDestroy(String(leadId), undefined, mapApiOptions())),

    // Sensor-Fleets
    getSensorFleets: () =>
        apiData(sdk.v2SensorFleetsList(undefined, mapApiOptions())),

    getSensorFleetDetails: (fleetId: EntityId) =>
        apiData(sdk.v2SensorFleetsRetrieve(String(fleetId), undefined, mapApiOptions())),

    getSensorFleetSensors: (fleetId: EntityId) =>
        apiData(sdk.v2SensorFleetsSensorsRetrieve(String(fleetId), undefined, mapApiOptions())),

    // Sensor Installs
    getStationSensorInstalls: (stationId: EntityId) =>
        apiData(sdk.v2StationsSensorInstallsList(String(stationId), undefined, mapApiOptions())),

    getStationSensorInstallsWithStatus: (stationId: EntityId, status: string) =>
        apiData(sdk.v2StationsSensorInstallsList(String(stationId), { status }, mapApiOptions())),

    // Preserve the generated response headers alongside the binary export body.
    getStationSensorInstallsAsExcel: (stationId: EntityId) =>
        sdk.v2StationsSensorInstallsExportExcelRetrieve(String(stationId), undefined, mapApiOptions()),

    getStationSensorInstallDetails: (stationId: EntityId, installId: EntityId) =>
        apiData(sdk.v2StationsSensorInstallsRetrieve(String(stationId), String(installId), undefined, mapApiOptions())),

    createStationSensorInstalls: (stationId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2StationsSensorInstallsCreateWithJson(String(stationId), { ...sensorBody(formData), sensor: formText(formData, 'sensor'), install_date: formText(formData, 'install_date') }, undefined, mapApiOptions(options))),

    updateStationSensorInstalls: (stationId: EntityId, installId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2StationsSensorInstallsPartialUpdateWithJson(String(stationId), String(installId), sensorBody(formData), undefined, mapApiOptions(options))),

    // GPS Tracks
    getGPSTracks: () =>
        apiData(sdk.v2GpsTracksList(undefined, mapApiOptions())),

    getGPSTrackDetails: (trackId: EntityId, options?: ApiRequestOptions) =>
        apiData(sdk.v2GpsTracksRetrieve(String(trackId), undefined, mapApiOptions(options))),

    // GIS Layers (private viewer only)
    getGISLayers: () =>
        apiData(sdk.v2GisLayersList(undefined, mapApiOptions())),

    getGISLayerDetails: (layerId: EntityId, options?: ApiRequestOptions) =>
        apiData(sdk.v2GisLayersRetrieve(String(layerId), undefined, mapApiOptions(options))),

    // GPX Import
    importGPX: (formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2ImportGpxUpdate(gpxBody(formData), undefined, mapApiOptions(options))),

    // ================== CYLINDER FLEETS ================== //

    // Cylinder Fleets
    getCylinderFleets: () =>
        apiData(sdk.v2CylinderFleetsList(undefined, mapApiOptions())),

    getCylinderFleetDetails: (fleetId: EntityId) =>
        apiData(sdk.v2CylinderFleetsRetrieve(String(fleetId), undefined, mapApiOptions())),

    getCylinderFleetCylinders: (fleetId: EntityId) =>
        apiData(sdk.v2CylinderFleetsCylindersRetrieve(String(fleetId), undefined, mapApiOptions())),

    // Cylinder Installs
    getCylinderInstalls: (params: sdk.V2CylinderInstallsListParams = {}) =>
        apiData(sdk.v2CylinderInstallsList(params, mapApiOptions())),

    getCylinderInstallsGeoJSON: () =>
        apiData(sdk.v2CylinderInstallsGeojsonRetrieve(undefined, mapApiOptions())),

    getAllCylinderInstallsGeoJSON: () =>
        apiData(sdk.v2CylinderInstallsGeojsonRetrieve(undefined, mapApiOptions())),

    createCylinderInstall: (installData: sdk.CylinderInstallCreateRequestRequest) =>
        apiData(sdk.v2CylinderInstallsCreateWithJson(installData, undefined, mapApiOptions())),

    getCylinderInstallDetails: (installId: EntityId) =>
        apiData(sdk.v2CylinderInstallsRetrieve(String(installId), undefined, mapApiOptions())),

    updateCylinderInstall: (installId: EntityId, installData: sdk.PatchedCylinderInstallRequest) =>
        apiData(sdk.v2CylinderInstallsPartialUpdateWithJson(String(installId), installData, undefined, mapApiOptions())),

    deleteCylinderInstall: (installId: EntityId) =>
        apiData(sdk.v2CylinderInstallsDestroy(String(installId), undefined, mapApiOptions())),

    // Cylinder Pressure Checks
    getCylinderPressureChecks: (installId: EntityId) =>
        apiData(sdk.v2CylinderInstallsPressureChecksList(String(installId), undefined, mapApiOptions())),

    createCylinderPressureCheck: (installId: EntityId, checkData: sdk.CylinderPressureCheckRequest) =>
        apiData(sdk.v2CylinderInstallsPressureChecksCreateWithJson(String(installId), checkData, undefined, mapApiOptions())),

    getCylinderPressureCheckDetails: (installId: EntityId, checkId: EntityId) =>
        apiData(sdk.v2CylinderInstallsPressureChecksRetrieve(String(installId), String(checkId), undefined, mapApiOptions())),

    updateCylinderPressureCheck: (installId: EntityId, checkId: EntityId, checkData: sdk.PatchedCylinderPressureCheckRequest) =>
        apiData(sdk.v2CylinderInstallsPressureChecksPartialUpdateWithJson(String(installId), String(checkId), checkData, undefined, mapApiOptions())),

    deleteCylinderPressureCheck: (installId: EntityId, checkId: EntityId) =>
        apiData(sdk.v2CylinderInstallsPressureChecksDestroy(String(installId), String(checkId), undefined, mapApiOptions())),
};
