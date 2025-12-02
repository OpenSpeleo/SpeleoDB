import { State } from '../state.js';
import { Geometry } from './geometry.js';
import { Config } from '../config.js';
import { Layers } from './layers.js';

// Drag threshold in pixels - must move this far before drag starts
const DRAG_THRESHOLD = 10;

export const Interactions = {
    handlers: {},

    // Handlers should contain:
    // onStationClick(stationId)
    // onLandmarkClick(landmarkId)
    // onStationDragEnd(stationId, snapResult, originalCoords)
    // onLandmarkDragEnd(landmarkId, newCoords, originalCoords)
    // onContextMenu(event, type, data)
    // onMapClick(coords)

    init: function (map, handlers) {
        this.handlers = handlers || {};
        this.setupHoverEffects(map);
        this.setupClickHandlers(map);
        this.setupDragHandlers(map);
        this.setupContextMenu(map);
    },

    setupHoverEffects: function (map) {
        map.on('mousemove', (e) => {
            const features = map.queryRenderedFeatures(e.point);
            let isInteractive = false;

            for (const feature of features) {
                if (!feature.layer || !feature.layer.id) continue;
                // Check for subsurface stations, surface stations, and Landmarks
                if (feature.layer.id.includes('stations-') ||
                    feature.layer.id.startsWith('surface-stations-') ||
                    feature.layer.id === 'landmarks-layer' ||
                    feature.layer.id === 'landmarks-labels') {
                    isInteractive = true;
                    break;
                }
            }

            map.getCanvas().style.cursor = isInteractive ? 'pointer' : '';
        });
    },

    setupClickHandlers: function (map) {
        map.on('click', (e) => {
            if (e.defaultPrevented) return;

            const features = map.queryRenderedFeatures(e.point);

            // Check for Subsurface Stations (circles)
            const stationFeature = features.find(f =>
                f.layer && f.layer.id &&
                f.layer.id.startsWith('stations-') &&
                f.layer.id.endsWith('-circles') &&
                !f.layer.id.startsWith('surface-')
            );

            if (stationFeature) {
                const stationId = stationFeature.properties.id;
                if (this.handlers.onStationClick) {
                    this.handlers.onStationClick(stationId, 'subsurface');
                }
                return;
            }

            // Check for Surface Stations (diamond symbols)
            const surfaceStationFeature = features.find(f =>
                f.layer && f.layer.id &&
                f.layer.id.startsWith('surface-stations-') &&
                !f.layer.id.endsWith('-labels')
            );

            if (surfaceStationFeature) {
                const stationId = surfaceStationFeature.properties.id;
                if (this.handlers.onStationClick) {
                    this.handlers.onStationClick(stationId, 'surface');
                }
                return;
            }

            // Check for Landmarks
            const poiFeature = features.find(f =>
                f.layer && (f.layer.id === 'landmarks-layer' || f.layer.id === 'landmarks-labels')
            );

            if (poiFeature) {
                const landmarkId = poiFeature.properties.id;
                if (this.handlers.onLandmarkClick) {
                    this.handlers.onLandmarkClick(landmarkId);
                }
                return;
            }

            // Map Click (background)
            if (this.handlers.onMapClick) {
                this.handlers.onMapClick(e.lngLat.toArray());
            }
        });
    },

    setupDragHandlers: function (map) {
        // State for drag handling
        let isPotentialDrag = false;
        let isDragging = false;
        let hasMoved = false;
        let draggedFeatureId = null;
        let draggedType = null; // 'station' or 'landmark'
        let originalCoords = null;
        let mouseDownPoint = null;
        let currentSnapResult = null;
        let draggedProjectId = null;
        let originalColor = null;

        const self = this;

        map.on('mousedown', (e) => {
            if (e.originalEvent.button !== 0) return; // Only left click

            const features = map.queryRenderedFeatures(e.point);
            if (!features.length) return;

            // Check Station
            const stationFeature = features.find(f =>
                f.layer && f.layer.id && f.layer.id.startsWith('stations-') && f.layer.id.endsWith('-circles')
            );

            if (stationFeature) {
                const projectId = Geometry.findProjectForFeature(stationFeature, map, State.allProjectLayers);
                if (Config.hasProjectWriteAccess(projectId)) {
                    isPotentialDrag = true;
                    hasMoved = false;
                    isDragging = false;
                    draggedFeatureId = stationFeature.properties.id;
                    draggedType = 'station';
                    originalCoords = stationFeature.geometry.coordinates.slice();
                    mouseDownPoint = e.point;
                    draggedProjectId = projectId;
                    originalColor = stationFeature.properties.color;
                    currentSnapResult = null;

                    // Disable pan immediately to avoid interference
                    map.dragPan.disable();
                    return;
                }
            }

            // Check Landmark
            const poiFeature = features.find(f =>
                f.layer && f.layer.id === 'landmarks-layer'
            );

            if (poiFeature) {
                // Any authenticated user can drag their Landmarks
                isPotentialDrag = true;
                hasMoved = false;
                isDragging = false;
                draggedFeatureId = poiFeature.properties.id;
                draggedType = 'landmark';
                originalCoords = poiFeature.geometry.coordinates.slice();
                mouseDownPoint = e.point;
                draggedProjectId = null;
                currentSnapResult = null;

                map.dragPan.disable();
            }
        });

        map.on('mousemove', (e) => {
            if (!isPotentialDrag) return;

            // Check if we've moved past the threshold
            if (!hasMoved && mouseDownPoint) {
                const dx = e.point.x - mouseDownPoint.x;
                const dy = e.point.y - mouseDownPoint.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < DRAG_THRESHOLD) {
                    return; // Not dragging yet
                }

                // Threshold exceeded - now we're dragging
                hasMoved = true;
                isDragging = true;
                map.getCanvas().style.cursor = 'grabbing';
                map.doubleClickZoom.disable();

                console.log(`🫳 Started dragging ${draggedType}: ${draggedFeatureId}`);
            }

            if (!isDragging) return;

            const coords = [e.lngLat.lng, e.lngLat.lat];

            if (draggedType === 'station') {
                // Check for snap
                const snapResult = Geometry.findMagneticSnapPoint(coords, null);
                currentSnapResult = snapResult;

                // Use snapped coordinates if snapping
                const displayCoords = snapResult.snapped ? snapResult.coordinates : coords;

                // Update visual position
                Layers.updateStationPosition(draggedProjectId, draggedFeatureId, displayCoords);

                // Show snap indicator
                Geometry.showSnapIndicator(displayCoords, map, snapResult.snapped);

                // Update station color to indicate snap status
                const newColor = snapResult.snapped ? '#10b981' : '#f59e0b'; // Green if snapped, amber if not
                Layers.updateStationColor(draggedProjectId, draggedFeatureId, newColor);

            } else if (draggedType === 'landmark') {
                // Landmarks don't snap to survey lines
                if (self.handlers.onLandmarkDrag) {
                    self.handlers.onLandmarkDrag(draggedFeatureId, coords);
                }
            }
        });

        const onUp = (e) => {
            if (!isPotentialDrag) return;

            const wasDragging = isDragging && hasMoved;

            // Hide snap indicator
            Geometry.hideSnapIndicator();

            // Restore cursor and map interactions
            map.getCanvas().style.cursor = '';
            map.dragPan.enable();
            map.doubleClickZoom.enable();

            if (wasDragging) {
                if (draggedType === 'station') {
                    // Calculate final snap result
                    const finalCoords = [e.lngLat.lng, e.lngLat.lat];
                    const snapResult = Geometry.findMagneticSnapPoint(finalCoords, null);

                    // Restore original color (will be updated after confirm/cancel)
                    Layers.updateStationColor(draggedProjectId, draggedFeatureId, originalColor || '#fb923c');

                    // Call handler with snap result
                    if (self.handlers.onStationDragEnd) {
                        self.handlers.onStationDragEnd(
                            draggedFeatureId,
                            draggedProjectId,
                            snapResult,
                            originalCoords
                        );
                    }
                } else if (draggedType === 'landmark') {
                    const finalCoords = [e.lngLat.lng, e.lngLat.lat];
                    if (self.handlers.onLandmarkDragEnd) {
                        self.handlers.onLandmarkDragEnd(draggedFeatureId, finalCoords, originalCoords);
                    }
                }
            } else {
                // It was just a click - re-enable pan
                // The click handler will fire automatically
            }

            // Reset state
            isPotentialDrag = false;
            isDragging = false;
            hasMoved = false;
            draggedFeatureId = null;
            draggedType = null;
            originalCoords = null;
            mouseDownPoint = null;
            currentSnapResult = null;
            draggedProjectId = null;
            originalColor = null;
        };

        map.on('mouseup', onUp);
    },

    setupContextMenu: function (map) {
        map.on('contextmenu', (e) => {
            const features = map.queryRenderedFeatures(e.point);

            // Check Subsurface Station
            const stationFeature = features.find(f =>
                f.layer && f.layer.id &&
                f.layer.id.startsWith('stations-') &&
                f.layer.id.endsWith('-circles') &&
                !f.layer.id.startsWith('surface-')
            );

            if (stationFeature) {
                if (this.handlers.onContextMenu) {
                    this.handlers.onContextMenu(e, 'station', {
                        id: stationFeature.properties.id,
                        feature: stationFeature,
                        stationType: 'subsurface'
                    });
                }
                return;
            }

            // Check Surface Station
            const surfaceStationFeature = features.find(f =>
                f.layer && f.layer.id &&
                f.layer.id.startsWith('surface-stations-') &&
                !f.layer.id.endsWith('-labels')
            );

            if (surfaceStationFeature) {
                if (this.handlers.onContextMenu) {
                    this.handlers.onContextMenu(e, 'surface-station', {
                        id: surfaceStationFeature.properties.id,
                        feature: surfaceStationFeature,
                        stationType: 'surface'
                    });
                }
                return;
            }

            // Check Landmark
            const poiFeature = features.find(f =>
                f.layer && (f.layer.id === 'landmarks-layer' || f.layer.id === 'landmarks-labels')
            );

            if (poiFeature) {
                if (this.handlers.onContextMenu) {
                    this.handlers.onContextMenu(e, 'landmark', {
                        id: poiFeature.properties.id,
                        feature: poiFeature
                    });
                }
                return;
            }

            // Map Background
            if (this.handlers.onContextMenu) {
                this.handlers.onContextMenu(e, 'map', {
                    coordinates: e.lngLat.toArray()
                });
            }
        });
    }
};



