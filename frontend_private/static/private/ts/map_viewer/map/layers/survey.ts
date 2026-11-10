import { Renderer } from '../renderer.ts';
import type { RendererGeoJSONSource, RendererLayer } from '../../../../../../../ts-types/domain/renderer.ts';
import type { PreparedProject } from '../../../../../../../ts-types/domain/map-preparation.ts';
import { applyDepthLimit } from '../depth.ts';
import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ColorMode, DisplayConcern } from '../../../../../../../ts-types/domain/map-display.ts';
import type { ViewerGeoJSON } from '../../../../../../../ts-types/domain/map-geometry.ts';
import type { ViewerUpdateResult } from '@speleodb/map-viewer/update-scheduler';
import { DEFAULTS } from '../../defaults.ts';
import { State } from '../../state.ts';
import { Colors } from '../colors.ts';
import { Geometry } from '../geometry.ts';
import { geoJSONLineWidth } from '../line_rendering.ts';
import { readViewerGeoJSON } from '../read_geojson.ts';
import { prepareProjectGeoJSON } from '../preparation.ts';

interface SurveyLayerOwner {
    colorMode: ColorMode;
    applyProjectLayerVisibility(id: EntityId, visibilityOverride?: boolean, layerIds?: string[]): void;
    scheduleDisplayUpdate(...concerns: DisplayConcern[]): Promise<ViewerUpdateResult>;
}
const ZOOM_LEVELS = DEFAULTS.ZOOM_LEVELS;

interface ProjectGeoJSONLoadOptions {
    signal?: AbortSignal;
    throwOnError?: boolean;
    transformData?: (data: ViewerGeoJSON, isCurrent: () => boolean) => Promise<ViewerGeoJSON>;
    isCurrent?: () => boolean;
}

export async function addProjectGeoJSON(this: Pick<SurveyLayerOwner, 'colorMode' | 'applyProjectLayerVisibility' | 'scheduleDisplayUpdate'>, projectId: EntityId, url: string, options: ProjectGeoJSONLoadOptions = {}) {
    const map = State.map;
    if (!map) return;

    const sourceId = `project-geojson-${projectId}`;
    const generation = State.layerGeneration;
    const isCurrent = () => State.map === map && State.layerGeneration === generation && (options.isCurrent?.() ?? true);

    try {
        if (options.transformData) {
            // A failed or empty bounded reload must not leave previously rendered data.
            const id = String(projectId);
            for (const layerId of State.allProjectLayers.get(id) ?? []) {
                if (map.getLayer(layerId)) map.removeLayer(layerId);
            }
            if (map.getSource(sourceId)) map.removeSource(sourceId);
            State.allProjectLayers.delete(id);
            State.projectBounds.delete(id);
            State.projectDepthDomains.delete(id);
            State.effectiveProjectVisibility.delete(id);
            Geometry.cachePreparedSnapPoints(projectId, []);
        }
        const response = await fetch(url, options.signal ? { signal: options.signal } : undefined);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const rawData = await readViewerGeoJSON(response, { isCurrent }) as unknown as ViewerGeoJSON;
        const displayData = options.transformData ? await options.transformData(rawData, isCurrent) : rawData;
        const prepared = await prepareProjectGeoJSON(displayData, { isCurrent });
        if (!isCurrent()) return;
        const { data, domain, snapPoints, boundsCoordinates } = prepared;
        if (options.transformData && !boundsCoordinates) {
            await this.scheduleDisplayUpdate('depth');
            return;
        }
        State.projectDepthDomains.set(String(projectId), domain);
        Geometry.cachePreparedSnapPoints(projectId, snapPoints);

        if (map.getSource(sourceId)) {
            map.getSource(sourceId)!.setData(data);
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
            const projectLayers = State.allProjectLayers.get(String(projectId))!;

            for (const layer of surveyLayers(projectId, sourceId, this.colorMode)) {
                map.addLayer(layer);
                projectLayers.push(layer.id);
            }

            // Initial visibility is handled by centralized project-visibility logic.
            this.applyProjectLayerVisibility(projectId);

        }

        if (boundsCoordinates) {
            State.projectBounds.set(String(projectId), new Renderer.LngLatBounds(boundsCoordinates[0], boundsCoordinates[1]));
        } else {
            State.projectBounds.delete(String(projectId));
        }
        await this.scheduleDisplayUpdate('depth');

    } catch (e) {
        if (isCurrent() && !(e instanceof Error && e.name === 'AbortError')) {
            console.error(`Error loading GeoJSON for project ${projectId}`, e);
            if (options.transformData) {
                await this.scheduleDisplayUpdate('depth');
            }
            if (options.transformData || options.throwOnError) throw e;
        }
    }
}

function surveyLayers(projectId: EntityId, sourceId: string, colorMode: ColorMode, suffix = ''): RendererLayer[] {
    const layers: RendererLayer[] = [];
    // Lines (survey lines visible from zoom 0)
    const lineLayerId = `project-layer-${projectId}${suffix}`;
    layers.push({
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
            'line-color': Colors.getSurveyPaint(projectId, colorMode, State.activeDepthDomain),
            'line-width': geoJSONLineWidth(DEFAULTS.PROJECT_RENDER.DETAIL_WIDTH, DEFAULTS.PROJECT_RENDER.CLOSE_WIDTH),
            'line-opacity': 1
        }
    });

    // 3. Line Labels
    const labelLayerId = `project-labels-${projectId}${suffix}`;
    layers.push({
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

    // 4. Points
    const pointLayerId = `project-points-${projectId}${suffix}`;
    layers.push({
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

    return layers;
}

/** Exact historical replacement: the displayed source is untouched until a native frame accepts its candidate. */
export async function replaceHistoricalProject(
    owner: SurveyLayerOwner,
    projectId: EntityId,
    url: string,
    { signal, isCurrent, onDisplayed }: { signal: AbortSignal; isCurrent: () => boolean; onDisplayed: () => void },
): Promise<boolean> {
    const map = State.map;
    if (!map || signal.aborted || !isCurrent()) return false;
    const current = () => State.map === map && !signal.aborted && isCurrent();
    const response = await fetch(url, { signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const raw = await readViewerGeoJSON(response, { isCurrent: current }) as unknown as ViewerGeoJSON;
    const prepared = await prepareProjectGeoJSON(raw, { isCurrent: current });
    if (!current()) return false;

    const id = String(projectId);
    const previousLayers = State.allProjectLayers.get(id) ?? [];
    const previousSource = previousLayers.map(layer => map.getLayer(layer)?.source).find(Boolean);
    const canonicalSource = `project-geojson-${id}`;
    const suffix = previousSource === canonicalSource ? '-history' : '';
    const sourceId = suffix ? `project-history-geojson-${id}` : canonicalSource;
    const candidate = surveyLayers(projectId, sourceId, owner.colorMode, suffix);
    let promoted = false;
    let accepted = false;
    let candidateSource: RendererGeoJSONSource | undefined;

    const removeCandidate = () => {
        if (map.getSource(sourceId) !== candidateSource) return;
        for (const layer of candidate) if (map.getLayer(layer.id)) map.removeLayer(layer.id);
        if (map.getSource(sourceId)) map.removeSource(sourceId);
        if (promoted) owner.applyProjectLayerVisibility(projectId);
    };

    try {
        map.addSource(sourceId, { type: 'geojson', data: prepared.data, generateId: true, tolerance: DEFAULTS.GEOJSON_RENDER.TOLERANCE });
        const source = map.getSource(sourceId);
        candidateSource = source;
        for (const layer of candidate) {
            // Invisible lines keep native viewport tile preparation active. Symbols
            // remain excluded from collision placement until the exact handoff.
            if (layer.type === 'line') layer.paint = { ...layer.paint, 'line-opacity': 0, 'line-opacity-transition': { duration: 0 } };
            else layer.layout = { ...layer.layout, visibility: 'none' };
            map.addLayer(layer);
        }
        accepted = await new Promise<boolean>((resolve, reject) => {
            const timeout = setTimeout(() => finish(new Error('The revision map did not finish rendering.')), DEFAULTS.HISTORY.SOURCE_READY_TIMEOUT_MS);
            const finish = (error?: Error) => {
                clearTimeout(timeout);
                map.off('render', render);
                map.off('error', failed);
                signal.removeEventListener('abort', canceled);
                if (error) reject(error);
                else resolve(accepted);
            };
            const canceled = () => { finish(); };
            const failed = (event: { sourceId?: string; error?: Error }) => {
                if (event.sourceId === sourceId) finish(event.error ?? new Error('Unable to render this revision.'));
            };
            const render = () => {
                if (!current() || map.getSource(sourceId) !== source) { finish(); return; }
                if (!map.isSourceLoaded(sourceId)) return;
                if (!promoted) {
                    for (const layerId of previousLayers) if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
                    for (const layer of candidate) {
                        if (layer.type === 'line') {
                            map.setPaintProperty(layer.id, 'line-color', Colors.getSurveyPaint(projectId, owner.colorMode,
                                applyDepthLimit(prepared.domain, State.displayPreferences.depthLimitFeet)));
                            map.setPaintProperty(layer.id, 'line-opacity', 1);
                        }
                    }
                    owner.applyProjectLayerVisibility(projectId, undefined, candidate.map(layer => layer.id));
                    promoted = true;
                    map.triggerRepaint();
                    return;
                }
                // This event follows the renderer draw. Updating the DOM in its
                // callback publishes revision metadata in the same browser frame.
                State.allProjectLayers.set(id, candidate.map(layer => layer.id));
                publishPreparedProject(projectId, prepared);
                owner.applyProjectLayerVisibility(projectId);
                accepted = true;
                onDisplayed();
                finish();
            };
            map.on('render', render);
            map.on('error', failed);
            signal.addEventListener('abort', canceled, { once: true });
            map.triggerRepaint();
        });
    } finally {
        if (!accepted) removeCandidate();
    }
    if (accepted) {
        for (const layerId of previousLayers) if (map.getLayer(layerId)) map.removeLayer(layerId);
        if (previousSource && map.getSource(previousSource)) map.removeSource(previousSource);
        await owner.scheduleDisplayUpdate('depth');
    }
    return accepted;
}

function publishPreparedProject(projectId: EntityId, prepared: PreparedProject<ViewerGeoJSON>) {
    const id = String(projectId);
    State.projectDepthDomains.set(id, prepared.domain);
    Geometry.cachePreparedSnapPoints(projectId, prepared.snapPoints);
    if (prepared.boundsCoordinates) {
        State.projectBounds.set(id, new Renderer.LngLatBounds(prepared.boundsCoordinates[0], prepared.boundsCoordinates[1]));
    } else State.projectBounds.delete(id);
}
