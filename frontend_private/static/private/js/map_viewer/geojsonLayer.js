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
