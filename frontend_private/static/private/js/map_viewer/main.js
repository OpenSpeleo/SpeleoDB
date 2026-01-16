import { Config } from './config.js';
import { State } from './state.js';
import { MapCore } from './map/core.js';
import { Layers } from './map/layers.js';
import { Interactions } from './map/interactions.js';
import { Geometry } from './map/geometry.js';
import { StationManager } from './stations/manager.js';
import { StationUI } from './stations/ui.js';
import { StationDetails } from './stations/details.js';
import { StationTags } from './stations/tags.js';
import { SurfaceStationManager } from './surface_stations/manager.js';
import { SurfaceStationUI } from './surface_stations/ui.js';
import { LandmarkManager } from './landmarks/manager.js';
import { LandmarkUI } from './landmarks/ui.js';
import { ExplorationLeadManager } from './exploration_leads/manager.js';
import { ExplorationLeadUI } from './exploration_leads/ui.js';
import { CylinderInstalls } from './stations/cylinders.js';
import { Utils } from './utils.js';
import { ContextMenu } from './components/context_menu.js';
import { ProjectPanel } from './components/project_panel.js';
import { GPSTracksPanel } from './components/gps_tracks_panel.js';
import { API } from './api.js';

// Parse URL parameters for initial map position
// Usage: ?goto=LAT,LONG (e.g., ?goto=38.1234,-85.5678)
// Silently returns null values if format is invalid
function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const gotoParam = params.get('goto');
    
    // No goto param specified
    if (!gotoParam) {
        return { lat: null, long: null };
    }
    
    const parts = gotoParam.split(',');
    
    // Must have exactly 2 parts (LAT,LONG)
    if (parts.length !== 2) {
        return { lat: null, long: null };
    }
    
    const lat = parseFloat(parts[0].trim());
    const long = parseFloat(parts[1].trim());
    
    // Both must be valid floats
    if (isNaN(lat) || isNaN(long)) {
        return { lat: null, long: null };
    }
    
    // Validate lat/long ranges
    if (lat < -90 || lat > 90 || long < -180 || long > 180) {
        return { lat: null, long: null };
    }

    return { lat, long };
}

// Global entry point
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 SpeleoDB Map Viewer Initializing...');

    // 1. Initialize State
    State.init();

    // 2. Load Projects, Networks, and GPS Tracks from API (needed for permissions and lists)
    await Config.loadProjects();
    await Config.loadNetworks();
    await Config.loadGPSTracks();

    // 3. Initialize Map
    const token = window.SPELEO_CONTEXT?.mapboxToken || '';
    if (!token) {
        console.error('Mapbox token not found');
        Utils.showNotification('error', 'Map configuration missing');
        return;
    }

    const map = MapCore.init(token, 'map');

    // Simple function to set map height
    function setMapHeight() {
        const mapElement = document.getElementById('map');
        const rect = mapElement.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const mapTop = rect.top;
        const isMobile = window.innerWidth <= 640;
        const newHeight = isMobile ? (viewportHeight - mapTop) : Math.max(viewportHeight - mapTop - 20, 600);
        mapElement.style.height = newHeight + 'px';
    }

    // Set initial map height
    setMapHeight();

    // Update map height on window resize
    window.addEventListener('resize', setMapHeight);

    // 3. Setup Interactions
    Interactions.init(map, {
        onStationClick: (stationId, stationType) => {
            if (stationType === 'surface') {
                const station = State.allSurfaceStations.get(stationId);
                StationDetails.openModal(stationId, station?.network, false, 'surface');
            } else {
                const station = State.allStations.get(stationId);
                StationDetails.openModal(stationId, station?.project, false, 'subsurface');
            }
        },
        onLandmarkClick: (landmarkId) => LandmarkUI.openDetailsModal(landmarkId),
        onExplorationLeadClick: (leadId) => ExplorationLeadUI.showDetailsModal(leadId),
        onSafetyCylinderClick: (cylinderId) => {
            // Open cylinder details modal for installed cylinders
            CylinderInstalls.showCylinderDetails(cylinderId);
        },
        onStationDrag: (stationId, projectId, newCoords) => {
            Layers.updateStationPosition(projectId, stationId, newCoords);
        },
        onLandmarkDrag: (landmarkId, newCoords) => {
            Layers.revertLandmarkPosition(landmarkId, newCoords);
        },
        onStationDragEnd: (stationId, projectId, snapResult, originalCoords) => {
            // Show drag confirm modal with snap information
            showStationDragConfirmModal(stationId, projectId, snapResult, originalCoords);
        },
        onLandmarkDragEnd: (landmarkId, newCoords, originalCoords) => {
            // Show Landmark drag confirm modal
            showLandmarkDragConfirmModal(landmarkId, newCoords, originalCoords);
        },
        onMarkerDragEnd: (markerType, markerId, snapResult, originalCoords) => {
            // Show marker drag confirm modal (same pattern as stations)
            showMarkerDragConfirmModal(markerType, markerId, snapResult, originalCoords);
        },
        onContextMenu: (event, type, data) => {
            const items = [];

            if (type === 'station') {
                // Get subsurface station data for coordinates
                const station = State.allStations.get(data.id);
                const stationLat = station?.latitude?.toFixed(7) || 'N/A';
                const stationLng = station?.longitude?.toFixed(7) || 'N/A';

                // Copy GPS Coordinates
                items.push({
                    label: 'Copy GPS Coordinates',
                    subtitle: `${stationLat}, ${stationLng}`,
                    icon: '📋',
                    onClick: () => Utils.copyToClipboard(`${stationLat}, ${stationLng}`)
                });

                // Delete Station (if admin access)
                if (station && Config.hasProjectAdminAccess && Config.hasProjectAdminAccess(station.project)) {
                    items.push({
                        label: 'Delete Station',
                        subtitle: station.name,
                        icon: '🗑️',
                        onClick: () => StationDetails.confirmDelete(station, 'subsurface')
                    });
                }

            } else if (type === 'surface-station') {
                // Get surface station data for coordinates
                const station = State.allSurfaceStations.get(data.id);
                const stationLat = station?.latitude?.toFixed(7) || 'N/A';
                const stationLng = station?.longitude?.toFixed(7) || 'N/A';

                // Copy GPS Coordinates
                items.push({
                    label: 'Copy GPS Coordinates',
                    subtitle: `${stationLat}, ${stationLng}`,
                    icon: '📋',
                    onClick: () => Utils.copyToClipboard(`${stationLat}, ${stationLng}`)
                });

                // Delete Surface Station (if network admin access)
                if (station && Config.hasNetworkAdminAccess(station.network)) {
                    items.push({
                        label: 'Delete Surface Station',
                        subtitle: station.name,
                        icon: '🗑️',
                        onClick: () => StationDetails.confirmDelete(station, 'surface')
                    });
                }

            } else if (type === 'landmark') {
                // Get Landmark data
                const landmark = State.allLandmarks.get(data.id);
                const landmarkLat = landmark?.latitude?.toFixed(7) || data.feature?.properties?.latitude?.toFixed(7) || 'N/A';
                const landmarkLong = landmark?.longitude?.toFixed(7) || data.feature?.properties?.longitude?.toFixed(7) || 'N/A';
                const landmarkName = landmark?.name || data.feature?.properties?.name || 'Landmark';
                // Copy GPS Coordinates
                items.push({
                    label: 'Copy GPS Coordinates',
                    subtitle: `${landmarkLat}, ${landmarkLong}`,
                    icon: '📋',
                    onClick: () => Utils.copyToClipboard(`${landmarkLat}, ${landmarkLong}`)
                });

                // Delete Landmark (any authenticated user can manage their Landmarks)
                items.push({
                    label: 'Delete Landmark',
                    subtitle: landmarkName,
                    icon: '🗑️',
                    onClick: () => LandmarkUI.showDeleteConfirmModal(landmark || data.feature.properties)
                });

            } else if (type === 'safety-cylinder') {
                // Get Safety Cylinder data
                const marker = State.safetyCylinders.get(data.id);
                const coords = marker?.coordinates || data.feature?.geometry?.coordinates;
                const markerLat = coords?.[1]?.toFixed(7) || 'N/A';
                const markerLng = coords?.[0]?.toFixed(7) || 'N/A';
                const lineName = marker?.lineName || 'Survey Line';

                // Copy GPS Coordinates
                items.push({
                    label: 'Copy GPS Coordinates',
                    subtitle: `${markerLat}, ${markerLng}`,
                    icon: '📋',
                    onClick: () => Utils.copyToClipboard(`${markerLat}, ${markerLng}`)
                });

                // Delete Safety Cylinder
                items.push({
                    label: 'Delete Safety Cylinder',
                    subtitle: `On ${lineName}`,
                    icon: '🗑️',
                    onClick: () => showDeleteMarkerModal('safety-cylinder', data.id, lineName)
                });

            } else if (type === 'exploration-lead') {
                // Get Exploration Lead data
                const marker = State.explorationLeads.get(data.id);
                const coords = marker?.coordinates || data.feature?.geometry?.coordinates;
                const markerLat = coords?.[1]?.toFixed(7) || 'N/A';
                const markerLng = coords?.[0]?.toFixed(7) || 'N/A';
                const lineName = marker?.lineName || 'Survey Line';

                // Open Details
                items.push({
                    label: 'Open Details',
                    subtitle: marker?.description ? marker.description.substring(0, 30) + '...' : 'View/Edit lead',
                    icon: `<img src="${window.SPELEO_CONTEXT.icons.explorationLead}" style="width:20px;height:20px;">`,
                    onClick: () => ExplorationLeadUI.showDetailsModal(data.id)
                });

                // Copy GPS Coordinates
                items.push({
                    label: 'Copy GPS Coordinates',
                    subtitle: `${markerLat}, ${markerLng}`,
                    icon: '📋',
                    onClick: () => Utils.copyToClipboard(`${markerLat}, ${markerLng}`)
                });

                // Delete Exploration Lead
                items.push({
                    label: 'Delete Exploration Lead',
                    subtitle: `On ${lineName}`,
                    icon: '🗑️',
                    onClick: () => ExplorationLeadUI.showDeleteConfirmModal(data.id, lineName)
                });

            } else {
                // Right-click on empty map area
                const coords = data.coordinates;
                const lngLat = { lat: coords[1], lng: coords[0] };

                // Check if we can create a station here (need snap point within radius)
                const snapCheck = Geometry.findNearestSnapPointWithinRadius(coords, Geometry.getSnapRadius());

                // Need to be snapped to a survey line with a valid project ID
                const hasValidSnap = snapCheck.snapped && snapCheck.projectId && Layers.isProjectVisible(snapCheck.projectId);
                
                if (!hasValidSnap) {
                    // Can't create station - too far from survey line or no project context
                    items.push({
                        label: 'Create Station',
                        subtitle: "Can't create a station at this location. Too far from the line",
                        icon: '📌',
                        disabled: true
                    });
                } else {
                    // Near a survey line - show all line-related options
                    const nearestProjectId = snapCheck.projectId;
                    const lineName = snapCheck.lineName || 'Survey Line';
                    const canCreate = nearestProjectId && Config.hasProjectWriteAccess(nearestProjectId);

                    if (canCreate) {
                        items.push({
                            label: 'Create Station',
                            subtitle: `At ${lngLat.lat.toFixed(4)}, ${lngLat.lng.toFixed(4)}`,
                            icon: '📌',
                            onClick: () => StationUI.showCreateStationModal(coords, nearestProjectId)
                        });
                    } else {
                        items.push({
                            label: 'Create Station',
                            subtitle: "No write access for this project",
                            icon: '🔒',
                            disabled: true
                        });
                    }

                    // Install Safety Cylinder - uses new persistent cylinder system
                    items.push({
                        label: 'Install Safety Cylinder',
                        subtitle: `At ${lngLat.lat.toFixed(4)}, ${lngLat.lng.toFixed(4)}`,
                        icon: `<img src="${window.SPELEO_CONTEXT.icons.cylinderOrange}" style="width:20px;height:20px;">`,
                        onClick: () => {
                            CylinderInstalls.showInstallModal(snapCheck.coordinates, lineName, nearestProjectId);
                        }
                    });

                    if (canCreate) {
                        items.push({
                            label: 'Mark Exploration Lead',
                            subtitle: `On ${lineName} (${snapCheck.pointType} point)`,
                            icon: `<img src="${window.SPELEO_CONTEXT.icons.explorationLead}" style="width:20px;height:20px;">`,
                            onClick: () => {
                                ExplorationLeadUI.showCreateModal(snapCheck.coordinates, lineName, nearestProjectId);
                            }
                        });
                    } else {
                        items.push({
                            label: 'Mark Exploration Lead',
                            subtitle: "No write access for this project",
                            icon: '🔒',
                            disabled: true
                        });
                    }
                }

                // Landmark creation is always available for authenticated users
                items.push({
                    label: 'Create Landmark',
                    subtitle: 'Landmark',
                    icon: '📍',
                    onClick: () => LandmarkUI.openCreateModal(coords)
                });

                items.push('-');

                // Copy Coordinates
                items.push({
                    label: 'Copy Coordinates',
                    subtitle: `${lngLat.lat.toFixed(7)}, ${lngLat.lng.toFixed(7)}`,
                    icon: '📋',
                    onClick: () => Utils.copyToClipboard(`${lngLat.lat.toFixed(7)}, ${lngLat.lng.toFixed(7)}`)
                });
            }

            if (items.length > 0) ContextMenu.show(event.point.x, event.point.y, items);
        }
    });

    const legend = document.getElementById('map-legend');

    // Track current color mode
    window.colorMode = 'project';

    // Update depth legend visibility based on active mode and data availability
    function updateDepthLegendVisibility() {
        try {
            const depthLegend = document.getElementById('depth-scale-fixed');
            if (!depthLegend) return;
            const shouldShow = (window.colorMode === 'depth' && window.depthAvailable === true);
            depthLegend.style.display = shouldShow ? 'block' : 'none';
            // Also hide depth cursor indicator when legend hidden
            if (!shouldShow) {
                const cursor = document.getElementById('depth-cursor-indicator');
                const label = document.getElementById('depth-cursor-label');
                if (cursor) cursor.style.display = 'none';
                if (label) label.style.display = 'none';
            }
        } catch (e) {
            // ignore
        }
    }

    // Create depth scale dynamically (matching old implementation)
    function createDepthScale() {
        try {
            const mapContainer = document.getElementById('map');
            const existing = document.getElementById('depth-scale-fixed');
            let container = existing;

            if (!container) {
                container = document.createElement('div');
                container.id = 'depth-scale-fixed';
                container.style.position = 'absolute';
                container.style.left = '5px';
                container.style.bottom = '5px';
                container.style.zIndex = '5';
                container.style.backgroundColor = '#0f172a';
                container.style.border = '2px solid #475569';
                container.style.borderRadius = '8px';
                container.style.padding = '8px 10px';
                mapContainer.appendChild(container);
            }

            const maxVal = Number.isFinite(window.depthMax) ? window.depthMax : 9999;
            container.innerHTML = `
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="color:#94a3b8; font-size:12px;">Depth</span>
                    <div id="depth-scale-gradient" style="position:relative; width:160px; height:10px; background: linear-gradient(90deg, #4575b4 0%, #e6f598 50%, #d73027 100%); border-radius: 4px;">
                        <div id="depth-cursor-indicator" style="position:absolute; top:-3px; left:0; width:2px; height:16px; background:#ffffff; box-shadow:0 0 4px rgba(0,0,0,0.6); display:none; transition:left 0.15s ease-out;"></div>
                        <div id="depth-cursor-label" style="position:absolute; top:-27px; left:0; transform:translateX(-50%); color:#e5e7eb; font-size:13px; background: rgba(2, 6, 23, 0.9); border: 1px solid #334155; padding: 2px 6px; border-radius: 3px; display:none; pointer-events:none; white-space:nowrap; transition:left 0.15s ease-out;"></div>
                    </div>
                </div>
                <div style="display:flex; justify-content:space-between; color:#94a3b8; font-size:11px; margin-top:4px;">
                    <span>0 ft</span>
                    <span>${Math.ceil(maxVal)} ft</span>
                </div>
            `;

            // Respect initial color mode for legend visibility
            updateDepthLegendVisibility();
        } catch (e) {
            console.warn('Unable to render/update depth scale:', e);
        }
    }

    // 4. Load Data
    map.on('load', async () => {
        // Load custom marker images (cylinder icon for safety cylinders)
        await Layers.loadMarkerImages();

        // Initialize Projects Layers visibility
        Layers.loadProjectVisibilityPrefs();

        // Fetch GeoJSON metadata for all projects FIRST
        // This allows us to filter out projects without GeoJSON before showing the panel
        let geojsonMetadata = [];
        try {
            console.log('🔄 Fetching all projects\' GeoJSON metadata via single API call...');
            const response = await API.getAllProjectsGeoJSON();
            if (response && response.success && Array.isArray(response.data)) {
                geojsonMetadata = response.data;
                console.log(`✅ Cached GeoJSON metadata for ${geojsonMetadata.length} projects`);
            }
        } catch (e) {
            console.error('❌ Failed to load all-projects GeoJSON metadata:', e);
        }

        // Filter projects to only include those with GeoJSON data
        // This ensures the project panel only shows projects that can be displayed on the map
        Config.filterProjectsByGeoJSON(geojsonMetadata);

        // Initialize Project Panel (now shows only projects with GeoJSON)
        ProjectPanel.init();

        // Initialize GPS Tracks Panel (collapsed by default, all tracks OFF)
        GPSTracksPanel.init();

        // Load user tags and colors for tag management
        StationTags.init();

        // Load Stations and GeoJSON for each project with progress tracking
        const totalProjects = Config.projects.length;
        let loadedProjects = 0;
        const progressEl = document.getElementById('loading-progress');

        const updateProgress = () => {
            if (progressEl) {
                progressEl.textContent = `Downloading ${loadedProjects}/${totalProjects} Projects`;
            }
        };

        // Initial progress display
        updateProgress();

        const loadPromises = Config.projects.map(async (project) => {
            const projectPromises = [];

            // Load Stations
            projectPromises.push(
                StationManager.loadStationsForProject(project.id)
                    .then(stations => {
                        Layers.addSubSurfaceStationLayer(project.id, { type: 'FeatureCollection', features: stations });
                    })
                    .catch(e => {
                        console.error(`Error loading stations for ${project.name}`, e);
                    })
            );

            // Find GeoJSON URL for this project from metadata
            const projectMeta = geojsonMetadata.find(p => String(p.id) === String(project.id));
            const geojsonUrl = projectMeta?.geojson_file || project.geojson_url;

            // Load GeoJSON if available
            if (geojsonUrl) {
                projectPromises.push(
                    Layers.addProjectGeoJSON(project.id, geojsonUrl)
                        .then(() => {
                            loadedProjects++;
                            updateProgress();
                        })
                        .catch(e => {
                            console.error(`Error loading GeoJSON for ${project.name}`, e);
                            // Still count as loaded (even on error) to keep progress moving
                            loadedProjects++;
                            updateProgress();
                        })
                );
            } else {
                // No GeoJSON URL - count immediately
                loadedProjects++;
                updateProgress();
            }

            return Promise.all(projectPromises);
        });

        await Promise.all(loadPromises);

        // Load Surface Stations for each network
        Layers.loadNetworkVisibilityPrefs();
        const surfaceStationPromises = Config.networks.map(async (network) => {
            try {
                const stations = await SurfaceStationManager.loadStationsForNetwork(network.id);
                Layers.addSurfaceStationLayer(network.id, { type: 'FeatureCollection', features: stations });
            } catch (e) {
                console.error(`Error loading surface stations for ${network.name}`, e);
            }
        });
        await Promise.all(surfaceStationPromises);

        // Reorder layers to ensure stations are on top of survey lines
        Layers.reorderLayers();

        // Load Landmarks (no delay - load immediately to ensure spinner waits for all data)
        try {
            const landmarksData = await LandmarkManager.loadAllLandmarks();
            Layers.addLandmarkLayer(landmarksData);
            // Reorder again after Landmarks are loaded
            Layers.reorderLayers();
        } catch (e) {
            console.error('Error loading Landmarks', e);
        }

        // Load Exploration Leads for all projects
        try {
            await ExplorationLeadManager.loadAllLeads();
            Layers.refreshExplorationLeadsLayer();
            Layers.reorderLayers();
            console.log('✅ Exploration leads loaded');
        } catch (e) {
            console.error('Error loading Exploration Leads', e);
        }

        // Load Cylinder Installs (safety cylinders from fleets)
        try {
            await Layers.loadCylinderInstalls();
            console.log('✅ Cylinder installs loaded');
        } catch (e) {
            console.error('Error loading Cylinder Installs', e);
        }

        // Create depth scale dynamically
        createDepthScale();

        // Check for URL parameters to fly to a specific location
        const urlParams = getUrlParams();

        if (urlParams.lat !== null && urlParams.long !== null) {
            // Fly to the specified coordinates from URL
            console.log(`🎯 Flying to URL coordinates: ${urlParams.lat}, ${urlParams.long}`);
            map.flyTo({
                center: [urlParams.long, urlParams.lat],
                zoom: 18,
                essential: true
            });
        } else if (State.projectBounds.size > 0) {
            // Auto-zoom to fit all project bounds
            const allBounds = new mapboxgl.LngLatBounds();
            State.projectBounds.forEach(bounds => {
                allBounds.extend(bounds);
            });

            if (!allBounds.isEmpty()) {
                map.fitBounds(allBounds, { padding: 50, maxZoom: 16 });
            }
        }

        // Hide Loading Overlay - only after ALL data (projects, GeoJSON, stations, Landmarks) is loaded
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('opacity-0', 'pointer-events-none');
            setTimeout(() => overlay.remove(), 500);
        }

        console.log('✅ Map Data Loaded (Projects, GeoJSON, Stations, Landmarks)');
    });

    // Setup UI listeners
    MapCore.setupColorModeToggle(map);

    // Setup Landmarks Toggle
    const landmarksToggle = document.getElementById('landmarks-toggle');
    const landmarksToggleButton = document.getElementById('landmarks-toggle-button');
    if (landmarksToggle && landmarksToggleButton) {
        // Prevent button click from toggling
        landmarksToggleButton.addEventListener('click', (e) => {
            e.preventDefault();
            landmarksToggle.checked = !landmarksToggle.checked;
            Layers.toggleLandmarkVisibility(landmarksToggle.checked);
        });

        // Handle direct checkbox change
        landmarksToggle.addEventListener('change', (e) => {
            e.stopPropagation();
            Layers.toggleLandmarkVisibility(landmarksToggle.checked);
        });
    }

    // Setup Landmark Manager Button (backup to onclick in HTML)
    const landmarkManagerButton = document.getElementById('landmark-manager-button');
    if (landmarkManagerButton && !landmarkManagerButton.onclick) {
        landmarkManagerButton.addEventListener('click', () => LandmarkUI.openManagerModal());
    }

    // Ensure depth scale is hidden initially
    updateDepthLegendVisibility();

    const legendToggleBtn = document.getElementById('legend-toggle-button');
    if (legendToggleBtn && legend) {
        legendToggleBtn.addEventListener('click', () => {
            legend.classList.toggle('hidden');
        });
    }

    // Listen for Color Mode Changes to update and auto-show legend
    window.addEventListener('speleo:color-mode-changed', (e) => {
        window.colorMode = e.detail.mode;
        updateDepthLegendVisibility();
    });

    // Listen for depth data updates to refresh legend range
    window.addEventListener('speleo:depth-data-updated', (e) => {
        // Recreate the depth scale with updated max value
        createDepthScale();
        // Update visibility now that we have depth data
        updateDepthLegendVisibility();
    });

    // Setup mouse hover for depth indicator (matching old implementation)
    map.on('mousemove', (e) => {
        if (window.colorMode !== 'depth' || window.depthAvailable !== true) return;

        const indicator = document.getElementById('depth-cursor-indicator');
        const labelEl = document.getElementById('depth-cursor-label');
        const gradientEl = document.getElementById('depth-scale-gradient');

        if (!gradientEl || !indicator || !labelEl) return;

        // Query line layers for depth data
        const queryPaddingPx = 12;
        const queryBox = [
            [e.point.x - queryPaddingPx, e.point.y - queryPaddingPx],
            [e.point.x + queryPaddingPx, e.point.y + queryPaddingPx]
        ];

        let features = [];
        try {
            features = map.queryRenderedFeatures(queryBox);
        } catch (err) {
            // ignore query errors
        }

        // Find line features with depth data
        const lineFeature = features.find(f =>
            f.layer && f.layer.type === 'line' &&
            f.properties &&
            (f.properties.depth_val !== undefined || f.properties.depth_norm !== undefined)
        );

        if (!lineFeature) {
            indicator.style.display = 'none';
            labelEl.style.display = 'none';
            return;
        }

        const props = lineFeature.properties || {};
        const depthVal = props.depth_val;
        const norm = props.depth_norm;

        // Use depth_val if available (already in feet), otherwise compute from normalized
        if (typeof depthVal === 'number' && isFinite(depthVal)) {
            const maxVal = Number.isFinite(window.depthMax) ? window.depthMax : 9999;
            const pct = Math.min(Math.max(depthVal / maxVal, 0), 1) * 100;
            indicator.style.left = `calc(${pct}% - 1px)`;
            indicator.style.display = 'block';
            labelEl.textContent = `${depthVal.toFixed(1)} ft`;
            labelEl.style.left = `calc(${pct}% - 0px)`;
            labelEl.style.display = 'block';
        } else if (typeof norm === 'number' && isFinite(norm)) {
            // Fallback to normalized if depth_val not present
            const maxVal = Number.isFinite(window.depthMax) ? window.depthMax : 9999;
            const clamped = Math.min(Math.max(norm, 0), 1);
            const depth = clamped * maxVal;
            const pct = clamped * 100;
            indicator.style.left = `calc(${pct}% - 1px)`;
            indicator.style.display = 'block';
            labelEl.textContent = `${depth.toFixed(1)} ft`;
            labelEl.style.left = `calc(${pct}% - 0px)`;
            labelEl.style.display = 'block';
        } else {
            indicator.style.display = 'none';
            labelEl.style.display = 'none';
        }
    });

    // Listen for Refresh Events
    window.addEventListener('speleo:refresh-stations', async (e) => {
        const { projectId } = e.detail;
        if (projectId) {
            const stations = await StationManager.loadStationsForProject(projectId);
            Layers.addSubSurfaceStationLayer(projectId, { type: 'FeatureCollection', features: stations });
            // Ensure stations remain on top of survey lines
            Layers.reorderLayers();
        }
    });

    // Listen for Surface Station Refresh Events
    window.addEventListener('speleo:refresh-surface-stations', async (e) => {
        const { networkId } = e.detail;
        if (networkId) {
            const stations = await SurfaceStationManager.loadStationsForNetwork(networkId);
            Layers.addSurfaceStationLayer(networkId, { type: 'FeatureCollection', features: stations });
            // Ensure stations remain on top of survey lines
            Layers.reorderLayers();
        }
    });

    // Listen for Landmark Refresh Events (e.g., after GPX import)
    window.addEventListener('speleo:refresh-landmarks', async () => {
        console.log('📍 Refreshing landmarks...');
        try {
            const landmarksData = await LandmarkManager.loadAllLandmarks();
            Layers.addLandmarkLayer(landmarksData);
            Layers.reorderLayers();
            Utils.showNotification('success', 'Landmarks refreshed');
        } catch (e) {
            console.error('Error refreshing Landmarks', e);
        }
    });

    // Listen for GPS Tracks Refresh Events (e.g., after GPX import)
    window.addEventListener('speleo:refresh-gps-tracks', async (e) => {
        const { deactivateAll } = e.detail || {};
        console.log('🛤️ Refreshing GPS tracks...');
        try {
            // Clear the existing GPS track cache
            State.gpsTrackCache.clear();

            // Deactivate all visible GPS tracks
            if (deactivateAll) {
                State.gpsTrackLayerStates.forEach((isVisible, trackId) => {
                    if (isVisible) {
                        Layers.showGPSTrackLayers(trackId, false);
                        State.gpsTrackLayerStates.set(trackId, false);
                    }
                });
            }

            // Reset Config's internal GPS tracks cache to force reload
            Config._gpsTracks = null;

            // Reload GPS tracks from API
            await Config.loadGPSTracks();

            // Refresh the GPS tracks panel - check if panel exists
            const panelExists = document.getElementById('gps-tracks-panel');
            if (panelExists) {
                GPSTracksPanel.refreshList();
            } else if (Config.gpsTracks.length > 0) {
                // Panel doesn't exist but we now have tracks - initialize it
                GPSTracksPanel.init();
            }

            Utils.showNotification('success', 'GPS tracks refreshed');
        } catch (e) {
            console.error('Error refreshing GPS tracks', e);
        }
    });

    // Global Exposes
    window.openSurveyStationManager = () => StationUI.openManagerModal();
    window.openSurfaceStationManager = () => SurfaceStationUI.openManagerModal();
    // Expose Landmark Manager for the button we added above or HTML onclick
    window.openLandmarkManager = () => LandmarkUI.openManagerModal();
    window.LandmarkUI = LandmarkUI; // Expose for inline HTML onclicks
    window.StationUI = StationUI; // Expose for inline HTML onclicks
    window.CylinderInstalls = CylinderInstalls; // Expose for cylinder install modals
    window.refreshCylinderInstallsLayer = () => Layers.refreshCylinderInstallsLayer();
    window.API = API; // Expose API for cylinder install and other modules
    
    // Listen for cylinder refresh events from the cylinder module
    document.addEventListener('speleo:refresh-cylinder-installs', () => {
        Layers.refreshCylinderInstallsLayer();
    });
    
    // Close station modal function (used by cylinder install modal and others)
    window.closeStationModal = () => {
        const modal = document.getElementById('station-modal');
        if (modal) modal.classList.add('hidden');
    };

    // Expose snap debugging functions (like old implementation)
    window.getSnapInfo = () => Geometry.getSnapInfo();
    window.setSnapRadius = (radius) => Geometry.setSnapRadius(radius);

    window.goToStation = (id, lat, lon) => {
        map.flyTo({ center: [lon, lat], zoom: 18 });
        // Check if it's a subsurface or surface station
        const station = State.allStations.get(id);
        const surfaceStation = State.allSurfaceStations.get(id);
        if (station) {
            Layers.toggleProjectVisibility(station.project, true);
        } else if (surfaceStation) {
            Layers.toggleNetworkVisibility(surfaceStation.network, true);
        }
    };

    // Expose station modal for compatibility with old HTML handlers
    window.openStationModal = (stationId, projectId, isNewlyCreated = false) => {
        StationDetails.openModal(stationId, projectId, isNewlyCreated);
    };

    // Landmark drag confirmation modal
    function showLandmarkDragConfirmModal(landmarkId, newCoords, originalCoords) {
        const landmark = State.allLandmarks.get(landmarkId);
        const landmarkName = landmark?.name || 'Landmark';

        const modalHtml = `
            <div id="landmark-drag-confirm-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6">
                        <div class="flex items-center justify-center mb-4">
                            <div class="w-12 h-12 rounded-full flex items-center justify-center text-2xl" 
                                 style="background: linear-gradient(135deg, #3b82f6, #2563eb);">
                                📍
                            </div>
                        </div>
                        <h3 class="text-lg font-semibold text-white text-center mb-2">Move Landmark</h3>
                        <p class="text-slate-300 text-center mb-6">
                            Move "${landmarkName}" to this location?
                        </p>
                        
                        <div class="bg-slate-700/50 rounded-lg p-4 space-y-2 mb-6">
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">Landmark Name:</span>
                                <span class="text-white">${landmarkName}</span>
                            </div>
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">New Location:</span>
                                <span class="text-white font-mono">${newCoords[1].toFixed(7)}, ${newCoords[0].toFixed(7)}</span>
                            </div>
                        </div>
                        
                        <div class="flex gap-3">
                            <button id="landmark-drag-cancel-btn" class="flex-1 px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg transition-colors">
                                Cancel
                            </button>
                            <button id="landmark-drag-confirm-btn" class="flex-1 px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition-colors">
                                Move Landmark
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove any existing modal
        const existingModal = document.getElementById('landmark-drag-confirm-modal');
        if (existingModal) existingModal.remove();

        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Setup handlers
        document.getElementById('landmark-drag-cancel-btn').onclick = () => {
            Layers.revertLandmarkPosition(landmarkId, originalCoords);
            document.getElementById('landmark-drag-confirm-modal').remove();
        };

        document.getElementById('landmark-drag-confirm-btn').onclick = async () => {
            const modal = document.getElementById('landmark-drag-confirm-modal');

            try {
                await LandmarkManager.moveLandmark(landmarkId, newCoords);
                Utils.showNotification('success', 'Landmark moved successfully!');
            } catch (error) {
                console.error('Error moving Landmark:', error);
                Utils.showNotification('error', 'Failed to move Landmark');
                Layers.revertLandmarkPosition(landmarkId, originalCoords);
            }

            modal.remove();
        };

        // Close on backdrop click
        document.getElementById('landmark-drag-confirm-modal').onclick = (e) => {
            if (e.target.id === 'landmark-drag-confirm-modal') {
                Layers.revertLandmarkPosition(landmarkId, originalCoords);
                e.target.remove();
            }
        };
    }

    // Station drag confirmation modal
    function showStationDragConfirmModal(stationId, projectId, snapResult, originalCoords) {
        const station = State.allStations.get(stationId);
        const stationName = station?.name || 'Station';
        const finalCoords = snapResult.coordinates;

        // Create modal HTML
        const actionText = snapResult.snapped
            ? `snap to survey line "${snapResult.lineName}"`
            : 'place at the exact GPS coordinates';

        const modalHtml = `
            <div id="drag-confirm-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6">
                        <div class="flex items-center justify-center mb-4">
                            <div class="w-12 h-12 rounded-full flex items-center justify-center text-2xl" 
                                 style="background: linear-gradient(135deg, ${snapResult.snapped ? '#10b981, #059669' : '#f59e0b, #d97706'});">
                                ${snapResult.snapped ? '🧲' : '📍'}
                            </div>
                        </div>
                        <h3 class="text-lg font-semibold text-white text-center mb-2">Move Station</h3>
                        <p class="text-slate-300 text-center mb-6">
                            Move "${stationName}" to this location and ${actionText}?
                        </p>
                        
                        <div class="bg-slate-700/50 rounded-lg p-4 space-y-2 mb-6">
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">Station Name:</span>
                                <span class="text-white">${stationName}</span>
                            </div>
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">New Location:</span>
                                <span class="text-white font-mono">${finalCoords[1].toFixed(7)}, ${finalCoords[0].toFixed(7)}</span>
                            </div>
                            ${snapResult.snapped ? `
                                <div class="flex justify-between text-sm">
                                    <span class="text-slate-400">Magnetic Snap:</span>
                                    <span class="text-emerald-400">🧲 ${snapResult.lineName}</span>
                                </div>
                                <div class="flex justify-between text-sm">
                                    <span class="text-slate-400">Snap Point:</span>
                                    <span class="text-white capitalize">${snapResult.pointType || 'vertex'} point</span>
                                </div>
                                <div class="flex justify-between text-sm">
                                    <span class="text-slate-400">Distance:</span>
                                    <span class="text-white">${snapResult.distance.toFixed(1)}m</span>
                                </div>
                            ` : `
                                <div class="flex justify-between text-sm">
                                    <span class="text-slate-400">Warning:</span>
                                    <span class="text-amber-400">⚠️ Not snapped to survey line</span>
                                </div>
                            `}
                        </div>
                        
                        <div class="flex gap-3">
                            <button id="drag-cancel-btn" class="flex-1 px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg transition-colors">
                                Cancel
                            </button>
                            <button id="drag-confirm-btn" class="flex-1 px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition-colors">
                                Move Station
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove any existing modal
        const existingModal = document.getElementById('drag-confirm-modal');
        if (existingModal) existingModal.remove();

        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Setup handlers
        document.getElementById('drag-cancel-btn').onclick = () => {
            // Revert to original position
            Layers.updateStationPosition(projectId, stationId, originalCoords);
            document.getElementById('drag-confirm-modal').remove();
        };

        document.getElementById('drag-confirm-btn').onclick = async () => {
            const modal = document.getElementById('drag-confirm-modal');

            try {
                // Update station via API
                await StationManager.moveStation(stationId, finalCoords);

                const snapMessage = snapResult.snapped
                    ? ` and snapped to ${snapResult.lineName}`
                    : '';
                Utils.showNotification('success', `Station moved successfully${snapMessage}!`);

                // Refresh stations
                Layers.refreshStationsAfterChange(projectId);

            } catch (error) {
                console.error('Error moving station:', error);
                Utils.showNotification('error', 'Failed to move station');

                // Revert on error
                Layers.updateStationPosition(projectId, stationId, originalCoords);
            }

            modal.remove();
        };

        // Close on backdrop click
        document.getElementById('drag-confirm-modal').onclick = (e) => {
            if (e.target.id === 'drag-confirm-modal') {
                Layers.updateStationPosition(projectId, stationId, originalCoords);
                e.target.remove();
            }
        };
    }

    // Delete marker confirmation modal
    function showDeleteMarkerModal(markerType, markerId, lineName) {
        const typeLabel = markerType === 'safety-cylinder' ? 'Safety Cylinder' : 'Exploration Lead';
        const typeIcon = markerType === 'safety-cylinder' ? '🛢️' : '❗';

        const modalHtml = `
            <div id="delete-marker-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6">
                        <div class="flex items-center justify-center mb-4">
                            <div class="w-12 h-12 rounded-full flex items-center justify-center text-2xl" 
                                 style="background: linear-gradient(135deg, #ef4444, #dc2626);">
                                🗑️
                            </div>
                        </div>
                        <h3 class="text-lg font-semibold text-white text-center mb-2">Delete ${typeLabel}</h3>
                        <p class="text-slate-300 text-center mb-6">
                            Are you sure you want to delete this ${typeLabel.toLowerCase()} on "${lineName}"?
                        </p>
                        
                        <div class="flex gap-3">
                            <button id="delete-marker-cancel-btn" class="flex-1 px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg transition-colors">
                                Cancel
                            </button>
                            <button id="delete-marker-confirm-btn" class="flex-1 px-4 py-2 bg-red-500 hover:bg-red-400 text-white rounded-lg transition-colors">
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove any existing modal
        const existingModal = document.getElementById('delete-marker-modal');
        if (existingModal) existingModal.remove();

        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Setup handlers
        document.getElementById('delete-marker-cancel-btn').onclick = () => {
            document.getElementById('delete-marker-modal').remove();
        };

        document.getElementById('delete-marker-confirm-btn').onclick = () => {
            if (markerType === 'safety-cylinder') {
                Layers.removeSafetyCylinderMarker(markerId);
            } else {
                Layers.removeExplorationLeadMarker(markerId);
            }
            Utils.showNotification('success', `${typeLabel} deleted`);
            document.getElementById('delete-marker-modal').remove();
        };

        // Close on backdrop click
        document.getElementById('delete-marker-modal').onclick = (e) => {
            if (e.target.id === 'delete-marker-modal') {
                e.target.remove();
            }
        };
    }

    // Marker drag confirmation modal (shared for safety-cylinder and exploration-lead)
    function showMarkerDragConfirmModal(markerType, markerId, snapResult, originalCoords) {
        const marker = markerType === 'safety-cylinder'
            ? State.safetyCylinders.get(markerId)
            : State.explorationLeads.get(markerId);
        const typeLabel = markerType === 'safety-cylinder' ? 'Safety Cylinder' : 'Exploration Lead';
        const typeIcon = markerType === 'safety-cylinder' ? '🛢️' : '❗';
        const lineName = marker?.lineName || snapResult.lineName || 'Survey Line';
        const finalCoords = snapResult.coordinates;

        const modalHtml = `
            <div id="marker-drag-confirm-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6">
                        <div class="flex items-center justify-center mb-4">
                            <div class="w-12 h-12 rounded-full flex items-center justify-center text-2xl" 
                                 style="background: linear-gradient(135deg, ${snapResult.snapped ? '#10b981, #059669' : '#f59e0b, #d97706'});">
                                ${snapResult.snapped ? '🧲' : '📍'}
                            </div>
                        </div>
                        <h3 class="text-lg font-semibold text-white text-center mb-2">Move ${typeLabel}</h3>
                        <p class="text-slate-300 text-center mb-6">
                            Move this ${typeLabel.toLowerCase()} to the new location?
                        </p>
                        
                        <div class="bg-slate-700/50 rounded-lg p-4 space-y-2 mb-6">
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">Type:</span>
                                <span class="text-white">${typeIcon} ${typeLabel}</span>
                            </div>
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">New Location:</span>
                                <span class="text-white font-mono">${finalCoords[1].toFixed(7)}, ${finalCoords[0].toFixed(7)}</span>
                            </div>
                            ${snapResult.snapped ? `
                                <div class="flex justify-between text-sm">
                                    <span class="text-slate-400">Snapped to:</span>
                                    <span class="text-emerald-400">🧲 ${snapResult.lineName} (${snapResult.pointType})</span>
                                </div>
                            ` : `
                                <div class="flex justify-between text-sm">
                                    <span class="text-slate-400">Warning:</span>
                                    <span class="text-amber-400">⚠️ Not snapped - will revert</span>
                                </div>
                            `}
                        </div>
                        
                        <div class="flex gap-3">
                            <button id="marker-drag-cancel-btn" class="flex-1 px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg transition-colors">
                                Cancel
                            </button>
                            <button id="marker-drag-confirm-btn" class="flex-1 px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition-colors" ${!snapResult.snapped ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}>
                                Move ${typeLabel}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove any existing modal
        const existingModal = document.getElementById('marker-drag-confirm-modal');
        if (existingModal) existingModal.remove();

        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Setup handlers
        const revertPosition = () => {
            if (markerType === 'safety-cylinder') {
                Layers.updateSafetyCylinderPosition(markerId, originalCoords);
            } else {
                Layers.updateExplorationLeadPosition(markerId, originalCoords);
            }
        };

        document.getElementById('marker-drag-cancel-btn').onclick = () => {
            revertPosition();
            document.getElementById('marker-drag-confirm-modal').remove();
        };

        document.getElementById('marker-drag-confirm-btn').onclick = async () => {
            if (snapResult.snapped) {
                try {
                    // Update to final snapped position
                    if (markerType === 'safety-cylinder') {
                        Layers.updateSafetyCylinderPosition(markerId, finalCoords);
                        Utils.showNotification('success', `${typeLabel} moved to ${snapResult.lineName}`);
                    } else {
                        // Update exploration lead via API
                        await ExplorationLeadManager.moveLead(markerId, finalCoords);
                        Layers.updateExplorationLeadPosition(markerId, finalCoords);
                        Utils.showNotification('success', `${typeLabel} moved to ${snapResult.lineName}`);
                    }
                } catch (error) {
                    console.error(`Error moving ${typeLabel}:`, error);
                    Utils.showNotification('error', `Failed to move ${typeLabel}`);
                    revertPosition();
                }
            } else {
                revertPosition();
            }
            document.getElementById('marker-drag-confirm-modal').remove();
        };

        // Close on backdrop click (revert)
        document.getElementById('marker-drag-confirm-modal').onclick = (e) => {
            if (e.target.id === 'marker-drag-confirm-modal') {
                revertPosition();
                e.target.remove();
            }
        };
    }

    window.goToLandmark = (id, lat, lon) => {
        map.flyTo({ center: [lon, lat], zoom: 18 });
    };
});
