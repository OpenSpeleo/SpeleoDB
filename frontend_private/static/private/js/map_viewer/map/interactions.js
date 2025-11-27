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
    // onPOIClick(poiId)
    // onStationDragEnd(stationId, snapResult, originalCoords)
    // onPOIDragEnd(poiId, newCoords, originalCoords)
    // onContextMenu(event, type, data)
    // onMapClick(coords)
    
    init: function(map, handlers) {
        this.handlers = handlers || {};
        this.setupHoverEffects(map);
        this.setupClickHandlers(map);
        this.setupDragHandlers(map);
        this.setupContextMenu(map);
    },

    setupHoverEffects: function(map) {
        map.on('mousemove', (e) => {
            const features = map.queryRenderedFeatures(e.point);
            let isInteractive = false;
            
            for (const feature of features) {
                if (!feature.layer || !feature.layer.id) continue;
                if (feature.layer.id.includes('stations-') || 
                    feature.layer.id === 'pois-layer' || 
                    feature.layer.id === 'pois-labels') {
                    isInteractive = true;
                    break;
                }
            }
            
            map.getCanvas().style.cursor = isInteractive ? 'pointer' : '';
        });
    },

    setupClickHandlers: function(map) {
        map.on('click', (e) => {
            if (e.defaultPrevented) return;

            const features = map.queryRenderedFeatures(e.point);
            
            // Check for Stations
            const stationFeature = features.find(f => 
                f.layer && f.layer.id && f.layer.id.startsWith('stations-') && f.layer.id.endsWith('-circles')
            );
            
            if (stationFeature) {
                const stationId = stationFeature.properties.id;
                if (this.handlers.onStationClick) {
                    this.handlers.onStationClick(stationId);
                }
                return;
            }

            // Check for POIs
            const poiFeature = features.find(f => 
                f.layer && (f.layer.id === 'pois-layer' || f.layer.id === 'pois-labels')
            );
            
            if (poiFeature) {
                const poiId = poiFeature.properties.id;
                if (this.handlers.onPOIClick) {
                    this.handlers.onPOIClick(poiId);
                }
                return;
            }

            // Map Click (background)
            if (this.handlers.onMapClick) {
                this.handlers.onMapClick(e.lngLat.toArray());
            }
        });
    },

    setupDragHandlers: function(map) {
        // State for drag handling
        let isPotentialDrag = false;
        let isDragging = false;
        let hasMoved = false;
        let draggedFeatureId = null;
        let draggedType = null; // 'station' or 'poi'
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
            
            if (stationFeature && Config.hasWriteAccess) {
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

            // Check POI
            const poiFeature = features.find(f => 
                f.layer && f.layer.id === 'pois-layer'
            );
            
            if (poiFeature && Config.hasWriteAccess) {
                isPotentialDrag = true;
                hasMoved = false;
                isDragging = false;
                draggedFeatureId = poiFeature.properties.id;
                draggedType = 'poi';
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
                
            } else if (draggedType === 'poi') {
                // POIs don't snap to survey lines
                if (self.handlers.onPOIDrag) {
                    self.handlers.onPOIDrag(draggedFeatureId, coords);
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
                } else if (draggedType === 'poi') {
                    const finalCoords = [e.lngLat.lng, e.lngLat.lat];
                    if (self.handlers.onPOIDragEnd) {
                        self.handlers.onPOIDragEnd(draggedFeatureId, finalCoords, originalCoords);
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

    setupContextMenu: function(map) {
        map.on('contextmenu', (e) => {
            const features = map.queryRenderedFeatures(e.point);
            
            // Check Station
            const stationFeature = features.find(f => 
                f.layer && f.layer.id && f.layer.id.startsWith('stations-') && f.layer.id.endsWith('-circles')
            );
            
            if (stationFeature) {
                if (this.handlers.onContextMenu) {
                    this.handlers.onContextMenu(e, 'station', {
                        id: stationFeature.properties.id,
                        feature: stationFeature
                    });
                }
                return;
            }

            // Check POI
            const poiFeature = features.find(f => 
                f.layer && (f.layer.id === 'pois-layer' || f.layer.id === 'pois-labels')
            );
            
            if (poiFeature) {
                if (this.handlers.onContextMenu) {
                    this.handlers.onContextMenu(e, 'poi', {
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

