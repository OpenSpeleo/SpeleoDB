import type { MapSourceChangeEvent } from '../../../ts-types/domain/map-sources.ts';
import type { PublicViewerData, PublicViewerLoadOptions, PublicViewerMap } from '../../../ts-types/domain/viewer-composition.ts';
import type { ProjectResponse, ViewerProject } from '../../../ts-types/domain/map-config.ts';
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

import { State } from '../../../frontend_private/static/private/ts/map_viewer/state.ts';
import { DisplayPreferences } from '../../../frontend_private/static/private/ts/map_viewer/display_preferences.ts';
import { MapCore } from '../../../frontend_private/static/private/ts/map_viewer/map/core.ts';
import { MapSources } from '../../../frontend_private/static/private/ts/map_viewer/map/sources.ts';
import { Layers } from '../../../frontend_private/static/private/ts/map_viewer/map/layers.ts';
import { Utils } from '../../../frontend_private/static/private/ts/map_viewer/utils.ts';
import { ProjectPanel } from '../../../frontend_private/static/private/ts/map_viewer/components/project_panel.ts';
import { DepthLegend } from '../../../frontend_private/static/private/ts/map_viewer/components/depth_legend.ts';
import { Config, DEFAULTS } from '../../../frontend_private/static/private/ts/map_viewer/config.ts';
import { getRuntimeContext } from '../../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';
import { clearRenderedSurveyState, createMapHeightUpdater, registerViewerDataLifecycle } from '../../../frontend_private/static/private/ts/map_viewer/viewer_lifecycle.ts';

// Global entry point for Public GIS View Map Viewer
export async function initPublicGISViewer() {
    console.log('🚀 SpeleoDB Public GIS View Viewer Initializing...');

    const context = getRuntimeContext();

    // Validate context for public view mode
    if (context.viewMode !== 'public' || !context.gisToken) {
        console.error('❌ Invalid GIS View context - viewMode or gisToken missing');
        Utils.showNotification('error', 'Invalid GIS View configuration');
        return;
    }

    // 1. Initialize State
    State.resetLayerState();
    DisplayPreferences.init({ persist: false });

    // 2. Initialize Map
    const token = context.mapboxToken || '';

    // Limit max zoom to 12 if precise zoom is not allowed
    const allowPreciseZoom = context.allowPreciseZoom !== false;
    const maxZoom = allowPreciseZoom ? DEFAULTS.MAP.PRECISE_MAX_ZOOM : DEFAULTS.MAP.LIMITED_MAX_ZOOM;

    const map = MapCore.init(token, 'map') as PublicViewerMap;
    map.setMaxZoom(maxZoom);
    DepthLegend.init(map);

    // Prefetch the GIS View GeoJSON concurrently with the Mapbox style/tile
    // load so the (single) network request overlaps map init instead of only
    // starting once the map 'load' event fires. The result is consumed once in
    // loadPublicMapData; later reloads reuse Config.projects unless the list is
    // empty or fresh project data is explicitly requested (original behavior).
    let pendingViewData: Promise<PublicViewerData> | null = fetchPublicViewData();
    // Attach a no-op rejection handler so a failed prefetch is not reported as
    // an unhandled rejection. Real error handling still happens on consume,
    // where `await` rethrows into loadPublicMapData's try/catch.
    void pendingViewData.catch(() => { });

    // Simple function to set map height
    const setMapHeight = createMapHeightUpdater();

    // Set initial map height
    setMapHeight();

    // Update map height on window resize
    window.addEventListener('resize', setMapHeight);

    function clearRenderedMapState() {
        clearRenderedSurveyState(State);
    }

    async function fetchPublicViewData() {
        const response = await fetch(Urls['api:v2:gis-ogc:view-geojson'](context.gisToken!));

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const viewData: unknown = await response.json();

        if (!viewData || typeof viewData !== 'object') {
            throw new Error('Invalid API response');
        }

        return viewData as PublicViewerData;
    }

    async function loadPublicMapData(options: PublicViewerLoadOptions = {}) {
        const {
            fetchProjects = false,
            fitCamera = false,
            hideOverlay = false,
        } = options;

        try {
            let projects: (ViewerProject | ProjectResponse)[] = Config.projects;

            if (fetchProjects || projects.length === 0) {
                console.log('🔄 Fetching GIS View GeoJSON data...');
                // Consume the prefetched request started during init, if still
                // available; otherwise fetch fresh. Swap to null first so a
                // failed prefetch can be retried by the next entry while
                // Config.projects is still empty.
                const pending = pendingViewData;
                pendingViewData = null;
                const viewData = await (pending ?? fetchPublicViewData());
                projects = viewData.projects || [];

                console.log(`✅ Received ${projects.length} projects from GIS View "${viewData.view_name}"`);

                Config.setPublicProjects(projects.map(p => ({
                    id: p.id,
                    name: p.name,
                    color: p.color,
                    geojson_file: (p as ProjectResponse).geojson_file,
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
            void Layers.reorderLayers();

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
    registerViewerDataLifecycle(map, {
        load: async () => {
            await loadPublicMapData({ fetchProjects: true, fitCamera: true, hideOverlay: true });
        },
        sourceChange: async (event: Event & MapSourceChangeEvent) => {
            if (!MapSources.requiresDataReload(event)) return;
            clearRenderedMapState();
            await loadPublicMapData();
        },
    });

    // 4. Setup Color Mode Toggle
    MapCore.setupColorModeToggle(map);
    MapCore.setupMapSourceControl(map, token);
}
