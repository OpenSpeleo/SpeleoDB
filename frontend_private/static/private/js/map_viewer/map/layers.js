import { Config } from '../config.js';
import { State } from '../state.js';
import { Colors } from './colors.js';
import {
    buildSectionDepthAverageMap,
    computeProjectDepthDomain,
    mergeDepthDomains,
    resolveLineDepthValue
} from './depth.js';
import { Geometry } from './geometry.js';
import { API } from '../api.js';

// Track whether custom marker images have been loaded
let markerImagesLoaded = false;

const ZOOM_LEVELS = {
    // Survey GeoJSONs
    PROJECT_LINE: 8,
    PROJECT_LINE_LABEL: 14,
    PROJECT_ENTRY_SYMBOL: 10,

    // Landmarks
    LANDMARK_SYMBOL: 12,
    LANDMARK_LABEL: 16,

    // Surface Stations
    SURFACE_STATION_SYMBOL: 12,
    SURFACE_STATION_LABEL: 16,

    // Subsurface Stations
    SUBSURFACE_STATION_SYMBOL: 12,
    SUBSURFACE_STATION_LABEL: 16,

    // Cylinder Installs
    CYLINDER_INSTALL_SYMBOL: 12,
    CYLINDER_INSTALL_LABEL: 16,

    // Exploration Leads
    EXPLORATION_LEAD_SYMBOL: 12,

    // GPS Tracks
    GPS_TRACK_LINE: 8,
};

const PROJECT_SCOPED_MARKER_PROPERTY = 'project_id';
const PROJECT_SCOPED_MARKER_LAYER_IDS = Object.freeze([
    'cylinder-installs-layer',
    'cylinder-installs-labels',
    'exploration-leads-layer'
]);

/**
 * Remove map layers first, then their source to avoid dependent-layer issues.
 */
function removeLayersAndSource(map, layerIds, sourceId) {
    layerIds.forEach((layerId) => {
        if (map.getLayer(layerId)) {
            map.removeLayer(layerId);
        }
    });

    if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
    }
}

/**
 * Build gas mix label text from cylinder percentages.
 */
function getCylinderGasMixTextExpression() {
    return [
        'case',
        ['==', ['get', 'o2_percentage'], 100], 'Oxygen',
        ['>', ['get', 'he_percentage'], 0],
        [
            'concat',
            ['to-string', ['get', 'o2_percentage']],
            '/',
            ['to-string', ['get', 'he_percentage']]
        ],
        ['==', ['get', 'o2_percentage'], 21], 'Air',
        ['concat', 'NX', ['to-string', ['get', 'o2_percentage']]]
    ];
}

/**
 * Build label for cylinder installs: install-date\ngas-mix@pressure.
 */
function getCylinderInstallLabelExpression() {
    return [
        'concat',
        ['coalesce', ['get', 'install_date'], 'Unknown date'],
        '\n',
        getCylinderGasMixTextExpression(),
        '@',
        ['to-string', ['get', 'pressure']],
        ' ',
        ['case',
            ['==', ['get', 'pressure_unit_system'], 'imperial'], 'PSI',
            'BAR'
        ]
    ];
}

/**
 * Add normalized project visibility property to map marker feature properties.
 */
function withProjectScopedMarkerProperties(properties, projectId) {
    return {
        ...properties,
        [PROJECT_SCOPED_MARKER_PROPERTY]: projectId ? String(projectId) : null
    };
}

// Process project GeoJSON once on load/refresh and cache project-level depth domain.
function processGeoJSON(projectId, geojsonData) {
    const pid = String(projectId);
    if (!geojsonData || !Array.isArray(geojsonData.features)) {
        State.projectDepthDomains.set(pid, null);
        return geojsonData;
    }

    const processed = JSON.parse(JSON.stringify(geojsonData));
    const sectionDepthAvgMap = buildSectionDepthAverageMap(processed.features);
    const projectDepthDomain = computeProjectDepthDomain(processed, sectionDepthAvgMap);
    State.projectDepthDomains.set(pid, projectDepthDomain);
    const maxVal = projectDepthDomain ? Math.max(1e-9, projectDepthDomain.max) : 1;

    function forceZero(c) {
        if (!Array.isArray(c) || c.length === 0) return c;
        if (typeof c[0] === 'number') return c.length >= 3 ? [c[0], c[1], 0] : c;
        return c.map(forceZero);
    }

    processed.features.forEach((feature) => {
        // Stamp canonical depth values on lines once; style expressions use depth_val.
        if (feature?.geometry?.type === 'LineString' && feature.properties) {
            const depthValue = resolveLineDepthValue(feature.properties, sectionDepthAvgMap);
            if (typeof depthValue === 'number' && Number.isFinite(depthValue)) {
                const norm = depthValue / maxVal;
                feature.properties.depth_norm = Math.min(Math.max(norm, 0), 1);
                feature.properties.depth_val = depthValue;
            } else {
                delete feature.properties.depth_norm;
                delete feature.properties.depth_val;
            }
        }

        // Force Z=0
        if (feature?.geometry?.coordinates) {
            feature.geometry.coordinates = forceZero(feature.geometry.coordinates);
        }
    });

    return processed;
}

export const Layers = {
    // Current mode
    colorMode: 'project', // 'project' or 'depth'

    // Persist project visibility preferences
    loadProjectVisibilityPrefs: function () {
        try {
            const prefs = localStorage.getItem(Config.VISIBILITY_PREFS_STORAGE_KEY);
            if (prefs) {
                const parsed = JSON.parse(prefs);
                // Apply to state
                Object.keys(parsed).forEach(id => {
                    State.projectLayerStates.set(id, parsed[id]);
                });
            }
        } catch (e) {
            console.error('Error loading visibility prefs', e);
        }
    },

    saveProjectVisibilityPref: function (projectId, isVisible) {
        try {
            State.projectLayerStates.set(String(projectId), isVisible);

            // Serialize Map to Object for storage
            const prefsObj = {};
            State.projectLayerStates.forEach((value, key) => {
                prefsObj[key] = value;
            });

            localStorage.setItem(Config.VISIBILITY_PREFS_STORAGE_KEY, JSON.stringify(prefsObj));
        } catch (e) {
            console.error('Error saving visibility pref', e);
        }
    },

    isProjectVisible: function (projectId) {
        try {
            return State.projectLayerStates.get(String(projectId)) !== false;
        } catch (e) {
            return true;
        }
    },

    /**
     * Build list of currently visible project IDs.
     */
    getVisibleProjectIds: function () {
        return Config.projects
            .map(project => String(project.id))
            .filter(projectId => this.isProjectVisible(projectId));
    },

    getActiveDepthDomain: function () {
        return State.activeDepthDomain;
    },

    emitDepthDomainUpdated: function () {
        const depthDomain = State.activeDepthDomain;
        const detail = {
            domain: depthDomain,
            available: Boolean(depthDomain),
            max: depthDomain ? depthDomain.max : null
        };

        if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') {
            return;
        }

        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', { detail }));
        // Keep legacy event for existing listeners.
        window.dispatchEvent(new CustomEvent('speleo:depth-data-updated', { detail }));
    },

    recomputeActiveDepthDomain: function () {
        const activeDomains = this.getVisibleProjectIds().map((projectId) => {
            return State.projectDepthDomains.get(String(projectId)) || null;
        });
        State.activeDepthDomain = mergeDepthDomains(activeDomains);
        this.emitDepthDomainUpdated();
        return State.activeDepthDomain;
    },

    /**
     * Filter expression for markers tied to project visibility.
     * Markers without project scoping remain visible.
     */
    getProjectScopedMarkerFilter: function () {
        const visibleProjectIds = this.getVisibleProjectIds();
        return [
            'any',
            ['!', ['has', PROJECT_SCOPED_MARKER_PROPERTY]],
            ['==', ['get', PROJECT_SCOPED_MARKER_PROPERTY], null],
            ['in', ['to-string', ['get', PROJECT_SCOPED_MARKER_PROPERTY]], ['literal', visibleProjectIds]]
        ];
    },

    /**
     * Apply project visibility rules to cross-project marker layers.
     */
    applyProjectScopedMarkerVisibility: function () {
        const map = State.map;
        if (!map || !map.getStyle()) return;

        const filter = this.getProjectScopedMarkerFilter();
        PROJECT_SCOPED_MARKER_LAYER_IDS.forEach((layerId) => {
            if (map.getLayer(layerId)) {
                map.setFilter(layerId, filter);
            }
        });
    },

    /**
     * Apply visibility to all tracked layers of one project.
     */
    applyProjectLayerVisibility: function (projectId) {
        const map = State.map;
        if (!map || !map.getStyle()) return;

        const pid = String(projectId);
        const isVisible = this.isProjectVisible(pid);
        const projectLayerIds = State.allProjectLayers.get(pid) || [];

        projectLayerIds.forEach((layerId) => {
            if (map.getLayer(layerId)) {
                map.setLayoutProperty(layerId, 'visibility', isVisible ? 'visible' : 'none');
            }
        });
    },

    /**
     * Apply complete project visibility rules (project layers + scoped markers).
     */
    applyProjectVisibility: function (projectId) {
        this.applyProjectLayerVisibility(projectId);
        this.applyProjectScopedMarkerVisibility();
    },

    // Network visibility preferences
    loadNetworkVisibilityPrefs: function () {
        try {
            const prefs = localStorage.getItem(Config.NETWORK_VISIBILITY_PREFS_STORAGE_KEY);
            if (prefs) {
                const parsed = JSON.parse(prefs);
                Object.keys(parsed).forEach(id => {
                    State.networkLayerStates.set(id, parsed[id]);
                });
            }
        } catch (e) {
            console.error('Error loading network visibility prefs', e);
        }
    },

    saveNetworkVisibilityPref: function (networkId, isVisible) {
        try {
            State.networkLayerStates.set(String(networkId), isVisible);
            const prefsObj = {};
            State.networkLayerStates.forEach((value, key) => {
                prefsObj[key] = value;
            });
            localStorage.setItem(Config.NETWORK_VISIBILITY_PREFS_STORAGE_KEY, JSON.stringify(prefsObj));
        } catch (e) {
            console.error('Error saving network visibility pref', e);
        }
    },

    isNetworkVisible: function (networkId) {
        try {
            return State.networkLayerStates.get(String(networkId)) !== false;
        } catch (e) {
            return true;
        }
    },

    // GPS tracks default to OFF (false) - explicit true required to be visible
    // No persistence - visibility is session-only
    isGPSTrackVisible: function (trackId) {
        try {
            return State.gpsTrackLayerStates.get(String(trackId)) === true;
        } catch (e) {
            return false; // Default to OFF
        }
    },

    // Check if GPS track is currently loading
    isGPSTrackLoading: function (trackId) {
        return State.gpsTrackLoadingStates.get(String(trackId)) === true;
    },

    // Set GPS track loading state
    setGPSTrackLoading: function (trackId, isLoading) {
        State.gpsTrackLoadingStates.set(String(trackId), isLoading);
        // Dispatch event for UI updates
        window.dispatchEvent(new CustomEvent('speleo:gps-track-loading-changed', {
            detail: { trackId, isLoading }
        }));
    },

    // Toggle GPS track visibility - handles lazy loading of GeoJSON
    toggleGPSTrackVisibility: async function (trackId, isVisible, trackUrl) {
        const tid = String(trackId);

        // Update in-memory state (no persistence)
        State.gpsTrackLayerStates.set(tid, isVisible);

        if (isVisible) {
            // Check if we need to download the GeoJSON (lazy loading)
            if (!State.gpsTrackCache.has(tid)) {
                // Start loading
                this.setGPSTrackLoading(tid, true);

                try {
                    console.log(`🔄 Downloading GPS track GeoJSON: ${trackId}`);
                    const response = await fetch(trackUrl);
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    const geojsonData = await response.json();

                    // Cache the data
                    State.gpsTrackCache.set(tid, geojsonData);
                    console.log(`✅ Cached GPS track GeoJSON: ${trackId}`);

                    // Add the layer to the map
                    await this.addGPSTrackLayer(tid, geojsonData);
                } catch (e) {
                    console.error(`❌ Failed to download GPS track ${trackId}:`, e);
                    // Revert visibility state on error
                    State.gpsTrackLayerStates.set(tid, false);
                    this.setGPSTrackLoading(tid, false);
                    return;
                }

                this.setGPSTrackLoading(tid, false);
            } else {
                // Data is cached - just show the existing layers
                this.showGPSTrackLayers(tid, true);
            }
        } else {
            // Hide the layers (don't remove - keep cached)
            this.showGPSTrackLayers(tid, false);
        }
    },

    // Show/hide GPS track layers
    showGPSTrackLayers: function (trackId, isVisible) {
        const map = State.map;
        if (!map || !map.getStyle()) return;

        const layers = State.allGPSTrackLayers.get(String(trackId)) || [];
        layers.forEach(layerId => {
            if (map.getLayer(layerId)) {
                map.setLayoutProperty(layerId, 'visibility', isVisible ? 'visible' : 'none');
            }
        });
    },

    // Add GPS track GeoJSON layers to the map
    addGPSTrackLayer: async function (trackId, geojsonData) {
        const map = State.map;
        if (!map) return;

        const tid = String(trackId);
        const sourceId = `gps-track-source-${tid}`;
        const lineLayerId = `gps-track-line-${tid}`;
        const pointsLayerId = `gps-track-points-${tid}`;

        // Remove existing layers and source if they exist
        removeLayersAndSource(map, [pointsLayerId, lineLayerId], sourceId);

        // Get color for this track
        const color = Colors.getGPSTrackColor(tid);

        // Add source
        map.addSource(sourceId, {
            type: 'geojson',
            data: geojsonData,
            generateId: true
        });

        // Track layers for this GPS track
        if (!State.allGPSTrackLayers.has(tid)) {
            State.allGPSTrackLayers.set(tid, []);
        }
        const trackLayers = State.allGPSTrackLayers.get(tid);

        // GPS track line - simple dotted pattern for clear distinction from survey lines
        map.addLayer({
            id: lineLayerId,
            type: 'line',
            source: sourceId,
            filter: ['==', '$type', 'LineString'],
            minzoom: ZOOM_LEVELS.GPS_TRACK_LINE,
            layout: {
                'line-join': 'round',
                'line-cap': 'round'
            },
            paint: {
                'line-color': color,
                'line-width': ['interpolate', ['linear'], ['zoom'], 6, 3, 10, 4, 14, 5, 18, 7],
                'line-opacity': 1,
                // Simple dots: tiny dash with gap creates dotted effect
                'line-dasharray': [0.1, 1.5]
            }
        });
        trackLayers.push(lineLayerId);

        // Calculate and store bounds for fly-to functionality
        const bounds = new mapboxgl.LngLatBounds();
        if (geojsonData && geojsonData.features) {
            geojsonData.features.forEach(feature => {
                if (feature.geometry && feature.geometry.coordinates) {
                    // Helper to extend bounds recursively
                    const extend = (coords) => {
                        if (typeof coords[0] === 'number') {
                            bounds.extend(coords);
                        } else {
                            coords.forEach(extend);
                        }
                    };
                    extend(feature.geometry.coordinates);
                }
            });
        }

        if (!bounds.isEmpty()) {
            State.gpsTrackBounds.set(tid, bounds);
            console.log(`📍 Calculated bounds for GPS track ${trackId}`);
        }

        console.log(`📍 Added GPS track layers for ${trackId}`);

        // Reorder layers to ensure proper z-ordering
        this.reorderLayers();
    },

    toggleNetworkVisibility: function (networkId, isVisible) {
        const nid = String(networkId);
        this.saveNetworkVisibilityPref(nid, isVisible);

        if (State.map && State.map.getStyle()) {
            const surfaceStationLayerId = `surface-stations-${nid}`;
            const surfaceStationLabelsId = `surface-stations-${nid}-labels`;

            [surfaceStationLayerId, surfaceStationLabelsId].forEach(layerId => {
                if (State.map.getLayer(layerId)) {
                    State.map.setLayoutProperty(
                        layerId,
                        'visibility',
                        isVisible ? 'visible' : 'none'
                    );
                }
            });
        }
    },

    toggleProjectVisibility: function (projectId, isVisible) {
        const pid = String(projectId);

        // Update state and storage
        this.saveProjectVisibilityPref(pid, isVisible);

        // Update button UI
        const button = document.querySelector(`.project-button[data-project-id="${pid}"]`);
        if (button) {
            if (isVisible) {
                button.classList.remove('opacity-50');
                button.querySelector('.project-color-dot').style.backgroundColor = button.dataset.color;
            } else {
                button.classList.add('opacity-50');
                button.querySelector('.project-color-dot').style.backgroundColor = '#94a3b8'; // Slate-400
            }
        }

        // Update map visibility in one place for project layers and scoped markers.
        this.applyProjectVisibility(pid);

        this.recomputeActiveDepthDomain();
        if (this.colorMode === 'depth') {
            this.applyDepthLineColors();
        }
    },

    forEachProjectLineLayer: function (callback) {
        const map = State.map;
        if (!map) return;

        State.allProjectLayers.forEach((layers, projectId) => {
            layers.forEach((layerId) => {
                const layer = map.getLayer(layerId);
                if (layer && layer.type === 'line') {
                    callback(layerId, String(projectId));
                }
            });
        });
    },

    applyProjectLineColors: function () {
        const map = State.map;
        if (!map) return;

        this.forEachProjectLineLayer((layerId, projectId) => {
            map.setPaintProperty(layerId, 'line-color', Colors.getProjectColor(projectId));
        });
    },

    applyDepthLineColors: function () {
        const map = State.map;
        if (!map) return;

        const depthPaint = Colors.getDepthPaint(State.activeDepthDomain);
        this.forEachProjectLineLayer((layerId) => {
            map.setPaintProperty(layerId, 'line-color', depthPaint);
        });
    },

    setColorMode: function (mode) {
        if (mode !== 'project' && mode !== 'depth') return;
        this.colorMode = mode;

        if (mode === 'depth') {
            this.recomputeActiveDepthDomain();
            this.applyDepthLineColors();
            return;
        }

        this.applyProjectLineColors();
    },

    addProjectGeoJSON: async function (projectId, url) {
        const map = State.map;
        if (!map) return;

        const sourceId = `project-geojson-${projectId}`;

        try {
            let data;
            if (map.getSource(sourceId)) {
                // Refresh data
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const rawData = await response.json();
                data = processGeoJSON(projectId, rawData);

                // Cache line features for magnetic snapping
                Geometry.cacheLineFeatures(projectId, data);

                map.getSource(sourceId).setData(data);
            } else {
                // Fetch and add
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const rawData = await response.json();
                data = processGeoJSON(projectId, rawData);

                // Cache line features for magnetic snapping
                Geometry.cacheLineFeatures(projectId, data);

                map.addSource(sourceId, {
                    type: 'geojson',
                    data: data,
                    generateId: true,
                    tolerance: 0  // Prevent line simplification at low zoom levels
                });

                // Use Color Helper
                const color = Colors.getProjectColor(projectId);

                // Track layers
                if (!State.allProjectLayers.has(String(projectId))) {
                    State.allProjectLayers.set(String(projectId), []);
                }
                const projectLayers = State.allProjectLayers.get(String(projectId));

                // // 1. Polygons (Fill & Stroke) - visible from zoom 0
                // const fillLayerId = `project-fill-${projectId}`;
                // const strokeLayerId = `project-stroke-${projectId}`;

                // map.addLayer({
                //     id: fillLayerId,
                //     type: 'fill',
                //     source: sourceId,
                //     filter: ['in', '$type', 'Polygon'],
                //     minzoom: 0,
                //     paint: {
                //         'fill-color': color,
                //         'fill-opacity': 0.6
                //     }
                // });
                // projectLayers.push(fillLayerId);

                // map.addLayer({
                //     id: strokeLayerId,
                //     type: 'line',
                //     source: sourceId,
                //     filter: ['in', '$type', 'Polygon'],
                //     minzoom: 0,
                //     paint: {
                //         'line-color': '#000',
                //         'line-width': 2
                //     }
                // });
                // projectLayers.push(strokeLayerId);

                // 2. Lines (survey lines visible from zoom 0)
                const lineLayerId = `project-layer-${projectId}`;
                map.addLayer({
                    id: lineLayerId,
                    type: 'line',
                    source: sourceId,
                    filter: ['==', '$type', 'LineString'],
                    minzoom: ZOOM_LEVELS.PROJECT_LINE,
                    layout: {
                        'line-join': 'round',
                        'line-cap': 'round'
                    },
                    paint: {
                        'line-color': this.colorMode === 'project'
                            ? color
                            : Colors.getDepthPaint(State.activeDepthDomain),
                        // Thicker lines at low zoom for visibility from high altitude
                        'line-width': ['interpolate', ['linear'], ['zoom'], 0, 2, 6, 2.5, 10, 3, 14, 4, 18, 6],
                        'line-opacity': 1
                    }
                });
                projectLayers.push(lineLayerId);

                // 3. Line Labels
                const labelLayerId = `project-labels-${projectId}`;
                map.addLayer({
                    id: labelLayerId,
                    type: 'symbol',
                    source: sourceId,
                    filter: ['all', ['==', '$type', 'LineString'], ['has', 'section_name']],
                    minzoom: ZOOM_LEVELS.PROJECT_LINE_LABEL,
                    layout: {
                        'text-field': ['get', 'section_name'],
                        'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
                        'text-size': 12,
                        'symbol-placement': 'line',
                        'text-rotation-alignment': 'map',
                        'text-pitch-alignment': 'viewport'
                    },
                    paint: {
                        'text-color': '#ffffff',
                        'text-halo-color': '#000000',
                        'text-halo-width': 2
                    }
                });
                projectLayers.push(labelLayerId);

                // 4. Points
                const pointLayerId = `project-points-${projectId}`;
                map.addLayer({
                    id: pointLayerId,
                    type: 'symbol',
                    source: sourceId,
                    filter: ['==', '$type', 'Point'],
                    minzoom: ZOOM_LEVELS.PROJECT_ENTRY_SYMBOL,
                    layout: {
                        'text-field': '★',
                        'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                        'text-size': ['interpolate', ['linear'], ['zoom'], 8, 18, 14, 24],
                        'text-allow-overlap': true,
                        'text-ignore-placement': true
                    },
                    paint: {
                        'text-color': '#F5E027',
                        'text-halo-color': '#000000',
                        'text-halo-width': 1.5
                    }
                });
                projectLayers.push(pointLayerId);

                // Initial visibility is handled by centralized project-visibility logic.
                this.applyProjectLayerVisibility(projectId);

            }

            // Calculate and store bounds
            const bounds = new mapboxgl.LngLatBounds();
            if (data && data.features) {
                data.features.forEach(feature => {
                    if (feature.geometry && feature.geometry.coordinates) {
                        // Helper to extend bounds recursively
                        const extend = (coords) => {
                            if (typeof coords[0] === 'number') {
                                bounds.extend(coords);
                            } else {
                                coords.forEach(extend);
                            }
                        };
                        extend(feature.geometry.coordinates);
                    }
                });
            }

            if (!bounds.isEmpty()) {
                State.projectBounds.set(String(projectId), bounds);
            }

            this.recomputeActiveDepthDomain();
            if (this.colorMode === 'depth') {
                this.applyDepthLineColors();
            }

        } catch (e) {
            console.error(`Error loading GeoJSON for project ${projectId}`, e);
        }
    },

    addSubSurfaceStationLayer: function (projectId, data) {
        const map = State.map;
        if (!map) return;

        const sourceId = `stations-source-${projectId}`;
        const circleLayerId = `stations-${projectId}-circles`;
        const biologyLayerId = `stations-${projectId}-biology-icons`;
        const boneLayerId = `stations-${projectId}-bone-icons`;
        const artifactLayerId = `stations-${projectId}-artifact-icons`;
        const geologyLayerId = `stations-${projectId}-geology-icons`;
        const labelLayerId = `stations-${projectId}-labels`;

        console.log(`📍 Adding ${data.features?.length || 0} stations to map for project ${projectId}`);

        // Remove existing layers and source if they exist (for refresh)
        removeLayersAndSource(
            map,
            [labelLayerId, geologyLayerId, artifactLayerId, boneLayerId, biologyLayerId, circleLayerId],
            sourceId
        );

        if (!data.features || data.features.length === 0) {
            console.log(`📍 No stations to display for project ${projectId}`);
            return;
        }

        // Ensure id and color properties are set on each feature
        // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
        data.features.forEach(feature => {
            if (feature.id && !feature.properties.id) {
                feature.properties.id = feature.id;
            }
            if (!feature.properties.color) {
                // Use tag color if available, otherwise use default orange
                const tag = feature.properties.tag;
                feature.properties.color = (tag && tag.color) ? tag.color : '#fb923c';
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: data,
            promoteId: 'id'
        });

        // Add Circle Layer for Sensor stations (type is null, undefined, or 'sensor')
        // Use data-driven color from feature properties
        map.addLayer({
            id: circleLayerId,
            type: 'circle',
            source: sourceId,
            filter: ['any',
                ['!', ['has', 'type']],
                ['==', ['get', 'type'], null],
                ['==', ['get', 'type'], 'sensor']
            ],
            minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
            paint: {
                'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 5, 18, 8],
                'circle-color': ['coalesce', ['get', 'color'], '#fb923c'],
                'circle-stroke-width': 2,
                'circle-stroke-color': '#ffffff',
                'circle-opacity': 1
            }
        });

        // Add Biology Station Icon Layer (for type === 'biology')
        if (map.hasImage('biology-station-icon')) {
            map.addLayer({
                id: biologyLayerId,
                type: 'symbol',
                source: sourceId,
                filter: ['==', ['get', 'type'], 'biology'],
                minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
                layout: {
                    'icon-image': 'biology-station-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        }

        // Add Bone Station Icon Layer (for type === 'bone')
        if (map.hasImage('bone-station-icon')) {
            map.addLayer({
                id: boneLayerId,
                type: 'symbol',
                source: sourceId,
                filter: ['==', ['get', 'type'], 'bone'],
                minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
                layout: {
                    'icon-image': 'bone-station-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        }

        // Add Artifact Station Icon Layer (for type === 'artifact')
        if (map.hasImage('artifact-station-icon')) {
            map.addLayer({
                id: artifactLayerId,
                type: 'symbol',
                source: sourceId,
                filter: ['==', ['get', 'type'], 'artifact'],
                minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
                layout: {
                    'icon-image': 'artifact-station-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        }

        // Add Geology Station Icon Layer (for type === 'geology')
        if (map.hasImage('geology-station-icon')) {
            map.addLayer({
                id: geologyLayerId,
                type: 'symbol',
                source: sourceId,
                filter: ['==', ['get', 'type'], 'geology'],
                minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
                layout: {
                    'icon-image': 'geology-station-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        }

        // Add Label Layer for all station types
        map.addLayer({
            id: labelLayerId,
            type: 'symbol',
            source: sourceId,
            minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_LABEL,
            layout: {
                'text-field': ['get', 'name'],
                'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
                'text-offset': [0, 1.2],
                'text-size': 12,
                'text-anchor': 'top',
                'text-allow-overlap': false,
                'text-ignore-placement': false
            },
            paint: {
                'text-color': '#222',
                'text-halo-color': '#ffffff',
                'text-halo-width': 2
            }
        });

        // Track layers
        if (!State.allProjectLayers.has(String(projectId))) {
            State.allProjectLayers.set(String(projectId), []);
        }
        const projectLayers = State.allProjectLayers.get(String(projectId));
        const newLayers = [circleLayerId, biologyLayerId, boneLayerId, artifactLayerId, geologyLayerId, labelLayerId];
        newLayers.forEach(layerId => {
            if (!projectLayers.includes(layerId)) {
                projectLayers.push(layerId);
            }
        });

        // Respect initial visibility through centralized project-layer logic.
        this.applyProjectLayerVisibility(projectId);
    },

    addLandmarkLayer: function (data) {
        const map = State.map;
        if (!map) return;

        const sourceId = 'landmarks-source';

        console.log(`📍 Adding ${data.features?.length || 0} Landmarks to map`);

        // Remove existing layer and source if they exist (to refresh)
        removeLayersAndSource(map, ['landmarks-labels', 'landmarks-layer'], sourceId);

        if (!data.features || data.features.length === 0) {
            console.log('📍 No Landmarks to display');
            return;
        }

        // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
        data.features.forEach(feature => {
            if (feature.id && !feature.properties.id) {
                feature.properties.id = feature.id;
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: data,
            promoteId: 'id'
        });

        // Determine initial visibility based on state
        const visibility = State.landmarksVisible ? 'visible' : 'none';

        // Landmark symbol layer (triangle marker visible from far zoom)
        map.addLayer({
            id: 'landmarks-layer',
            type: 'symbol',
            source: sourceId,
            minzoom: ZOOM_LEVELS.LANDMARK_SYMBOL,
            layout: {
                'text-field': '▼',  // Triangle pointing down
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                'text-size': ['interpolate', ['linear'], ['zoom'], 6, 10, 10, 14, 14, 20, 18, 28],
                'text-allow-overlap': true,
                'text-ignore-placement': true,
                'visibility': visibility
            },
            paint: {
                'text-color': '#3b82f6',
                'text-halo-color': '#ffffff',
                'text-halo-width': 2,
                'text-halo-blur': 0.5
            }
        });

        // Landmark labels (visible from moderate zoom)
        map.addLayer({
            id: 'landmarks-labels',
            type: 'symbol',
            source: sourceId,
            minzoom: ZOOM_LEVELS.LANDMARK_LABEL,
            layout: {
                'text-field': ['get', 'name'],
                'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
                'text-offset': [0, 1.5],
                'text-size': ['interpolate', ['linear'], ['zoom'], 10, 10, 14, 12, 18, 14],
                'text-anchor': 'top',
                'text-allow-overlap': false,
                'visibility': visibility
            },
            paint: {
                'text-color': '#3b82f6',
                'text-halo-color': '#ffffff',
                'text-halo-width': 1.5
            }
        });
    },

    toggleLandmarkVisibility: function (isVisible) {
        State.landmarksVisible = isVisible;

        if (State.map && State.map.getStyle()) {
            const layerIds = ['landmarks-layer', 'landmarks-labels'];

            layerIds.forEach(layerId => {
                if (State.map.getLayer(layerId)) {
                    State.map.setLayoutProperty(
                        layerId,
                        'visibility',
                        isVisible ? 'visible' : 'none'
                    );
                }
            });

            console.log(`📍 Landmarks visibility: ${isVisible ? 'visible' : 'hidden'}`);
        }
    },

    // Surface Station Layer - uses diamond (◆) symbol instead of circle
    addSurfaceStationLayer: function (networkId, data) {
        const map = State.map;
        if (!map) return;

        const sourceId = `surface-stations-source-${networkId}`;
        const symbolLayerId = `surface-stations-${networkId}`;
        const labelLayerId = `surface-stations-${networkId}-labels`;

        console.log(`📍 Adding ${data.features?.length || 0} surface stations to map for network ${networkId}`);

        // Remove existing layer and source if they exist (for refresh)
        removeLayersAndSource(map, [labelLayerId, symbolLayerId], sourceId);

        if (!data.features || data.features.length === 0) {
            console.log(`📍 No surface stations to display for network ${networkId}`);
            return;
        }

        // Ensure id and color properties are set on each feature
        // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
        data.features.forEach(feature => {
            if (feature.id && !feature.properties.id) {
                feature.properties.id = feature.id;
            }
            if (!feature.properties.color) {
                // Use tag color if available, otherwise use default orange
                const tag = feature.properties.tag;
                feature.properties.color = (tag && tag.color) ? tag.color : '#fb923c';
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: data,
            promoteId: 'id'
        });

        // Add Diamond Symbol Layer (◆)
        // Use text-field with unicode diamond instead of circle
        map.addLayer({
            id: symbolLayerId,
            type: 'symbol',
            source: sourceId,
            minzoom: ZOOM_LEVELS.SURFACE_STATION_SYMBOL,
            layout: {
                'text-field': '◆',  // Diamond shape
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                'text-size': ['interpolate', ['linear'], ['zoom'], 14, 16, 18, 24],
                'text-allow-overlap': true,
                'text-ignore-placement': true
            },
            paint: {
                'text-color': ['coalesce', ['get', 'color'], '#fb923c'],
                'text-halo-color': '#ffffff',
                'text-halo-width': 2,
                'text-halo-blur': 0.5
            }
        });

        // Add Label Layer
        map.addLayer({
            id: labelLayerId,
            type: 'symbol',
            source: sourceId,
            minzoom: ZOOM_LEVELS.SURFACE_STATION_LABEL,
            layout: {
                'text-field': ['get', 'name'],
                'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
                'text-offset': [0, 1.2],
                'text-size': 12,
                'text-anchor': 'top',
                'text-allow-overlap': false,
                'text-ignore-placement': false
            },
            paint: {
                'text-color': '#222',
                'text-halo-color': '#ffffff',
                'text-halo-width': 2
            }
        });

        // Track layers
        if (!State.allNetworkLayers.has(String(networkId))) {
            State.allNetworkLayers.set(String(networkId), []);
        }
        const networkLayers = State.allNetworkLayers.get(String(networkId));
        if (!networkLayers.includes(symbolLayerId)) {
            networkLayers.push(symbolLayerId, labelLayerId);
        }

        // Respect initial visibility
        if (!this.isNetworkVisible(networkId)) {
            map.setLayoutProperty(symbolLayerId, 'visibility', 'none');
            map.setLayoutProperty(labelLayerId, 'visibility', 'none');
        }
    },

    updateSurfaceStationPosition: function (networkId, stationId, newCoords) {
        const map = State.map;
        if (!map) return;

        const sourceId = `surface-stations-source-${networkId}`;
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === stationId);
            if (feature) {
                feature.geometry.coordinates = newCoords;
                source.setData(data);

                // Update in our local lookup as well
                const station = State.allSurfaceStations.get(stationId);
                if (station) {
                    station.latitude = newCoords[1];
                    station.longitude = newCoords[0];
                }
            }
        }
    },

    updateSurfaceStationColor: function (networkId, stationId, color) {
        const map = State.map;
        if (!map) return;

        const sourceId = `surface-stations-source-${networkId}`;
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === stationId);
            if (feature) {
                feature.properties.color = color;
                source.setData(data);
            }
        }
    },

    updateSurfaceStationProperties: function (networkId, stationId, properties) {
        const map = State.map;
        if (!map) return;

        const sourceId = `surface-stations-source-${networkId}`;
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === stationId);
            if (feature) {
                // Update all provided properties
                Object.assign(feature.properties, properties);
                source.setData(data);
            }
        }
    },

    refreshSurfaceStationsAfterChange: async function (networkId) {
        window.dispatchEvent(new CustomEvent('speleo:refresh-surface-stations', { detail: { networkId } }));
    },

    updateStationPosition: function (projectId, stationId, newCoords) {
        const map = State.map;
        if (!map) return;

        const sourceId = `stations-source-${projectId}`;
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === stationId);
            if (feature) {
                feature.geometry.coordinates = newCoords;
                source.setData(data);

                // Update in our local lookup as well
                const station = State.allStations.get(stationId);
                if (station) {
                    station.latitude = newCoords[1];
                    station.longitude = newCoords[0];
                }
            }
        }
    },

    updateStationColor: function (projectId, stationId, color) {
        const map = State.map;
        if (!map) return;

        const sourceId = `stations-source-${projectId}`;
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === stationId);
            if (feature) {
                feature.properties.color = color;
                source.setData(data);
            }
        }
    },

    // Update station properties (name, description, etc.) on the map
    updateStationProperties: function (projectId, stationId, properties) {
        const map = State.map;
        if (!map) return;

        const sourceId = `stations-source-${projectId}`;
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === stationId);
            if (feature) {
                // Update all provided properties
                Object.assign(feature.properties, properties);
                source.setData(data);
            }
        }
    },

    revertLandmarkPosition: function (landmarkId, originalCoords) {
        const map = State.map;
        if (!map) return;

        const source = map.getSource('landmarks-source');
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === landmarkId);
            if (feature) {
                feature.geometry.coordinates = originalCoords;
                source.setData(data);

                // Reset internal state if needed
                const landmark = State.allLandmarks.get(landmarkId);
                if (landmark) {
                    landmark.latitude = originalCoords[1];
                    landmark.longitude = originalCoords[0];
                }
            }
        }
    },

    refreshStationsAfterChange: async function (projectId) {
        // This needs to call back to main/manager to fetch data
        // We will trigger a custom event 'speleo:refresh-stations'
        window.dispatchEvent(new CustomEvent('speleo:refresh-stations', { detail: { projectId } }));
    },

    /**
     * Ensure stations, surface stations, Landmarks, and GPS tracks are rendered correctly.
     * GPS tracks should be below survey lines but visible.
     * Call this after all layers are loaded to fix z-ordering.
     */
    reorderLayers: function () {
        const map = State.map;
        if (!map) return;

        console.log('🔄 Reordering layers to ensure proper z-ordering...');

        // Get all layer IDs
        const style = map.getStyle();
        if (!style || !style.layers) return;

        const allLayerIds = style.layers.map(l => l.id);

        // Find all layer types
        const gpsTrackLineLayers = allLayerIds.filter(id => id.startsWith('gps-track-line-'));
        const gpsTrackPointLayers = allLayerIds.filter(id => id.startsWith('gps-track-points-'));
        const stationCircleLayers = allLayerIds.filter(id => id.includes('stations-') && id.includes('-circles') && !id.includes('surface-'));
        const stationBiologyIconLayers = allLayerIds.filter(id => id.includes('stations-') && id.includes('-biology-icons'));
        const stationBoneIconLayers = allLayerIds.filter(id => id.includes('stations-') && id.includes('-bone-icons'));
        const stationArtifactIconLayers = allLayerIds.filter(id => id.includes('stations-') && id.includes('-artifact-icons'));
        const stationGeologyIconLayers = allLayerIds.filter(id => id.includes('stations-') && id.includes('-geology-icons'));
        const stationLabelLayers = allLayerIds.filter(id => id.includes('stations-') && id.includes('-labels') && !id.includes('surface-'));
        const surfaceStationSymbolLayers = allLayerIds.filter(id => id.startsWith('surface-stations-') && !id.includes('-labels'));
        const surfaceStationLabelLayers = allLayerIds.filter(id => id.startsWith('surface-stations-') && id.includes('-labels'));
        const landmarkLayers = allLayerIds.filter(id => id.startsWith('landmarks-'));
        const cylinderInstallLayers = allLayerIds.filter(id => id.startsWith('cylinder-installs'));
        const explorationLeadLayers = allLayerIds.filter(id => id.startsWith('exploration-leads'));

        // Move layers to top in order (later moves go on top)
        // Order: GPS track lines -> GPS track points -> subsurface stations -> surface stations -> Landmarks

        // GPS track line layers
        gpsTrackLineLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // GPS track point layers
        gpsTrackPointLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Subsurface station circles (sensor stations)
        stationCircleLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Subsurface station biology icons
        stationBiologyIconLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Subsurface station bone icons
        stationBoneIconLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Subsurface station artifact icons
        stationArtifactIconLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Subsurface station geology icons
        stationGeologyIconLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Subsurface station labels
        stationLabelLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Surface station symbols
        surfaceStationSymbolLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Surface station labels
        surfaceStationLabelLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Move cylinder install and exploration lead layers
        cylinderInstallLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        explorationLeadLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        // Finally move Landmark layers (on top of everything)
        landmarkLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        console.log('✅ Layer reordering complete');
    },

    /**
     * Load custom marker images from SVG files
     * Uses map.loadImage() for proper CORS handling with S3/CDN hosted assets
     */
    loadMarkerImages: async function () {
        const map = State.map;
        if (!map || markerImagesLoaded) return;

        // Helper to load image using Mapbox's loadImage (handles CORS properly)
        const loadImage = (url) => {
            return new Promise((resolve, reject) => {
                map.loadImage(url, (error, image) => {
                    if (error) reject(error);
                    else resolve(image);
                });
            });
        };

        try {
            // Load pre-colored orange cylinder SVG for cylinder installs
            if (!map.hasImage('cylinder-icon')) {
                const cylinderImage = await loadImage(window.MAPVIEWER_CONTEXT.icons.cylinderOrange);
                map.addImage('cylinder-icon', cylinderImage);
            }

            // Load exploration lead SVG
            if (!map.hasImage('exploration-lead-icon')) {
                const leadImage = await loadImage(window.MAPVIEWER_CONTEXT.icons.explorationLead);
                map.addImage('exploration-lead-icon', leadImage);
            }

            // Load biology icon for biology stations
            if (!map.hasImage('biology-station-icon')) {
                const biologyImage = await loadImage(window.MAPVIEWER_CONTEXT.icons.biology);
                map.addImage('biology-station-icon', biologyImage);
            }

            // Load bone icon for bone stations
            if (!map.hasImage('bone-station-icon')) {
                const boneImage = await loadImage(window.MAPVIEWER_CONTEXT.icons.bone);
                map.addImage('bone-station-icon', boneImage);
            }

            // Load artifact icon for artifact stations
            if (!map.hasImage('artifact-station-icon')) {
                const artifactImage = await loadImage(window.MAPVIEWER_CONTEXT.icons.artifact);
                map.addImage('artifact-station-icon', artifactImage);
            }

            // Load geology icon for geology stations
            if (!map.hasImage('geology-station-icon')) {
                const geologyImage = await loadImage(window.MAPVIEWER_CONTEXT.icons.geology);
                map.addImage('geology-station-icon', geologyImage);
            }

            markerImagesLoaded = true;
            console.log('✅ Custom marker images loaded from SVG files');
        } catch (e) {
            console.error('❌ Error loading marker images:', e);
        }
    },

    /**
     * Add an exploration lead marker to the map
     */
    addExplorationLeadMarker: function (id, coordinates, lineName = 'Survey Line', description = '', projectId = null) {
        const map = State.map;
        if (!map) return;

        // Store in state
        State.explorationLeads.set(id, {
            id,
            coordinates,
            lineName,
            description,
            projectId,
            createdAt: new Date().toISOString()
        });

        // Refresh the exploration leads layer
        this.refreshExplorationLeadsLayer();
        this.reorderLayers();

        console.log(`⚠️ Exploration lead added: ${id} at ${coordinates}`);
    },

    /**
     * Refresh the exploration leads layer with current state
     */
    refreshExplorationLeadsLayer: function () {
        const map = State.map;
        if (!map) return;

        const sourceId = 'exploration-leads-source';
        const layerId = 'exploration-leads-layer';

        // Build GeoJSON from state
        // Mapbox requires promoteId for string IDs - include id in properties
        const features = Array.from(State.explorationLeads.values()).map(marker => ({
            type: 'Feature',
            id: marker.id,
            geometry: {
                type: 'Point',
                coordinates: marker.coordinates
            },
            properties: withProjectScopedMarkerProperties({
                id: marker.id,
                lineName: marker.lineName
            }, marker.projectId)
        }));

        const geojson = {
            type: 'FeatureCollection',
            features
        };

        // Update or create source
        if (map.getSource(sourceId)) {
            map.getSource(sourceId).setData(geojson);
        } else {
            map.addSource(sourceId, {
                type: 'geojson',
                data: geojson,
                promoteId: 'id'
            });

            // Add layer with red exclamation mark icon
            if (map.hasImage('exploration-lead-icon')) {
                map.addLayer({
                    id: layerId,
                    type: 'symbol',
                    source: sourceId,
                    minzoom: ZOOM_LEVELS.EXPLORATION_LEAD_SYMBOL,
                    layout: {
                        'icon-image': 'exploration-lead-icon',
                        'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.4, 18, 0.6],
                        'icon-allow-overlap': true,
                        'icon-ignore-placement': true
                    },
                    paint: {
                        'icon-opacity': 1
                    }
                });
            } else {
                // Fallback: use a circle marker if image not loaded
                map.addLayer({
                    id: layerId,
                    type: 'circle',
                    source: sourceId,
                    minzoom: ZOOM_LEVELS.EXPLORATION_LEAD_SYMBOL,
                    paint: {
                        'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 8, 18, 12],
                        'circle-color': '#EF4444',
                        'circle-stroke-width': 2,
                        'circle-stroke-color': '#ffffff',
                        'circle-opacity': 1
                    }
                });
            }
        }

        this.applyProjectScopedMarkerVisibility();
    },

    /**
     * Remove an exploration lead marker
     */
    removeExplorationLeadMarker: function (id) {
        State.explorationLeads.delete(id);
        this.refreshExplorationLeadsLayer();
        console.log(`⚠️ Exploration lead removed: ${id}`);
    },

    /**
     * Update cylinder install position (for drag)
     */
    updateCylinderInstallPosition: function (markerId, newCoords) {
        const map = State.map;
        if (!map) return;

        const sourceId = 'cylinder-installs-source';
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === markerId || f.properties?.id === markerId);
            if (feature) {
                feature.geometry.coordinates = newCoords;
                source.setData(data);
            }
        }
    },

    /**
     * Update exploration lead position (for drag)
     */
    updateExplorationLeadPosition: function (markerId, newCoords) {
        const marker = State.explorationLeads.get(markerId);
        if (marker) {
            marker.coordinates = newCoords;
            this.refreshExplorationLeadsLayer();
        }
    },

    /**
     * Show marker drag highlight - adds a colored circle behind the marker
     * @param {string} markerType - 'cylinder-install' or 'exploration-lead'
     * @param {Array} coordinates - [lng, lat]
     * @param {boolean} isSnapped - whether currently snapped (green=snapped, amber=not)
     */
    showMarkerDragHighlight: function (markerType, coordinates, isSnapped) {
        const map = State.map;
        if (!map) return;

        const highlightId = 'marker-drag-highlight';
        const highlightSourceId = 'marker-drag-highlight-source';
        const color = isSnapped ? '#10b981' : '#f59e0b'; // Same colors as stations

        const geojson = {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                geometry: { type: 'Point', coordinates }
            }]
        };

        if (map.getSource(highlightSourceId)) {
            map.getSource(highlightSourceId).setData(geojson);
            if (map.getLayer(highlightId)) {
                map.setPaintProperty(highlightId, 'circle-color', color);
            }
        } else {
            map.addSource(highlightSourceId, { type: 'geojson', data: geojson });
            map.addLayer({
                id: highlightId,
                type: 'circle',
                source: highlightSourceId,
                paint: {
                    'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 18, 18, 28],
                    'circle-color': color,
                    'circle-opacity': 0.4,
                    'circle-stroke-width': 3,
                    'circle-stroke-color': color,
                    'circle-stroke-opacity': 0.8
                }
            });
        }
    },

    /**
     * Hide marker drag highlight
     */
    hideMarkerDragHighlight: function () {
        const map = State.map;
        if (!map) return;

        const highlightId = 'marker-drag-highlight';
        const highlightSourceId = 'marker-drag-highlight-source';

        if (map.getLayer(highlightId)) {
            map.removeLayer(highlightId);
        }
        if (map.getSource(highlightSourceId)) {
            map.removeSource(highlightSourceId);
        }
    },

    /**
     * Set marker visual feedback during drag (wrapper for highlight)
     */
    setMarkerDragFeedback: function (markerType, opacity, isSnapped, coordinates) {
        // Show highlight circle at current position
        if (coordinates) {
            this.showMarkerDragHighlight(markerType, coordinates, isSnapped);
        }
    },

    /**
     * Reset marker visual feedback after drag
     */
    resetMarkerDragFeedback: function (markerType) {
        this.hideMarkerDragHighlight();
    },

    /**
     * Load and display installed cylinders from the API
     * Fetches GeoJSON data for all installed cylinders the user has access to
     */
    loadCylinderInstalls: async function () {
        const map = State.map;
        if (!map) return;

        try {
            console.log('🔄 Loading cylinder installs...');
            // GeoJSON endpoint returns raw FeatureCollection via NoWrapResponse
            const geojsonData = await API.getAllCylinderInstallsGeoJSON();

            if (
                geojsonData &&
                geojsonData.type === 'FeatureCollection' &&
                Array.isArray(geojsonData.features)
            ) {
                this.addCylinderInstallsLayer(geojsonData);
                console.log(`✅ Loaded ${geojsonData.features.length} cylinder installs`);
            } else {
                console.log('⚠️ No cylinder installs to display or invalid response format');
            }
        } catch (e) {
            console.error('❌ Failed to load cylinder installs:', e);
        }
    },

    /**
     * Add cylinder installs layer to the map
     */
    addCylinderInstallsLayer: function (geojsonData) {
        const map = State.map;
        if (!map) return;

        const sourceId = 'cylinder-installs-source';
        const layerId = 'cylinder-installs-layer';
        const labelLayerId = 'cylinder-installs-labels';

        console.log(`Adding ${geojsonData.features?.length || 0} cylinder installs to map`);

        // Remove existing layers before removing source (safe refresh order).
        removeLayersAndSource(map, [labelLayerId, layerId], sourceId);

        if (!geojsonData.features || geojsonData.features.length === 0) {
            console.log('No cylinder installs to display');
            return;
        }

        // Clear and populate the cylinder installs cache
        State.cylinderInstalls.clear();
        geojsonData.features.forEach(feature => {
            // Ensure id property is set on each feature for Mapbox promoteId
            if (feature.id && !feature.properties.id) {
                feature.properties.id = feature.id;
            }
            // Cache cylinder install data by ID
            const id = feature.id || feature.properties.id;
            if (id) {
                State.cylinderInstalls.set(id, {
                    id,
                    coordinates: feature.geometry.coordinates,
                    ...feature.properties
                });
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: geojsonData,
            promoteId: 'id'
        });

        // Use cylinder icon if loaded, otherwise fallback
        if (map.hasImage('cylinder-icon')) {
            map.addLayer({
                id: layerId,
                type: 'symbol',
                source: sourceId,
                minzoom: ZOOM_LEVELS.CYLINDER_INSTALL_SYMBOL,
                layout: {
                    'icon-image': 'cylinder-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.8, 18, 1.2],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        } else {
            // Fallback to text symbol
            // Note: Using ● (U+25CF) instead of emoji - Mapbox doesn't support glyphs > 65535
            map.addLayer({
                id: layerId,
                type: 'symbol',
                source: sourceId,
                minzoom: ZOOM_LEVELS.CYLINDER_INSTALL_SYMBOL,
                layout: {
                    'text-field': '●',
                    'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                    'text-size': ['interpolate', ['linear'], ['zoom'], 14, 18, 18, 26],
                    'text-allow-overlap': true,
                    'text-ignore-placement': true
                },
                paint: {
                    'text-color': '#FF6B00',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 2
                }
            });
        }

        // Add label layer for cylinder installs
        map.addLayer({
            id: labelLayerId,
            type: 'symbol',
            source: sourceId,
            minzoom: ZOOM_LEVELS.CYLINDER_INSTALL_LABEL,
            layout: {
                'text-field': getCylinderInstallLabelExpression(),
                'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
                'text-size': 11,
                'text-offset': [0, 1.5],
                'text-anchor': 'top',
                'text-allow-overlap': false,
                'text-ignore-placement': false
            },
            paint: {
                'text-color': '#000000',
                'text-halo-color': '#ffffff',
                'text-halo-width': 1.5
            }
        });

        this.applyProjectScopedMarkerVisibility();

        // Reorder to ensure proper z-ordering
        this.reorderLayers();
    },

    /**
     * Refresh cylinder installs layer (called after install/uninstall)
     */
    refreshCylinderInstallsLayer: async function () {
        await this.loadCylinderInstalls();
    }
};
