/**
 * Simplified Map Viewer Entry Point for Public GIS Views
 * 
 * This module provides a read-only map viewer for publicly shared GIS Views.
 * It displays ONLY GeoJSON survey data without any management features
 * (no stations, landmarks, context menus, drag/drop, etc.)
 * 
 * Features:
 * - Loads GeoJSON data from a GIS View via public API
 * - Supports color modes: "By Project" and "By Depth"
 * - Project panel for visibility toggling
 * - Auto-zoom to fit all projects
 */

import { State } from '../../../frontend_private/static/private/js/map_viewer/state.js';
import { MapCore } from '../../../frontend_private/static/private/js/map_viewer/map/core.js';
import { MapSources } from '../../../frontend_private/static/private/js/map_viewer/map/sources.js';
import { Layers } from '../../../frontend_private/static/private/js/map_viewer/map/layers.js';
import { Utils } from '../../../frontend_private/static/private/js/map_viewer/utils.js';
import { ProjectPanel } from '../../../frontend_private/static/private/js/map_viewer/components/project_panel.js';
import { DepthLegend } from '../../../frontend_private/static/private/js/map_viewer/components/depth_legend.js';
import { Config, DEFAULTS } from '../../../frontend_private/static/private/js/map_viewer/config.js';

// Global entry point for Public GIS View Map Viewer
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 SpeleoDB Public GIS View Viewer Initializing...');

    const context = window.MAPVIEWER_CONTEXT || {};

    // Validate context for public view mode
    if (context.viewMode !== 'public' || !context.gisToken) {
        console.error('❌ Invalid GIS View context - viewMode or gisToken missing');
        Utils.showNotification('error', 'Invalid GIS View configuration');
        return;
    }

    // 1. Initialize State
    State.resetLayerState();

    // 2. Initialize Map
    const token = context.mapboxToken || '';

    // Limit max zoom to 12 if precise zoom is not allowed
    const allowPreciseZoom = context.allowPreciseZoom !== false;
    const maxZoom = allowPreciseZoom ? DEFAULTS.MAP.PRECISE_MAX_ZOOM : DEFAULTS.MAP.LIMITED_MAX_ZOOM;

    const map = MapCore.init(token, 'map');
    map.setMaxZoom(maxZoom);
    DepthLegend.init(map);

    // Simple function to set map height
    function setMapHeight() {
        const mapElement = document.getElementById('map');
        const rect = mapElement.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const mapTop = rect.top;
        const isMobile = window.innerWidth <= DEFAULTS.UI.MOBILE_BREAKPOINT;
        const newHeight = isMobile ? (viewportHeight - mapTop) : Math.max(viewportHeight - mapTop - DEFAULTS.UI.MAP_PADDING_OFFSET, DEFAULTS.UI.MIN_MAP_HEIGHT);
        mapElement.style.height = newHeight + 'px';
    }

    // Set initial map height
    setMapHeight();

    // Update map height on window resize
    window.addEventListener('resize', setMapHeight);

    function clearRenderedMapState() {
        State.effectiveProjectVisibility = new Map();
        State.allProjectLayers = new Map();
        State.projectDepthDomains = new Map();
        State.activeDepthDomain = null;
        State.projectBounds = new Map();
    }

    async function fetchPublicViewData() {
        const response = await fetch(Urls['api:v2:gis-ogc:view-geojson'](context.gisToken));

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const viewData = await response.json();

        if (!viewData || typeof viewData !== 'object') {
            throw new Error('Invalid API response');
        }

        return viewData;
    }

    async function loadPublicMapData(options = {}) {
        const {
            fetchProjects = false,
            fitCamera = false,
            hideOverlay = false,
        } = options;

        try {
            let projects = Config.projects;

            if (fetchProjects || projects.length === 0) {
                console.log('🔄 Fetching GIS View GeoJSON data...');
                const viewData = await fetchPublicViewData();
                projects = viewData.projects || [];

                console.log(`✅ Received ${projects.length} projects from GIS View "${viewData.view_name}"`);

                Config.setPublicProjects(projects.map(p => ({
                    id: p.id,
                    name: p.name,
                    color: p.color,
                    geojson_file: p.geojson_file,
                })));
                projects = Config.projects;

                // Initialize Project Panel (shows projects from the view)
                ProjectPanel.init();
            } else {
                ProjectPanel.refreshList();
            }

            // Load GeoJSON for each project
            const loadPromises = Config.projects.map(async (project) => {
                const geojsonUrl = project.geojson_url;

                if (geojsonUrl) {
                    try {
                        await Layers.addProjectGeoJSON(project.id, geojsonUrl);
                        console.log(`✅ Loaded GeoJSON for project: ${project.name}`);
                    } catch (e) {
                        console.error(`❌ Error loading GeoJSON for ${project.name}:`, e);
                    }
                }
            });

            await Promise.all(loadPromises);

            // Reorder layers for proper stacking
            Layers.reorderLayers();

            // Auto-zoom to fit all project bounds
            if (fitCamera && State.projectBounds.size > 0) {
                const allBounds = new mapboxgl.LngLatBounds();
                State.projectBounds.forEach(bounds => {
                    allBounds.extend(bounds);
                });

                if (!allBounds.isEmpty()) {
                    const fitMaxZoom = allowPreciseZoom ? DEFAULTS.MAP.FIT_BOUNDS_MAX_ZOOM : DEFAULTS.MAP.LIMITED_MAX_ZOOM;
                    map.fitBounds(allBounds, { padding: DEFAULTS.MAP.FIT_BOUNDS_PADDING, maxZoom: fitMaxZoom });
                }
            }

            console.log('✅ Public GIS View Map Data Loaded');

        } catch (error) {
            console.error('❌ Failed to load GIS View data:', error);
            Utils.showNotification('error', 'Failed to load map data');
        }

        if (hideOverlay) {
            const overlay = document.getElementById('loading-overlay');
            if (overlay) {
                overlay.classList.add('opacity-0', 'pointer-events-none');
                setTimeout(() => overlay.remove(), DEFAULTS.UI.OVERLAY_FADE_DELAY_MS);
            }
        }
    }

    // 3. Load Data when map is ready
    map.on('load', async () => {
        await loadPublicMapData({ fetchProjects: true, fitCamera: true, hideOverlay: true });
    });

    window.addEventListener('speleo:map-source-changed', async (event) => {
        if (!MapSources.requiresDataReload(event)) return;
        clearRenderedMapState();
        await loadPublicMapData();
    });

    // 4. Setup Color Mode Toggle
    MapCore.setupColorModeToggle(map);
    MapCore.setupMapSourceControl(map, token);
});
