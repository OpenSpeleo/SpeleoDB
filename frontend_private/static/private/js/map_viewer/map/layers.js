import { Config } from '../config.js';
import { State } from '../state.js';
import { Colors } from './colors.js';
import { DepthUtils } from './depth.js';
import { Geometry } from './geometry.js';

const ZOOM_LEVELS = {
    // Survey GeoJSONs
    PROJECT_LINE: 8,
    PROJECT_LINE_LABEL: 13,
    PROJECT_ENTRY_SYMBOL: 10,

    // Landmarks
    LANDMARK_SYMBOL: 10,
    LANDMARK_LABEL: 14,

    // Surface Stations
    SURFACE_STATION_SYMBOL: 10,
    SURFACE_STATION_LABEL: 14,

    // Subsurface Stations
    SUBSURFACE_STATION_SYMBOL: 10,
    SUBSURFACE_STATION_LABEL: 14,

    // GPS Tracks
    GPS_TRACK_LINE: 8,
};

// Helper to ensure altitude zero (defined locally or imported if moved to Utils)
function processGeoJSON(geojsonData) {
    if (!geojsonData || !geojsonData.features) return geojsonData;
    const processed = JSON.parse(JSON.stringify(geojsonData));

    // First pass: Calculate Depth Range and Normalize
    // Depth mapping: compute average depth per section_name from Point features
    const sectionDepthAccumulator = new Map();

    processed.features.forEach(feature => {
        const props = feature?.properties;
        const sectionName = DepthUtils.getFeatureSectionName(props);
        const pointDepth = DepthUtils.getFeatureDepthValue(props);

        if (
            feature &&
            feature.geometry &&
            feature.geometry.type === 'Point' &&
            sectionName != null &&
            typeof pointDepth === 'number' && isFinite(pointDepth)
        ) {
            const key = sectionName;
            const arr = sectionDepthAccumulator.get(key) || [];
            arr.push(pointDepth);
            sectionDepthAccumulator.set(key, arr);
        }
    });

    const sectionDepthAvgMap = new Map();
    sectionDepthAccumulator.forEach((arr, key) => {
        if (arr.length > 0) {
            const avg = arr.reduce((a, b) => a + b, 0) / arr.length;
            sectionDepthAvgMap.set(key, avg);
            if (typeof window.depthMin === 'undefined') {
                window.depthMin = Infinity;
                window.depthMax = -Infinity;
            }
            window.depthMax = Math.max(window.depthMax, avg);
            window.depthAvailable = true;
        }
    });

    // Also include depths specified directly on LineString features
    processed.features.forEach(feature => {
        const d = DepthUtils.getFeatureDepthValue(feature?.properties);
        if (
            feature &&
            feature.geometry &&
            feature.geometry.type === 'LineString' &&
            typeof d === 'number' &&
            isFinite(d)
        ) {
            if (typeof window.depthMax === 'undefined') {
                window.depthMax = d;
            } else {
                window.depthMax = Math.max(window.depthMax, d);
            }
            window.depthAvailable = true;
        }
    });

    // Second pass: Normalize and Force Zero Altitude
    const maxVal = (window.depthAvailable && Number.isFinite(window.depthMax)) ? window.depthMax : 9999;
    const range = Math.max(1e-9, maxVal);

    function forceZero(c) {
        if (typeof c[0] === 'number') return c.length >= 3 ? [c[0], c[1], 0] : c;
        return c.map(forceZero);
    }

    processed.features.forEach(f => {
        // Normalize Depth
        if (window.depthAvailable && f.geometry.type === 'LineString' && f.properties) {
            const lineDepth = DepthUtils.getFeatureDepthValue(f.properties);
            const sectionKey = DepthUtils.getFeatureSectionName(f.properties);
            const sectionDepth = sectionKey ? sectionDepthAvgMap.get(sectionKey) : undefined;

            const depthValue = (typeof lineDepth === 'number' && isFinite(lineDepth))
                ? lineDepth
                : (typeof sectionDepth === 'number' && isFinite(sectionDepth) ? sectionDepth : undefined);

            if (typeof depthValue === 'number') {
                const norm = depthValue / range;
                f.properties.depth_norm = Math.min(Math.max(norm, 0), 1);
                // Store raw depth for hover tooltip (in feet as per source data)
                f.properties.depth_val = depthValue;
            }
        }

        // Force Z=0
        if (f.geometry && f.geometry.coordinates) {
            f.geometry.coordinates = forceZero(f.geometry.coordinates);
        }
    });

    // Trigger legend update event
    if (window.depthAvailable) {
        window.dispatchEvent(new CustomEvent('speleo:depth-data-updated', {
            detail: { max: window.depthMax }
        }));
    }

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
        if (map.getLayer(pointsLayerId)) map.removeLayer(pointsLayerId);
        if (map.getLayer(lineLayerId)) map.removeLayer(lineLayerId);
        if (map.getSource(sourceId)) map.removeSource(sourceId);

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

        // Update Map Layers
        if (State.map && State.map.getStyle()) {
            const layers = State.allProjectLayers.get(pid) || [];

            // Also include the stations layer
            const stationCirclesId = `stations-${pid}-circles`;
            const stationLabelsId = `stations-${pid}-labels`;

            const allTargetLayers = [...layers, stationCirclesId, stationLabelsId];

            allTargetLayers.forEach(layerId => {
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

    setColorMode: function (mode) {
        if (mode !== 'project' && mode !== 'depth') return;
        this.colorMode = mode;

        const map = State.map;
        if (!map) return;

        // Iterate all project layers
        State.allProjectLayers.forEach((layers, projectId) => {
            layers.forEach(layerId => {
                if (map.getLayer(layerId) && map.getLayer(layerId).type === 'line') {
                    // Only apply to line layers (survey lines)
                    if (mode === 'project') {
                        const color = Colors.getProjectColor(projectId);
                        map.setPaintProperty(layerId, 'line-color', color);
                    } else {
                        // Depth mode
                        // We need depth range. For now, use fixed range or try to guess.
                        // Ideally we stored range per project.
                        // Let's assume 0 to 500m for now.
                        map.setPaintProperty(layerId, 'line-color', Colors.getDepthPaint(0, 500));
                    }
                }
            });
        });

        // Update Legend visibility (if legend logic existed in Layers, or dispatch event)
        // window.dispatchEvent(new CustomEvent('speleo:color-mode-changed', { detail: { mode } }));
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
                data = processGeoJSON(rawData);

                // Cache line features for magnetic snapping
                Geometry.cacheLineFeatures(projectId, data);

                map.getSource(sourceId).setData(data);
            } else {
                // Fetch and add
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const rawData = await response.json();
                data = processGeoJSON(rawData);

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
                        'line-color': this.colorMode === 'project' ? color : Colors.getDepthPaint(0, 500),
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

                // Initial visibility
                if (!this.isProjectVisible(projectId)) {
                    projectLayers.forEach(lid => {
                        if (map.getLayer(lid)) map.setLayoutProperty(lid, 'visibility', 'none');
                    });
                }

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

        } catch (e) {
            console.error(`Error loading GeoJSON for project ${projectId}`, e);
        }
    },

    addSubSurfaceStationLayer: function (projectId, data) {
        const map = State.map;
        if (!map) return;

        const sourceId = `stations-source-${projectId}`;
        const circleLayerId = `stations-${projectId}-circles`;
        const labelLayerId = `stations-${projectId}-labels`;

        console.log(`📍 Adding ${data.features?.length || 0} stations to map for project ${projectId}`);

        // Remove existing layer and source if they exist (for refresh)
        if (map.getLayer(labelLayerId)) {
            map.removeLayer(labelLayerId);
        }
        if (map.getLayer(circleLayerId)) {
            map.removeLayer(circleLayerId);
        }
        if (map.getSource(sourceId)) {
            map.removeSource(sourceId);
        }

        if (!data.features || data.features.length === 0) {
            console.log(`📍 No stations to display for project ${projectId}`);
            return;
        }

        // Ensure color property is set on each feature for data-driven styling
        data.features.forEach(feature => {
            if (!feature.properties.color) {
                // Use tag color if available, otherwise use default orange
                const tag = feature.properties.tag;
                feature.properties.color = (tag && tag.color) ? tag.color : '#fb923c';
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: data
        });

        // Add Circle Layer
        // Use data-driven color from feature properties
        map.addLayer({
            id: circleLayerId,
            type: 'circle',
            source: sourceId,
            minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
            paint: {
                'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 5, 18, 8],
                'circle-color': ['coalesce', ['get', 'color'], '#fb923c'],
                'circle-stroke-width': 2,
                'circle-stroke-color': '#ffffff',
                'circle-opacity': 1
            }
        });

        // Add Label Layer
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
        if (!projectLayers.includes(circleLayerId)) {
            projectLayers.push(circleLayerId, labelLayerId);
        }

        // Respect initial visibility
        if (!this.isProjectVisible(projectId)) {
            map.setLayoutProperty(circleLayerId, 'visibility', 'none');
            map.setLayoutProperty(labelLayerId, 'visibility', 'none');
        }
    },

    addLandmarkLayer: function (data) {
        const map = State.map;
        if (!map) return;

        const sourceId = 'landmarks-source';

        console.log(`📍 Adding ${data.features?.length || 0} Landmarks to map`);

        // Remove existing layer and source if they exist (to refresh)
        if (map.getLayer('landmarks-layer')) {
            map.removeLayer('landmarks-layer');
        }
        if (map.getLayer('landmarks-labels')) {
            map.removeLayer('landmarks-labels');
        }
        if (map.getSource(sourceId)) {
            map.removeSource(sourceId);
        }

        if (!data.features || data.features.length === 0) {
            console.log('📍 No Landmarks to display');
            return;
        }

        map.addSource(sourceId, {
            type: 'geojson',
            data: data
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
        if (map.getLayer(labelLayerId)) {
            map.removeLayer(labelLayerId);
        }
        if (map.getLayer(symbolLayerId)) {
            map.removeLayer(symbolLayerId);
        }
        if (map.getSource(sourceId)) {
            map.removeSource(sourceId);
        }

        if (!data.features || data.features.length === 0) {
            console.log(`📍 No surface stations to display for network ${networkId}`);
            return;
        }

        // Ensure color property is set on each feature for data-driven styling
        data.features.forEach(feature => {
            if (!feature.properties.color) {
                // Use tag color if available, otherwise use default orange
                const tag = feature.properties.tag;
                feature.properties.color = (tag && tag.color) ? tag.color : '#fb923c';
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: data
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
            const feature = data.features.find(f => f.properties.id === stationId);
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
            const feature = data.features.find(f => f.properties.id === stationId);
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
            const feature = data.features.find(f => f.properties.id === stationId);
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
            const feature = data.features.find(f => f.properties.id === stationId);
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
            const feature = data.features.find(f => f.properties.id === stationId);
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
            const feature = data.features.find(f => f.properties.id === stationId);
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
            const feature = data.features.find(f => f.properties.id === landmarkId);
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
        const stationLabelLayers = allLayerIds.filter(id => id.includes('stations-') && id.includes('-labels') && !id.includes('surface-'));
        const surfaceStationSymbolLayers = allLayerIds.filter(id => id.startsWith('surface-stations-') && !id.includes('-labels'));
        const surfaceStationLabelLayers = allLayerIds.filter(id => id.startsWith('surface-stations-') && id.includes('-labels'));
        const landmarkLayers = allLayerIds.filter(id => id.startsWith('landmarks-'));

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

        // Subsurface station circles
        stationCircleLayers.forEach(layerId => {
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

        // Landmark layers (on top of everything)
        landmarkLayers.forEach(layerId => {
            try {
                map.moveLayer(layerId);
            } catch (e) {
                // Layer might not exist
            }
        });

        console.log('✅ Layer reordering complete');
    }
};
