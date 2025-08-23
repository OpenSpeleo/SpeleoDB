"use strict";
// Wrapper helpers so HTML can call through a stable module surface
export function openStationManager() {
    try { if (typeof window.openStationManager === 'function') return window.openStationManager(); } catch (_) { }
}

export function returnToStationManager() {
    try { if (typeof window.returnToStationManager === 'function') return window.returnToStationManager(); } catch (_) { }
}

export function applySuggestion(...args) {
    try { if (typeof window.applySuggestion === 'function') return window.applySuggestion(...args); } catch (_) { }
}

export function deleteStation(stationId, projectId) {
    try { if (typeof window.deleteStation === 'function') return window.deleteStation(stationId, projectId); } catch (_) { }
}

export function editStation(stationId) {
    try { if (typeof window.editStation === 'function') return window.editStation(stationId); } catch (_) { }
}


