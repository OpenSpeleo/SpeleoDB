"use strict";

import { setMap, getMap, emit } from './state.js';
import * as ui from './ui.js';
import { getCSRFToken as apiGetCSRFToken, apiFetch } from './api.js';
// Ensure modules are loaded
// Avoid importing entire modules just to expose everything globally
// We'll keep globals lean and only expose what HTML calls directly
// Import resources helpers explicitly
import {
    initializeSketchCanvas,
    startDrawing,
    draw,
    stopDrawing,
    clearSketch,
    undoSketch,
    redoSketch,
    updateUndoRedoButtons,
    initializeEditSketchCanvas,
    startEditDrawing,
    editDraw,
    stopEditDrawing,
    clearEditSketch,
    undoEditSketch,
    redoEditSketch,
    updateEditUndoRedoButtons,
    deleteResource,
    confirmDeleteResource,
    cancelDeleteResource,
} from './resources.js';

// Minimal bootstrap for modular refactor; inert until features are migrated
console.debug('[map_viewer] module index loaded');

// Reduce global leakage: expose only the UI functions needed
window.__mv = window.__mv || {};
window.__mv.ui = ui;

// Explicit aliases only if present in UI module
if (ui.applySuggestion && !window.applySuggestion) window.applySuggestion = ui.applySuggestion;
if (ui.returnToStationManager && !window.returnToStationManager) window.returnToStationManager = ui.returnToStationManager;

// Expose UI functions globally for HTML inline handlers
window.showNotification = ui.showNotification;
window.openPhotoLightbox = ui.openPhotoLightbox;
window.closePhotoLightbox = ui.closePhotoLightbox;
window.downloadPhoto = ui.downloadPhoto;
window.openPhotoInNewTab = ui.openPhotoInNewTab;
window.openVideoModal = ui.openVideoModal;
window.uiCloseVideoModal = ui.closeVideoModal;
window.openNoteViewer = ui.openNoteViewer;
window.formatNoteContent = ui.formatNoteContent;
window.closeNoteViewer = ui.closeNoteViewer;
window.copyNoteToClipboard = ui.copyNoteToClipboard;

// Expose API helpers for HTML inline code to consume centralized CSRF handling
if (!window.getCSRFToken) window.getCSRFToken = apiGetCSRFToken;
if (!window.apiFetch) window.apiFetch = apiFetch;

// Expose sketch/resource functions directly
window.initializeSketchCanvas = initializeSketchCanvas;
window.startDrawing = startDrawing;
window.draw = draw;
window.stopDrawing = stopDrawing;
window.clearSketch = clearSketch;
window.undoSketch = undoSketch;
window.redoSketch = redoSketch;
window.updateUndoRedoButtons = updateUndoRedoButtons;
window.initializeEditSketchCanvas = initializeEditSketchCanvas;
window.startEditDrawing = startEditDrawing;
window.editDraw = editDraw;
window.stopEditDrawing = stopEditDrawing;
window.clearEditSketch = clearEditSketch;
window.undoEditSketch = undoEditSketch;
window.redoEditSketch = redoEditSketch;
window.updateEditUndoRedoButtons = updateEditUndoRedoButtons;
window.deleteResource = deleteResource;
window.confirmDeleteResource = confirmDeleteResource;
window.cancelDeleteResource = cancelDeleteResource;

// Global readiness gate
function domReady() {
    if (document.readyState !== 'loading') return Promise.resolve();
    return new Promise(res => document.addEventListener('DOMContentLoaded', res, { once: true }));
}

function waitFor(conditionFn, { interval = 50, timeout = 5000 } = {}) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        const t = setInterval(() => {
            try {
                if (conditionFn()) { clearInterval(t); return resolve(); }
                if (Date.now() - start > timeout) { clearInterval(t); return reject(new Error('waitFor timeout')); }
            } catch (e) { clearInterval(t); reject(e); }
        }, interval);
    });
}

async function isReady({ requireMapStyle = false, timeout = 8000 } = {}) {
    await domReady();
    // Ensure module globals are bound
    await waitFor(() => (
        typeof window.openPhotoLightbox === 'function' &&
        typeof window.openVideoModal === 'function' &&
        typeof window.openNoteViewer === 'function'
    ), { timeout });
    // Ensure legacy map exists
    await waitFor(() => !!(window.map && typeof window.map.on === 'function'), { timeout });
    if (requireMapStyle) {
        const m = window.map;
        if (m && typeof m.isStyleLoaded === 'function') {
            if (!m.isStyleLoaded()) await new Promise(res => m.once ? m.once('load', res) : m.on('load', res));
        }
    }
    window.__mv = window.__mv || {}; window.__mv.ready = true;
}

// Expose globally so inline HTML can gate its logic
try { window.isReady = isReady; } catch (_) { }

// Removed late dynamic rebind of sketch functions to minimize globals

function adoptExistingMapIfAny() {
    if (getMap()) return true;
    if (window.map && typeof window.map === 'object' && typeof window.map.on === 'function') {
        setMap(window.map);
        console.debug('[map_viewer] adopted legacy map instance');
        emit('map-ready', { map: window.map, source: 'legacy' });
        return true;
    }
    return false;
}

// Try to adopt the legacy-created map without creating a new one
document.addEventListener('DOMContentLoaded', () => {
    if (adoptExistingMapIfAny()) {
        try { ui.bindMapContextMenu(getMap()); } catch (_) { }
        return;
    }
    const startedAt = Date.now();
    const timer = setInterval(() => {
        if (adoptExistingMapIfAny()) { clearInterval(timer); try { ui.bindMapContextMenu(getMap()); } catch (_) { } return; }
        if (Date.now() - startedAt > 30000) {
            clearInterval(timer);
            console.debug('[map_viewer] legacy map not found within 4s; modules will create map later in cut-over');
        }
    }, 100);

    // Rebind notifications to module implementation (post-load) for consistency
    try {
        window.showNotification = ui.showNotification;
        // If map is already present, bind context menu via module
        const map = getMap();
        if (map) ui.bindMapContextMenu(map);
    } catch (e) {
        console.debug('[map_viewer] could not rebind showNotification', e);
    }
});
