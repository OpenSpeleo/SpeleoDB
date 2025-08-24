"use strict";
import { showNotification } from './ui.js';

function getResourceTypeLabel(type) {
    const labels = {
        'photo': '📷 Photo',
        'video': '🎥 Video',
        'note': '📝 Note',
        'sketch': '✏️ Sketch',
        'document': '📄 Document'
    };
    return labels[type] || type;
}

// Sketch utilities (callable from HTML)
let sketchState = null;
export function initializeSketchCanvas() {
    const canvas = document.getElementById('sketch-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    sketchState = { canvas, ctx, drawing: false, ops: [], redo: [] };
}
export function startDrawing(e) {
    if (!sketchState) return;
    sketchState.drawing = true;
    sketchState.ctx.beginPath();
    const { x, y } = getCanvasPos(e, sketchState.canvas);
    sketchState.ctx.moveTo(x, y);
    sketchState.ops.push({ t: 'begin', x, y });
}
export function draw(e) {
    if (!sketchState || !sketchState.drawing) return;
    const { x, y } = getCanvasPos(e, sketchState.canvas);
    sketchState.ctx.lineTo(x, y);
    sketchState.ctx.strokeStyle = '#e2e8f0';
    sketchState.ctx.lineWidth = 2;
    sketchState.ctx.stroke();
    sketchState.ops.push({ t: 'line', x, y });
}
export function stopDrawing() { if (sketchState) sketchState.drawing = false; }
export function clearSketch() { if (sketchState) { sketchState.ctx.clearRect(0, 0, sketchState.canvas.width, sketchState.canvas.height); sketchState.ops = []; sketchState.redo = []; } }
export function undoSketch() { /* no-op placeholder for brevity */ }
export function redoSketch() { /* no-op placeholder for brevity */ }
export function updateUndoRedoButtons() { /* no-op placeholder */ }

// Edit sketch
let editSketchState = null;

export function initializeEditSketchCanvas(existingData) {
    const canvas = document.getElementById('edit-sketch-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    editSketchState = { canvas, ctx, drawing: false };
}
export function startEditDrawing(e) { if (!editSketchState) return; editSketchState.drawing = true; const { x, y } = getCanvasPos(e, editSketchState.canvas); editSketchState.ctx.beginPath(); editSketchState.ctx.moveTo(x, y); }
export function editDraw(e) { if (!editSketchState || !editSketchState.drawing) return; const { x, y } = getCanvasPos(e, editSketchState.canvas); editSketchState.ctx.lineTo(x, y); editSketchState.ctx.strokeStyle = '#e2e8f0'; editSketchState.ctx.lineWidth = 2; editSketchState.ctx.stroke(); }
export function stopEditDrawing() { if (editSketchState) editSketchState.drawing = false; }
export function clearEditSketch() { if (editSketchState) { editSketchState.ctx.clearRect(0, 0, editSketchState.canvas.width, editSketchState.canvas.height); } }
export function undoEditSketch() { /* placeholder */ }
export function redoEditSketch() { /* placeholder */ }
export function updateEditUndoRedoButtons() { /* placeholder */ }

function getCanvasPos(e, canvas) {
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX != null ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
    const clientY = e.clientY != null ? e.clientY : (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
    return { x: clientX - rect.left, y: clientY - rect.top };
}


function getStationsMap() {
    try { if (typeof window !== 'undefined' && window.allStations instanceof Map) return window.allStations; } catch (_) { }
    try { if (typeof allStations !== 'undefined' && allStations instanceof Map) return allStations; } catch (_) { }
    return new Map();
}

export async function deleteResource(resourceId, stationId, projectId) {
    const stationMap = getStationsMap();
    const station = stationMap.get(stationId);
    let resourceDetails = null;
    if (station && station.resources) {
        resourceDetails = station.resources.find(r => r.id === resourceId);
    }

    // Populate hidden inputs instead of using an in-memory object
    const idInput = document.getElementById('resource-delete-id');
    const stInput = document.getElementById('resource-delete-station-id');
    const prInput = document.getElementById('resource-delete-project-id');
    if (idInput) idInput.value = resourceId || '';
    if (stInput) stInput.value = stationId || '';
    if (prInput) prInput.value = projectId || '';

    const detailsDiv = document.getElementById('resource-delete-confirm-details');
    if (detailsDiv && resourceDetails) {
        const createdRaw = resourceDetails.creation_date || resourceDetails.created_at || resourceDetails.createdAt || resourceDetails.created;
        const createdHtml = createdRaw ? `
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Created:</span>
                <span class="drag-confirm-value">${new Date(createdRaw).toLocaleDateString()}</span>
            </div>
        ` : '';
        detailsDiv.innerHTML = `
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Resource Type:</span>
                <span class="drag-confirm-value">${getResourceTypeLabel(resourceDetails.resource_type)}</span>
            </div>
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Title:</span>
                <span class="drag-confirm-value">${resourceDetails.title || 'Untitled'}</span>
            </div>
            ${createdHtml}
        `;
    }

    const modal = document.getElementById('resource-delete-confirm-modal');
    if (modal) modal.style.display = 'flex';
}

export function cancelDeleteResource() {
    const modal = document.getElementById('resource-delete-confirm-modal');
    if (modal) modal.style.display = 'none';
}

export async function confirmDeleteResource() {
    // Read identifiers from hidden inputs (source of truth)
    const idInput = document.getElementById('resource-delete-id');
    const stInput = document.getElementById('resource-delete-station-id');
    const prInput = document.getElementById('resource-delete-project-id');
    const resourceId = idInput ? idInput.value : '';
    const stationId = stInput ? stInput.value : '';
    const projectId = prInput ? prInput.value : '';
    if (!resourceId || !stationId || !projectId) return;

    if (!projectId || !Utils.hasProjectAdminAccess(projectId)) {
        showNotification('warning', 'Only admins can delete resources.');
        return;
    }

    const modal = document.getElementById('resource-delete-confirm-modal');
    if (modal) modal.style.display = 'none';

    const loadingOverlay = Station.showLoadingOverlay('Deleting Resource', 'Removing resource from server...');

    try {
        const resp = await fetch(`/api/v1/resources/${resourceId}/`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': (typeof window !== 'undefined' && window.CSRF_TOKEN) || (typeof window !== 'undefined' && typeof window.getCSRFToken === 'function' ? window.getCSRFToken() : ''),
                'X-CSRF-Token': (typeof window !== 'undefined' && window.CSRF_TOKEN) || (typeof window !== 'undefined' && typeof window.getCSRFToken === 'function' ? window.getCSRFToken() : ''),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        });
        if (resp.ok) {
            showNotification('success', 'Resource deleted successfully');
            const sMap = getStationsMap();
            const st = sMap.get(stationId);
            if (st && st.resources) {
                st.resources = st.resources.filter(r => r.id !== resourceId);
                st.resource_count = st.resources.length;
                sMap.set(stationId, st);
            }
            const currentTab = (typeof window !== 'undefined' && window.activeTab) ? window.activeTab : 'resources';
            if (currentTab === 'resources') {
                if (typeof window !== 'undefined' && typeof window.loadStationResources === 'function') {
                    window.loadStationResources(stationId, projectId);
                }
            } else {
                if (typeof window !== 'undefined' && typeof window.loadStationDetails === 'function') {
                    window.loadStationDetails(stationId, projectId);
                }
            }
            // As a fallback, remove the card from DOM to reflect deletion instantly
            try {
                const grid = document.querySelector('.resource-grid');
                if (grid) {
                    const cards = Array.from(grid.querySelectorAll('.resource-card'));
                    const match = cards.find(c => c.innerHTML.includes(resourceId));
                    if (match) match.remove();
                }
            } catch (_) { }
        } else {
            showNotification('error', 'Failed to delete resource. Please try again.');
        }
    } catch (error) {
        console.error('Error deleting resource:', error);
        showNotification('error', 'Error deleting resource. Please try again.');
    } finally {
        Station.hideLoadingOverlay(loadingOverlay);

        // Clear hidden inputs
        try { if (idInput) idInput.value = ''; if (stInput) stInput.value = ''; if (prInput) prInput.value = ''; } catch (_) { }
    }
}


