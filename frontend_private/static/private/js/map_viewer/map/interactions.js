import { State } from '../state.js';
import { Geometry } from './geometry.js';
import { Config, DEFAULTS } from '../config.js';
import { Layers } from './layers.js';

export const Interactions = {
    handlers: {},

    init: function (map, handlers) {
        this.handlers = handlers || {};
        this.setupHoverEffects(map);
        this.setupClickHandlers(map);
        this.setupDragHandlers(map);
        this.setupContextMenu(map);
    },

    QUERY_PADDING: DEFAULTS.DRAG.QUERY_PADDING_PX,

    setupHoverEffects: function (map) {
        map.on('mousemove', (e) => {
            // Use padded query box for better hit detection on icons
            const padding = this.QUERY_PADDING;
            const queryBox = [
                [e.point.x - padding, e.point.y - padding],
                [e.point.x + padding, e.point.y + padding]
            ];
            const features = map.queryRenderedFeatures(queryBox);
            let isInteractive = false;

            for (const feature of features) {
                if (!feature.layer || !feature.layer.id) continue;
                const layerId = feature.layer.id;
                // Check for subsurface stations (circles, biology/bone/artifact/geology icons), 
                // surface stations, Landmarks, and custom markers
                if ((layerId.startsWith('stations-') && 
                     (layerId.endsWith('-circles') || layerId.endsWith('-biology-icons') ||
                      layerId.endsWith('-bone-icons') || layerId.endsWith('-artifact-icons') || 
                      layerId.endsWith('-geology-icons') || layerId.endsWith('-labels'))) ||
                    layerId.startsWith('surface-stations-') ||
                    layerId === 'landmarks-layer' ||
                    layerId === 'landmarks-labels' ||
                    layerId === 'cylinder-installs-layer' ||
                    layerId === 'exploration-leads-layer') {
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

            // Use padded query box for better hit detection on icons
            const padding = this.QUERY_PADDING;
            const queryBox = [
                [e.point.x - padding, e.point.y - padding],
                [e.point.x + padding, e.point.y + padding]
            ];
            const features = map.queryRenderedFeatures(queryBox);

            // Check for Subsurface Stations (circles, biology/bone/artifact/geology icons)
            const stationFeature = features.find(f =>
                f.layer && f.layer.id &&
                f.layer.id.startsWith('stations-') &&
                (f.layer.id.endsWith('-circles') || f.layer.id.endsWith('-biology-icons') || 
                 f.layer.id.endsWith('-bone-icons') || f.layer.id.endsWith('-artifact-icons') ||
                 f.layer.id.endsWith('-geology-icons')) &&
                !f.layer.id.startsWith('surface-')
            );

            if (stationFeature) {
                const stationId = stationFeature.id;
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
                const stationId = surfaceStationFeature.id;
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
                const landmarkId = poiFeature.id;
                if (this.handlers.onLandmarkClick) {
                    this.handlers.onLandmarkClick(landmarkId);
                }
                return;
            }

            // Check for Exploration Leads
            const explorationLeadFeature = features.find(f =>
                f.layer && f.layer.id === 'exploration-leads-layer'
            );

            if (explorationLeadFeature) {
                const leadId = explorationLeadFeature.id;
                if (this.handlers.onExplorationLeadClick) {
                    this.handlers.onExplorationLeadClick(leadId);
                }
                return;
            }

            // Check for Cylinder Installs (persistent from database)
            const cylinderInstallFeature = features.find(f =>
                f.layer && f.layer.id === 'cylinder-installs-layer'
            );

            if (cylinderInstallFeature) {
                const cylinderId = cylinderInstallFeature.id;
                if (this.handlers.onCylinderInstallClick) {
                    this.handlers.onCylinderInstallClick(cylinderId);
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
        let draggedType = null; // 'station', 'landmark', 'cylinder-install', 'exploration-lead'
        let originalCoords = null;
        let mouseDownPoint = null;
        let currentSnapResult = null;
        let draggedProjectId = null;
        let originalColor = null;

        const self = this;

        // Types that snap to survey line endpoints (like stations)
        const SNAPPABLE_TYPES = ['station', 'cylinder-install', 'exploration-lead'];

        map.on('mousedown', (e) => {
            if (e.originalEvent.button !== 0) return; // Only left click

            // Use padded query box for better hit detection on icons (same as click/hover)
            const padding = self.QUERY_PADDING;
            const queryBox = [
                [e.point.x - padding, e.point.y - padding],
                [e.point.x + padding, e.point.y + padding]
            ];
            const features = map.queryRenderedFeatures(queryBox);
            if (!features.length) return;

            // Check Station (circles, biology/bone/artifact/geology icons)
            const stationFeature = features.find(f =>
                f.layer && f.layer.id && f.layer.id.startsWith('stations-') && 
                (f.layer.id.endsWith('-circles') || f.layer.id.endsWith('-biology-icons') || 
                 f.layer.id.endsWith('-bone-icons') || f.layer.id.endsWith('-artifact-icons') ||
                 f.layer.id.endsWith('-geology-icons'))
            );

            if (stationFeature) {
                const projectId = Geometry.findProjectForFeature(stationFeature, map, State.allProjectLayers);
                if (Config.hasScopedAccess('project', projectId, 'write')) {
                    isPotentialDrag = true;
                    hasMoved = false;
                    isDragging = false;
                    draggedFeatureId = stationFeature.id;
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

            // Check Cylinder Install (persistent from database)
            const cylinderInstallFeature = features.find(f =>
                f.layer && f.layer.id === 'cylinder-installs-layer'
            );

            if (cylinderInstallFeature) {
                const installProjectId = cylinderInstallFeature.properties?.project_id;
                if (Config.hasScopedAccess('project', installProjectId, 'write')) {
                    isPotentialDrag = true;
                    hasMoved = false;
                    isDragging = false;
                    draggedFeatureId = cylinderInstallFeature.id;
                    draggedType = 'cylinder-install';
                    originalCoords = cylinderInstallFeature.geometry.coordinates.slice();
                    mouseDownPoint = e.point;
                    draggedProjectId = null;
                    currentSnapResult = null;

                    map.dragPan.disable();
                    return;
                }
            }

            // Check Exploration Lead
            const explorationLeadFeature = features.find(f =>
                f.layer && f.layer.id === 'exploration-leads-layer'
            );

            if (explorationLeadFeature) {
                const leadProjectId = explorationLeadFeature.properties?.project_id;
                if (Config.hasScopedAccess('project', leadProjectId, 'write')) {
                    isPotentialDrag = true;
                    hasMoved = false;
                    isDragging = false;
                    draggedFeatureId = explorationLeadFeature.id;
                    draggedType = 'exploration-lead';
                    originalCoords = explorationLeadFeature.geometry.coordinates.slice();
                    mouseDownPoint = e.point;
                    draggedProjectId = null;
                    currentSnapResult = null;

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
                draggedFeatureId = poiFeature.id;
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

                if (distance < DEFAULTS.DRAG.THRESHOLD_PX) {
                    return; // Not dragging yet
                }

                // Threshold exceeded - now we're dragging
                hasMoved = true;
                isDragging = true;
                map.getCanvas().style.cursor = 'grabbing';
                map.doubleClickZoom.disable();
            }

            if (!isDragging) return;

            const coords = [e.lngLat.lng, e.lngLat.lat];

            // Handle snappable types (station, cylinder-install, exploration-lead)
            if (SNAPPABLE_TYPES.includes(draggedType)) {
                // Check for snap
                const snapResult = Geometry.findMagneticSnapPoint(coords, null);
                currentSnapResult = snapResult;

                // Use snapped coordinates if snapping
                const displayCoords = snapResult.snapped ? snapResult.coordinates : coords;

                // Update visual position and feedback based on type
                if (draggedType === 'station') {
                    Layers.updateStationPosition(draggedProjectId, draggedFeatureId, displayCoords);
                    const newColor = snapResult.snapped ? '#10b981' : '#f59e0b';
                    Layers.updateStationColor(draggedProjectId, draggedFeatureId, newColor);
                } else if (draggedType === 'cylinder-install' || draggedType === 'exploration-lead') {
                    // Update position
                    if (draggedType === 'cylinder-install') {
                        Layers.updateCylinderInstallPosition(draggedFeatureId, displayCoords);
                    } else {
                        Layers.updateExplorationLeadPosition(draggedFeatureId, displayCoords);
                    }
                    // Visual feedback: show colored highlight circle (green=snapped, amber=not)
                    Layers.setMarkerDragFeedback(draggedType, null, snapResult.snapped, displayCoords);
                }

                // Show snap indicator
                Geometry.showSnapIndicator(displayCoords, map, snapResult.snapped);

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
                const finalCoords = [e.lngLat.lng, e.lngLat.lat];
                const snapResult = Geometry.findMagneticSnapPoint(finalCoords, null);

                if (draggedType === 'station') {
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
                } else if (draggedType === 'cylinder-install' || draggedType === 'exploration-lead') {
                    // Reset visual feedback
                    Layers.resetMarkerDragFeedback(draggedType);

                    // Call handler with snap result (same pattern as stations)
                    if (self.handlers.onMarkerDragEnd) {
                        self.handlers.onMarkerDragEnd(
                            draggedType,
                            draggedFeatureId,
                            snapResult,
                            originalCoords
                        );
                    }
                } else if (draggedType === 'landmark') {
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
            // Use padded query box for better hit detection on icons (same as hover/click)
            const padding = this.QUERY_PADDING;
            const queryBox = [
                [e.point.x - padding, e.point.y - padding],
                [e.point.x + padding, e.point.y + padding]
            ];
            const features = map.queryRenderedFeatures(queryBox);

            // Check Subsurface Station (circles, biology/bone/artifact/geology icons)
            const stationFeature = features.find(f =>
                f.layer && f.layer.id &&
                f.layer.id.startsWith('stations-') &&
                (f.layer.id.endsWith('-circles') || f.layer.id.endsWith('-biology-icons') || 
                 f.layer.id.endsWith('-bone-icons') || f.layer.id.endsWith('-artifact-icons') ||
                 f.layer.id.endsWith('-geology-icons')) &&
                !f.layer.id.startsWith('surface-')
            );

            if (stationFeature) {
                if (this.handlers.onContextMenu) {
                    this.handlers.onContextMenu(e, 'station', {
                        id: stationFeature.id,
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
                        id: surfaceStationFeature.id,
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
                        id: poiFeature.id,
                        feature: poiFeature
                    });
                }
                return;
            }

            // Check Cylinder Install (persistent from database)
            const cylinderInstallFeature = features.find(f =>
                f.layer && f.layer.id === 'cylinder-installs-layer'
            );

            if (cylinderInstallFeature) {
                if (this.handlers.onContextMenu) {
                    this.handlers.onContextMenu(e, 'cylinder-install', {
                        id: cylinderInstallFeature.id,
                        feature: cylinderInstallFeature
                    });
                }
                return;
            }

            // Check Exploration Lead
            const explorationLeadFeature = features.find(f =>
                f.layer && f.layer.id === 'exploration-leads-layer'
            );

            if (explorationLeadFeature) {
                if (this.handlers.onContextMenu) {
                    this.handlers.onContextMenu(e, 'exploration-lead', {
                        id: explorationLeadFeature.id,
                        feature: explorationLeadFeature
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



