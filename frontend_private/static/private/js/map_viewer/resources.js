"use strict";
import { hasProjectAdminAccess } from './utils.js';
import { showNotification } from './ui.js';

// Placeholder module for station resources; real logic to be migrated
export function initResources() { /* no-op */ }

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

// File UI helpers & resource CRUD delegations
export function updateFileDisplay(fileContainer, file) {
    const textDiv = fileContainer.querySelector('.text-center');
    if (!textDiv) return;
    const resourceTypeSelect = document.querySelector('select[name="resource_type"]');
    const resourceType = resourceTypeSelect ? resourceTypeSelect.value : '';
    const maxVideoSize = 5 * 1024 * 1024;
    const maxPhotoSize = 10 * 1024 * 1024;
    let maxSize = 0, errorMessage = '';
    if (resourceType === 'video') { maxSize = maxVideoSize; errorMessage = 'Video files must be under 5MB'; }
    else if (resourceType === 'photo') { maxSize = maxPhotoSize; errorMessage = 'Photo files must be under 10MB'; }
    if (maxSize > 0 && file.size > maxSize) {
        const maxSizeMB = maxSize / (1024 * 1024);
        window.showNotification('error', `${resourceType.charAt(0).toUpperCase() + resourceType.slice(1)} file size cannot exceed ${maxSizeMB}MB. Your file is ${(file.size / (1024 * 1024)).toFixed(1)}MB`);
        const fileInput = textDiv.querySelector('input[type="file"]');
        if (fileInput) fileInput.value = '';
        fileContainer.classList.add('border-red-500');
        fileContainer.classList.remove('border-slate-600', 'border-green-500');
        textDiv.innerHTML = `
            <svg class="w-12 h-12 text-red-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <p class="text-red-400 font-medium text-sm mb-1">File Too Large!</p>
            <p class="text-slate-300 text-sm">${file.name}</p>
            <p class="text-red-400 text-xs">${errorMessage}</p>
            <p class="text-slate-400 text-xs mt-2">Current file: ${(file.size / (1024 * 1024)).toFixed(1)}MB</p>
            <input type="file" name="file" class="hidden" accept="image/*,video/*,.pdf,.doc,.docx,.mp4,.mov,.avi,.webm">
        `;
        const newFileInput = textDiv.querySelector('input[type="file"]');
        if (newFileInput) newFileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) updateFileDisplay(fileContainer, e.target.files[0]);
        });
        return;
    }
    const fileSize = file.size < 1024 * 1024 ? (file.size / 1024).toFixed(1) + ' KB' : (file.size / (1024 * 1024)).toFixed(1) + ' MB';
    const fileInput = textDiv.querySelector('input[type="file"]');
    if (!fileInput) return;
    Array.from(textDiv.children).forEach(child => { if (child !== fileInput) child.remove(); });
    const svg = document.createElement('svg'); svg.className = 'w-12 h-12 text-green-400 mx-auto mb-3'; svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor'); svg.setAttribute('viewBox', '0 0 24 24'); svg.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>';
    const statusP = document.createElement('p'); statusP.className = 'text-green-400 font-medium text-sm mb-1'; statusP.textContent = 'File Selected!';
    const nameP = document.createElement('p'); nameP.className = 'text-slate-300 text-sm'; nameP.textContent = file.name;
    const sizeP = document.createElement('p'); sizeP.className = 'text-slate-400 text-xs'; sizeP.textContent = `${fileSize} • ${file.type || 'Unknown type'}`;
    const changeP = document.createElement('p'); changeP.className = 'text-sky-400 text-xs mt-2 cursor-pointer hover:text-sky-300'; changeP.textContent = 'Click to change file'; changeP.onclick = () => fileContainer.click();
    textDiv.insertBefore(svg, fileInput); textDiv.insertBefore(statusP, fileInput); textDiv.insertBefore(nameP, fileInput); textDiv.insertBefore(sizeP, fileInput); textDiv.appendChild(changeP);
    fileContainer.classList.add('border-green-500'); fileContainer.classList.remove('border-slate-600', 'border-red-500');
}
export function resetFileDisplay(fileContainer) {
    const textDiv = fileContainer.querySelector('.text-center');
    if (!textDiv) return;
    textDiv.innerHTML = `
        <svg class="w-12 h-12 text-slate-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
        </svg>
        <p class="text-slate-300 text-sm mb-2">Click to select file or drag and drop</p>
        <p class="text-slate-400 text-xs">Max file size: 5MB • Images, videos, documents accepted</p>
        <input type="file" name="file" class="hidden" accept="image/*,video/*,.pdf,.doc,.docx,.mp4,.mov,.avi,.webm">
    `;
    fileContainer.classList.remove('border-green-500'); fileContainer.classList.add('border-slate-600');
    const fileInput = fileContainer.querySelector('input[type="file"]'); if (fileInput) fileInput.value = '';
}


export async function deleteResource(resourceId, stationId, projectId) {
    const station = allStations.get(stationId);
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
        detailsDiv.innerHTML = `
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Resource Type:</span>
                <span class="drag-confirm-value">${getResourceTypeLabel(resourceDetails.resource_type)}</span>
            </div>
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Title:</span>
                <span class="drag-confirm-value">${resourceDetails.title || 'Untitled'}</span>
            </div>
            ${resourceDetails.created_at ? `
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Created:</span>
                <span class="drag-confirm-value">${new Date(resourceDetails.created_at).toLocaleDateString()}</span>
            </div>
            ` : ''}
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

    if (!projectId || !hasProjectAdminAccess(projectId)) {
        showNotification('warning', 'Only admins can delete resources.');
        return;
    }

    const modal = document.getElementById('resource-delete-confirm-modal');
    if (modal) modal.style.display = 'none';

    const loadingOverlay = showStationLoadingOverlay('Deleting Resource', 'Removing resource from server...');
    try {
        const resp = await fetch(`/api/v1/resources/${resourceId}/`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.CSRF_TOKEN || getCSRFToken(),
                'X-CSRF-Token': window.CSRF_TOKEN || getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        });
        if (resp.ok) {
            showNotification('success', 'Resource deleted successfully');
            const station = allStations.get(stationId);
            if (station && station.resources) {
                station.resources = station.resources.filter(r => r.id !== resourceId);
                station.resource_count = station.resources.length;
            }
            if (activeTab === 'resources') {
                loadStationResources(stationId, projectId);
            } else {
                loadStationDetails(stationId, projectId);
            }
        } else {
            showNotification('error', 'Failed to delete resource. Please try again.');
        }
    } catch (error) {
        console.error('Error deleting resource:', error);
        showNotification('error', 'Error deleting resource. Please try again.');
    } finally {
        hideStationLoadingOverlay(loadingOverlay);
        // Clear hidden inputs
        try { if (idInput) idInput.value = ''; if (stInput) stInput.value = ''; if (prInput) prInput.value = ''; } catch (_) { }
    }
}


