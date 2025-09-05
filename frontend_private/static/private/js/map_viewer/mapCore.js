"use strict";

import { setMap, emit, getMap as getMapFromState } from './state.js';

export function createMap(containerId, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`[mapCore] container not found: ${containerId}`);
        return null;
    }
    if (!window.mapboxgl) {
        console.warn('[mapCore] mapboxgl not loaded');
        return null;
    }
    const map = new mapboxgl.Map({ container: containerId, ...options });
    setMap(map);
    map.on('load', () => emit('map-ready', { map }));
    return map;
}

export const getMap = () => getMapFromState();


