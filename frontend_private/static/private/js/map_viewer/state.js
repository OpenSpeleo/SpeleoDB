export const State = {
    map: null,
    projectLayerStates: new Map(), // Track visibility state for each project
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
    projectBounds: new Map(), // Track bounds for each project for auto-zoom and fly-to
    networkBounds: new Map(), // Track bounds for each network for auto-zoom and fly-to

    // Landmark visibility state (default: true = visible)
    landmarksVisible: true,

    // GPS Tracks state
    gpsTrackLayerStates: new Map(), // Track visibility state for each GPS track (default: all OFF)
    gpsTrackCache: new Map(), // Cache downloaded GeoJSON data by track ID
    gpsTrackLoadingStates: new Map(), // Track which GPS tracks are currently loading
    allGPSTrackLayers: new Map(), // Track all layer IDs for each GPS track
    gpsTrackBounds: new Map(), // Track bounds for each GPS track for fly-to

    // Initializer to reset state if needed
    init: function () {
        this.projectLayerStates = new Map();
        this.networkLayerStates = new Map();
        this.allProjectLayers = new Map();
        this.allNetworkLayers = new Map();
        this.allStations = new Map();
        this.allSurfaceStations = new Map();
        this.allLandmarks = new Map();
        this.projectBounds = new Map();
        this.networkBounds = new Map();
        this.landmarksVisible = true;
        // GPS Tracks
        this.gpsTrackLayerStates = new Map();
        this.gpsTrackCache = new Map();
        this.gpsTrackLoadingStates = new Map();
        this.allGPSTrackLayers = new Map();
        this.gpsTrackBounds = new Map();
    }
};


