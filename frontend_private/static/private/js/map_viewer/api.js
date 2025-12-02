import { Utils } from './utils.js';

const apiRequest = async (url, method = 'GET', body = null, isFormData = false) => {
    const headers = {
        'X-CSRFToken': Utils.getCSRFToken()
    };

    if (!isFormData) {
        headers['Content-Type'] = 'application/json';
    }

    const config = {
        method,
        headers,
        credentials: 'same-origin'
    };

    if (body) {
        config.body = isFormData ? body : JSON.stringify(body);
    }

    const response = await fetch(url, config);

    // Handle 204 No Content
    if (response.status === 204) {
        return { ok: true, status: 204 };
    }

    const data = await response.json();

    if (!response.ok) {
        const error = new Error(data.message || data.error || data.detail || 'API request failed');
        error.data = data;
        error.status = response.status;
        throw error;
    }

    return data;
};

export const API = {
    // Stations
    createStation: (projectId, stationData) =>
        apiRequest(Urls['api:v1:project-stations'](projectId), 'POST', stationData),

    updateStation: (stationId, stationData) =>
        apiRequest(Urls['api:v1:station-detail'](stationId), 'PATCH', stationData),

    deleteStation: (stationId) =>
        apiRequest(Urls['api:v1:station-detail'](stationId), 'DELETE'),

    getProjectStations: (projectId) =>
        apiRequest(Urls['api:v1:project-stations'](projectId)),

    getStationDetails: (stationId) =>
        apiRequest(Urls['api:v1:station-detail'](stationId)),

    // All Stations GeoJSON (single API call for all stations)
    getAllStationsGeoJSON: () =>
        apiRequest(Urls['api:v1:stations-geojson']()),

    // Surface Networks
    getAllSurfaceNetworks: () =>
        apiRequest(Urls['api:v1:surface-networks']()),

    // Surface Stations
    createSurfaceStation: (networkId, stationData) =>
        apiRequest(Urls['api:v1:network-stations'](networkId), 'POST', stationData),

    getNetworkStations: (networkId) =>
        apiRequest(Urls['api:v1:network-stations'](networkId)),

    getNetworkStationsGeoJSON: (networkId) =>
        apiRequest(Urls['api:v1:network-stations-geojson'](networkId)),

    getAllSurfaceStations: () =>
        apiRequest(Urls['api:v1:surface-stations']()),

    getAllSurfaceStationsGeoJSON: () =>
        apiRequest(Urls['api:v1:surface-stations-geojson']()),

    // Landmarks
    createLandmark: (poiData) =>
        apiRequest(Urls['api:v1:landmarks'](), 'POST', poiData),

    updateLandmark: (poiId, poiData) =>
        apiRequest(Urls['api:v1:landmark-detail'](poiId), 'PATCH', poiData),

    deleteLandmark: (poiId) =>
        apiRequest(Urls['api:v1:landmark-detail'](poiId), 'DELETE'),

    getAllLandmarks: () =>
        apiRequest(Urls['api:v1:landmarks']()),

    // All Landmarks GeoJSON (single API call)
    getAllLandmarksGeoJSON: () =>
        apiRequest(Urls['api:v1:landmarks-geojson']()),

    // Tags
    getUserTags: () =>
        apiRequest(Urls['api:v1:station-tags']()),

    getTagColors: () =>
        apiRequest(Urls['api:v1:station-tag-colors']()),

    createTag: (name, color) =>
        apiRequest(Urls['api:v1:station-tags'](), 'POST', { name, color }),

    setStationTag: (stationId, tagId) =>
        apiRequest(Urls['api:v1:station-tags-manage'](stationId), 'POST', { tag_id: tagId }),

    removeStationTag: (stationId) =>
        apiRequest(Urls['api:v1:station-tags-manage'](stationId), 'DELETE'),

    // Station Logs
    getStationLogs: (stationId) =>
        apiRequest(Urls['api:v1:station-logs'](stationId)),

    createStationLog: (stationId, formData) =>
        apiRequest(Urls['api:v1:station-logs'](stationId), 'POST', formData, true),

    updateStationLog: (logId, formData) =>
        apiRequest(Urls['api:v1:log-detail'](logId), 'PATCH', formData, true),

    deleteStationLog: (logId) =>
        apiRequest(Urls['api:v1:log-detail'](logId), 'DELETE'),

    // Experiments
    getExperiments: () =>
        apiRequest(Urls['api:v1:experiments']()),

    getExperimentData: (stationId, experimentId) =>
        apiRequest(Urls['api:v1:experiment-records'](stationId, experimentId)),

    // Resources
    getStationResources: (stationId) =>
        apiRequest(Urls['api:v1:station-resources'](stationId)),

    createStationResource: (stationId, formData) =>
        apiRequest(Urls['api:v1:station-resources'](stationId), 'POST', formData, true),

    updateStationResource: (resourceId, formData) =>
        apiRequest(Urls['api:v1:resource-detail'](resourceId), 'PATCH', formData, true),

    deleteStationResource: (resourceId) =>
        apiRequest(Urls['api:v1:resource-detail'](resourceId), 'DELETE'),

    // Projects
    getAllProjects: () =>
        apiRequest(Urls['api:v1:projects']()),

    getAllProjectsGeoJSON: () =>
        apiRequest(Urls['api:v1:all-projects-geojson']()),

    // Sensor-Fleets
    getSensorFleets: () =>
        apiRequest(Urls['api:v1:sensor-fleets']()),

    getSensorFleetDetails: (fleetId) =>
        apiRequest(Urls['api:v1:sensor-fleet-detail'](fleetId)),

    getSensorFleetSensors: (fleetId) =>
        apiRequest(Urls['api:v1:sensor-fleet-sensors'](fleetId)),

    // Sensor Installs
    getStationSensorInstalls: (stationId) =>
        apiRequest(Urls['api:v1:station-sensor-installs'](stationId)),

    getStationSensorInstallsWithStatus: (stationId, status) =>
        apiRequest(Urls['api:v1:station-sensor-installs'](stationId) + "?status=" + status),

    // Returns raw Response object for blob download (not parsed JSON)
    getStationSensorInstallsAsExcel: async (stationId) => {
        const response = await fetch(Urls['api:v1:station-sensor-installs-export'](stationId), {
            method: 'GET',
            headers: {
                'X-CSRFToken': Utils.getCSRFToken()
            },
            credentials: 'same-origin'
        });
        return response;  // Return raw Response for blob handling
    },

    getStationSensorInstallDetails: (stationId, installId) =>
        apiRequest(Urls['api:v1:station-sensor-install-detail'](stationId, installId)),

    createStationSensorInstalls: (stationId, formData) =>
        apiRequest(Urls['api:v1:station-sensor-installs'](stationId), 'POST', formData, true),

    updateStationSensorInstalls: (stationId, installId, formData) =>
        apiRequest(Urls['api:v1:station-sensor-install-detail'](stationId, installId), 'PATCH', formData, true),
};





