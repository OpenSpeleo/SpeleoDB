"use strict";

// Wrapper helpers so HTML can call through a stable module surface
export function openPOIManager() {
    try { if (typeof window.openPOIManager === 'function') return window.openPOIManager(); } catch (_) { }
}

export function deletePOI(poiId, projectId) {
    try { if (typeof window.deletePOI === 'function') return window.deletePOI(poiId, projectId); } catch (_) { }
}

export function editPOI(poiId) {
    try { if (typeof window.editPOI === 'function') return window.editPOI(poiId); } catch (_) { }
}


