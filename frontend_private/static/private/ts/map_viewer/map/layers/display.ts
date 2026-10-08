import { stationTypesFilter } from '@speleodb/map-viewer/expressions';
import { publishDisplayEvent } from './display_events.ts';
import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ColorMode, DepthDomain, DisplayCategory, DisplayConcern, DisplayStationType } from '../../../../../../../ts-types/domain/map-display.ts';
import type { ViewerUpdateResult } from '../../../../../../../ts-types/domain/viewer-updates.ts';
import { DEFAULTS } from '../../defaults.ts';
import { State } from '../../state.ts';
import { ViewerUpdates } from '../../viewer_updates.ts';
import { Colors } from '../colors.ts';
import { applyDepthLimit, mergeDepthDomains, isValidDepthLimit } from '../depth.ts';
import { cancelMapNavigation } from '../navigation_intent.ts';

/** The display owner calls back through its facade so overrides retain their receiver. */
interface DisplayLayerOwner {
    colorMode: ColorMode;
    applyProjectLayerVisibility(id: EntityId, override?: boolean): void;
    applyNetworkLayerVisibility(id: EntityId): void;
    applyProjectScopedMarkerVisibility(): void;
    applyCategoryVisibility(id: DisplayCategory): void;
    recomputeActiveDepthDomain(emit?: boolean): DepthDomain | null;
    emitDepthDomainUpdated(): void;
    scheduleDisplayUpdate(...concerns: DisplayConcern[]): Promise<ViewerUpdateResult>;
    emitDisplayPreferencesChanged(): void;
    setCategoryVisibility(id: DisplayCategory, visible: unknown): Promise<ViewerUpdateResult> | undefined;
    setStationTypeVisibility(type: DisplayStationType, visible: unknown): Promise<ViewerUpdateResult> | undefined;
    isNetworkVisible(id: EntityId): boolean;
    getVisibleProjectIds(): string[];
    forEachProjectLineLayer(callback: (layerId: string, projectId: string) => void): void;
    applyLineColors(mode?: ColorMode): void;
}

export function applyLayerVisibility(layerIds: string[], visible: boolean) {
    const map = State.map;
    if (!map) return;
    for (const id of layerIds) {
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    }
}

export function scheduleDisplayUpdate(this: Pick<DisplayLayerOwner, 'applyProjectLayerVisibility' | 'applyNetworkLayerVisibility' | 'applyProjectScopedMarkerVisibility' | 'applyCategoryVisibility' | 'recomputeActiveDepthDomain' | 'colorMode' | 'emitDepthDomainUpdated'>, ...concerns: DisplayConcern[]) {
    concerns.forEach(concern => State.displayDirty.add(concern));
    const generation = State.layerGeneration;
    State.displayUpdatePending = true;
    publishDisplayEvent({ type: 'speleo:display-update-pending' });
    return ViewerUpdates.schedule('display', async context => {
        const map = State.map;
        const valid = () => context.isCurrent() && State.map === map && State.layerGeneration === generation;
        if (!valid()) return;
        const dirty = State.displayDirty;
        const applyProjects = dirty.has('projects') || dirty.has('categories');
        if (applyProjects) {
            for (const projectId of State.allProjectLayers.keys()) {
                if (!valid()) return;
                this.applyProjectLayerVisibility(projectId);
                if (context.shouldYield()) await context.yield();
            }
        }
        if (dirty.has('networks') || dirty.has('categories')) {
            for (const networkId of State.allNetworkLayers.keys()) {
                if (!valid()) return;
                this.applyNetworkLayerVisibility(networkId);
                if (context.shouldYield()) await context.yield();
            }
        }
        if (!valid()) return;
        if (applyProjects) this.applyProjectScopedMarkerVisibility();
        if (dirty.has('categories')) this.applyCategoryVisibility('landmarks');
        if (dirty.has('depth')) this.recomputeActiveDepthDomain(false);
        if (dirty.has('colors') || (dirty.has('depth') && this.colorMode === 'depth')) {
            for (const [projectId, layerIds] of State.allProjectLayers) {
                for (const layerId of layerIds) {
                    if (!valid()) return;
                    if (map?.getLayer(layerId)?.type === 'line') {
                        map.setPaintProperty(layerId, 'line-color', Colors.getSurveyPaint(projectId, this.colorMode, State.activeDepthDomain));
                    }
                    if (context.shouldYield()) await context.yield();
                }
            }
        }
        if (!valid()) return;
        const depthChanged = dirty.has('depth') || dirty.has('depth-labels');
        const colorsChanged = dirty.has('colors');
        dirty.clear();
        State.displayUpdatePending = false;
        if (depthChanged) this.emitDepthDomainUpdated();
        if (colorsChanged) publishDisplayEvent({ type: 'speleo:color-mode-changed', detail: { mode: this.colorMode } });
        publishDisplayEvent({ type: 'speleo:display-update-applied' });
    }, { onError: error => {
        if (State.layerGeneration !== generation) return;
        State.displayUpdatePending = false;
        publishDisplayEvent({ type: 'speleo:display-update-failed', detail: { error } });
    } });
}

export function setProjectVisibilityBatch(this: Pick<DisplayLayerOwner, 'scheduleDisplayUpdate'>, updates: { projectId: EntityId; visible: boolean }[]) {
    for (const { projectId, visible } of updates) {
        const id = String(projectId);
        State.effectiveProjectVisibility.set(id, visible);
        if (!visible) cancelMapNavigation(`project:${id}`);
    }
    return this.scheduleDisplayUpdate('projects', 'depth');
}

export function emitDisplayPreferencesChanged() {
    publishDisplayEvent({ type: 'speleo:display-preferences-changed',
        detail: { preferences: State.displayPreferences },
    });
}

export function setCategoryVisibility(this: Pick<DisplayLayerOwner, 'emitDisplayPreferencesChanged' | 'scheduleDisplayUpdate'>, id: DisplayCategory, visible: unknown) {
    if (!Object.hasOwn(State.displayPreferences.categories, id) || typeof visible !== 'boolean') return;
    if (State.displayPreferences.categories[id] === visible) return;
    State.displayPreferences.categories[id] = visible;
    this.emitDisplayPreferencesChanged();
    return this.scheduleDisplayUpdate('categories');
}

export function setStationTypeVisibility(this: Pick<DisplayLayerOwner, 'emitDisplayPreferencesChanged' | 'scheduleDisplayUpdate'>, type: DisplayStationType, visible: unknown) {
    if (!Object.hasOwn(State.displayPreferences.stationTypes, type) || typeof visible !== 'boolean') return;
    if (State.displayPreferences.stationTypes[type] === visible) return;
    State.displayPreferences.stationTypes[type] = visible;
    this.emitDisplayPreferencesChanged();
    return this.scheduleDisplayUpdate('categories');
}

export function revealCategory(this: Pick<DisplayLayerOwner, 'setCategoryVisibility' | 'setStationTypeVisibility'>, id: DisplayCategory, options: { stationType?: DisplayStationType | null | undefined } = {}) {
    void this.setCategoryVisibility(id, true);
    if (Object.hasOwn(options, 'stationType')) void this.setStationTypeVisibility(options.stationType ?? 'sensor', true);
}

export function applyCategoryVisibility(this: Pick<DisplayLayerOwner, 'applyProjectLayerVisibility' | 'applyNetworkLayerVisibility'>, id: DisplayCategory) {
    const visible = State.displayPreferences.categories[id];
    switch (id) {
        case 'caveEntrances':
        case 'surveyStations':
            State.allProjectLayers.forEach((_, projectId) => this.applyProjectLayerVisibility(projectId));
            break;
        case 'surfaceStations':
            State.allNetworkLayers.forEach((_, networkId) => this.applyNetworkLayerVisibility(networkId));
            break;
        case 'landmarks':
            applyLayerVisibility(['landmarks-layer', 'landmarks-labels'], visible);
            break;
        case 'explorationLeads':
            applyLayerVisibility(['exploration-leads-layer'], visible);
            break;
        case 'cylinders':
            applyLayerVisibility(['cylinder-installs-layer', 'cylinder-installs-labels'], visible);
            break;
    }
}

export function applyDisplayPreferences(this: Pick<DisplayLayerOwner, 'emitDisplayPreferencesChanged' | 'scheduleDisplayUpdate'>) {
    this.emitDisplayPreferencesChanged();
    return this.scheduleDisplayUpdate('categories', 'depth', 'colors');
}

export function applySurveyStationVisibility(projectId: EntityId, projectVisible: boolean) {
    const map = State.map;
    if (!map) return;
    const visible = projectVisible && State.displayPreferences.categories.surveyStations;
    for (const { id, layerSuffix } of DEFAULTS.DISPLAY.STATION_TYPES) {
        applyLayerVisibility([`stations-${projectId}-${layerSuffix}`], visible && State.displayPreferences.stationTypes[id]);
    }
    const labelId = `stations-${projectId}-labels`;
    if (map.getLayer(labelId)) {
        map.setFilter(labelId, stationTypesFilter(State.displayPreferences.stationTypes));
        applyLayerVisibility([labelId], visible);
    }
}

export function applyNetworkLayerVisibility(this: Pick<DisplayLayerOwner, 'isNetworkVisible'>, networkId: EntityId) {
    applyLayerVisibility(State.allNetworkLayers.get(String(networkId)) || [],
        this.isNetworkVisible(networkId) && State.displayPreferences.categories.surfaceStations);
}

export function getActiveDepthDomain() {
    return State.activeDepthDomain;
}

export function emitDepthDomainUpdated() {
    const depthDomain = State.activeDepthDomain;
    const detail = {
        domain: depthDomain,
        available: Boolean(depthDomain),
        max: depthDomain ? depthDomain.max : null
    };

    if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') {
        return;
    }

    publishDisplayEvent({ type: 'speleo:depth-domain-updated', detail });
    // Keep legacy event for existing listeners.
    publishDisplayEvent({ type: 'speleo:depth-data-updated', detail });
}

export function recomputeActiveDepthDomain(this: Pick<DisplayLayerOwner, 'getVisibleProjectIds' | 'emitDepthDomainUpdated'>, emit = true) {
    const activeDomains = this.getVisibleProjectIds().map((projectId) => {
        return State.projectDepthDomains.get(String(projectId)) || null;
    });
    State.activeDepthDomain = applyDepthLimit(
        mergeDepthDomains(activeDomains), State.displayPreferences.depthLimitFeet
    );
    if (emit) this.emitDepthDomainUpdated();
    return State.activeDepthDomain;
}

export function forEachProjectLineLayer(callback: (layerId: string, projectId: string) => void) {
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
}

export function applyLineColors(this: { colorMode: ColorMode; forEachProjectLineLayer(callback: (layerId: string, projectId: string) => void): void }, mode: ColorMode = this.colorMode) {
    const map = State.map;
    if (!map) return;

    this.forEachProjectLineLayer((layerId, projectId) => {
        map.setPaintProperty(layerId, 'line-color', Colors.getSurveyPaint(projectId, mode, State.activeDepthDomain));
    });
}

export function applyDepthLineColors(this: Pick<DisplayLayerOwner, 'applyLineColors'>) {
    this.applyLineColors('depth');
}

export function setColorMode(this: Pick<DisplayLayerOwner, 'colorMode' | 'emitDisplayPreferencesChanged' | 'scheduleDisplayUpdate'>, mode: unknown) {
    if (!Colors.isValidColorMode(mode)) return;
    this.colorMode = mode as ColorMode;

    this.emitDisplayPreferencesChanged();
    return this.scheduleDisplayUpdate('depth', 'colors');
}

export function setDepthLimit(this: Pick<DisplayLayerOwner, 'emitDisplayPreferencesChanged' | 'scheduleDisplayUpdate'>, limitFeet: unknown, unit: unknown) {
    if (!isValidDepthLimit(limitFeet) || (unit !== 'ft' && unit !== 'm')) return false;
    const preferences = State.displayPreferences;
    const limitChanged = preferences.depthLimitFeet !== limitFeet;
    if (!limitChanged && preferences.depthUnit === unit) return true;

    preferences.depthLimitFeet = limitFeet;
    preferences.depthUnit = unit;
    this.emitDisplayPreferencesChanged();
    void this.scheduleDisplayUpdate(...(limitChanged ? ['depth'] as const : ['depth-labels'] as const));
    return true;
}
