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
import { POIManager } from './pois/manager.js';
import { POIUI } from './pois/ui.js';
import { Utils } from './utils.js';
import { ContextMenu } from './components/context_menu.js';
import { ProjectPanel } from './components/project_panel.js';
import { API } from './api.js';

// Global entry point
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 SpeleoDB Map Viewer Initializing...');

    // 1. Initialize State
    State.init();

    // 2. Load Projects and Networks from API (needed for permissions and lists)
    await Config.loadProjects();
    await Config.loadNetworks();

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
        onPOIClick: (poiId) => POIUI.openDetailsModal(poiId),
        onStationDrag: (stationId, projectId, newCoords) => {
            Layers.updateStationPosition(projectId, stationId, newCoords);
        },
        onPOIDrag: (poiId, newCoords) => {
            Layers.revertPOIPosition(poiId, newCoords);
        },
        onStationDragEnd: (stationId, projectId, snapResult, originalCoords) => {
            // Show drag confirm modal with snap information
            showStationDragConfirmModal(stationId, projectId, snapResult, originalCoords);
        },
        onPOIDragEnd: (poiId, newCoords, originalCoords) => {
            // Show POI drag confirm modal
            showPOIDragConfirmModal(poiId, newCoords, originalCoords);
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
                
            } else if (type === 'poi') {
                // Get POI data
                const poi = State.allPOIs.get(data.id);
                const poiLat = poi?.latitude?.toFixed(7) || data.feature?.properties?.latitude?.toFixed(7) || 'N/A';
                const poiLng = poi?.longitude?.toFixed(7) || data.feature?.properties?.longitude?.toFixed(7) || 'N/A';
                const poiName = poi?.name || data.feature?.properties?.name || 'POI';
                
                // Copy GPS Coordinates
                items.push({ 
                    label: 'Copy GPS Coordinates', 
                    subtitle: `${poiLat}, ${poiLng}`,
                    icon: '📋', 
                    onClick: () => Utils.copyToClipboard(`${poiLat}, ${poiLng}`) 
                });
                
                // Delete POI (any authenticated user can manage their POIs)
                items.push({ 
                    label: 'Delete Point of Interest', 
                    subtitle: poiName,
                    icon: '🗑️', 
                    onClick: () => POIUI.showDeleteConfirmModal(poi || data.feature.properties) 
                });
                
            } else {
                // Right-click on empty map area
                const coords = data.coordinates;
                const lngLat = { lat: coords[1], lng: coords[0] };
                
                // Check if we can create a station here (need snap point within radius)
                const snapCheck = Geometry.findNearestSnapPointWithinRadius(coords, Geometry.getSnapRadius());
                
                if (!snapCheck.snapped || (snapCheck.projectId && !Layers.isProjectVisible(snapCheck.projectId))) {
                    // Can't create station - too far from survey line
                    items.push({ 
                        label: 'Create Station', 
                        subtitle: "Can't create a station at this location. Too far from the line",
                        icon: '📌', 
                        disabled: true
                    });
                } else {
                    // Check write access for the detected project
                    const nearestProjectId = snapCheck.projectId;
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
                            label: 'No write access', 
                            subtitle: "Can't create a station for this project",
                            icon: '🔒', 
                            disabled: true
                        });
                    }
                }
                
                // POI creation is always available for authenticated users
                items.push({ 
                    label: 'Create Point of Interest', 
                    subtitle: 'Point of Interest',
                    icon: '📍', 
                    onClick: () => POIUI.openCreateModal(coords) 
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
        
        // Load user tags and colors for tag management
        StationTags.init();

        // Load Stations and GeoJSON for each project
        const loadPromises = Config.projects.map(async (project) => {
            const projectPromises = [];

            // Load Stations
            projectPromises.push(
                StationManager.loadStationsForProject(project.id)
                    .then(stations => {
                        Layers.addStationLayer(project.id, { type: 'FeatureCollection', features: stations });
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
                        .catch(e => {
                            console.error(`Error loading GeoJSON for ${project.name}`, e);
                        })
                );
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

        // Load POIs (no delay - load immediately to ensure spinner waits for all data)
        try {
            const poisData = await POIManager.loadAllPOIs();
            Layers.addPOILayer(poisData);
            // Reorder again after POIs are loaded
            Layers.reorderLayers();
        } catch (e) {
            console.error('Error loading POIs', e);
        }

        // Create depth scale dynamically
        createDepthScale();

        // Auto-zoom to fit all project bounds
        if (State.projectBounds.size > 0) {
            const allBounds = new mapboxgl.LngLatBounds();
            State.projectBounds.forEach(bounds => {
                allBounds.extend(bounds);
            });

            if (!allBounds.isEmpty()) {
                map.fitBounds(allBounds, { padding: 50, maxZoom: 16 });
            }
        }

        // Hide Loading Overlay - only after ALL data (projects, GeoJSON, stations, POIs) is loaded
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('opacity-0', 'pointer-events-none');
            setTimeout(() => overlay.remove(), 500);
        }

        console.log('✅ Map Data Loaded (Projects, GeoJSON, Stations, POIs)');
    });

    // Setup UI listeners
    MapCore.setupColorModeToggle(map);

    // Setup POI Manager Button (backup to onclick in HTML)
    const poiManagerButton = document.getElementById('poi-manager-button');
    if (poiManagerButton && !poiManagerButton.onclick) {
        poiManagerButton.addEventListener('click', () => POIUI.openManagerModal());
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
            Layers.addStationLayer(projectId, { type: 'FeatureCollection', features: stations });
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

    // Global Exposes
    window.openStationManager = () => StationUI.openManagerModal();
    window.openSurfaceStationManager = () => SurfaceStationUI.openManagerModal();
    // Expose POI Manager for the button we added above or HTML onclick
    window.openPOIManager = () => POIUI.openManagerModal();
    window.POIUI = POIUI; // Expose for inline HTML onclicks
    window.StationUI = StationUI; // Expose for inline HTML onclicks
    
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

    // POI drag confirmation modal
    function showPOIDragConfirmModal(poiId, newCoords, originalCoords) {
        const poi = State.allPOIs.get(poiId);
        const poiName = poi?.name || 'Point of Interest';
        
        const modalHtml = `
            <div id="poi-drag-confirm-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6">
                        <div class="flex items-center justify-center mb-4">
                            <div class="w-12 h-12 rounded-full flex items-center justify-center text-2xl" 
                                 style="background: linear-gradient(135deg, #3b82f6, #2563eb);">
                                📍
                            </div>
                        </div>
                        <h3 class="text-lg font-semibold text-white text-center mb-2">Move Point of Interest</h3>
                        <p class="text-slate-300 text-center mb-6">
                            Move "${poiName}" to this location?
                        </p>
                        
                        <div class="bg-slate-700/50 rounded-lg p-4 space-y-2 mb-6">
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">POI Name:</span>
                                <span class="text-white">${poiName}</span>
                            </div>
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">New Location:</span>
                                <span class="text-white font-mono">${newCoords[1].toFixed(7)}, ${newCoords[0].toFixed(7)}</span>
                            </div>
                        </div>
                        
                        <div class="flex gap-3">
                            <button id="poi-drag-cancel-btn" class="flex-1 px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg transition-colors">
                                Cancel
                            </button>
                            <button id="poi-drag-confirm-btn" class="flex-1 px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition-colors">
                                Move POI
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove any existing modal
        const existingModal = document.getElementById('poi-drag-confirm-modal');
        if (existingModal) existingModal.remove();
        
        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Setup handlers
        document.getElementById('poi-drag-cancel-btn').onclick = () => {
            Layers.revertPOIPosition(poiId, originalCoords);
            document.getElementById('poi-drag-confirm-modal').remove();
        };
        
        document.getElementById('poi-drag-confirm-btn').onclick = async () => {
            const modal = document.getElementById('poi-drag-confirm-modal');
            
            try {
                await POIManager.movePOI(poiId, newCoords);
                Utils.showNotification('success', 'Point of Interest moved successfully!');
            } catch (error) {
                console.error('Error moving POI:', error);
                Utils.showNotification('error', 'Failed to move POI');
                Layers.revertPOIPosition(poiId, originalCoords);
            }
            
            modal.remove();
        };
        
        // Close on backdrop click
        document.getElementById('poi-drag-confirm-modal').onclick = (e) => {
            if (e.target.id === 'poi-drag-confirm-modal') {
                Layers.revertPOIPosition(poiId, originalCoords);
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

    window.goToPOI = (id, lat, lon) => {
        map.flyTo({ center: [lon, lat], zoom: 18 });
    };
});
