import {
    PROJECT_SCOPED_MARKER_PROPERTY,
    loadMarkerImages,
    addExplorationLeadMarker,
    refreshExplorationLeadsLayer,
    removeExplorationLeadMarker,
    updateCylinderInstallPosition,
    updateExplorationLeadPosition,
    showMarkerDragHighlight,
    hideMarkerDragHighlight,
    setMarkerDragFeedback,
    resetMarkerDragFeedback,
    loadCylinderInstalls,
    addCylinderInstallsLayer,
    refreshCylinderInstallsLayer,
} from './layers/markers.ts';

import { addLandmarkLayer, toggleLandmarkVisibility, revertLandmarkPosition } from './layers/landmarks.ts';
import {
    addSubSurfaceStationLayer,
    addSurfaceStationLayer,
    updateSurfaceStationPosition,
    updateSurfaceStationColor,
    updateSurfaceStationProperties,
    refreshSurfaceStationsAfterChange,
    updateStationPosition,
    updateStationColor,
    updateStationProperties,
    refreshStationsAfterChange,
} from './layers/stations.ts';
import {
    isGISGeometryVisible,
    showGISGeometryLayers,
    toggleGISGeometryVisibility,
    addGISGeometry,
    acceptGISGeometry,
    refreshGISGeometry,
    clearAppliedGISGeometries,
} from './layers/gis_geometry.ts';

import {
    isGISLayerVisible,
    isGISLayerLoading,
    getGISLayerGeometryTypes,
    isGISLayerGeometryTypeVisible,
    setGISLayerGeometryTypeVisibility,
    setGISLayerLoading,
    toggleGISLayerVisibility,
    showGISLayerLayers,
    addGISLayer,
} from './layers/gis.ts';
import {
    isGPSTrackVisible,
    isGPSTrackLoading,
    setGPSTrackLoading,
    toggleGPSTrackVisibility,
    showGPSTrackLayers,
    addGPSTrackLayer,
} from './layers/gps.ts';
import { addProjectGeoJSON } from './layers/survey.ts';

import {
    applyLayerVisibility,
    scheduleDisplayUpdate,
    setProjectVisibilityBatch,
    emitDisplayPreferencesChanged,
    setCategoryVisibility,
    setStationTypeVisibility,
    revealCategory,
    applyCategoryVisibility,
    applyDisplayPreferences,
    applySurveyStationVisibility,
    applyNetworkLayerVisibility,
    getActiveDepthDomain,
    emitDepthDomainUpdated,
    recomputeActiveDepthDomain,
    forEachProjectLineLayer,
    applyLineColors,
    applyDepthLineColors,
    setColorMode,
    setDepthLimit,
} from './layers/display.ts';

import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { ColorMode } from '../../../../../../ts-types/domain/map-display.ts';

import type { RendererLngLat, RendererValue } from '../../../../../../ts-types/domain/renderer.ts';
import type { GISPopupFeature } from '../../../../../../ts-types/domain/map-layers.ts';

import type { ViewerUpdateContext } from '../../../../../../ts-types/domain/viewer-updates.ts';
import { Config, DEFAULTS } from '../config.ts';
import { State } from '../state.ts';

import { isProjectEffectivelyVisible, isProjectVisible } from './project_visibility.ts';

import { ViewerUpdates } from '../viewer_updates.ts';
import { schedulePreferenceWrite } from '../display_preference_storage.ts';
import { cancelMapNavigation, resetMapNavigation } from './navigation_intent.ts';

import { closeGISFeaturePopups, openGISFeaturePopup } from './layers/gis_popup.ts';
export { bindGISPopupScrollIsolation, updateGISPopupOverflowAffordance, bindGISPopupScrollBehavior, buildGISFeaturePopup } from './layers/gis_popup.ts';
import { cancelLazyOverlays } from './layers/lazy_overlay.ts';

const PROJECT_SCOPED_MARKER_LAYER_IDS = Object.freeze([
    'cylinder-installs-layer',
    'cylinder-installs-labels',
    'exploration-leads-layer'
]);

export const Layers = {
    get colorMode() { return State.displayPreferences.colorMode; },
    set colorMode(mode: ColorMode) { State.displayPreferences.colorMode = mode; },

    whenDisplayApplied() { return ViewerUpdates.whenIdle(); },

    cancelPendingWork() {
        cancelLazyOverlays();
        clearAppliedGISGeometries();
        ViewerUpdates.cancelAll();
        State.layerGeneration += 1;
        State.displayUpdatePending = false;
        resetMapNavigation();
    },
    scheduleDisplayUpdate,
    setProjectVisibilityBatch,
    emitDisplayPreferencesChanged,
    setCategoryVisibility,
    setStationTypeVisibility,
    revealCategory,
    applyCategoryVisibility,
    applyDisplayPreferences,
    applySurveyStationVisibility,
    applyNetworkLayerVisibility,

    // Persist project visibility preferences
    loadProjectVisibilityPrefs: function () {
        try {
            const prefs = localStorage.getItem(Config.VISIBILITY_PREFS_STORAGE_KEY);
            if (prefs) {
                // Storage content retains its existing unchecked visibility contract.
                const parsed = JSON.parse(prefs) as Record<string, boolean>;
                // Apply to state
                Object.keys(parsed).forEach(id => {
                    State.projectLayerStates.set(id, parsed[id]!);
                });
            }
        } catch (e) {
            console.error('Error loading visibility prefs', e);
        }
    },

    saveProjectVisibilityPref: function (projectId: EntityId, isVisible: boolean) {
        State.projectLayerStates.set(String(projectId), isVisible);
        const preferences = State.projectLayerStates;
        schedulePreferenceWrite(Config.VISIBILITY_PREFS_STORAGE_KEY, () => Object.fromEntries(preferences));
    },

    isProjectVisible: function (projectId: EntityId) {
        return isProjectVisible(projectId);
    },

    /**
     * Whether a project is effectively visible on the map.
     * Checks effectiveProjectVisibility (set by applyProjectLayerVisibility)
     * first; falls back to individual preference for projects that haven't
     * been applied yet.
     */
    isProjectEffectivelyVisible: function (projectId: EntityId) {
        return isProjectEffectivelyVisible(projectId, pid => this.isProjectVisible(pid));
    },

    /**
     * Build list of currently visible project IDs (uses effective state).
     */
    getVisibleProjectIds: function () {
        return Config.projects
            .map(project => String(project.id))
            .filter(projectId => this.isProjectEffectivelyVisible(projectId));
    },
    getActiveDepthDomain,
    emitDepthDomainUpdated,
    recomputeActiveDepthDomain,

    /**
     * Filter expression for markers tied to project visibility.
     * Markers without project scoping remain visible.
     */
    getProjectScopedMarkerFilter: function (): RendererValue {
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
        if (!map) return;

        const filter = this.getProjectScopedMarkerFilter();
        PROJECT_SCOPED_MARKER_LAYER_IDS.forEach((layerId) => {
            if (map.getLayer(layerId)) {
                map.setFilter(layerId, filter);
            }
        });
        this.applyCategoryVisibility('explorationLeads');
        this.applyCategoryVisibility('cylinders');
    },

    /**
     * Apply visibility to all tracked layers of one project.
     * @param {string} projectId
     * @param {boolean} [visibilityOverride] - if provided, uses this value
     *   instead of reading from State.projectLayerStates.  Allows callers
     *   (e.g. country-level gate) to hide a project on the map without
     *   changing its stored individual preference.
     */
    applyProjectLayerVisibility: function (projectId: EntityId, visibilityOverride?: boolean) {
        const pid = String(projectId);
        let isVisible;
        if (visibilityOverride !== undefined) {
            isVisible = visibilityOverride;
        } else if (State.effectiveProjectVisibility.has(pid)) {
            isVisible = State.effectiveProjectVisibility.get(pid)!;
        } else {
            isVisible = this.isProjectVisible(pid);
        }

        // Record effective state before the map guard so that layers
        // added later (e.g. by addProjectGeoJSON) pick up the correct
        // visibility even when the map isn't ready yet.
        State.effectiveProjectVisibility.set(pid, isVisible);

        const map = State.map;
        if (!map) return;

        const projectLayerIds = State.allProjectLayers.get(pid) || [];
        projectLayerIds.forEach((layerId) => {
            if (layerId.startsWith(`stations-${pid}-`)) return;
            const categoryVisible = layerId !== `project-points-${pid}`
                || State.displayPreferences.categories.caveEntrances;
            applyLayerVisibility([layerId], isVisible && categoryVisible);
        });
        this.applySurveyStationVisibility(pid, isVisible);
    },

    /**
     * Apply complete project visibility rules (project layers + scoped markers).
     * @param {string} projectId
     * @param {boolean} [visibilityOverride] - forwarded to applyProjectLayerVisibility
     */
    applyProjectVisibility: function (projectId: EntityId, visibilityOverride?: boolean) {
        this.applyProjectLayerVisibility(projectId, visibilityOverride);
        this.applyProjectScopedMarkerVisibility();
    },

    // Network visibility preferences
    loadNetworkVisibilityPrefs: function () {
        try {
            const prefs = localStorage.getItem(Config.NETWORK_VISIBILITY_PREFS_STORAGE_KEY);
            if (prefs) {
                // Storage content retains its existing unchecked visibility contract.
                const parsed = JSON.parse(prefs) as Record<string, boolean>;
                Object.keys(parsed).forEach(id => {
                    State.networkLayerStates.set(id, parsed[id]!);
                });
            }
        } catch (e) {
            console.error('Error loading network visibility prefs', e);
        }
    },

    saveNetworkVisibilityPref: function (networkId: EntityId, isVisible: boolean) {
        State.networkLayerStates.set(String(networkId), isVisible);
        const preferences = State.networkLayerStates;
        schedulePreferenceWrite(Config.NETWORK_VISIBILITY_PREFS_STORAGE_KEY, () => Object.fromEntries(preferences));
    },

    isNetworkVisible: function (networkId: EntityId) {
        try {
            return State.networkLayerStates.get(String(networkId)) !== false;
        } catch (e) {
            return true;
        }
    },
    isGPSTrackVisible,
    isGPSTrackLoading,
    setGPSTrackLoading,
    toggleGPSTrackVisibility,
    showGPSTrackLayers,
    addGPSTrackLayer,
    isGISLayerVisible,
    isGISLayerLoading,
    getGISLayerGeometryTypes,
    isGISLayerGeometryTypeVisible,
    setGISLayerGeometryTypeVisibility,
    setGISLayerLoading,
    toggleGISLayerVisibility,
    showGISLayerLayers,

    closeGISFeaturePopups: function () {
        closeGISFeaturePopups(State.map);
    },

    openGISFeaturePopup: function (feature: GISPopupFeature, lngLat: RendererLngLat) {
        const map = State.map;
        if (!map) return;
        openGISFeaturePopup(map, feature, lngLat);
    },
    addGISLayer,
    isGISGeometryVisible,
    showGISGeometryLayers,
    toggleGISGeometryVisibility,
    addGISGeometry,
    acceptGISGeometry,
    refreshGISGeometry,

    toggleNetworkVisibility: function (networkId: EntityId, isVisible: boolean) {
        const nid = String(networkId);
        this.saveNetworkVisibilityPref(nid, isVisible);
        if (!isVisible) cancelMapNavigation(`network:${nid}`);
        return this.scheduleDisplayUpdate('networks');
    },

    // Country gates change effective visibility without rewriting individual choices.
    toggleProjectVisibility: function (projectId: EntityId, isVisible: boolean, visibilityOverride?: boolean) {
        const pid = String(projectId);
        this.saveProjectVisibilityPref(pid, isVisible);
        return this.setProjectVisibilityBatch([{ projectId: pid, visible: visibilityOverride ?? isVisible }]);
    },
    forEachProjectLineLayer,
    applyLineColors,
    applyDepthLineColors,
    setColorMode,
    setDepthLimit,
    addProjectGeoJSON,
    addSubSurfaceStationLayer,
    addLandmarkLayer,
    toggleLandmarkVisibility,
    addSurfaceStationLayer,
    updateSurfaceStationPosition,
    updateSurfaceStationColor,
    updateSurfaceStationProperties,
    refreshSurfaceStationsAfterChange,
    updateStationPosition,
    updateStationColor,
    updateStationProperties,
    revertLandmarkPosition,
    refreshStationsAfterChange,

    /**
     * Ensure stations, surface stations, Landmarks, and GPS tracks are rendered correctly.
     * GPS tracks should be below survey lines but visible.
     * Call this after all layers are loaded to fix z-ordering.
     */
    reorderLayers() {
        const map = State.map;
        const generation = State.layerGeneration;
        return ViewerUpdates.schedule('layer-order', context => {
            if (map === State.map && generation === State.layerGeneration) return this.reorderLayersNow(context);
        });
    },

    async reorderLayersNow(context: ViewerUpdateContext) {
        const map = State.map;
        if (!map) return;
        // Use our registries: getStyle serializes every GeoJSON source, even
        // when the only information needed is a few hundred layer IDs.
        function* registeredLayerIds() {
            for (const registry of [State.allGPSTrackLayers, State.allGISLayerLayers,
                State.allGISGeometryLayers, State.allProjectLayers, State.allNetworkLayers]) {
                for (const ids of registry.values()) yield* ids;
            }
            yield* PROJECT_SCOPED_MARKER_LAYER_IDS;
            yield* ['landmarks-layer', 'landmarks-labels'];
        }
        const matches: ((id: string) => boolean)[] = [
            id => id.startsWith('gps-track-line-'),
            id => id.startsWith('gps-track-points-'),
            id => id.startsWith('gis-layer-'),
            id => id.startsWith('gis-geometry-') && !id.startsWith('gis-geometry-draft-'),
            id => id.includes('stations-') && id.includes('-circles') && !id.includes('surface-'),
            id => id.includes('stations-') && id.includes('-biology-icons'),
            id => id.includes('stations-') && id.includes('-bone-icons'),
            id => id.includes('stations-') && id.includes('-artifact-icons'),
            id => id.includes('stations-') && id.includes('-geology-icons'),
            id => id.includes('stations-') && id.includes('-labels') && !id.includes('surface-'),
            id => id.startsWith('surface-stations-') && !id.includes('-labels'),
            id => id.startsWith('surface-stations-') && id.includes('-labels'),
            id => id.startsWith('cylinder-installs'),
            id => id.startsWith('exploration-leads'),
            id => id.startsWith('landmarks-'),
        ];
        const groups = matches.map((): string[] => []);
        const seen = new Set();
        for (const id of registeredLayerIds()) {
            if (context.shouldYield() && !await context.yield()) return;
            if (!context.isCurrent() || map !== State.map) return;
            if (seen.has(id)) continue;
            seen.add(id);
            for (let index = 0; index < matches.length; index++) {
                if (matches[index]!(id)) groups[index]!.push(id);
            }
        }
        // Later moves appear above earlier ones. Measurements and draft handles
        // stay above survey overlays, even when another update interrupts us.
        groups.push(DEFAULTS.MEASUREMENT.LAYER_ROLES.map(role => `${DEFAULTS.MEASUREMENT.LAYER_PREFIX}${role}`),
            DEFAULTS.GIS_GEOMETRY.DRAFT_LAYER_ROLES.map(role => `${DEFAULTS.GIS_GEOMETRY.DRAFT_LAYER_PREFIX}${role}`));
        for (const group of groups) {
            for (const id of group) {
                if (context.shouldYield() && !await context.yield()) return;
                if (!context.isCurrent() || map !== State.map) return;
                if (map.getLayer(id)) map.moveLayer(id);
            }
        }
    },
    loadMarkerImages,
    addExplorationLeadMarker,
    refreshExplorationLeadsLayer,
    removeExplorationLeadMarker,
    updateCylinderInstallPosition,
    updateExplorationLeadPosition,
    showMarkerDragHighlight,
    hideMarkerDragHighlight,
    setMarkerDragFeedback,
    resetMarkerDragFeedback,
    loadCylinderInstalls,
    addCylinderInstallsLayer,
    refreshCylinderInstallsLayer
};
