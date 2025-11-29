import { State } from '../state.js';
import { Layers } from './layers.js';

// Magnetic snap radius in meters
const MAGNETIC_SNAP_RADIUS = 10;

// Cache for line features by project
const lineFeatureCache = new Map();

// Cache for snap points (start/end vertices only) by project
const snapPointsCache = new Map();

export const Geometry = {
    // Calculate distance in meters between two lat/lng points using Haversine formula
    calculateDistanceInMeters: function(point1, point2) {
        const [lng1, lat1] = point1;
        const [lng2, lat2] = point2;

        const EARTH_RADIUS_METERS = 6_371_000; // WGS84 mean Earth radius
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng / 2) * Math.sin(dLng / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        
        return EARTH_RADIUS_METERS * c;
    },

    // Cache line features and extract start/end snap points from a project's GeoJSON source
    cacheLineFeatures: function(projectId, geojsonData) {
        if (!geojsonData || !geojsonData.features) return;
        
        const lines = new Map();
        const snapPoints = [];
        
        geojsonData.features.forEach((feature, index) => {
            if (feature.geometry && feature.geometry.type === 'LineString') {
                const coords = feature.geometry.coordinates;
                const lineName = feature.properties?.section_name || feature.properties?.name || `Line ${index}`;
                
                // Store full line data
                lines.set(`${projectId}-line-${index}`, {
                    coordinates: coords,
                    properties: feature.properties
                });
                
                // Extract ONLY start and end points for snapping
                if (coords.length >= 2) {
                    // Start point
                    const startCoord = [coords[0][0], coords[0][1]]; // [lng, lat] only
                    snapPoints.push({
                        coordinates: startCoord,
                        lineName: lineName,
                        type: 'start',
                        lineIndex: 0
                    });
                    
                    // End point
                    const endCoord = [coords[coords.length - 1][0], coords[coords.length - 1][1]];
                    snapPoints.push({
                        coordinates: endCoord,
                        lineName: lineName,
                        type: 'end',
                        lineIndex: coords.length - 1
                    });
                }
            }
        });
        
        if (lines.size > 0) {
            lineFeatureCache.set(String(projectId), lines);
            snapPointsCache.set(String(projectId), snapPoints);
            console.log(`📐 Project ${projectId}: ${lines.size} lines, ${snapPoints.length} snap points (start/end only)`);
        }
    },

    // Find magnetic snap point - ONLY snaps to start/end vertices of lines
    findMagneticSnapPoint: function(coordinates, projectId = null) {
        const [lng, lat] = coordinates;
        const target = [lng, lat];
        let bestPoint = null;
        let bestDistance = Infinity;
        let bestLineName = null;
        let bestPointType = null;
        let bestProjectId = null;

        // Only check snap points (start/end vertices), NOT arbitrary points on lines
        if (snapPointsCache && snapPointsCache.size > 0) {
            for (const [pid, points] of snapPointsCache.entries()) {
                // If a specific project is requested, only check that project
                if (projectId && pid !== String(projectId)) continue;
                
                // Skip hidden projects
                if (!Layers.isProjectVisible(pid)) continue;
                
                if (!Array.isArray(points) || points.length === 0) continue;
                
                for (const snapPoint of points) {
                    const d = this.calculateDistanceInMeters(target, snapPoint.coordinates);
                    
                    if (d < bestDistance) {
                        bestDistance = d;
                        bestPoint = snapPoint.coordinates;
                        bestLineName = snapPoint.lineName;
                        bestPointType = snapPoint.type; // 'start' or 'end'
                        bestProjectId = pid;
                    }
                    
                    if (bestDistance === 0) break;
                }
                if (bestDistance === 0) break;
            }
        }

        // Enforce snap radius threshold
        if (!isFinite(bestDistance) || bestDistance > MAGNETIC_SNAP_RADIUS) {
            return {
                coordinates: target,
                lineName: null,
                pointType: null,
                distance: bestDistance,
                snapped: false,
                projectId: null
            };
        }

        return {
            coordinates: bestPoint || target,
            lineName: bestLineName,
            pointType: bestPointType,
            distance: bestDistance,
            snapped: true,
            projectId: bestProjectId
        };
    },

    // Find project for a feature based on layer ID
    findProjectForFeature: function(feature, map, allProjectLayers) {
        if (!feature.layer || !feature.layer.id) return null;
        
        // Check if it's a station layer
        if (feature.layer.id.startsWith('stations-')) {
            const projectId = feature.layer.id.replace('stations-', '').replace('-circles', '').replace('-labels', '');
            return projectId;
        }
        
        // Check if it's a project layer
        for (const [projectId, layerIds] of allProjectLayers.entries()) {
            if (layerIds.includes(feature.layer.id)) {
                return projectId;
            }
        }
        return null;
    },

    // Snap indicator element
    snapIndicatorEl: null,

    showSnapIndicator: function(coordinates, map, isSnapped = false) {
        if (!this.snapIndicatorEl) {
            this.snapIndicatorEl = document.createElement('div');
            this.snapIndicatorEl.id = 'snap-indicator';
            this.snapIndicatorEl.style.cssText = `
                position: absolute;
                pointer-events: none;
                z-index: 1000;
                transition: all 0.1s ease-out;
            `;
            document.body.appendChild(this.snapIndicatorEl);
        }

        const point = map.project(coordinates);
        this.snapIndicatorEl.style.display = 'block';
        this.snapIndicatorEl.style.left = `${point.x}px`;
        this.snapIndicatorEl.style.top = `${point.y}px`;

        if (isSnapped) {
            this.snapIndicatorEl.style.cssText = `
                position: absolute;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                border: 3px solid #10b981;
                background: rgba(16, 185, 129, 0.3);
                box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
                transform: translate(-50%, -50%);
                pointer-events: none;
                z-index: 1000;
                transition: all 0.1s ease-out;
            `;
        } else {
            this.snapIndicatorEl.style.cssText = `
                position: absolute;
                width: 16px;
                height: 16px;
                border-radius: 50%;
                border: 2px solid #ef4444;
                background: rgba(239, 68, 68, 0.2);
                transform: translate(-50%, -50%);
                pointer-events: none;
                z-index: 1000;
                transition: all 0.1s ease-out;
            `;
        }
    },

    hideSnapIndicator: function() {
        if (this.snapIndicatorEl) {
            this.snapIndicatorEl.style.display = 'none';
        }
    },

    // Get snap radius for external access
    getSnapRadius: function() {
        return MAGNETIC_SNAP_RADIUS;
    },

    // Find nearest snap point (for creating stations from context menu)
    findNearestSnapPointWithinRadius: function(coordinates, radiusMeters = MAGNETIC_SNAP_RADIUS) {
        const [lng, lat] = coordinates;
        const target = [lng, lat];
        let bestPoint = null;
        let bestDistance = Infinity;
        let bestLineName = null;
        let bestPointType = null;
        let bestProjectId = null;

        if (snapPointsCache && snapPointsCache.size > 0) {
            for (const [pid, points] of snapPointsCache.entries()) {
                if (!Array.isArray(points) || points.length === 0) continue;
                if (!Layers.isProjectVisible(pid)) continue;
                
                for (const snapPoint of points) {
                    const d = this.calculateDistanceInMeters(target, snapPoint.coordinates);
                    if (d < bestDistance) {
                        bestDistance = d;
                        bestPoint = snapPoint.coordinates;
                        bestLineName = snapPoint.lineName;
                        bestPointType = snapPoint.type;
                        bestProjectId = pid;
                    }
                    if (bestDistance === 0) break;
                }
                if (bestDistance === 0) break;
            }
        }

        if (!isFinite(bestDistance) || bestDistance > radiusMeters) {
            return { snapped: false, coordinates: target, distance: bestDistance };
        }

        return {
            snapped: true,
            coordinates: bestPoint,
            distance: bestDistance,
            lineName: bestLineName,
            pointType: bestPointType,
            projectId: bestProjectId
        };
    },

    // Get snap info for debugging
    getSnapInfo: function() {
        const info = {
            snapRadius: MAGNETIC_SNAP_RADIUS,
            totalSnapPoints: Array.from(snapPointsCache.values()).reduce((total, points) => total + points.length, 0),
            projectsWithSnapPoints: snapPointsCache.size,
            snapPointsPerProject: {}
        };

        snapPointsCache.forEach((points, projectId) => {
            info.snapPointsPerProject[projectId] = points.length;
        });

        console.log('🧲 Current snap configuration:', info);
        return info;
    },

    // Set snap radius (for testing)
    setSnapRadius: function(radiusInMeters) {
        // Note: This requires changing the constant to a variable if we want runtime adjustment
        console.log(`🧲 Magnetic snap radius is ${MAGNETIC_SNAP_RADIUS}m (not adjustable at runtime)`);
        return MAGNETIC_SNAP_RADIUS;
    }
};



