"use strict";

import { setMap, getMap, emit } from './state.js';
import * as ui from './ui.js';
import { hasProjectWriteAccess, hasProjectAdminAccess } from './utils.js';
// Ensure modules are loaded
import * as API from './api.js';
import * as GEO from './geojsonLayer.js';
import * as STATIONS from './stations.js';
import * as POIS from './pois.js';
import * as STATE from './state.js';
import * as UTILS from './utils.js';
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
    updateFileDisplay,
    resetFileDisplay,
    deleteResource,
    confirmDeleteResource,
    cancelDeleteResource,
} from './resources.js';

// Minimal bootstrap for modular refactor; inert until features are migrated
console.debug('[map_viewer] module index loaded');

// Expose a tiny namespaced helper for debugging during migration
window.__mv = window.__mv || {};
window.__mv.ui = ui;

// Generic exposure of all exported functions from modules
function exposeAllFunctions(mod) {
    try {
        Object.keys(mod || {}).forEach((key) => {
            const val = mod[key];
            if (typeof val === 'function') {
                try { window[key] = val; } catch (_) { }
            }
        });
    } catch (_) { }
}

exposeAllFunctions(API);
exposeAllFunctions(GEO);
exposeAllFunctions(STATIONS);
exposeAllFunctions(POIS);
exposeAllFunctions(STATE);
exposeAllFunctions(UTILS);
exposeAllFunctions(ui);

// Explicit aliases for HTML references that may not match export names
window.applySuggestion = ui.applySuggestion || STATIONS.applySuggestion || POIS.applySuggestion;
window.returnToStationManager = ui.returnToStationManager || STATIONS.returnToStationManager;

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
window.updateFileDisplay = updateFileDisplay;
window.resetFileDisplay = resetFileDisplay;
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

// Expose sketch functions globally for HTML inline handlers
try {
    const r = await (async () => ui)();
    const res = await import('./resources.js');
    window.initializeSketchCanvas = res.initializeSketchCanvas;
    window.startDrawing = res.startDrawing;
    window.draw = res.draw;
    window.stopDrawing = res.stopDrawing;
    window.clearSketch = res.clearSketch;
    window.undoSketch = res.undoSketch;
    window.redoSketch = res.redoSketch;
    window.updateUndoRedoButtons = res.updateUndoRedoButtons;
    window.initializeEditSketchCanvas = res.initializeEditSketchCanvas;
    window.startEditDrawing = res.startEditDrawing;
    window.editDraw = res.editDraw;
    window.stopEditDrawing = res.stopEditDrawing;
    window.clearEditSketch = res.clearEditSketch;
    window.undoEditSketch = res.undoEditSketch;
    window.redoEditSketch = res.redoEditSketch;
    window.updateEditUndoRedoButtons = res.updateEditUndoRedoButtons;
} catch (_) { }

// Bind commonly used helpers early so inline code can use them
try {
    window.hasProjectWriteAccess = hasProjectWriteAccess;
    window.hasProjectAdminAccess = hasProjectAdminAccess;
} catch (e) {
    console.debug('[map_viewer] could not bind project access helpers', e);
}

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
