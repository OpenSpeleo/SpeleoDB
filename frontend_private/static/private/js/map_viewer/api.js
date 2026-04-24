import { Utils } from './utils.js';

const parseResponseBody = async response => {
    const contentType = response.headers?.get?.('content-type') || '';

    if (contentType.includes('application/json')) {
        try {
            return await response.json();
        } catch {
            return null;
        }
    }

    if (typeof response.text === 'function') {
        const text = await response.text();
        if (!text) {
            return null;
        }

        try {
            return JSON.parse(text);
        } catch {
            return text;
        }
    }

    if (typeof response.json === 'function') {
        try {
            return await response.json();
        } catch {
            return null;
        }
    }

    return null;
};

const getErrorMessage = (response, data) => {
    if (data && typeof data === 'object') {
        return data.message || data.error || data.detail || response.statusText || 'API request failed';
    }

    if (typeof data === 'string' && data.trim()) {
        return data;
    }

    return response.statusText || 'API request failed';
};

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

    const data = await parseResponseBody(response);

    if (!response.ok) {
        const error = new Error(getErrorMessage(response, data));
        error.data = data;
        error.status = response.status;
        throw error;
    }

    return data;
};

export const API = {
    // Stations
    createStation: (projectId, stationData) =>
        apiRequest(Urls['api:v2:project-stations'](projectId), 'POST', stationData),

    updateStation: (stationId, stationData) =>
        apiRequest(Urls['api:v2:station-detail'](stationId), 'PATCH', stationData),

    deleteStation: (stationId) =>
        apiRequest(Urls['api:v2:station-detail'](stationId), 'DELETE'),

    getProjectStations: (projectId) =>
        apiRequest(Urls['api:v2:project-stations'](projectId)),

    getStationDetails: (stationId) =>
        apiRequest(Urls['api:v2:station-detail'](stationId)),

    // All Stations GeoJSON (single API call for all stations)
    getAllStationsGeoJSON: () =>
        apiRequest(Urls['api:v2:subsurface-stations-geojson']()),

    // Surface Networks
    getAllSurfaceNetworks: () =>
        apiRequest(Urls['api:v2:surface-networks']()),

    // Surface Stations
    createSurfaceStation: (networkId, stationData) =>
        apiRequest(Urls['api:v2:network-stations'](networkId), 'POST', stationData),

    getNetworkStations: (networkId) =>
        apiRequest(Urls['api:v2:network-stations'](networkId)),

    getNetworkStationsGeoJSON: (networkId) =>
        apiRequest(Urls['api:v2:network-stations-geojson'](networkId)),

    getAllSurfaceStations: () =>
        apiRequest(Urls['api:v2:surface-stations']()),

    getAllSurfaceStationsGeoJSON: () =>
        apiRequest(Urls['api:v2:surface-stations-geojson']()),

    // Landmarks
    createLandmark: (landmarkData) =>
        apiRequest(Urls['api:v2:landmarks'](), 'POST', landmarkData),

    updateLandmark: (landmarkId, landmarkData) =>
        apiRequest(Urls['api:v2:landmark-detail'](landmarkId), 'PATCH', landmarkData),

    deleteLandmark: (landmarkId) =>
        apiRequest(Urls['api:v2:landmark-detail'](landmarkId), 'DELETE'),

    getAllLandmarks: () =>
        apiRequest(Urls['api:v2:landmarks']()),

    // All Landmarks GeoJSON (single API call)
    getAllLandmarksGeoJSON: () =>
        apiRequest(Urls['api:v2:landmarks-geojson']()),

    // Tags
    getUserTags: () =>
        apiRequest(Urls['api:v2:station-tags']()),

    getTagColors: () =>
        apiRequest(Urls['api:v2:station-tag-colors']()),

    createTag: (name, color) =>
        apiRequest(Urls['api:v2:station-tags'](), 'POST', { name, color }),

    setStationTag: (stationId, tagId) =>
        apiRequest(Urls['api:v2:station-tags-manage'](stationId), 'POST', { tag_id: tagId }),

    removeStationTag: (stationId) =>
        apiRequest(Urls['api:v2:station-tags-manage'](stationId), 'DELETE'),

    // Station Logs
    getStationLogs: (stationId) =>
        apiRequest(Urls['api:v2:station-logs'](stationId)),

    createStationLog: (stationId, formData) =>
        apiRequest(Urls['api:v2:station-logs'](stationId), 'POST', formData, true),

    updateStationLog: (logId, formData) =>
        apiRequest(Urls['api:v2:log-detail'](logId), 'PATCH', formData, true),

    deleteStationLog: (logId) =>
        apiRequest(Urls['api:v2:log-detail'](logId), 'DELETE'),

    // Experiments
    getExperiments: () =>
        apiRequest(Urls['api:v2:experiments']()),

    getExperimentData: (stationId, experimentId) =>
        apiRequest(Urls['api:v2:experiment-records'](stationId, experimentId)),

    createExperimentRecord: (stationId, experimentId, recordData) =>
        apiRequest(Urls['api:v2:experiment-records'](stationId, experimentId), 'POST', recordData),

    updateExperimentRecord: (recordId, recordData) =>
        apiRequest(Urls['api:v2:experiment-records-detail'](recordId), 'PUT', recordData),

    deleteExperimentRecord: (recordId) =>
        apiRequest(Urls['api:v2:experiment-records-detail'](recordId), 'DELETE'),

    // Resources
    getStationResources: (stationId) =>
        apiRequest(Urls['api:v2:station-resources'](stationId)),

    createStationResource: (stationId, formData) =>
        apiRequest(Urls['api:v2:station-resources'](stationId), 'POST', formData, true),

    updateStationResource: (resourceId, formData) =>
        apiRequest(Urls['api:v2:resource-detail'](resourceId), 'PATCH', formData, true),

    deleteStationResource: (resourceId) =>
        apiRequest(Urls['api:v2:resource-detail'](resourceId), 'DELETE'),

    // Projects
    getAllProjects: () =>
        apiRequest(Urls['api:v2:projects']()),

    getAllProjectsGeoJSON: () =>
        apiRequest(Urls['api:v2:all-projects-geojson']()),

    // Exploration Leads
    getProjectExplorationLeadsGeoJSON: (projectId) =>
        apiRequest(Urls['api:v2:project-exploration-leads-geojson'](projectId)),

    getAllProjectExplorationLeadsGeoJSON: () =>
        apiRequest(Urls['api:v2:exploration-lead-all-geojson']()),

    getProjectExplorationLeads: (projectId) =>
        apiRequest(Urls['api:v2:project-exploration-leads'](projectId)),

    createExplorationLead: (projectId, leadData) =>
        apiRequest(Urls['api:v2:project-exploration-leads'](projectId), 'POST', leadData),

    updateExplorationLead: (leadId, leadData) =>
        apiRequest(Urls['api:v2:exploration-lead-detail'](leadId), 'PATCH', leadData),

    deleteExplorationLead: (leadId) =>
        apiRequest(Urls['api:v2:exploration-lead-detail'](leadId), 'DELETE'),

    // Sensor-Fleets
    getSensorFleets: () =>
        apiRequest(Urls['api:v2:sensor-fleets']()),

    getSensorFleetDetails: (fleetId) =>
        apiRequest(Urls['api:v2:sensor-fleet-detail'](fleetId)),

    getSensorFleetSensors: (fleetId) =>
        apiRequest(Urls['api:v2:sensor-fleet-sensors'](fleetId)),

    // Sensor Installs
    getStationSensorInstalls: (stationId) =>
        apiRequest(Urls['api:v2:station-sensor-installs'](stationId)),

    getStationSensorInstallsWithStatus: (stationId, status) =>
        apiRequest(Urls['api:v2:station-sensor-installs'](stationId) + "?status=" + status),

    // Returns raw Response object for blob download (not parsed JSON)
    getStationSensorInstallsAsExcel: async (stationId) => {
        const response = await fetch(Urls['api:v2:station-sensor-installs-export'](stationId), {
            method: 'GET',
            headers: {
                'X-CSRFToken': Utils.getCSRFToken()
            },
            credentials: 'same-origin'
        });
        return response;  // Return raw Response for blob handling
    },

    getStationSensorInstallDetails: (stationId, installId) =>
        apiRequest(Urls['api:v2:station-sensor-install-detail'](stationId, installId)),

    createStationSensorInstalls: (stationId, formData) =>
        apiRequest(Urls['api:v2:station-sensor-installs'](stationId), 'POST', formData, true),

    updateStationSensorInstalls: (stationId, installId, formData) =>
        apiRequest(Urls['api:v2:station-sensor-install-detail'](stationId, installId), 'PATCH', formData, true),

    // GPS Tracks
    getGPSTracks: () =>
        apiRequest(Urls['api:v2:gps-tracks']()),

    // GPX Import
    importGPX: (formData) =>
        apiRequest(Urls['api:v2:gpx-import'](), 'PUT', formData, true),

    // ================== CYLINDER FLEETS ================== //

    // Cylinder Fleets
    getCylinderFleets: () =>
        apiRequest(Urls['api:v2:cylinder-fleets']()),

    getCylinderFleetDetails: (fleetId) =>
        apiRequest(Urls['api:v2:cylinder-fleet-detail'](fleetId)),

    getCylinderFleetCylinders: (fleetId) =>
        apiRequest(Urls['api:v2:cylinder-fleet-cylinders'](fleetId)),

    // Cylinder Installs
    getCylinderInstalls: (params = {}) => {
        let url = Urls['api:v2:cylinder-installs']();
        const queryParams = [];
        if (params.cylinder_id) queryParams.push(`cylinder_id=${params.cylinder_id}`);
        if (params.fleet_id) queryParams.push(`fleet_id=${params.fleet_id}`);
        if (params.status) queryParams.push(`status=${params.status}`);
        if (queryParams.length > 0) url += '?' + queryParams.join('&');
        return apiRequest(url);
    },

    getCylinderInstallsGeoJSON: () =>
        apiRequest(Urls['api:v2:cylinder-installs-geojson']()),

    getAllCylinderInstallsGeoJSON: () =>
        apiRequest(Urls['api:v2:cylinder-installs-geojson']()),

    createCylinderInstall: (installData) =>
        apiRequest(Urls['api:v2:cylinder-installs'](), 'POST', installData),

    getCylinderInstallDetails: (installId) =>
        apiRequest(Urls['api:v2:cylinder-install-detail'](installId)),

    updateCylinderInstall: (installId, installData) =>
        apiRequest(Urls['api:v2:cylinder-install-detail'](installId), 'PATCH', installData),

    deleteCylinderInstall: (installId) =>
        apiRequest(Urls['api:v2:cylinder-install-detail'](installId), 'DELETE'),

    // Cylinder Pressure Checks
    getCylinderPressureChecks: (installId) =>
        apiRequest(Urls['api:v2:cylinder-install-pressure-checks'](installId)),

    createCylinderPressureCheck: (installId, checkData) =>
        apiRequest(Urls['api:v2:cylinder-install-pressure-checks'](installId), 'POST', checkData),

    getCylinderPressureCheckDetails: (installId, checkId) =>
        apiRequest(Urls['api:v2:cylinder-pressure-check-detail'](installId, checkId)),

    updateCylinderPressureCheck: (installId, checkId, checkData) =>
        apiRequest(Urls['api:v2:cylinder-pressure-check-detail'](installId, checkId), 'PATCH', checkData),

    deleteCylinderPressureCheck: (installId, checkId) =>
        apiRequest(Urls['api:v2:cylinder-pressure-check-detail'](installId, checkId), 'DELETE'),
};





