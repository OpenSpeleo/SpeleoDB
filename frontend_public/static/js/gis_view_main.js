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

            // Create depth scale dynamically
            createDepthScale();

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

    // Create depth scale dynamically (matching main implementation)
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

    // Ensure depth scale is hidden initially
    updateDepthLegendVisibility();

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

    // Setup mouse hover for depth indicator (matching main implementation)
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
});

