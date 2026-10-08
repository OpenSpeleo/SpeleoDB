import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerGeoJSON } from '../../../../../../../ts-types/domain/map-geometry.ts';
import type { OverlayInstallOptions, PreparedGPSOverlay } from '../../../../../../../ts-types/domain/map-layers.ts';
import type { ViewerUpdateResult } from '../../../../../../../ts-types/domain/viewer-updates.ts';
import { Config, DEFAULTS } from '../../config.ts';
import { State } from '../../state.ts';
import { API } from '../../api.ts';
import { Colors } from '../colors.ts';
import { geoJSONLineWidth } from '../line_rendering.ts';
import { readViewerGeoJSON } from '../read_geojson.ts';
import { prepareGeoJSONBounds } from '../preparation.ts';
import { removeLayersAndSource } from './source_lifecycle.ts';
import { toggleLazyOverlay } from './lazy_overlay.ts';

interface GPSLayerOwner {
    addGPSTrackLayer(id: EntityId, data: ViewerGeoJSON, options?: OverlayInstallOptions<PreparedGPSOverlay>): Promise<void>;
    showGPSTrackLayers(id: EntityId, visible: boolean): void;
    setGPSTrackLoading(id: EntityId, loading: boolean): void;
    reorderLayers(): Promise<ViewerUpdateResult> | undefined;
}
const ZOOM_LEVELS = DEFAULTS.ZOOM_LEVELS;

// GPS tracks default to OFF (false) - explicit true required to be visible
// No persistence - visibility is session-only
export function isGPSTrackVisible(trackId: EntityId) {
    try {
        return State.gpsTrackLayerStates.get(String(trackId)) === true;
    } catch (e) {
        return false; // Default to OFF
    }
}

// Check if GPS track is currently loading
export function isGPSTrackLoading(trackId: EntityId) {
    return State.gpsTrackLoadingStates.get(String(trackId)) === true;
}

// Set GPS track loading state
export function setGPSTrackLoading(trackId: EntityId, isLoading: boolean) {
    State.gpsTrackLoadingStates.set(String(trackId), isLoading);
    // Dispatch event for UI updates
    window.dispatchEvent(new CustomEvent('speleo:gps-track-loading-changed', {
        detail: { trackId, isLoading }
    }));
}

// Toggle GPS track visibility - handles lazy loading of GeoJSON
export async function toggleGPSTrackVisibility(this: Pick<GPSLayerOwner, 'addGPSTrackLayer' | 'showGPSTrackLayers' | 'setGPSTrackLoading'>, trackId: EntityId, isVisible: boolean) {
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
            // Existing display-file contract is asserted after transport, without new validation.
            return readViewerGeoJSON(response, { isCurrent: () => !signal.aborted }) as unknown as Promise<ViewerGeoJSON>;
        },
        prepare: async (data, isCurrent) => ({ boundsCoordinates: await prepareGeoJSONBounds(data, { isCurrent }) }),
        install: (data, isCurrent, prepared) => this.addGPSTrackLayer(id, data, { isCurrent, prepared }),
        show: visible => this.showGPSTrackLayers(id, visible),
        loading: value => this.setGPSTrackLoading(id, value),
    });
}

// Show/hide GPS track layers
export function showGPSTrackLayers(trackId: EntityId, isVisible: boolean) {
    const map = State.map;
    if (!map) return;

    const layers = State.allGPSTrackLayers.get(String(trackId)) || [];
    layers.forEach(layerId => {
        if (map.getLayer(layerId)) {
            map.setLayoutProperty(layerId, 'visibility', isVisible ? 'visible' : 'none');
        }
    });
}

// Add GPS track GeoJSON layers to the map
export async function addGPSTrackLayer(this: Pick<GPSLayerOwner, 'reorderLayers'>, trackId: EntityId, geojsonData: ViewerGeoJSON, { isCurrent = () => true, prepared }: OverlayInstallOptions<PreparedGPSOverlay> = {}) {
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
    const trackLayers: string[] = [];
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
    void this.reorderLayers();
}
