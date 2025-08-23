"use strict";

import { getMap } from './mapCore.js';
import { state } from './state.js';
import { deepCopy } from './utils.js';

export function processGeoJSONForAltitudeZero(geojsonData) {
    if (!geojsonData || !geojsonData.features) return geojsonData;
    const processed = deepCopy(geojsonData);
    processed.features.forEach(f => {
        const g = f.geometry;
        if (!g) return;
        if (g.type === 'LineString') {
            g.coordinates = g.coordinates.map(([lng, lat]) => [lng, lat, 0]);
        } else if (g.type === 'MultiLineString') {
            g.coordinates = g.coordinates.map(line => line.map(([lng, lat]) => [lng, lat, 0]));
        } else if (g.type === 'Polygon') {
            g.coordinates = g.coordinates.map(ring => ring.map(([lng, lat]) => [lng, lat, 0]));
        } else if (g.type === 'MultiPolygon') {
            g.coordinates = g.coordinates.map(poly => poly.map(ring => ring.map(([lng, lat]) => [lng, lat, 0])));
        }
    });
    return processed;
}

export function toggleProjectVisibility(projectId, visible) {
    state.store.projectVisibility.set(projectId, visible);
    const map = getMap();
    if (!map) return;
    // Layers naming convention assumed; to be aligned when migrating layers
    const base = `project-geojson-${projectId}`;
    [
        `${base}-lines`,
        `${base}-lines-outline`,
        `${base}-points`,
    ].forEach(layerId => {
        if (map.getLayer(layerId)) {
            map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
        }
    });
}

// ---- Inert placeholders for upcoming color/depth helpers ----
export function computeLineColorPaint(projectColor) {
    // Placeholder: return a basic paint object; will be replaced with real logic
    return {
        'line-color': projectColor || '#38bdf8',
        'line-width': 2,
    };
}

export function parseDepthValue(raw) {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
}

export function getFeatureSectionName(props) {
    return props && (props.section_name || props.name || props.id) || '';
}

export function getFeatureDepthValue(props) {
    if (!props) return null;
    return parseDepthValue(props.depth || props.depth_value || props.elevation);
}

export function updateDepthLegendVisibility() {
    // Placeholder: implemented during UI migration
}

export function setColorMode(mode) {
    // Placeholder: will iterate over layers and update paint properties
    console.debug('[geojsonLayer] setColorMode ->', mode);
}


