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

type GeometryWrite = sdk.GISGeometryRequest;
/** The map owns its CSRF source; all transport and contracts are shared. */
function mapApiOptions(options: Omit<sdk.ApiRequestOptions, 'client'> = {}) {
    return webApiOptions({ ...options, headers: { 'X-CSRFToken': Utils.getCSRFToken(), ...options.headers } });
}

export const API = {
    getGISGeometries: () => apiData(sdk.v2GisGeometriesList(mapApiOptions())),
    getGISGeometryDetails: (id: EntityId, options?: ApiRequestOptions) => apiData(sdk.v2GisGeometriesRetrieve(String(id), mapApiOptions(options))),
    createGISGeometry: (data: GeometryWrite) => apiData(sdk.v2GisGeometriesCreateWithJson(data, mapApiOptions())),
    updateGISGeometry: (id: EntityId, data: sdk.PatchedGISGeometryUpdateRequest) => apiData(sdk.v2GisGeometriesPartialUpdateWithJson(String(id), data, mapApiOptions())),

    // Stations
    createStation: (projectId: EntityId, stationData: sdk.SubSurfaceStationRequest) =>
        apiData(sdk.v2ProjectsStationsCreateWithJson(String(projectId), stationData, mapApiOptions())),

    updateStation: (stationId: EntityId, stationData: sdk.PatchedStationUpdateRequest) =>
        apiData(sdk.v2StationsPartialUpdateWithJson(String(stationId), stationData, mapApiOptions())),

    deleteStation: (stationId: EntityId) =>
        apiData(sdk.v2StationsDestroy(String(stationId), mapApiOptions())),

    getProjectStations: (projectId: EntityId) =>
        apiData(sdk.v2ProjectsStationsRetrieve(String(projectId), mapApiOptions())),

    getStationDetails: (stationId: EntityId) =>
        apiData(sdk.v2StationsRetrieve(String(stationId), mapApiOptions())),

    // All Stations GeoJSON (single API call for all stations)
    getAllStationsGeoJSON: () =>
        apiData(sdk.v2StationsSubsurfaceGeojsonRetrieve(mapApiOptions())),

    // Surface Networks
    getAllSurfaceNetworks: () =>
        apiData(sdk.v2SurfaceNetworksList(mapApiOptions())),

    // Surface Stations
    createSurfaceStation: (networkId: EntityId, stationData: sdk.SurfaceStationRequest) =>
        apiData(sdk.v2SurfaceNetworksStationsCreateWithJson(String(networkId), stationData, mapApiOptions())),

    getNetworkStations: (networkId: EntityId) =>
        apiData(sdk.v2SurfaceNetworksStationsRetrieve(String(networkId), mapApiOptions())),

    getNetworkStationsGeoJSON: (networkId: EntityId) =>
        apiData(sdk.v2SurfaceNetworksStationsGeojsonRetrieve(String(networkId), mapApiOptions())),

    getAllSurfaceStations: () =>
        apiData(sdk.v2StationsSurfaceRetrieve(mapApiOptions())),

    getAllSurfaceStationsGeoJSON: () =>
        apiData(sdk.v2StationsSurfaceGeojsonRetrieve(mapApiOptions())),

    // Landmarks
    createLandmark: (landmarkData: sdk.LandmarkRequest) =>
        apiData(sdk.v2LandmarksCreateWithJson(landmarkData, mapApiOptions())),

    updateLandmark: (landmarkId: EntityId, landmarkData: sdk.PatchedLandmarkRequest) =>
        apiData(sdk.v2LandmarksPartialUpdateWithJson(String(landmarkId), landmarkData, mapApiOptions())),

    deleteLandmark: (landmarkId: EntityId) =>
        apiData(sdk.v2LandmarksDestroy(String(landmarkId), mapApiOptions())),

    getAllLandmarks: () =>
        apiData(sdk.v2LandmarksList(mapApiOptions())),

    getLandmarkCollections: () =>
        apiData(sdk.v2LandmarkCollectionsList(mapApiOptions())),

    // All Landmarks GeoJSON (single API call)
    getAllLandmarksGeoJSON: () =>
        apiData(sdk.v2LandmarksGeojsonRetrieve(mapApiOptions())),

    // Tags
    getUserTags: () =>
        apiData(sdk.v2StationTagsList(mapApiOptions())),

    getTagColors: () =>
        apiData(sdk.v2StationTagsColorsRetrieve(mapApiOptions())),

    createTag: (name: string, color: string) =>
        apiData(sdk.v2StationTagsCreateWithJson({ name, color }, mapApiOptions())),

    setStationTag: (stationId: EntityId, tagId: EntityId) =>
        apiData(sdk.v2StationsTagsCreateWithJson(String(stationId), { tag_id: String(tagId) }, mapApiOptions())),

    removeStationTag: (stationId: EntityId) =>
        apiData(sdk.v2StationsTagsDestroy(String(stationId), mapApiOptions())),

    // Station Logs
    getStationLogs: (stationId: EntityId) =>
        apiData(sdk.v2StationsLogsRetrieve(String(stationId), mapApiOptions())),

    createStationLog: (stationId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2StationsLogsCreateWithFormData(String(stationId), logBody(formData), mapApiOptions(options))),

    updateStationLog: (logId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2LogsPartialUpdateWithFormData(String(logId), logBody(formData), mapApiOptions(options))),

    deleteStationLog: (logId: EntityId) =>
        apiData(sdk.v2LogsDestroy(String(logId), mapApiOptions())),

    // Experiments
    getExperiments: () =>
        apiData(sdk.v2ExperimentsList(mapApiOptions())),

    getExperimentData: (stationId: EntityId, experimentId: EntityId) =>
        apiData(sdk.v2StationsExperimentRecordsRetrieve(String(stationId), String(experimentId), mapApiOptions())),

    createExperimentRecord: (stationId: EntityId, experimentId: EntityId, recordData: ExperimentValues) =>
        apiData(sdk.v2StationsExperimentRecordsCreate(String(stationId), String(experimentId), recordData, mapApiOptions())),

    updateExperimentRecord: (recordId: EntityId, recordData: ExperimentValues) =>
        apiData(sdk.v2ExperimentRecordsUpdate(String(recordId), recordData, mapApiOptions())),

    deleteExperimentRecord: (recordId: EntityId) =>
        apiData(sdk.v2ExperimentRecordsDestroy(String(recordId), mapApiOptions())),

    // Resources
    getStationResources: (stationId: EntityId) =>
        apiData(sdk.v2StationsResourcesRetrieve(String(stationId), mapApiOptions())),

    createStationResource: (stationId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2StationsResourcesCreateWithFormData(String(stationId), resourceBody(formData), mapApiOptions(options))),

    updateStationResource: (resourceId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2ResourcesPartialUpdateWithFormData(String(resourceId), resourceUpdateBody(formData), mapApiOptions(options))),

    deleteStationResource: (resourceId: EntityId) =>
        apiData(sdk.v2ResourcesDestroy(String(resourceId), mapApiOptions())),

    // Projects
    getAllProjects: () =>
        apiData(sdk.v2ProjectsList(mapApiOptions())),

    getAllProjectsGeoJSON: () =>
        apiData(sdk.v2ProjectsGeojsonList(mapApiOptions())),

    // Exploration Leads
    getProjectExplorationLeadsGeoJSON: (projectId: EntityId) =>
        apiData(sdk.v2ProjectsExplorationLeadsGeojsonRetrieve(String(projectId), mapApiOptions())),

    getAllProjectExplorationLeadsGeoJSON: () =>
        apiData(sdk.v2ExplorationLeadsGeojsonRetrieve(mapApiOptions())),

    getProjectExplorationLeads: (projectId: EntityId) =>
        apiData(sdk.v2ProjectsExplorationLeadsRetrieve(String(projectId), mapApiOptions())),

    createExplorationLead: (projectId: EntityId, leadData: sdk.ExplorationLeadRequest) =>
        apiData(sdk.v2ProjectsExplorationLeadsCreateWithJson(String(projectId), leadData, mapApiOptions())),

    updateExplorationLead: (leadId: EntityId, leadData: sdk.PatchedExplorationLeadRequest) =>
        apiData(sdk.v2ExplorationLeadsPartialUpdateWithJson(String(leadId), leadData, mapApiOptions())),

    deleteExplorationLead: (leadId: EntityId) =>
        apiData(sdk.v2ExplorationLeadsDestroy(String(leadId), mapApiOptions())),

    // Sensor-Fleets
    getSensorFleets: () =>
        apiData(sdk.v2SensorFleetsList(mapApiOptions())),

    getSensorFleetDetails: (fleetId: EntityId) =>
        apiData(sdk.v2SensorFleetsRetrieve(String(fleetId), mapApiOptions())),

    getSensorFleetSensors: (fleetId: EntityId) =>
        apiData(sdk.v2SensorFleetsSensorsRetrieve(String(fleetId), mapApiOptions())),

    // Sensor Installs
    getStationSensorInstalls: (stationId: EntityId) =>
        apiData(sdk.v2StationsSensorInstallsList(String(stationId), undefined, mapApiOptions())),

    getStationSensorInstallsWithStatus: (stationId: EntityId, status: string) =>
        apiData(sdk.v2StationsSensorInstallsList(String(stationId), { status }, mapApiOptions())),

    // Preserve the generated response headers alongside the binary export body.
    getStationSensorInstallsAsExcel: (stationId: EntityId) =>
        sdk.v2StationsSensorInstallsExportExcelRetrieve(String(stationId), mapApiOptions()),

    getStationSensorInstallDetails: (stationId: EntityId, installId: EntityId) =>
        apiData(sdk.v2StationsSensorInstallsRetrieve(String(stationId), String(installId), mapApiOptions())),

    createStationSensorInstalls: (stationId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2StationsSensorInstallsCreateWithJson(String(stationId), { ...sensorBody(formData), sensor: formText(formData, 'sensor'), install_date: formText(formData, 'install_date') }, mapApiOptions(options))),

    updateStationSensorInstalls: (stationId: EntityId, installId: EntityId, formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2StationsSensorInstallsPartialUpdateWithJson(String(stationId), String(installId), sensorBody(formData), mapApiOptions(options))),

    // GPS Tracks
    getGPSTracks: () =>
        apiData(sdk.v2GpsTracksList(mapApiOptions())),

    getGPSTrackDetails: (trackId: EntityId, options?: ApiRequestOptions) =>
        apiData(sdk.v2GpsTracksRetrieve(String(trackId), mapApiOptions(options))),

    // GIS Layers (private viewer only)
    getGISLayers: () =>
        apiData(sdk.v2GisLayersList(mapApiOptions())),

    getGISLayerDetails: (layerId: EntityId, options?: ApiRequestOptions) =>
        apiData(sdk.v2GisLayersRetrieve(String(layerId), mapApiOptions(options))),

    // GPX Import
    importGPX: (formData: FormData, options?: Omit<sdk.ApiRequestOptions, 'client'>) =>
        apiData(sdk.v2ImportGpxUpdate(gpxBody(formData), mapApiOptions(options))),

    // ================== CYLINDER FLEETS ================== //

    // Cylinder Fleets
    getCylinderFleets: () =>
        apiData(sdk.v2CylinderFleetsList(mapApiOptions())),

    getCylinderFleetDetails: (fleetId: EntityId) =>
        apiData(sdk.v2CylinderFleetsRetrieve(String(fleetId), mapApiOptions())),

    getCylinderFleetCylinders: (fleetId: EntityId) =>
        apiData(sdk.v2CylinderFleetsCylindersRetrieve(String(fleetId), mapApiOptions())),

    // Cylinder Installs
    getCylinderInstalls: (params: sdk.V2CylinderInstallsListParams = {}) =>
        apiData(sdk.v2CylinderInstallsList(params, mapApiOptions())),

    getCylinderInstallsGeoJSON: () =>
        apiData(sdk.v2CylinderInstallsGeojsonRetrieve(mapApiOptions())),

    getAllCylinderInstallsGeoJSON: () =>
        apiData(sdk.v2CylinderInstallsGeojsonRetrieve(mapApiOptions())),

    createCylinderInstall: (installData: sdk.CylinderInstallCreateRequestRequest) =>
        apiData(sdk.v2CylinderInstallsCreateWithJson(installData, mapApiOptions())),

    getCylinderInstallDetails: (installId: EntityId) =>
        apiData(sdk.v2CylinderInstallsRetrieve(String(installId), mapApiOptions())),

    updateCylinderInstall: (installId: EntityId, installData: sdk.PatchedCylinderInstallRequest) =>
        apiData(sdk.v2CylinderInstallsPartialUpdateWithJson(String(installId), installData, mapApiOptions())),

    deleteCylinderInstall: (installId: EntityId) =>
        apiData(sdk.v2CylinderInstallsDestroy(String(installId), mapApiOptions())),

    // Cylinder Pressure Checks
    getCylinderPressureChecks: (installId: EntityId) =>
        apiData(sdk.v2CylinderInstallsPressureChecksList(String(installId), mapApiOptions())),

    createCylinderPressureCheck: (installId: EntityId, checkData: sdk.CylinderPressureCheckRequest) =>
        apiData(sdk.v2CylinderInstallsPressureChecksCreateWithJson(String(installId), checkData, mapApiOptions())),

    getCylinderPressureCheckDetails: (installId: EntityId, checkId: EntityId) =>
        apiData(sdk.v2CylinderInstallsPressureChecksRetrieve(String(installId), String(checkId), mapApiOptions())),

    updateCylinderPressureCheck: (installId: EntityId, checkId: EntityId, checkData: sdk.PatchedCylinderPressureCheckRequest) =>
        apiData(sdk.v2CylinderInstallsPressureChecksPartialUpdateWithJson(String(installId), String(checkId), checkData, mapApiOptions())),

    deleteCylinderPressureCheck: (installId: EntityId, checkId: EntityId) =>
        apiData(sdk.v2CylinderInstallsPressureChecksDestroy(String(installId), String(checkId), mapApiOptions())),
};
