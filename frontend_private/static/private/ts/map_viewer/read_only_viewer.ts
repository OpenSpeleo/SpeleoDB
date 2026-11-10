import { Renderer } from './map/renderer.ts';
import { computeGeoJSONBounds } from './map/geojson.ts';
import { clipProjectGeoJSON } from './map/preparation.ts';
import type { MapSourceChangeEvent } from '../../../../../ts-types/domain/map-sources.ts';
import type { ReadOnlyViewerData, PublicViewerLoadOptions, PublicViewerMap } from '../../../../../ts-types/domain/viewer-composition.ts';
import type { ProjectMapInput, ViewerProject } from '../../../../../ts-types/domain/map-config.ts';
/**
 * Shared Read-only Survey Map Composition
 *
 * This module renders public GIS Views and authenticated historical projects.
 * It displays ONLY GeoJSON survey data without any management features
 * (no stations, landmarks, context menus, drag/drop, etc.)
 *
 * Features:
 * - Loads authorized GeoJSON data through the owning controller's loader
 * - Supports color modes: "By Project" and "By Depth"
 * - Project panel for visibility toggling
 * - Auto-zoom to fit all projects
 */

import { State } from './state.ts';
import { DisplayPreferences } from './display_preferences.ts';
import { MapCore } from './map/core.ts';
import { MapSources } from './map/sources.ts';
import { Layers } from './map/layers.ts';
import { Utils } from './utils.ts';
import { ProjectPanel } from './components/project_panel.ts';
import { DepthLegend } from './components/depth_legend.ts';
import { Config, DEFAULTS } from './config.ts';
import type { MapRuntimeContext } from '../../../../../ts-types/domain/map-runtime.ts';
import { clearRenderedSurveyState, createMapHeightUpdater, registerViewerDataLifecycle } from './viewer_lifecycle.ts';

export async function initReadOnlyViewer(
    context: Pick<MapRuntimeContext, 'mapboxToken' | 'allowPreciseZoom'>,
    loadData: () => Promise<ReadOnlyViewerData>,
    { showProjectPanel = true, fullscreenContainer }: { showProjectPanel?: boolean; fullscreenContainer?: HTMLElement } = {},
) {
    // 1. Initialize State
    State.resetLayerState();
    DisplayPreferences.init({ persist: false });

    // 2. Initialize Map
    const token = context.mapboxToken || '';

    // Limit max zoom when precise zoom is not allowed
    const allowPreciseZoom = context.allowPreciseZoom !== false;
    const maxZoom = allowPreciseZoom ? DEFAULTS.MAP.PRECISE_MAX_ZOOM : DEFAULTS.MAP.LIMITED_MAX_ZOOM;

    const map = MapCore.init(token, 'map', fullscreenContainer ? { fullscreenContainer } : {}) as PublicViewerMap;
    map.setMaxZoom(maxZoom);
    DepthLegend.init(map);

    // Prefetch the authorized survey metadata concurrently with the Renderer style/tile
    // load so the (single) network request overlaps map init instead of only
    // starting once the map 'load' event fires. The result is consumed once in
    // loadPublicMapData; later reloads reuse the complete source-project list
    // unless unbounded data is empty or fresh data is explicitly requested.
    // Keep that list separate from Config, which contains only the projects
    // surviving a geographic bound.
    let pendingViewData: Promise<ReadOnlyViewerData> | null = loadData();
    // Attach a no-op rejection handler so a failed prefetch is not reported as
    // an unhandled rejection. Real error handling still happens on consume,
    // where `await` rethrows into loadPublicMapData's try/catch.
    void pendingViewData.catch(() => { });
    let sourceProjects: (ViewerProject | ProjectMapInput)[] | null = null;
    let geographicBound: ReadOnlyViewerData['geographic_bound'] = null;
    let dataLoadGeneration = 0;
    let pendingHideOverlay = false;
    let mapReady = false;
    let mapRemoved = false;
    let pendingSelection: { project: ProjectMapInput; resolve: (loaded: boolean) => void } | null = null;

    // Simple function to set map height
    const setMapHeight = createMapHeightUpdater(() => !!fullscreenContainer && document.fullscreenElement === fullscreenContainer);

    // Set initial map height
    setMapHeight();

    // Update map height on window resize
    window.addEventListener('resize', setMapHeight);

    function clearRenderedMapState() {
        clearRenderedSurveyState(State);
    }

    async function loadPublicMapData(options: PublicViewerLoadOptions = {}) {
        const selection = pendingSelection;
        const loadGeneration = ++dataLoadGeneration;
        const layerGeneration = State.layerGeneration;
        const mapAtLoad = State.map;
        const isCurrentLoad = () => loadGeneration === dataLoadGeneration && layerGeneration === State.layerGeneration && mapAtLoad === State.map;
        const {
            fetchProjects = false,
            fitCamera = false,
            hideOverlay = false,
        } = options;
        pendingHideOverlay ||= hideOverlay;
        let loaded = false;

        try {
            let projects: (ViewerProject | ProjectMapInput)[] = sourceProjects ?? Config.projects;

            if (selection) {
                projects = [selection.project];
                geographicBound = null;
                Config.setPublicProjects(projects);
            } else if (fetchProjects || sourceProjects === null || (!geographicBound && projects.length === 0)) {
                console.log('🔄 Fetching GIS View GeoJSON data...');
                // Consume the prefetched request started during init, if still
                // available; otherwise fetch fresh. Swap to null first so a
                // failed prefetch can be retried by the next entry while
                // sourceProjects has not yet been initialized.
                const pending = pendingViewData;
                pendingViewData = null;
                const viewData = await (pending ?? loadData());
                if (!isCurrentLoad()) return;
                projects = [...viewData.projects];
                sourceProjects = projects;
                geographicBound = viewData.geographic_bound ?? null;

                console.log(`✅ Received ${projects.length} projects from GIS View "${viewData.view_name}"`);

                Config.setPublicProjects(projects.map(p => ({
                    id: p.id,
                    name: p.name,
                    color: p.color,
                    geojson_file: (p as ProjectMapInput).geojson_file,
                })));
                projects = Config.projects;

                // Initialize Project Panel (shows projects from the view)
                if (showProjectPanel && !geographicBound) ProjectPanel.init();
            } else {
                Config.setPublicProjects(projects);
                if (showProjectPanel && !geographicBound) ProjectPanel.refreshList();
            }

            // Load GeoJSON for each project
            let boundedLoadFailed = false;
            const loadPromises = Config.projects.map(async (project) => {
                const geojsonUrl = project.geojson_url;

                if (geojsonUrl) {
                    try {
                        if (geographicBound) {
                            const polygon = geographicBound.geojson;
                            await Layers.addProjectGeoJSON(project.id, geojsonUrl, {
                                isCurrent: isCurrentLoad,
                                transformData: (data, isCurrent) => clipProjectGeoJSON(data, polygon, { isCurrent }),
                            });
                        } else {
                            await Layers.addProjectGeoJSON(project.id, geojsonUrl, { isCurrent: isCurrentLoad, throwOnError: true });
                        }
                        if (isCurrentLoad()) console.log(`✅ Loaded GeoJSON for project: ${project.name}`);
                    } catch (e) {
                        if (!isCurrentLoad() || (e instanceof Error && e.name === 'AbortError')) return;
                        boundedLoadFailed = true;
                        console.error(`❌ Error loading GeoJSON for ${project.name}:`, e);
                    }
                }
            });

            await Promise.all(loadPromises);
            if (!isCurrentLoad()) return;

            if (boundedLoadFailed) {
                Utils.showNotification('error', geographicBound
                    ? 'Some survey data could not be displayed within the geographic bound.'
                    : 'Failed to load survey data. Refresh the page to try again.');
            }

            if (geographicBound) {
                Config.setPublicProjects(Config.projects.filter(project => State.projectBounds.has(String(project.id))));
                if (showProjectPanel) ProjectPanel.init();
            }

            if (geographicBound?.geojson.type === 'Polygon') {
                State.gisGeometryStates.set(String(geographicBound.id), true);
                Layers.addGISGeometry(geographicBound);
            }

            // Reorder layers for proper stacking
            void Layers.reorderLayers();

            // Auto-zoom includes the boundary even when every survey clips to empty.
            if ((!selection || !boundedLoadFailed) && (fitCamera || selection) && (State.projectBounds.size > 0 || geographicBound?.geojson.type === 'Polygon')) {
                const allBounds = geographicBound?.geojson.type === 'Polygon'
                    ? computeGeoJSONBounds(geographicBound.geojson, { wrapLongitude: false })
                    : new Renderer.LngLatBounds();
                State.projectBounds.forEach(bounds => {
                    allBounds.extend(bounds);
                });

                if (!allBounds.isEmpty()) {
                    const fitMaxZoom = allowPreciseZoom ? DEFAULTS.MAP.FIT_BOUNDS_MAX_ZOOM : DEFAULTS.MAP.LIMITED_MAX_ZOOM;
                    map.fitBounds(allBounds, { padding: DEFAULTS.MAP.FIT_BOUNDS_PADDING, maxZoom: fitMaxZoom });
                }
            }

            loaded = !boundedLoadFailed;
            if (loaded) console.log('✅ Public GIS View Map Data Loaded');

        } catch (error) {
            if (!isCurrentLoad()) return;
            console.error('❌ Failed to load GIS View data:', error);
            Utils.showNotification('error', 'Failed to load map data');
        }

        if (selection && pendingSelection === selection && isCurrentLoad()) {
            pendingSelection = null;
            if (loaded) {
                sourceProjects = [selection.project];
            } else {
                Config.setPublicProjects(sourceProjects ?? []);
                // A style replacement can remove the previous source while the
                // selected revision is downloading. Restore its committed data.
                if (!sourceProjects || !State.map?.getSource(`project-geojson-${selection.project.id}`)) {
                    await loadPublicMapData({ fitCamera: !sourceProjects });
                }
            }
            selection.resolve(loaded);
        }

        if (pendingHideOverlay) {
            pendingHideOverlay = false;
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
            mapReady = true;
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

    map.on('remove', () => {
        mapRemoved = true;
        ++dataLoadGeneration;
        pendingSelection?.resolve(false);
        pendingSelection = null;
    });

    return {
        showProject(project: ProjectMapInput): Promise<boolean> {
            if (mapRemoved) return Promise.resolve(false);
            pendingSelection?.resolve(false);
            ++dataLoadGeneration;
            return new Promise(resolve => {
                pendingSelection = { project, resolve };
                if (mapReady) void loadPublicMapData();
            });
        },
    };
}
