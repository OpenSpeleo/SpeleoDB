import type { GeometryFacade, SnapInfo } from '../../../../../../ts-types/domain/map-snapping.ts';
import { findNearestGeographicCandidate } from '@speleodb/map-core/nearest';
import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { PreparedSnapPoint } from '../../../../../../ts-types/domain/map-preparation.ts';
import { isProjectEffectivelyVisible } from './project_visibility.ts';
import { DEFAULTS } from '../defaults.ts';
import { calculateDistanceInMeters } from './geodesy.ts';

let MAGNETIC_SNAP_RADIUS = DEFAULTS.SNAP.RADIUS_METERS;

// Cache for snap points (start/end vertices only) by project
const snapPointsCache = new Map<string, PreparedSnapPoint[]>();

/** Eligibility and project ownership stay in the web adapter. */
function nearestVisibleSnapPoint(
    target: readonly number[],
    projectId: EntityId | null,
    distanceInMeters: GeometryFacade['calculateDistanceInMeters'],
) {
    let point: PreparedSnapPoint | null = null;
    let distance = Infinity;
    let owner: string | null = null;
    for (const [pid, points] of snapPointsCache) {
        if (projectId && pid !== String(projectId)) continue;
        if (!isProjectEffectivelyVisible(pid) || !Array.isArray(points) || !points.length) continue;
        const nearest = findNearestGeographicCandidate(target, points, distanceInMeters);
        if (nearest.distance < distance) {
            point = nearest.candidate;
            distance = nearest.distance;
            owner = pid;
        }
        if (distance === 0) break;
    }
    return { point, distance, projectId: owner };
}

export const Geometry: GeometryFacade = {
    // Calculate distance in meters between two lat/lng points using Haversine formula
    calculateDistanceInMeters,

    // Publish endpoints prepared with the source, without another feature scan.
    cachePreparedSnapPoints(projectId, snapPoints) {
        if (snapPoints.length) snapPointsCache.set(String(projectId), snapPoints);
        else snapPointsCache.delete(String(projectId));
    },

    // Cache line features and extract start/end snap points from a project's GeoJSON source
    cacheLineFeatures: function(projectId, geojsonData) {
        if (!geojsonData || !geojsonData.features) return;

        const snapPoints: PreparedSnapPoint[] = [];
        let lineCount = 0;

        geojsonData.features.forEach((feature, index) => {
            if (feature.geometry && feature.geometry.type === 'LineString') {
                const coords = feature.geometry.coordinates;
                const lineName = feature.properties?.section_name || feature.properties?.name || `Line ${index}`;
                lineCount++;

                if (coords.length >= 2) {
                    const startCoord: [number, number] = [coords[0]![0]!, coords[0]![1]!];
                    snapPoints.push({
                        coordinates: startCoord,
                        lineName: lineName,
                        type: 'start',
                        lineIndex: 0
                    });

                    const endCoord: [number, number] = [coords[coords.length - 1]![0]!, coords[coords.length - 1]![1]!];
                    snapPoints.push({
                        coordinates: endCoord,
                        lineName: lineName,
                        type: 'end',
                        lineIndex: coords.length - 1
                    });
                }
            }
        });

        if (lineCount > 0) {
            snapPointsCache.set(String(projectId), snapPoints);
            console.log(`📐 Project ${projectId}: ${lineCount} lines, ${snapPoints.length} snap points (start/end only)`);
        }
    },

    // Find magnetic snap point - ONLY snaps to start/end vertices of lines
    findMagneticSnapPoint: function(coordinates, projectId = null) {
        const [lng, lat] = coordinates as readonly [number, number];
        const target: [number, number] = [lng, lat];
        const nearest = nearestVisibleSnapPoint(target, projectId,
            (a, b) => this.calculateDistanceInMeters(a, b));
        const bestDistance = nearest.distance;

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
            coordinates: nearest.point?.coordinates || target,
            lineName: nearest.point?.lineName ?? null,
            pointType: nearest.point?.type ?? null,
            distance: bestDistance,
            snapped: true,
            projectId: nearest.projectId
        };
    },

    // Find project for a feature based on layer ID
    findProjectForFeature: function(feature, map, allProjectLayers) {
        if (!feature.layer || !feature.layer.id) return null;

        // Check if it's a station layer - extract UUID from layer ID
        if (feature.layer.id.startsWith('stations-')) {
            const uuidMatch = feature.layer.id.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
            return uuidMatch ? uuidMatch[0] : null;
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
            map.getContainer().appendChild(this.snapIndicatorEl);
        }

        const point = map.project(coordinates);

        if (isSnapped) {
            this.snapIndicatorEl.style.cssText = `
                position: absolute;
                display: block;
                left: ${point.x}px;
                top: ${point.y}px;
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
                display: block;
                left: ${point.x}px;
                top: ${point.y}px;
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
        const [lng, lat] = coordinates as readonly [number, number];
        const target: [number, number] = [lng, lat];
        const nearest = nearestVisibleSnapPoint(target, null,
            (a, b) => this.calculateDistanceInMeters(a, b));
        const bestDistance = nearest.distance;

        if (!isFinite(bestDistance) || bestDistance > radiusMeters) {
            return { snapped: false, coordinates: target, distance: bestDistance };
        }

        return {
            snapped: true,
            coordinates: nearest.point?.coordinates ?? null,
            distance: bestDistance,
            lineName: nearest.point?.lineName ?? null,
            pointType: nearest.point?.type ?? null,
            projectId: nearest.projectId
        };
    },

    // Get snap info for debugging
    getSnapInfo: function() {
        const info: SnapInfo = {
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

    setSnapRadius: function(radiusInMeters) {
        const prev = MAGNETIC_SNAP_RADIUS;
        MAGNETIC_SNAP_RADIUS = Math.max(DEFAULTS.SNAP.MIN_RADIUS, Number(radiusInMeters) || DEFAULTS.SNAP.RADIUS_METERS);
        console.log(`🧲 Magnetic snap radius changed: ${prev}m → ${MAGNETIC_SNAP_RADIUS}m`);
        return MAGNETIC_SNAP_RADIUS;
    }
};
