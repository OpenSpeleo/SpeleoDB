import { DEFAULTS } from './config.js';

export function createDefaultDisplayPreferences() {
    return {
        colorMode: DEFAULTS.DISPLAY.COLOR_MODE,
        depthLimitFeet: DEFAULTS.DEPTH.LIMIT_FEET,
        depthUnit: DEFAULTS.DEPTH.UNIT,
        categories: Object.fromEntries(DEFAULTS.DISPLAY.CATEGORIES.map(({ id }) => [id, true])),
        stationTypes: Object.fromEntries(DEFAULTS.DISPLAY.STATION_TYPES.map(({ id }) => [id, true])),
    };
}

export const State = {
    map: null,
    displayPreferences: createDefaultDisplayPreferences(),
    projectLayerStates: new Map(), // Individual user preference per project
    effectiveProjectVisibility: new Map(), // Actual map visibility (preference AND country gate)
    networkLayerStates: new Map(), // Track visibility state for each network
    userTags: [], // Store all user's tags
    tagColors: [], // Store predefined colors
    currentStationForTagging: null, // Track which station is being tagged
    allProjectLayers: new Map(), // Track all layer IDs for each project
    allNetworkLayers: new Map(), // Track all layer IDs for each network
    currentProjectId: null, // Track currently selected project for station creation
    allStations: new Map(), // Track all subsurface stations (demo + API) by ID for easy access
    allSurfaceStations: new Map(), // Track all surface stations by ID for easy access
    allLandmarks: new Map(), // Track all Landmarks by ID for easy access
    landmarkCollections: new Map(), // Track Landmark Collections by ID for selectors/grouping
    projectDepthDomains: new Map(), // Per-project depth domain cache ({ min, max } | null)
    activeDepthDomain: null, // Merged depth domain for currently visible projects
    projectBounds: new Map(), // Track bounds for each project for auto-zoom and fly-to
    networkBounds: new Map(), // Track bounds for each network for auto-zoom and fly-to

    // Local-only markers (not yet persisted to API)
    explorationLeads: new Map(), // Track exploration lead markers by ID

    // Cylinder installs (persistent from database)
    cylinderInstalls: new Map(), // Track cylinder installs by ID for easy access

    // Existing consumers share the canonical preference rather than a second flag.
    get landmarksVisible() { return this.displayPreferences.categories.landmarks; },
    set landmarksVisible(visible) { this.displayPreferences.categories.landmarks = visible; },

    // GPS Tracks state
    gpsTrackLayerStates: new Map(), // Track visibility state for each GPS track (default: all OFF)
    gpsTrackCache: new Map(), // Cache downloaded GeoJSON data by track ID
    gpsTrackLoadingStates: new Map(), // Track which GPS tracks are currently loading
    allGPSTrackLayers: new Map(), // Track all layer IDs for each GPS track
    gpsTrackBounds: new Map(), // Track bounds for each GPS track for fly-to

    // GIS Layers state (session-only, default OFF)
    gisLayerStates: new Map(),
    gisLayerCache: new Map(),
    gisLayerLoadingStates: new Map(),
    allGISLayerLayers: new Map(),
    gisLayerBounds: new Map(),
    gisLayerClickableLayerIds: new Set(),

    // GIS Geometry is private, lazy-loaded, and hidden on every fresh session.
    gisGeometryStates: new Map(),
    gisGeometryCache: new Map(),
    gisGeometryLoading: new Map(),
    allGISGeometryLayers: new Map(),
    gisGeometryBounds: new Map(),
    gisGeometryEditingId: null,

    // Resets layer and map data state. Does NOT reset map instance,
    // userTags, tagColors, currentStationForTagging, currentProjectId, or display
    // preferences. Route initialization, not a map-data reload, resets preferences.
    resetLayerState: function () {
        this.projectLayerStates = new Map();
        this.effectiveProjectVisibility = new Map();
        this.networkLayerStates = new Map();
        this.allProjectLayers = new Map();
        this.allNetworkLayers = new Map();
        this.allStations = new Map();
        this.allSurfaceStations = new Map();
        this.allLandmarks = new Map();
        this.landmarkCollections = new Map();
        this.projectDepthDomains = new Map();
        this.activeDepthDomain = null;
        this.projectBounds = new Map();
        this.networkBounds = new Map();
        this.explorationLeads = new Map();
        this.cylinderInstalls = new Map();
        // GPS Tracks
        this.gpsTrackLayerStates = new Map();
        this.gpsTrackCache = new Map();
        this.gpsTrackLoadingStates = new Map();
        this.allGPSTrackLayers = new Map();
        this.gpsTrackBounds = new Map();
        // GIS Layers
        this.gisLayerStates = new Map();
        this.gisLayerCache = new Map();
        this.gisLayerLoadingStates = new Map();
        this.allGISLayerLayers = new Map();
        this.gisLayerBounds = new Map();
        this.gisLayerClickableLayerIds = new Set();
        this.gisGeometryStates = new Map();
        this.gisGeometryCache = new Map();
        this.gisGeometryLoading = new Map();
        this.allGISGeometryLayers = new Map();
        this.gisGeometryBounds = new Map();
        this.gisGeometryEditingId = null;
    }
};
