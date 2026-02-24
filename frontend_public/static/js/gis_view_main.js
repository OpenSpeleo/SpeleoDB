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
import { Layers } from '../../../frontend_private/static/private/js/map_viewer/map/layers.js';
import { Utils } from '../../../frontend_private/static/private/js/map_viewer/utils.js';
import { ProjectPanel } from '../../../frontend_private/static/private/js/map_viewer/components/project_panel.js';
import { DepthLegend } from '../../../frontend_private/static/private/js/map_viewer/components/depth_legend.js';
import { Config } from '../../../frontend_private/static/private/js/map_viewer/config.js';

const LIMITED_MAX_ZOOM = 13;

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
    State.init();

    // 2. Initialize Map
    const token = context.mapboxToken || '';
    if (!token) {
        console.error('❌ Mapbox token not found');
        Utils.showNotification('error', 'Map configuration missing');
        return;
    }

    // Limit max zoom to 12 if precise zoom is not allowed
    const allowPreciseZoom = context.allowPreciseZoom !== false;
    const maxZoom = allowPreciseZoom ? 22 : LIMITED_MAX_ZOOM;

    const map = MapCore.init(token, 'map');
    map.setMaxZoom(maxZoom);
    DepthLegend.init(map);

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

    // 3. Load Data when map is ready
    map.on('load', async () => {
        console.log('🔄 Fetching GIS View GeoJSON data...');

        try {
            // Fetch GeoJSON URLs from public API
            const response = await fetch(`/api/v1/gis-ogc/view/${context.gisToken}/geojson`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const apiResponse = await response.json();

            if (!apiResponse.success || !apiResponse.data) {
                throw new Error(apiResponse.message || 'Invalid API response');
            }

            const viewData = apiResponse.data;
            const projects = viewData.projects || [];

            console.log(`✅ Received ${projects.length} projects from GIS View "${viewData.view_name}"`);

            // Set up minimal project config for layers (read-only)
            Config._projects = projects.map(p => ({
                id: p.id,
                name: p.name,
                permissions: 'READ_ONLY',  // Public view is always read-only
                geojson_url: p.geojson_file
            }));

            // Initialize Project Panel (shows projects from the view)
            ProjectPanel.init();

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
            if (State.projectBounds.size > 0) {
                const allBounds = new mapboxgl.LngLatBounds();
                State.projectBounds.forEach(bounds => {
                    allBounds.extend(bounds);
                });

                if (!allBounds.isEmpty()) {
                    const fitMaxZoom = allowPreciseZoom ? 16 : LIMITED_MAX_ZOOM;
                    map.fitBounds(allBounds, { padding: 50, maxZoom: fitMaxZoom });
                }
            }

            console.log('✅ Public GIS View Map Data Loaded');

        } catch (error) {
            console.error('❌ Failed to load GIS View data:', error);
            Utils.showNotification('error', 'Failed to load map data');
        }

        // Hide Loading Overlay
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('opacity-0', 'pointer-events-none');
            setTimeout(() => overlay.remove(), 500);
        }
    });

    // 4. Setup Color Mode Toggle
    MapCore.setupColorModeToggle(map);
});

