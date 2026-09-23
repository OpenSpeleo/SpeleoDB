import { Config, DEFAULTS } from '../config.js';
import { State } from '../state.js';
import { Colors } from './colors.js';
import {
    applyDepthLimit,
    mergeDepthDomains,
    isValidDepthLimit
} from './depth.js';
import { Geometry } from './geometry.js';
import { computeGeoJSONBounds } from './geojson.js';
import { addVectorOverlay, VECTOR_OVERLAY_GEOMETRY_TYPES } from './vector_overlay.js';
import { gisLayerGeometryFilter } from './gis_layer_geometry.js';
import { geoJSONLineWidth } from './line_rendering.js';
import { API } from '../api.js';
import { getRuntimeContext } from '../runtime_context.js';
import { ViewerUpdates } from '../viewer_updates.js';
import { schedulePreferenceWrite } from '../display_preference_storage.js';
import { cancelMapNavigation, resetMapNavigation } from './navigation_intent.js';
import { Utils } from '../utils.js';
import { prepareProjectGeoJSON, prepareGeoJSONBounds, prepareGISLayerGeoJSONAsync } from './preparation.js';
import { readViewerGeoJSON } from './read_geojson.js';

// Track whether custom marker images have been loaded
let markerImagesLoaded = false;
const gisFeaturePopups = new WeakMap();

// Data requests are shared independently of the serial map-application queue.
const overlayRequests = new Map();
const overlayIntents = new Map();
const overlayCachedVersions = new Map();
const overlayAppliedVersions = new Map();
const gisGeometryAppliedRecords = new Map();

async function toggleLazyOverlay({ kind, id, visible, cache, states, layers, details, prepare, install, show, loading, metadata }) {
    const key = `${kind}:${id}`;
    const intent = {};
    overlayIntents.set(key, intent);
    states.set(id, visible);
    const map = State.map;
    const generation = State.layerGeneration;
    const tracksMetadata = Boolean(metadata?.());
    const revision = () => metadata?.()?.modified_date ?? null;
    const sameSession = () => State.layerGeneration === generation && State.map === map;
    const ownsIntent = () => sameSession() && overlayIntents.get(key) === intent;
    const entityExists = () => !tracksMetadata || Boolean(metadata?.());
    const current = () => ownsIntent() && entityExists();
    if (!visible) {
        loading?.(false);
        cancelMapNavigation(key);
        const result = await ViewerUpdates.schedule(key, () => { if (current()) show(false); });
        return current() && result.status === 'applied';
    }
    try {
        while (current() && states.get(id)) {
            const version = revision();
            const versionCurrent = () => current() && revision() === version;
            try {
                let data = cache.get(id);
                const cached = overlayCachedVersions.get(key);
                if (data && cached?.generation !== generation) {
                    // Adopt cached sources restored before this intent tracker first saw them.
                    const ids = layers.get(id);
                    if (ids?.length && map?.getLayer(ids[0])) {
                        overlayAppliedVersions.set(key, { generation, revision: version, data });
                    }
                }
                if (data && cached?.generation === generation && cached.data === data && cached.revision !== version) {
                    cache.delete(id);
                    data = undefined;
                }
                if (!data) {
                    loading?.(true);
                    let request = overlayRequests.get(key);
                    if (!request || request.generation !== generation || request.revision !== version) {
                        request?.controller.abort();
                        const controller = new AbortController();
                        request = { generation, revision: version, controller };
                        request.promise = details(controller.signal);
                        overlayRequests.set(key, request);
                        // An older finalizer must not clear its replacement.
                        void request.promise.finally(() => {
                            if (overlayRequests.get(key) === request) overlayRequests.delete(key);
                        }).catch(() => {});
                    }
                    data = await request.promise;
                    if (!sameSession() || !entityExists()) return false;
                    // A list refresh may have published a newer file during the download.
                    if (revision() !== version) continue;
                    cache.set(id, data);
                }
                overlayCachedVersions.set(key, { generation, revision: version, data });
                if (!versionCurrent() || !states.get(id)) return false;
                const needsInstall = () => {
                    const ids = layers.get(id);
                    const applied = overlayAppliedVersions.get(key);
                    return !ids?.length || !map?.getLayer(ids[0]) || applied?.generation !== generation
                        || applied.revision !== version || applied.data !== data;
                };
                const prepared = needsInstall() && prepare ? await prepare(data, versionCurrent) : undefined;
                if (!current()) return false;
                if (!versionCurrent()) continue;
                const result = await ViewerUpdates.schedule(key, async context => {
                    if (!versionCurrent() || !context.isCurrent()) return;
                    if (needsInstall()) {
                        await install(data, () => versionCurrent() && context.isCurrent(), prepared);
                        if (!versionCurrent() || !context.isCurrent()) return;
                        overlayAppliedVersions.set(key, { generation, revision: version, data });
                    }
                    show(states.get(id) === true);
                });
                if (!current()) return false;
                if (!versionCurrent()) continue;
                if (result.status === 'failed') throw result.error;
                return result.status === 'applied' && states.get(id) === true;
            } catch (error) {
                // Retry only a changed metadata revision, never a genuine failed request.
                if (current() && revision() !== version) continue;
                throw error;
            }
        }
        return false;
    } catch (error) {
        if (!current()) return false;
        states.set(id, false);
        cache.delete(id);
        show(false);
        console.error(`Failed to display ${kind}:`, error);
        Utils.showNotification('error', 'Unable to display this item. Toggle it on to retry.');
        return false;
    } finally {
        // Metadata removal invalidates rendering, but this intent still owns its spinner.
        if (ownsIntent()) loading?.(false);
    }
}

const ZOOM_LEVELS = DEFAULTS.ZOOM_LEVELS;

const PROJECT_SCOPED_MARKER_PROPERTY = 'project_id';
const PROJECT_SCOPED_MARKER_LAYER_IDS = Object.freeze([
    'cylinder-installs-layer',
    'cylinder-installs-labels',
    'exploration-leads-layer'
]);

function applyLayerVisibility(layerIds, visible) {
    const map = State.map;
    if (!map) return;
    for (const id of layerIds) {
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    }
}

function boundedGISPopupText(value, maxLength) {
    const text = String(value ?? '').trim();
    if (text.length <= maxLength) return text;
    return `${text.slice(0, maxLength - 1).trimEnd()}…`;
}

function structuredGISPopupValue(value) {
    if (value && typeof value === 'object') return value;
    if (typeof value !== 'string') return null;
    try {
        const parsed = JSON.parse(value);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch {
        return null;
    }
}

function readableGISPopupLabel(value) {
    return String(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

function gisPopupMetadataRows(feature) {
    const properties = feature?.properties || {};
    const rows = [];
    const geometryType = feature?.geometry?.type;
    if (geometryType) rows.push(['Geometry', readableGISPopupLabel(geometryType)]);

    const folderPath = structuredGISPopupValue(properties.folder_path);
    if (Array.isArray(folderPath) && folderPath.length > 0) {
        rows.push(['Folder', folderPath.map(String).join(' / ')]);
    }

    const extendedData = structuredGISPopupValue(properties.extended_data);
    if (extendedData && !Array.isArray(extendedData)) {
        for (const [key, value] of Object.entries(extendedData)) {
            if (value === null || value === undefined || typeof value === 'object') continue;
            rows.push([readableGISPopupLabel(key), value]);
        }
    }
    return rows.slice(0, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_MAX_ROWS);
}

export function bindGISPopupScrollIsolation(container) {
    const stopPropagation = event => event.stopPropagation();
    container.addEventListener('wheel', stopPropagation, { passive: true });
    container.addEventListener('touchmove', stopPropagation, { passive: true });
    return () => {
        container.removeEventListener('wheel', stopPropagation);
        container.removeEventListener('touchmove', stopPropagation);
    };
}

export function updateGISPopupOverflowAffordance(card) {
    const viewport = card.querySelector('.gis-layer-feature-card__scroll');
    if (!viewport) return false;
    const tolerance = DEFAULTS.GIS_LAYER_RENDER.POPUP_OVERFLOW_TOLERANCE_PX;
    const maxScrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    const isScrollable = maxScrollTop > tolerance;
    card.classList.toggle('is-scrollable', isScrollable);

    const rail = card.querySelector('.gis-layer-feature-card__scroll-rail');
    const thumb = rail?.querySelector('.gis-layer-feature-card__scroll-thumb');
    if (!isScrollable) {
        viewport.removeAttribute('tabindex');
        viewport.removeAttribute('aria-label');
        thumb?.style.removeProperty('height');
        thumb?.style.removeProperty('transform');
        return false;
    }

    viewport.tabIndex = 0;
    viewport.setAttribute('aria-label', 'Scrollable feature description');
    if (rail && thumb && rail.clientHeight > 0) {
        const render = DEFAULTS.GIS_LAYER_RENDER;
        const proportionalHeight = rail.clientHeight * (viewport.clientHeight / viewport.scrollHeight);
        const thumbHeight = Math.min(
            rail.clientHeight,
            Math.max(render.POPUP_SCROLL_THUMB_MIN_PX, proportionalHeight),
        );
        const availableTravel = Math.max(0, rail.clientHeight - thumbHeight);
        const scrollProgress = Math.min(1, Math.max(0, viewport.scrollTop / maxScrollTop));
        thumb.style.height = `${thumbHeight}px`;
        thumb.style.transform = `translateY(${availableTravel * scrollProgress}px)`;
    } else {
        thumb?.style.removeProperty('height');
        thumb?.style.removeProperty('transform');
    }
    return isScrollable;
}

export function bindGISPopupScrollBehavior(card) {
    const viewport = card.querySelector('.gis-layer-feature-card__scroll');
    if (!viewport) return () => {};

    const stopIsolation = bindGISPopupScrollIsolation(viewport);
    const update = () => updateGISPopupOverflowAffordance(card);
    const frame = window.requestAnimationFrame(update);
    viewport.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update, { passive: true });

    const resizeObserver = globalThis.ResizeObserver ? new ResizeObserver(update) : null;
    resizeObserver?.observe(viewport);
    if (viewport.firstElementChild) resizeObserver?.observe(viewport.firstElementChild);

    return () => {
        window.cancelAnimationFrame(frame);
        viewport.removeEventListener('scroll', update);
        window.removeEventListener('resize', update);
        resizeObserver?.disconnect();
        stopIsolation();
    };
}

export function buildGISFeaturePopup(feature) {
    const properties = feature?.properties || {};
    const card = document.createElement('article');
    card.className = 'gis-layer-feature-card';
    card.setAttribute('aria-label', 'GIS feature details');

    const header = document.createElement('header');
    header.className = 'gis-layer-feature-card__header';
    const eyebrow = document.createElement('span');
    eyebrow.className = 'gis-layer-feature-card__eyebrow';
    eyebrow.textContent = 'GIS feature';
    const title = document.createElement('h3');
    title.className = 'gis-layer-feature-card__title';
    title.textContent = boundedGISPopupText(
        properties.name || properties.title || properties.render_label || 'Untitled feature',
        DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS,
    );
    header.append(eyebrow, title);
    card.appendChild(header);

    const description = boundedGISPopupText(
        properties.description,
        DEFAULTS.GIS_LAYER_RENDER.POPUP_DESCRIPTION_MAX_CHARS,
    );
    if (description) {
        const body = document.createElement('div');
        body.className = 'gis-layer-feature-card__body';
        const viewport = document.createElement('div');
        viewport.className = 'gis-layer-feature-card__scroll';
        const descriptionElement = document.createElement('p');
        descriptionElement.className = 'gis-layer-feature-card__description';
        descriptionElement.textContent = description;
        viewport.appendChild(descriptionElement);

        const rail = document.createElement('span');
        rail.className = 'gis-layer-feature-card__scroll-rail';
        rail.setAttribute('aria-hidden', 'true');
        const thumb = document.createElement('span');
        thumb.className = 'gis-layer-feature-card__scroll-thumb';
        rail.appendChild(thumb);
        body.append(viewport, rail);
        card.appendChild(body);
    }

    const rows = gisPopupMetadataRows(feature);
    if (rows.length > 0) {
        const metadata = document.createElement('dl');
        metadata.className = 'gis-layer-feature-card__metadata';
        for (const [label, value] of rows) {
            const term = document.createElement('dt');
            term.textContent = boundedGISPopupText(label, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS);
            const detail = document.createElement('dd');
            detail.textContent = boundedGISPopupText(value, DEFAULTS.GIS_LAYER_RENDER.POPUP_METADATA_VALUE_MAX_CHARS);
            metadata.append(term, detail);
        }
        card.appendChild(metadata);
    }
    return card;
}

function openGISFeaturePopup(map, feature, lngLat) {
    if (!globalThis.mapboxgl?.Popup) return;
    const content = buildGISFeaturePopup(feature);
    const cleanup = bindGISPopupScrollBehavior(content);
    const popup = new mapboxgl.Popup({
        className: 'gis-layer-feature-popup',
        closeButton: true,
        closeOnClick: true,
        focusAfterOpen: true,
        maxWidth: `${DEFAULTS.GIS_LAYER_RENDER.POPUP_MAX_WIDTH_PX}px`,
    });
    if (!gisFeaturePopups.has(map)) gisFeaturePopups.set(map, new Set());
    const popups = gisFeaturePopups.get(map);
    popups.add(popup);
    popup.once?.('close', () => {
        popups.delete(popup);
        cleanup();
    });
    popup
        .setLngLat(lngLat)
        .setDOMContent(content)
        .addTo(map);
}

/**
 * Remove map layers first, then their source to avoid dependent-layer issues.
 */
function removeLayersAndSource(map, layerIds, sourceId) {
    layerIds.forEach((layerId) => {
        if (map.getLayer(layerId)) {
            map.removeLayer(layerId);
        }
    });

    if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
    }
}

/**
 * Build gas mix label text from cylinder percentages.
 */
function getCylinderGasMixTextExpression() {
    return [
        'case',
        ['==', ['get', 'o2_percentage'], 100], 'Oxygen',
        ['>', ['get', 'he_percentage'], 0],
        [
            'concat',
            ['to-string', ['get', 'o2_percentage']],
            '/',
            ['to-string', ['get', 'he_percentage']]
        ],
        ['==', ['get', 'o2_percentage'], 21], 'Air',
        ['concat', 'NX', ['to-string', ['get', 'o2_percentage']]]
    ];
}

/**
 * Build label for cylinder installs: install-date\ngas-mix@pressure.
 */
function getCylinderInstallLabelExpression() {
    return [
        'concat',
        ['coalesce', ['get', 'install_date'], 'Unknown date'],
        '\n',
        getCylinderGasMixTextExpression(),
        '@',
        ['to-string', ['get', 'pressure']],
        ' ',
        ['case',
            ['==', ['get', 'pressure_unit_system'], 'imperial'], 'PSI',
            'BAR'
        ]
    ];
}

/**
 * Add normalized project visibility property to map marker feature properties.
 */
function withProjectScopedMarkerProperties(properties, projectId) {
    return {
        ...properties,
        [PROJECT_SCOPED_MARKER_PROPERTY]: projectId ? String(projectId) : null
    };
}

export const Layers = {
    get colorMode() { return State.displayPreferences.colorMode; },
    set colorMode(mode) { State.displayPreferences.colorMode = mode; },

    whenDisplayApplied() { return ViewerUpdates.whenIdle(); },

    cancelPendingWork() {
        for (const request of overlayRequests.values()) request.controller.abort();
        overlayRequests.clear();
        overlayIntents.clear();
        overlayCachedVersions.clear();
        overlayAppliedVersions.clear();
        gisGeometryAppliedRecords.clear();
        ViewerUpdates.cancelAll();
        State.layerGeneration += 1;
        State.displayUpdatePending = false;
        resetMapNavigation();
    },

    scheduleDisplayUpdate(...concerns) {
        concerns.forEach(concern => State.displayDirty.add(concern));
        const generation = State.layerGeneration;
        State.displayUpdatePending = true;
        window.dispatchEvent(new CustomEvent('speleo:display-update-pending'));
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
            if (colorsChanged) window.dispatchEvent(new CustomEvent('speleo:color-mode-changed', { detail: { mode: this.colorMode } }));
            window.dispatchEvent(new CustomEvent('speleo:display-update-applied'));
        }, { onError: error => {
            if (State.layerGeneration !== generation) return;
            State.displayUpdatePending = false;
            window.dispatchEvent(new CustomEvent('speleo:display-update-failed', { detail: { error } }));
        } });
    },

    setProjectVisibilityBatch(updates) {
        for (const { projectId, visible } of updates) {
            const id = String(projectId);
            State.effectiveProjectVisibility.set(id, visible);
            if (!visible) cancelMapNavigation(`project:${id}`);
        }
        return this.scheduleDisplayUpdate('projects', 'depth');
    },

    emitDisplayPreferencesChanged() {
        window.dispatchEvent(new CustomEvent('speleo:display-preferences-changed', {
            detail: { preferences: State.displayPreferences },
        }));
    },

    setCategoryVisibility(id, visible) {
        if (!Object.hasOwn(State.displayPreferences.categories, id) || typeof visible !== 'boolean') return;
        if (State.displayPreferences.categories[id] === visible) return;
        State.displayPreferences.categories[id] = visible;
        this.emitDisplayPreferencesChanged();
        return this.scheduleDisplayUpdate('categories');
    },

    setStationTypeVisibility(type, visible) {
        if (!Object.hasOwn(State.displayPreferences.stationTypes, type) || typeof visible !== 'boolean') return;
        if (State.displayPreferences.stationTypes[type] === visible) return;
        State.displayPreferences.stationTypes[type] = visible;
        this.emitDisplayPreferencesChanged();
        return this.scheduleDisplayUpdate('categories');
    },

    revealCategory(id, options = {}) {
        this.setCategoryVisibility(id, true);
        if (Object.hasOwn(options, 'stationType')) this.setStationTypeVisibility(options.stationType ?? 'sensor', true);
    },

    applyCategoryVisibility(id) {
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
    },

    applyDisplayPreferences() {
        this.emitDisplayPreferencesChanged();
        return this.scheduleDisplayUpdate('categories', 'depth', 'colors');
    },

    applySurveyStationVisibility(projectId, projectVisible) {
        const map = State.map;
        if (!map) return;
        const visible = projectVisible && State.displayPreferences.categories.surveyStations;
        for (const { id, layerSuffix } of DEFAULTS.DISPLAY.STATION_TYPES) {
            applyLayerVisibility([`stations-${projectId}-${layerSuffix}`], visible && State.displayPreferences.stationTypes[id]);
        }
        const labelId = `stations-${projectId}-labels`;
        if (map.getLayer(labelId)) {
            const enabledTypes = DEFAULTS.DISPLAY.STATION_TYPES
                .filter(({ id }) => State.displayPreferences.stationTypes[id]).map(({ id }) => id);
            map.setFilter(labelId, ['in', ['coalesce', ['get', 'type'], 'sensor'], ['literal', enabledTypes]]);
            applyLayerVisibility([labelId], visible);
        }
    },

    applyNetworkLayerVisibility(networkId) {
        applyLayerVisibility(State.allNetworkLayers.get(String(networkId)) || [],
            this.isNetworkVisible(networkId) && State.displayPreferences.categories.surfaceStations);
    },

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
        State.projectLayerStates.set(String(projectId), isVisible);
        const preferences = State.projectLayerStates;
        schedulePreferenceWrite(Config.VISIBILITY_PREFS_STORAGE_KEY, () => Object.fromEntries(preferences));
    },

    isProjectVisible: function (projectId) {
        try {
            return State.projectLayerStates.get(String(projectId)) !== false;
        } catch (e) {
            return true;
        }
    },

    /**
     * Whether a project is effectively visible on the map.
     * Checks effectiveProjectVisibility (set by applyProjectLayerVisibility)
     * first; falls back to individual preference for projects that haven't
     * been applied yet.
     */
    isProjectEffectivelyVisible: function (projectId) {
        const pid = String(projectId);
        if (State.effectiveProjectVisibility.has(pid)) {
            return State.effectiveProjectVisibility.get(pid);
        }
        return this.isProjectVisible(pid);
    },

    /**
     * Build list of currently visible project IDs (uses effective state).
     */
    getVisibleProjectIds: function () {
        return Config.projects
            .map(project => String(project.id))
            .filter(projectId => this.isProjectEffectivelyVisible(projectId));
    },

    getActiveDepthDomain: function () {
        return State.activeDepthDomain;
    },

    emitDepthDomainUpdated: function () {
        const depthDomain = State.activeDepthDomain;
        const detail = {
            domain: depthDomain,
            available: Boolean(depthDomain),
            max: depthDomain ? depthDomain.max : null
        };

        if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') {
            return;
        }

        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', { detail }));
        // Keep legacy event for existing listeners.
        window.dispatchEvent(new CustomEvent('speleo:depth-data-updated', { detail }));
    },

    recomputeActiveDepthDomain: function (emit = true) {
        const activeDomains = this.getVisibleProjectIds().map((projectId) => {
            return State.projectDepthDomains.get(String(projectId)) || null;
        });
        State.activeDepthDomain = applyDepthLimit(
            mergeDepthDomains(activeDomains), State.displayPreferences.depthLimitFeet
        );
        if (emit) this.emitDepthDomainUpdated();
        return State.activeDepthDomain;
    },

    /**
     * Filter expression for markers tied to project visibility.
     * Markers without project scoping remain visible.
     */
    getProjectScopedMarkerFilter: function () {
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
    applyProjectLayerVisibility: function (projectId, visibilityOverride) {
        const pid = String(projectId);
        let isVisible;
        if (visibilityOverride !== undefined) {
            isVisible = visibilityOverride;
        } else if (State.effectiveProjectVisibility.has(pid)) {
            isVisible = State.effectiveProjectVisibility.get(pid);
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
    applyProjectVisibility: function (projectId, visibilityOverride) {
        this.applyProjectLayerVisibility(projectId, visibilityOverride);
        this.applyProjectScopedMarkerVisibility();
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
        State.networkLayerStates.set(String(networkId), isVisible);
        const preferences = State.networkLayerStates;
        schedulePreferenceWrite(Config.NETWORK_VISIBILITY_PREFS_STORAGE_KEY, () => Object.fromEntries(preferences));
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
    toggleGPSTrackVisibility: async function (trackId, isVisible) {
        const id = String(trackId);
        return toggleLazyOverlay({
            metadata: () => Config.getGPSTrackById?.(id),
            kind: 'gps', id, visible: isVisible,
            cache: State.gpsTrackCache, states: State.gpsTrackLayerStates, layers: State.allGPSTrackLayers,
            details: async signal => {
                const record = await API.getGPSTrackDetails(id, { signal });
                if (!record?.file) throw new Error('The GPS Track has no display file.');
                const response = await fetch(record.file, { signal });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return readViewerGeoJSON(response, { isCurrent: () => !signal.aborted });
            },
            prepare: async (data, isCurrent) => ({ boundsCoordinates: await prepareGeoJSONBounds(data, { isCurrent }) }),
            install: (data, isCurrent, prepared) => this.addGPSTrackLayer(id, data, { isCurrent, prepared }),
            show: visible => this.showGPSTrackLayers(id, visible),
            loading: value => this.setGPSTrackLoading(id, value),
        });
    },

    // Show/hide GPS track layers
    showGPSTrackLayers: function (trackId, isVisible) {
        const map = State.map;
        if (!map) return;

        const layers = State.allGPSTrackLayers.get(String(trackId)) || [];
        layers.forEach(layerId => {
            if (map.getLayer(layerId)) {
                map.setLayoutProperty(layerId, 'visibility', isVisible ? 'visible' : 'none');
            }
        });
    },

    // Add GPS track GeoJSON layers to the map
    addGPSTrackLayer: async function (trackId, geojsonData, { isCurrent = () => true, prepared } = {}) {
        const map = State.map;
        if (!map) return;
        const boundsCoordinates = prepared ? prepared.boundsCoordinates : await prepareGeoJSONBounds(geojsonData, { isCurrent });
        if (!isCurrent() || State.map !== map) return;

        const tid = String(trackId);
        const sourceId = `gps-track-source-${tid}`;
        const lineLayerId = `gps-track-line-${tid}`;
        const pointsLayerId = `gps-track-points-${tid}`;

        // Remove existing layers and source if they exist
        removeLayersAndSource(map, [pointsLayerId, lineLayerId], sourceId);

        // Get color for this track
        const color = Colors.getGPSTrackColor(tid);

        // Add source
        map.addSource(sourceId, {
            type: 'geojson',
            data: geojsonData,
            generateId: true,
            tolerance: DEFAULTS.GEOJSON_RENDER.TOLERANCE
        });

        // Track layers for this GPS track
        if (!State.allGPSTrackLayers.has(tid)) {
            State.allGPSTrackLayers.set(tid, []);
        }
        const trackLayers = [];
        State.allGPSTrackLayers.set(tid, trackLayers);

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
                'line-width': geoJSONLineWidth(DEFAULTS.GPS_TRACK_RENDER.DETAIL_WIDTH, DEFAULTS.GPS_TRACK_RENDER.CLOSE_WIDTH),
                'line-opacity': 1,
                // Simple dots: tiny dash with gap creates dotted effect
                'line-dasharray': [0.1, 1.5]
            }
        });
        trackLayers.push(lineLayerId);

        if (boundsCoordinates) {
            const bounds = new mapboxgl.LngLatBounds(boundsCoordinates[0], boundsCoordinates[1]);
            State.gpsTrackBounds.set(tid, bounds);
            console.log(`📍 Calculated bounds for GPS track ${trackId}`);
        } else {
            State.gpsTrackBounds.delete(tid);
        }

        console.log(`📍 Added GPS track layers for ${trackId}`);

        // Reorder layers to ensure proper z-ordering
        this.reorderLayers();
    },

    // GIS Layers follow the same session-only lazy loading pattern as GPS Tracks.
    isGISLayerVisible: function (layerId) {
        return State.gisLayerStates.get(String(layerId)) === true;
    },

    isGISLayerLoading: function (layerId) {
        return State.gisLayerLoadingStates.get(String(layerId)) === true;
    },

    getGISLayerGeometryTypes: function (layerId) {
        return [...(State.gisLayerGeometryTypeStates.get(String(layerId))?.keys() || [])];
    },

    isGISLayerGeometryTypeVisible: function (layerId, geometryType) {
        return State.gisLayerGeometryTypeStates.get(String(layerId))?.get(geometryType) !== false;
    },

    setGISLayerGeometryTypeVisibility: function (layerId, geometryType, isVisible) {
        const id = String(layerId);
        const states = State.gisLayerGeometryTypeStates.get(id);
        if (!states?.has(geometryType)) return;
        states.set(geometryType, isVisible);
        if (!isVisible) this.closeGISFeaturePopups();
        const generation = State.layerGeneration;
        return ViewerUpdates.schedule(`gis-types:${id}`, () => {
            if (generation !== State.layerGeneration) return;
            const enabledTypes = [...states].filter(([, visible]) => visible).map(([type]) => type);
            const map = State.map;
            if (!map) return;
            const layerIds = State.allGISLayerLayers.get(id) || [];
            layerIds.forEach((renderLayerId, index) => {
                if (map.getLayer(renderLayerId)) {
                    map.setFilter(renderLayerId, gisLayerGeometryFilter(VECTOR_OVERLAY_GEOMETRY_TYPES[index], enabledTypes));
                }
            });
        });
    },

    setGISLayerLoading: function (layerId, isLoading) {
        const id = String(layerId);
        State.gisLayerLoadingStates.set(id, isLoading);
        window.dispatchEvent(new CustomEvent('speleo:gis-layer-loading-changed', {
            detail: { layerId: id, isLoading }
        }));
    },

    toggleGISLayerVisibility: async function (layerId, isVisible) {
        const id = String(layerId);
        return toggleLazyOverlay({
            metadata: () => Config.getGISLayerById?.(id),
            kind: 'gis-layer', id, visible: isVisible,
            cache: State.gisLayerCache, states: State.gisLayerStates, layers: State.allGISLayerLayers,
            details: async signal => {
                const record = await API.getGISLayerDetails(id, { signal });
                if (!record?.file) throw new Error('The GIS Layer has no display file.');
                const response = await fetch(record.file, { signal });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return readViewerGeoJSON(response, { isCurrent: () => !signal.aborted });
            },
            prepare: async (data, isCurrent) => ({
                boundsCoordinates: await prepareGeoJSONBounds(data, { isCurrent }),
                ...await prepareGISLayerGeoJSONAsync(data, { isCurrent }),
            }),
            install: (data, isCurrent, prepared) => this.addGISLayer(id, data, { isCurrent, prepared }),
            show: visible => this.showGISLayerLayers(id, visible),
            loading: value => this.setGISLayerLoading(id, value),
        });
    },

    showGISLayerLayers: function (layerId, isVisible) {
        const map = State.map;
        if (!map) return;
        const layerIds = State.allGISLayerLayers.get(String(layerId)) || [];
        layerIds.forEach(id => {
            if (map.getLayer(id)) {
                map.setLayoutProperty(id, 'visibility', isVisible ? 'visible' : 'none');
            }
        });
    },

    closeGISFeaturePopups: function () {
        const popups = gisFeaturePopups.get(State.map);
        if (!popups) return;
        for (const popup of popups) popup.remove();
        popups.clear();
    },

    openGISFeaturePopup: function (feature, lngLat) {
        const map = State.map;
        if (!map) return;
        openGISFeaturePopup(map, feature, lngLat);
    },

    addGISLayer: async function (layerId, geojsonData, { isCurrent = () => true, prepared } = {}) {
        const map = State.map;
        if (!map) return;
        const boundsCoordinates = prepared ? prepared.boundsCoordinates : await prepareGeoJSONBounds(geojsonData, { isCurrent });
        const { data, geometryTypes } = prepared || await prepareGISLayerGeoJSONAsync(geojsonData, { isCurrent });
        if (!isCurrent() || State.map !== map) return;

        const id = String(layerId);
        const sourceId = `gis-layer-source-${id}`;
        const fillLayerId = `gis-layer-${id}-fill`;
        const outlineLayerId = `gis-layer-${id}-outline`;
        const lineLayerId = `gis-layer-${id}-line`;
        const pointLayerId = `gis-layer-${id}-point`;
        const layerIds = [fillLayerId, outlineLayerId, lineLayerId, pointLayerId];
        State.gisLayerClickableLayerIds.delete(fillLayerId);
        State.gisLayerClickableLayerIds.delete(pointLayerId);
        removeLayersAndSource(map, [...layerIds].reverse(), sourceId);

        const previousStates = State.gisLayerGeometryTypeStates.get(id);
        const typeStates = new Map(geometryTypes.map(type => [
            type, geometryTypes.length === 1 || previousStates?.get(type) !== false
        ]));
        State.gisLayerGeometryTypeStates.set(id, typeStates);
        const enabledTypes = geometryTypes.filter(type => typeStates.get(type));
        const color = Config.getGISLayerById(id)?.color || DEFAULTS.COLORS.FALLBACK;
        addVectorOverlay(map, {
            sourceId, layerIds, data, color,
            filterForGeometry: type => gisLayerGeometryFilter(type, enabledTypes)
        });

        State.allGISLayerLayers.set(id, layerIds);
        State.gisLayerClickableLayerIds.add(fillLayerId);
        State.gisLayerClickableLayerIds.add(pointLayerId);
        if (boundsCoordinates) State.gisLayerBounds.set(id, new mapboxgl.LngLatBounds(boundsCoordinates[0], boundsCoordinates[1]));
        else State.gisLayerBounds.delete(id);
        this.reorderLayers();
    },

    isGISGeometryVisible(id) {
        return State.gisGeometryStates.get(String(id)) === true;
    },

    showGISGeometryLayers(id, visible) {
        const key = String(id);
        const show = visible && State.gisGeometryEditingId !== key;
        for (const layerId of State.allGISGeometryLayers.get(key) || []) {
            if (State.map?.getLayer(layerId)) {
                State.map.setLayoutProperty(layerId, 'visibility', show ? 'visible' : 'none');
            }
        }
    },

    async toggleGISGeometryVisibility(id, visible) {
        const key = String(id);
        const operationKey = `gis-geometry:${key}`;
        const intent = {};
        overlayIntents.set(operationKey, intent);
        const map = State.map;
        const generation = State.layerGeneration;
        const sessionCurrent = () => State.map === map && State.layerGeneration === generation;
        const isCurrent = () => sessionCurrent() && overlayIntents.get(operationKey) === intent;
        State.gisGeometryStates.set(key, visible);
        if (!visible) {
            cancelMapNavigation(operationKey);
            await ViewerUpdates.schedule(operationKey, () => {
                if (isCurrent()) this.showGISGeometryLayers(key, false);
            });
            return isCurrent();
        }
        let record = State.gisGeometryCache.get(key);
        let pending;
        try {
            if (!record) {
                pending = State.gisGeometryLoading.get(key);
                if (!pending) {
                    pending = API.getGISGeometryDetails(key);
                    State.gisGeometryLoading.set(key, pending);
                }
                record = await pending;
                if (!sessionCurrent()) return false;
                if (!record?.geojson) throw new Error('The geometry is unavailable.');
                const cached = State.gisGeometryCache.get(key);
                if (cached && cached.revision > record.revision) record = cached;
                State.gisGeometryCache.set(key, record);
                Config.upsertGISGeometry(record);
            }
            if (!isCurrent() || !this.isGISGeometryVisible(key)) return false;
            const result = await ViewerUpdates.schedule(operationKey, () => {
                if (!isCurrent()) return;
                // An editor save may have replaced the baseline during our paint wait.
                record = State.gisGeometryCache.get(key) || record;
                const ids = State.allGISGeometryLayers.get(key);
                const applied = gisGeometryAppliedRecords.get(key);
                if (!ids?.length || !State.map?.getLayer(ids[0]) || applied?.record !== record
                    || applied.generation !== generation || applied.map !== map) this.addGISGeometry(record);
                this.showGISGeometryLayers(key, this.isGISGeometryVisible(key));
            });
            if (result.status === 'failed') throw result.error;
            return isCurrent() && result.status === 'applied';
        } catch (error) {
            if (!isCurrent()) return false;
            const cached = State.gisGeometryCache.get(key);
            if (cached && cached !== record) return this.isGISGeometryVisible(key);
            State.gisGeometryStates.set(key, false);
            this.showGISGeometryLayers(key, false);
            console.error('Failed to show GIS Geometry:', error);
            Utils.showNotification('error', 'Unable to display this geometry. Toggle it on to retry.');
            return false;
        } finally {
            if (sessionCurrent() && State.gisGeometryLoading.get(key) === pending) State.gisGeometryLoading.delete(key);
        }
    },

    addGISGeometry(record) {
        const map = State.map;
        if (!map) return;
        const id = String(record.id);
        const sourceId = `gis-geometry-source-${id}`;
        const layerIds = ['fill', 'outline', 'line', 'point'].map(role => `gis-geometry-${id}-${role}`);
        removeLayersAndSource(map, [...layerIds].reverse(), sourceId);
        addVectorOverlay(map, {
            sourceId, layerIds,
            data: { type: 'Feature', properties: { name: record.name }, geometry: record.geojson },
            color: record.color || DEFAULTS.COLORS.FALLBACK,
            fillOpacity: DEFAULTS.GIS_GEOMETRY.FILL_OPACITY,
        });
        State.allGISGeometryLayers.set(id, layerIds);
        gisGeometryAppliedRecords.set(id, { record, map, generation: State.layerGeneration });
        // Stored Geometry never has a trusted caller-supplied bbox.
        const bounds = computeGeoJSONBounds(record.geojson, { wrapLongitude: false });
        if (!bounds.isEmpty()) State.gisGeometryBounds.set(id, bounds);
        this.showGISGeometryLayers(id, this.isGISGeometryVisible(id));
        this.reorderLayers();
    },

    acceptGISGeometry(record) {
        const id = String(record.id);
        Config.upsertGISGeometry(record);
        State.gisGeometryCache.set(id, record);
        State.gisGeometryStates.set(id, true);
        return ViewerUpdates.schedule(`gis-geometry:${id}`, () => {
            if (State.gisGeometryCache.get(id) === record) this.addGISGeometry(record);
        });
    },

    refreshGISGeometry(record) {
        const id = String(record.id);
        Config.upsertGISGeometry(record);
        State.gisGeometryCache.set(id, record);
        // Refresh the saved baseline without changing the pre-edit visibility.
        return ViewerUpdates.schedule(`gis-geometry:${id}`, () => {
            if (State.gisGeometryCache.get(id) === record) this.addGISGeometry(record);
        });
    },

    toggleNetworkVisibility: function (networkId, isVisible) {
        const nid = String(networkId);
        this.saveNetworkVisibilityPref(nid, isVisible);
        if (!isVisible) cancelMapNavigation(`network:${nid}`);
        return this.scheduleDisplayUpdate('networks');
    },

    // Country gates change effective visibility without rewriting individual choices.
    toggleProjectVisibility: function (projectId, isVisible, visibilityOverride) {
        const pid = String(projectId);
        this.saveProjectVisibilityPref(pid, isVisible);
        return this.setProjectVisibilityBatch([{ projectId: pid, visible: visibilityOverride ?? isVisible }]);
    },

    forEachProjectLineLayer: function (callback) {
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
    },

    applyLineColors: function (mode = this.colorMode) {
        const map = State.map;
        if (!map) return;

        this.forEachProjectLineLayer((layerId, projectId) => {
            map.setPaintProperty(layerId, 'line-color', Colors.getSurveyPaint(projectId, mode, State.activeDepthDomain));
        });
    },

    applyDepthLineColors: function () {
        this.applyLineColors('depth');
    },

    setColorMode: function (mode) {
        if (!Colors.isValidColorMode(mode)) return;
        this.colorMode = mode;

        this.emitDisplayPreferencesChanged();
        return this.scheduleDisplayUpdate('depth', 'colors');
    },

    setDepthLimit(limitFeet, unit) {
        if (!isValidDepthLimit(limitFeet) || (unit !== 'ft' && unit !== 'm')) return false;
        const preferences = State.displayPreferences;
        const limitChanged = preferences.depthLimitFeet !== limitFeet;
        if (!limitChanged && preferences.depthUnit === unit) return true;

        preferences.depthLimitFeet = limitFeet;
        preferences.depthUnit = unit;
        this.emitDisplayPreferencesChanged();
        this.scheduleDisplayUpdate(...(limitChanged ? ['depth'] : ['depth-labels']));
        return true;
    },

    addProjectGeoJSON: async function (projectId, url) {
        const map = State.map;
        if (!map) return;

        const sourceId = `project-geojson-${projectId}`;
        const generation = State.layerGeneration;
        const isCurrent = () => State.map === map && State.layerGeneration === generation;

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const rawData = await readViewerGeoJSON(response, { isCurrent });
            const prepared = await prepareProjectGeoJSON(rawData, { isCurrent });
            if (!isCurrent()) return;
            const { data, domain, snapPoints, boundsCoordinates } = prepared;
            State.projectDepthDomains.set(String(projectId), domain);
            Geometry.cachePreparedSnapPoints(projectId, snapPoints);

            if (map.getSource(sourceId)) {
                map.getSource(sourceId).setData(data);
            } else {
                map.addSource(sourceId, {
                    type: 'geojson',
                    data: data,
                    generateId: true,
                    tolerance: DEFAULTS.GEOJSON_RENDER.TOLERANCE
                });

                // Track layers
                if (!State.allProjectLayers.has(String(projectId))) {
                    State.allProjectLayers.set(String(projectId), []);
                }
                const projectLayers = State.allProjectLayers.get(String(projectId));

                // Lines (survey lines visible from zoom 0)
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
                        'line-color': Colors.getSurveyPaint(projectId, this.colorMode, State.activeDepthDomain),
                        'line-width': geoJSONLineWidth(DEFAULTS.PROJECT_RENDER.DETAIL_WIDTH, DEFAULTS.PROJECT_RENDER.CLOSE_WIDTH),
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

                // Initial visibility is handled by centralized project-visibility logic.
                this.applyProjectLayerVisibility(projectId);

            }

            if (boundsCoordinates) {
                State.projectBounds.set(String(projectId), new mapboxgl.LngLatBounds(boundsCoordinates[0], boundsCoordinates[1]));
            }
            await this.scheduleDisplayUpdate('depth');

        } catch (e) {
            if (isCurrent()) console.error(`Error loading GeoJSON for project ${projectId}`, e);
        }
    },

    addSubSurfaceStationLayer: function (projectId, data) {
        const map = State.map;
        if (!map) return;

        const sourceId = `stations-source-${projectId}`;
        const circleLayerId = `stations-${projectId}-circles`;
        const biologyLayerId = `stations-${projectId}-biology-icons`;
        const boneLayerId = `stations-${projectId}-bone-icons`;
        const artifactLayerId = `stations-${projectId}-artifact-icons`;
        const geologyLayerId = `stations-${projectId}-geology-icons`;
        const labelLayerId = `stations-${projectId}-labels`;

        console.log(`📍 Adding ${data.features?.length || 0} stations to map for project ${projectId}`);

        // Remove existing layers and source if they exist (for refresh)
        removeLayersAndSource(
            map,
            [labelLayerId, geologyLayerId, artifactLayerId, boneLayerId, biologyLayerId, circleLayerId],
            sourceId
        );

        if (!data.features || data.features.length === 0) {
            console.log(`📍 No stations to display for project ${projectId}`);
            return;
        }

        // Ensure id and color properties are set on each feature
        // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
        data.features.forEach(feature => {
            if (feature.id && !feature.properties.id) {
                feature.properties.id = feature.id;
            }
            if (!feature.properties.color) {
                // Use tag color if available, otherwise use default orange
                const tag = feature.properties.tag;
                feature.properties.color = (tag && tag.color) ? tag.color : DEFAULTS.COLORS.DEFAULT_STATION;
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: data,
            promoteId: 'id'
        });

        // Add Circle Layer for Sensor stations (type is null, undefined, or 'sensor')
        // Use data-driven color from feature properties
        map.addLayer({
            id: circleLayerId,
            type: 'circle',
            source: sourceId,
            filter: ['any',
                ['!', ['has', 'type']],
                ['==', ['get', 'type'], null],
                ['==', ['get', 'type'], 'sensor']
            ],
            minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
            paint: {
                'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 5, 18, 8],
                'circle-color': ['coalesce', ['get', 'color'], DEFAULTS.COLORS.DEFAULT_STATION],
                'circle-stroke-width': 2,
                'circle-stroke-color': '#ffffff',
                'circle-opacity': 1
            }
        });

        // Add Biology Station Icon Layer (for type === 'biology')
        if (map.hasImage('biology-station-icon')) {
            map.addLayer({
                id: biologyLayerId,
                type: 'symbol',
                source: sourceId,
                filter: ['==', ['get', 'type'], 'biology'],
                minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
                layout: {
                    'icon-image': 'biology-station-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        }

        // Add Bone Station Icon Layer (for type === 'bone')
        if (map.hasImage('bone-station-icon')) {
            map.addLayer({
                id: boneLayerId,
                type: 'symbol',
                source: sourceId,
                filter: ['==', ['get', 'type'], 'bone'],
                minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
                layout: {
                    'icon-image': 'bone-station-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        }

        // Add Artifact Station Icon Layer (for type === 'artifact')
        if (map.hasImage('artifact-station-icon')) {
            map.addLayer({
                id: artifactLayerId,
                type: 'symbol',
                source: sourceId,
                filter: ['==', ['get', 'type'], 'artifact'],
                minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
                layout: {
                    'icon-image': 'artifact-station-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        }

        // Add Geology Station Icon Layer (for type === 'geology')
        if (map.hasImage('geology-station-icon')) {
            map.addLayer({
                id: geologyLayerId,
                type: 'symbol',
                source: sourceId,
                filter: ['==', ['get', 'type'], 'geology'],
                minzoom: ZOOM_LEVELS.SUBSURFACE_STATION_SYMBOL,
                layout: {
                    'icon-image': 'geology-station-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.6, 18, 1.0],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        }

        // Add Label Layer for all station types
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
        const newLayers = [circleLayerId, biologyLayerId, boneLayerId, artifactLayerId, geologyLayerId, labelLayerId];
        newLayers.forEach(layerId => {
            if (!projectLayers.includes(layerId)) {
                projectLayers.push(layerId);
            }
        });

        // Respect initial visibility through centralized project-layer logic.
        this.applyProjectLayerVisibility(projectId);
    },

    addLandmarkLayer: function (data) {
        const map = State.map;
        if (!map) return;

        const sourceId = 'landmarks-source';

        console.log(`📍 Adding ${data.features?.length || 0} Landmarks to map`);

        // Remove existing layer and source if they exist (to refresh)
        removeLayersAndSource(map, ['landmarks-labels', 'landmarks-layer'], sourceId);

        if (!data.features || data.features.length === 0) {
            console.log('📍 No Landmarks to display');
            return;
        }

        // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
        data.features.forEach(feature => {
            if (feature.id && !feature.properties.id) {
                feature.properties.id = feature.id;
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: data,
            promoteId: 'id'
        });

        // Determine initial visibility based on state
        const visibility = State.landmarksVisible ? 'visible' : 'none';
        const landmarkColorExpression = ['coalesce', ['get', 'collection_color'], Colors.FALLBACK_COLOR];
        const landmarkHaloColorExpression = [
            'case',
            ['==', ['get', 'collection_color'], '#ffffff'],
            '#0f172a',
            '#ffffff'
        ];

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
                'text-color': landmarkColorExpression,
                'text-halo-color': landmarkHaloColorExpression,
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
                'text-color': landmarkColorExpression,
                'text-halo-color': landmarkHaloColorExpression,
                'text-halo-width': 1.5
            }
        });
    },

    toggleLandmarkVisibility: function (isVisible) {
        this.setCategoryVisibility('landmarks', isVisible);
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
        removeLayersAndSource(map, [labelLayerId, symbolLayerId], sourceId);

        if (!data.features || data.features.length === 0) {
            console.log(`📍 No surface stations to display for network ${networkId}`);
            return;
        }

        // Ensure id and color properties are set on each feature
        // Mapbox requires promoteId for string IDs - copy feature.id to properties.id
        data.features.forEach(feature => {
            if (feature.id && !feature.properties.id) {
                feature.properties.id = feature.id;
            }
            if (!feature.properties.color) {
                // Use tag color if available, otherwise use default orange
                const tag = feature.properties.tag;
                feature.properties.color = (tag && tag.color) ? tag.color : DEFAULTS.COLORS.DEFAULT_STATION;
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: data,
            promoteId: 'id'
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
                'text-color': ['coalesce', ['get', 'color'], DEFAULTS.COLORS.DEFAULT_STATION],
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
        if (!networkLayers.includes(symbolLayerId)) networkLayers.push(symbolLayerId);
        if (!networkLayers.includes(labelLayerId)) networkLayers.push(labelLayerId);

        // Respect initial visibility
        this.applyNetworkLayerVisibility(networkId);
    },

    updateSurfaceStationPosition: function (networkId, stationId, newCoords) {
        const map = State.map;
        if (!map) return;

        const sourceId = `surface-stations-source-${networkId}`;
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === stationId);
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
            const feature = data.features.find(f => f.id === stationId);
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
            const feature = data.features.find(f => f.id === stationId);
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
            const feature = data.features.find(f => f.id === stationId);
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
            const feature = data.features.find(f => f.id === stationId);
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
            const feature = data.features.find(f => f.id === stationId);
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
            const feature = data.features.find(f => f.id === landmarkId);
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
    reorderLayers() {
        const map = State.map;
        const generation = State.layerGeneration;
        return ViewerUpdates.schedule('layer-order', context => {
            if (map === State.map && generation === State.layerGeneration) return this.reorderLayersNow(context);
        });
    },

    async reorderLayersNow(context) {
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
        const matches = [
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
        const groups = matches.map(() => []);
        const seen = new Set();
        for (const id of registeredLayerIds()) {
            if (context.shouldYield() && !await context.yield()) return;
            if (!context.isCurrent() || map !== State.map) return;
            if (seen.has(id)) continue;
            seen.add(id);
            for (let index = 0; index < matches.length; index++) {
                if (matches[index](id)) groups[index].push(id);
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

    /**
     * Load custom marker images from SVG files
     * Uses map.loadImage() for proper CORS handling with S3/CDN hosted assets
     */
    loadMarkerImages: async function () {
        const map = State.map;
        if (!map) return;

        const requiredImageIds = [
            'cylinder-icon',
            'exploration-lead-icon',
            'biology-station-icon',
            'bone-station-icon',
            'artifact-station-icon',
            'geology-station-icon',
        ];
        if (markerImagesLoaded && requiredImageIds.every(imageId => map.hasImage(imageId))) return;

        // Helper to load image using Mapbox's loadImage (handles CORS properly)
        const loadImage = (url) => {
            return new Promise((resolve, reject) => {
                map.loadImage(url, (error, image) => {
                    if (error) reject(error);
                    else resolve(image);
                });
            });
        };

        try {
            // Load pre-colored orange cylinder SVG for cylinder installs
            if (!map.hasImage('cylinder-icon')) {
                const cylinderImage = await loadImage(getRuntimeContext().icons.cylinderOrange);
                map.addImage('cylinder-icon', cylinderImage);
            }

            // Load exploration lead SVG
            if (!map.hasImage('exploration-lead-icon')) {
                const leadImage = await loadImage(getRuntimeContext().icons.explorationLead);
                map.addImage('exploration-lead-icon', leadImage);
            }

            // Load biology icon for biology stations
            if (!map.hasImage('biology-station-icon')) {
                const biologyImage = await loadImage(getRuntimeContext().icons.biology);
                map.addImage('biology-station-icon', biologyImage);
            }

            // Load bone icon for bone stations
            if (!map.hasImage('bone-station-icon')) {
                const boneImage = await loadImage(getRuntimeContext().icons.bone);
                map.addImage('bone-station-icon', boneImage);
            }

            // Load artifact icon for artifact stations
            if (!map.hasImage('artifact-station-icon')) {
                const artifactImage = await loadImage(getRuntimeContext().icons.artifact);
                map.addImage('artifact-station-icon', artifactImage);
            }

            // Load geology icon for geology stations
            if (!map.hasImage('geology-station-icon')) {
                const geologyImage = await loadImage(getRuntimeContext().icons.geology);
                map.addImage('geology-station-icon', geologyImage);
            }

            markerImagesLoaded = true;
            console.log('✅ Custom marker images loaded from SVG files');
        } catch (e) {
            console.error('❌ Error loading marker images:', e);
        }
    },

    /**
     * Add an exploration lead marker to the map
     */
    addExplorationLeadMarker: function (id, coordinates, lineName = 'Survey Line', description = '', projectId = null) {
        const map = State.map;
        if (!map) return;

        // Store in state
        State.explorationLeads.set(id, {
            id,
            coordinates,
            lineName,
            description,
            projectId,
            createdAt: new Date().toISOString()
        });

        // Refresh the exploration leads layer
        this.refreshExplorationLeadsLayer();
        this.reorderLayers();

        console.log(`⚠️ Exploration lead added: ${id} at ${coordinates}`);
    },

    /**
     * Refresh the exploration leads layer with current state
     */
    refreshExplorationLeadsLayer: function () {
        const map = State.map;
        if (!map) return;

        const sourceId = 'exploration-leads-source';
        const layerId = 'exploration-leads-layer';

        // Build GeoJSON from state
        // Mapbox requires promoteId for string IDs - include id in properties
        const features = Array.from(State.explorationLeads.values()).map(marker => ({
            type: 'Feature',
            id: marker.id,
            geometry: {
                type: 'Point',
                coordinates: marker.coordinates
            },
            properties: withProjectScopedMarkerProperties({
                id: marker.id,
                lineName: marker.lineName
            }, marker.projectId)
        }));

        const geojson = {
            type: 'FeatureCollection',
            features
        };

        // Update or create source
        if (map.getSource(sourceId)) {
            map.getSource(sourceId).setData(geojson);
        } else {
            map.addSource(sourceId, {
                type: 'geojson',
                data: geojson,
                promoteId: 'id'
            });

            // Add layer with red exclamation mark icon
            if (map.hasImage('exploration-lead-icon')) {
                map.addLayer({
                    id: layerId,
                    type: 'symbol',
                    source: sourceId,
                    minzoom: ZOOM_LEVELS.EXPLORATION_LEAD_SYMBOL,
                    layout: {
                        'icon-image': 'exploration-lead-icon',
                        'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.4, 18, 0.6],
                        'icon-allow-overlap': true,
                        'icon-ignore-placement': true
                    },
                    paint: {
                        'icon-opacity': 1
                    }
                });
            } else {
                // Fallback: use a circle marker if image not loaded
                map.addLayer({
                    id: layerId,
                    type: 'circle',
                    source: sourceId,
                    minzoom: ZOOM_LEVELS.EXPLORATION_LEAD_SYMBOL,
                    paint: {
                        'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 8, 18, 12],
                        'circle-color': '#EF4444',
                        'circle-stroke-width': 2,
                        'circle-stroke-color': '#ffffff',
                        'circle-opacity': 1
                    }
                });
            }
        }

        this.applyProjectScopedMarkerVisibility();
    },

    /**
     * Remove an exploration lead marker
     */
    removeExplorationLeadMarker: function (id) {
        State.explorationLeads.delete(id);
        this.refreshExplorationLeadsLayer();
        console.log(`⚠️ Exploration lead removed: ${id}`);
    },

    /**
     * Update cylinder install position (for drag)
     */
    updateCylinderInstallPosition: function (markerId, newCoords) {
        const map = State.map;
        if (!map) return;

        const sourceId = 'cylinder-installs-source';
        const source = map.getSource(sourceId);
        if (source && source._data) {
            const data = source._data;
            const feature = data.features.find(f => f.id === markerId || f.properties?.id === markerId);
            if (feature) {
                feature.geometry.coordinates = newCoords;
                source.setData(data);
            }
        }
    },

    /**
     * Update exploration lead position (for drag)
     */
    updateExplorationLeadPosition: function (markerId, newCoords) {
        const marker = State.explorationLeads.get(markerId);
        if (marker) {
            marker.coordinates = newCoords;
            this.refreshExplorationLeadsLayer();
        }
    },

    /**
     * Show marker drag highlight - adds a colored circle behind the marker
     * @param {string} markerType - 'cylinder-install' or 'exploration-lead'
     * @param {Array} coordinates - [lng, lat]
     * @param {boolean} isSnapped - whether currently snapped (green=snapped, amber=not)
     */
    showMarkerDragHighlight: function (markerType, coordinates, isSnapped) {
        const map = State.map;
        if (!map) return;

        const highlightId = 'marker-drag-highlight';
        const highlightSourceId = 'marker-drag-highlight-source';
        const color = isSnapped ? '#10b981' : '#f59e0b'; // Same colors as stations

        const geojson = {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                geometry: { type: 'Point', coordinates }
            }]
        };

        if (map.getSource(highlightSourceId)) {
            map.getSource(highlightSourceId).setData(geojson);
            if (map.getLayer(highlightId)) {
                map.setPaintProperty(highlightId, 'circle-color', color);
            }
        } else {
            map.addSource(highlightSourceId, { type: 'geojson', data: geojson });
            map.addLayer({
                id: highlightId,
                type: 'circle',
                source: highlightSourceId,
                paint: {
                    'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 18, 18, 28],
                    'circle-color': color,
                    'circle-opacity': 0.4,
                    'circle-stroke-width': 3,
                    'circle-stroke-color': color,
                    'circle-stroke-opacity': 0.8
                }
            });
        }
    },

    /**
     * Hide marker drag highlight
     */
    hideMarkerDragHighlight: function () {
        const map = State.map;
        if (!map) return;

        const highlightId = 'marker-drag-highlight';
        const highlightSourceId = 'marker-drag-highlight-source';

        if (map.getLayer(highlightId)) {
            map.removeLayer(highlightId);
        }
        if (map.getSource(highlightSourceId)) {
            map.removeSource(highlightSourceId);
        }
    },

    /**
     * Set marker visual feedback during drag (wrapper for highlight)
     */
    setMarkerDragFeedback: function (markerType, opacity, isSnapped, coordinates) {
        // Show highlight circle at current position
        if (coordinates) {
            this.showMarkerDragHighlight(markerType, coordinates, isSnapped);
        }
    },

    /**
     * Reset marker visual feedback after drag
     */
    resetMarkerDragFeedback: function (markerType) {
        this.hideMarkerDragHighlight();
    },

    /**
     * Load and display installed cylinders from the API
     * Fetches GeoJSON data for all installed cylinders the user has access to
     */
    loadCylinderInstalls: async function () {
        const map = State.map;
        if (!map) return;

        try {
            console.log('🔄 Loading cylinder installs...');
            // GeoJSON endpoint returns raw FeatureCollection via NoWrapResponse
            const geojsonData = await API.getAllCylinderInstallsGeoJSON();

            if (
                geojsonData &&
                geojsonData.type === 'FeatureCollection' &&
                Array.isArray(geojsonData.features)
            ) {
                this.addCylinderInstallsLayer(geojsonData);
                console.log(`✅ Loaded ${geojsonData.features.length} cylinder installs`);
            } else {
                console.log('⚠️ No cylinder installs to display or invalid response format');
            }
        } catch (e) {
            console.error('❌ Failed to load cylinder installs:', e);
        }
    },

    /**
     * Add cylinder installs layer to the map
     */
    addCylinderInstallsLayer: function (geojsonData) {
        const map = State.map;
        if (!map) return;

        const sourceId = 'cylinder-installs-source';
        const layerId = 'cylinder-installs-layer';
        const labelLayerId = 'cylinder-installs-labels';

        console.log(`Adding ${geojsonData.features?.length || 0} cylinder installs to map`);

        // Remove existing layers before removing source (safe refresh order).
        removeLayersAndSource(map, [labelLayerId, layerId], sourceId);

        if (!geojsonData.features || geojsonData.features.length === 0) {
            console.log('No cylinder installs to display');
            return;
        }

        // Clear and populate the cylinder installs cache
        State.cylinderInstalls.clear();
        geojsonData.features.forEach(feature => {
            // Ensure id property is set on each feature for Mapbox promoteId
            if (feature.id && !feature.properties.id) {
                feature.properties.id = feature.id;
            }
            // Cache cylinder install data by ID
            const id = feature.id || feature.properties.id;
            if (id) {
                State.cylinderInstalls.set(id, {
                    id,
                    coordinates: feature.geometry.coordinates,
                    ...feature.properties
                });
            }
        });

        map.addSource(sourceId, {
            type: 'geojson',
            data: geojsonData,
            promoteId: 'id'
        });

        // Use cylinder icon if loaded, otherwise fallback
        if (map.hasImage('cylinder-icon')) {
            map.addLayer({
                id: layerId,
                type: 'symbol',
                source: sourceId,
                minzoom: ZOOM_LEVELS.CYLINDER_INSTALL_SYMBOL,
                layout: {
                    'icon-image': 'cylinder-icon',
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.8, 18, 1.2],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                },
                paint: {
                    'icon-opacity': 1
                }
            });
        } else {
            // Fallback to text symbol
            // Note: Using ● (U+25CF) instead of emoji - Mapbox doesn't support glyphs > 65535
            map.addLayer({
                id: layerId,
                type: 'symbol',
                source: sourceId,
                minzoom: ZOOM_LEVELS.CYLINDER_INSTALL_SYMBOL,
                layout: {
                    'text-field': '●',
                    'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                    'text-size': ['interpolate', ['linear'], ['zoom'], 14, 18, 18, 26],
                    'text-allow-overlap': true,
                    'text-ignore-placement': true
                },
                paint: {
                    'text-color': '#FF6B00',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 2
                }
            });
        }

        // Add label layer for cylinder installs
        map.addLayer({
            id: labelLayerId,
            type: 'symbol',
            source: sourceId,
            minzoom: ZOOM_LEVELS.CYLINDER_INSTALL_LABEL,
            layout: {
                'text-field': getCylinderInstallLabelExpression(),
                'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
                'text-size': 11,
                'text-offset': [0, 1.5],
                'text-anchor': 'top',
                'text-allow-overlap': false,
                'text-ignore-placement': false
            },
            paint: {
                'text-color': '#000000',
                'text-halo-color': '#ffffff',
                'text-halo-width': 1.5
            }
        });

        this.applyProjectScopedMarkerVisibility();

        // Reorder to ensure proper z-ordering
        this.reorderLayers();
    },

    /**
     * Refresh cylinder installs layer (called after install/uninstall)
     */
    refreshCylinderInstallsLayer: async function () {
        await this.loadCylinderInstalls();
    }
};
