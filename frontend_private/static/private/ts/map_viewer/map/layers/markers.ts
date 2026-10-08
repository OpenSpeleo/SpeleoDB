import type { EntityId } from '../../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerUpdateResult } from '../../../../../../../ts-types/domain/viewer-updates.ts';
import { State } from '../../state.ts';
import { DEFAULTS } from '../../defaults.ts';
import type { Feature, FeatureCollection, Point } from 'geojson';
import type { RendererValue, MapPointCollection } from '../../../../../../../ts-types/domain/renderer.ts';
import type { CylinderInstallRecord } from '../../../../../../../ts-types/domain/fleet-records.ts';
import { API } from '../../api.ts';
import { getRuntimeContext } from '../../runtime_context.ts';
import { removeLayersAndSource, addOwnedSource, getSourceData, setOwnedSourceData } from './source_lifecycle.ts';
// Track whether custom marker images have been loaded
let markerImagesLoaded = false;
export const PROJECT_SCOPED_MARKER_PROPERTY = 'project_id';
const ZOOM_LEVELS = DEFAULTS.ZOOM_LEVELS;
interface MarkerLayerOwner {
    refreshExplorationLeadsLayer(): void;
    reorderLayers(): Promise<ViewerUpdateResult> | undefined;
    applyProjectScopedMarkerVisibility(): void;
    showMarkerDragHighlight(type: string, coordinates: [number, number], snapped: boolean): void;
    hideMarkerDragHighlight(): void;
    addCylinderInstallsLayer(data: MapPointCollection<Omit<CylinderInstallRecord, 'id'> & { id?: EntityId }>): void;
    loadCylinderInstalls(): Promise<void>;
}
/**
 * Build gas mix label text from cylinder percentages.
 */
function getCylinderGasMixTextExpression(): RendererValue {
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
function getCylinderInstallLabelExpression(): RendererValue {
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
function withProjectScopedMarkerProperties<Properties extends object>(properties: Properties, projectId: EntityId | null) {
    return {
        ...properties,
        [PROJECT_SCOPED_MARKER_PROPERTY]: projectId ? String(projectId) : null
    };
}

/**
 * Load custom marker images from SVG files
 * Uses map.loadImage() for proper CORS handling with S3/CDN hosted assets
 */
export async function loadMarkerImages() {
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

    // MapLibre loadImage resolves the image response and handles CORS.
    const loadImage = async (url: string) => (await map.loadImage(url)).data;

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
}

/**
 * Add an exploration lead marker to the map
 */
export function addExplorationLeadMarker(this: Pick<MarkerLayerOwner, 'refreshExplorationLeadsLayer' | 'reorderLayers'>, id: EntityId, coordinates: [number, number], lineName = 'Survey Line', description = '', projectId: EntityId | null = null) {
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
    void this.reorderLayers();

    console.log(`⚠️ Exploration lead added: ${id} at ${coordinates as unknown as string}`);
}

/**
 * Refresh the exploration leads layer with current state
 */
export function refreshExplorationLeadsLayer(this: Pick<MarkerLayerOwner, 'applyProjectScopedMarkerVisibility'>) {
    const map = State.map;
    if (!map) return;

    const sourceId = 'exploration-leads-source';
    const layerId = 'exploration-leads-layer';

    // Build GeoJSON from state
    // MapLibre requires promoteId for string IDs - include id in properties
    const features = Array.from(State.explorationLeads.values()).map((marker): Feature<Point, { id: EntityId; lineName: string; project_id: string | null }> => ({
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

    const geojson: FeatureCollection<Point, { id: EntityId; lineName: string; project_id: string | null }> = {
        type: 'FeatureCollection',
        features
    };

    // Update or create source
    if (map.getSource(sourceId)) {
        setOwnedSourceData(map.getSource(sourceId)!, geojson);
    } else {
        addOwnedSource(map, sourceId, {
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
}

/**
 * Remove an exploration lead marker
 */
export function removeExplorationLeadMarker(this: Pick<MarkerLayerOwner, 'refreshExplorationLeadsLayer'>, id: EntityId) {
    State.explorationLeads.delete(id);
    this.refreshExplorationLeadsLayer();
    console.log(`⚠️ Exploration lead removed: ${id}`);
}

/**
 * Update cylinder install position (for drag)
 */
export function updateCylinderInstallPosition(markerId: EntityId, newCoords: [number, number]) {
    const map = State.map;
    if (!map) return;

    const sourceId = 'cylinder-installs-source';
    const source = map.getSource(sourceId);
    const data = getSourceData<MapPointCollection>(source);
    if (source && data) {
        const feature = data.features.find(f => f.id === markerId || f.properties?.id === markerId);
        if (feature) {
            feature.geometry.coordinates = newCoords;
            source.setData(data);
        }
    }
}

/**
 * Update exploration lead position (for drag)
 */
export function updateExplorationLeadPosition(this: Pick<MarkerLayerOwner, 'refreshExplorationLeadsLayer'>, markerId: EntityId, newCoords: [number, number]) {
    const marker = State.explorationLeads.get(markerId);
    if (marker) {
        marker.coordinates = newCoords;
        this.refreshExplorationLeadsLayer();
    }
}

/**
 * Show marker drag highlight - adds a colored circle behind the marker
 * @param {string} markerType - 'cylinder-install' or 'exploration-lead'
 * @param {Array} coordinates - [lng, lat]
 * @param {boolean} isSnapped - whether currently snapped (green=snapped, amber=not)
 */
export function showMarkerDragHighlight(markerType: string, coordinates: [number, number], isSnapped: boolean) {
    const map = State.map;
    if (!map) return;

    const highlightId = 'marker-drag-highlight';
    const highlightSourceId = 'marker-drag-highlight-source';
    const color = isSnapped ? '#10b981' : '#f59e0b'; // Same colors as stations

    const geojson = {
        // MapLibre accepts this existing property-less temporary highlight feature.
        type: 'FeatureCollection' as const,
        features: [{
            type: 'Feature' as const,
            geometry: { type: 'Point' as const, coordinates }
        }]
    };

    if (map.getSource(highlightSourceId)) {
        setOwnedSourceData(map.getSource(highlightSourceId)!, geojson);
        if (map.getLayer(highlightId)) {
            map.setPaintProperty(highlightId, 'circle-color', color);
        }
    } else {
        addOwnedSource(map, highlightSourceId, { type: 'geojson', data: geojson });
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
}

/**
 * Hide marker drag highlight
 */
export function hideMarkerDragHighlight() {
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
}

/**
 * Set marker visual feedback during drag (wrapper for highlight)
 */
export function setMarkerDragFeedback(this: Pick<MarkerLayerOwner, 'showMarkerDragHighlight'>, markerType: string, opacity: number | null, isSnapped: boolean, coordinates?: [number, number]) {
    // Show highlight circle at current position
    if (coordinates) {
        this.showMarkerDragHighlight(markerType, coordinates, isSnapped);
    }
}

/**
 * Reset marker visual feedback after drag
 */
export function resetMarkerDragFeedback(this: Pick<MarkerLayerOwner, 'hideMarkerDragHighlight'>, markerType: string) {
    this.hideMarkerDragHighlight();
}

/**
 * Load and display installed cylinders from the API
 * Fetches GeoJSON data for all installed cylinders the user has access to
 */
export async function loadCylinderInstalls(this: Pick<MarkerLayerOwner, 'addCylinderInstallsLayer'>) {
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
            this.addCylinderInstallsLayer(geojsonData as MapPointCollection<CylinderInstallRecord>);
            console.log(`✅ Loaded ${geojsonData.features.length} cylinder installs`);
        } else {
            console.log('⚠️ No cylinder installs to display or invalid response format');
        }
    } catch (e) {
        console.error('❌ Failed to load cylinder installs:', e);
    }
}

/**
 * Add cylinder installs layer to the map
 */
export function addCylinderInstallsLayer(this: Pick<MarkerLayerOwner, 'applyProjectScopedMarkerVisibility' | 'reorderLayers'>, geojsonData: MapPointCollection<Omit<CylinderInstallRecord, 'id'> & { id?: EntityId }>) {
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
        // Ensure id property is set on each feature for Renderer promoteId
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

    addOwnedSource(map, sourceId, {
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
        // Note: Using ● (U+25CF) instead of emoji - Renderer doesn't support glyphs > 65535
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
    void this.reorderLayers();
}

/**
 * Refresh cylinder installs layer (called after install/uninstall)
 */
export async function refreshCylinderInstallsLayer(this: Pick<MarkerLayerOwner, 'loadCylinderInstalls'>) {
    await this.loadCylinderInstalls();
}
