import { Renderer } from '../renderer.ts';
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
    applyProjectLayerVisibility(id: EntityId): void;
    scheduleDisplayUpdate(...concerns: DisplayConcern[]): Promise<ViewerUpdateResult>;
}
const ZOOM_LEVELS = DEFAULTS.ZOOM_LEVELS;

interface ProjectGeoJSONLoadOptions {
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
        const response = await fetch(url);
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
            State.projectBounds.set(String(projectId), new Renderer.LngLatBounds(boundsCoordinates[0], boundsCoordinates[1]));
        }
        await this.scheduleDisplayUpdate('depth');

    } catch (e) {
        if (isCurrent() && !(e instanceof Error && e.name === 'AbortError')) {
            console.error(`Error loading GeoJSON for project ${projectId}`, e);
            if (options.transformData) {
                await this.scheduleDisplayUpdate('depth');
                throw e;
            }
        }
    }
}
