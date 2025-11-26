export const State = {
    map: null,
    projectLayerStates: new Map(), // Track visibility state for each project
    userTags: [], // Store all user's tags
    tagColors: [], // Store predefined colors
    currentStationForTagging: null, // Track which station is being tagged
    allProjectLayers: new Map(), // Track all layer IDs for each project
    currentProjectId: null, // Track currently selected project for station creation
    allStations: new Map(), // Track all stations (demo + API) by ID for easy access
    allPOIs: new Map(), // Track all POIs by ID for easy access
    projectBounds: new Map(), // Track bounds for each project for auto-zoom and fly-to
    
    // Initializer to reset state if needed
    init: function() {
        this.projectLayerStates = new Map();
        this.allProjectLayers = new Map();
        this.allStations = new Map();
        this.allPOIs = new Map();
        this.projectBounds = new Map();
    }
};


