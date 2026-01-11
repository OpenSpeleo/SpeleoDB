import { LandmarkManager } from './manager.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { Modal } from '../components/modal.js';

export const LandmarkUI = {
    openManagerModal() {
        const modal = document.getElementById('landmark-manager-modal');
        if (!modal) {
            console.error('❌ Landmark Manager modal element not found!');
            return;
        }

        // Show modal
        modal.classList.remove('hidden');

        // Load content
        this.loadLandmarkManagerContent();

        // Setup close handlers
        const closeBtn = document.getElementById('landmark-manager-close');
        if (closeBtn) {
            closeBtn.onclick = () => {
                modal.classList.add('hidden');
            };
        }

        // Close on backdrop click
        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        };
    },

    loadLandmarkManagerContent() {
        const content = document.getElementById('landmark-manager-content');
        if (!content) {
            console.error('❌ landmark-manager-content element not found!');
            return;
        }

        // Gather all Landmarks
        const landmarks = Array.from(State.allLandmarks.values());
        const totalLandmarks = landmarks.length;

        // Sort Landmarks by name
        landmarks.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        // Build HTML
        let html = `
            <div class="p-6 overflow-y-auto" style="max-height: calc(100vh - 200px);">
                <div class="mb-6">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-lg font-medium text-white">All Landmarks</h3>
                        <div class="flex items-center gap-4">
                            <span class="text-sm text-slate-400">${totalLandmarks} Landmark${totalLandmarks !== 1 ? 's' : ''} total</span>
                            <button id="create-landmark-manual-btn" class="btn-primary text-sm py-2 px-4 flex items-center gap-2">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                                </svg>
                                Create Landmark
                            </button>
                        </div>
                    </div>
                </div>
        `;

        if (totalLandmarks === 0) {
            html += `
                <div class="text-center py-12">
                    <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                    <h3 class="text-white text-lg font-medium mb-2">No Landmarks Yet</h3>
                    <p class="text-slate-400">Right-click on the map to create your first Landmark.</p>
                </div>
            `;
        } else {
            html += `<div class="space-y-2">`;

            landmarks.forEach(landmark => {
                html += `
                    <div class="bg-slate-700/50 rounded-lg p-3 hover:bg-slate-700 transition-colors group">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-3 flex-1 cursor-pointer landmark-item" data-landmark-id="${landmark.id}">
                                <div class="w-4 h-5 flex-shrink-0">
                                    <svg viewBox="0 0 24 32" fill="none">
                                        <path d="M12 14 L12 30" stroke="#6b7280" stroke-width="2.5" stroke-linecap="round"/>
                                        <circle cx="12" cy="8" r="6.5" fill="#ef4444" stroke="#ffffff" stroke-width="1.5"/>
                                        <circle cx="12" cy="8" r="4" fill="#dc2626" opacity="0.6"/>
                                    </svg>
                                </div>
                                <div>
                                    <h5 class="text-white font-medium">${landmark.name}</h5>
                                    <p class="text-xs text-slate-400">
                                        ${Number(landmark.latitude).toFixed(5)}, ${Number(landmark.longitude).toFixed(5)}
                                    </p>
                                </div>
                            </div>
                            <div class="flex items-center space-x-2">
                                <button class="p-1.5 text-slate-400 hover:text-sky-400 hover:bg-slate-600 rounded transition-all go-to-landmark-btn" 
                                        data-landmark-id="${landmark.id}"
                                        data-lat="${Number(landmark.latitude)}"
                                        data-lon="${Number(landmark.longitude)}"
                                        title="Go to Landmark on map">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                                    </svg>
                                </button>
                                <svg class="w-5 h-5 text-slate-400 group-hover:text-white transition-colors cursor-pointer open-landmark-btn"
                                    data-landmark-id="${landmark.id}"
                                    fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                                </svg>
                            </div>
                        </div>
                    </div>
                `;
            });

            html += `</div>`;
        }

        html += '</div>';
        content.innerHTML = html;

        // Attach event listeners
        content.querySelectorAll('.go-to-landmark-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const landmarkId = btn.dataset.landmarkId;
                const lat = parseFloat(btn.dataset.lat);
                const lon = parseFloat(btn.dataset.lon);
                if (window.goToLandmark) {
                    window.goToLandmark(landmarkId, lat, lon);
                }
            });
        });

        content.querySelectorAll('.landmark-item, .open-landmark-btn').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.closest('.go-to-landmark-btn')) return; // Skip if clicking go-to button
                const landmarkId = el.dataset.landmarkId;
                if (landmarkId) {
                    document.getElementById('landmark-manager-modal').classList.add('hidden');
                    this.openDetailsModal(landmarkId);
                }
            });
        });

        // Attach event listener to create button
        const createBtn = document.getElementById('create-landmark-manual-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => {
                document.getElementById('landmark-manager-modal').classList.add('hidden');
                this.openCreateModalManual();
            });
        }
    },

    openDetailsModal(landmarkId, isNewlyCreated = false) {
        const landmark = landmarkId ? State.allLandmarks.get(landmarkId) : null;
        if (!landmark && landmarkId) {
            Utils.showNotification('error', 'Landmark not found');
            return;
        }

        const title = landmark ? `Landmark: ${landmark.name}` : 'Landmark Details';
        const extraTitle = isNewlyCreated ? '<span class="ml-2 text-sm text-emerald-400">✨ Newly Created</span>' : '';

        const content = landmark ? `
            <div class="space-y-4">
                <div>
                    <h3 class="text-lg font-semibold text-white mb-2">${landmark.name}</h3>
                    ${landmark.description ? `<p class="text-slate-300">${landmark.description}</p>` : '<p class="text-slate-400 italic">No description</p>'}
                </div>
                <div class="bg-slate-700/50 rounded-lg p-4 space-y-2">
                    <p class="text-slate-300"><strong>Coordinates:</strong> ${Number(landmark.latitude).toFixed(7)}, ${Number(landmark.longitude).toFixed(7)}</p>
                    <p class="text-slate-300"><strong>Created:</strong> ${landmark.creation_date ? new Date(landmark.creation_date).toLocaleDateString() : 'Unknown'}</p>
                </div>
            </div>` :
            `<div class="text-center py-8"><h3 class="text-white text-lg font-medium mb-2">Landmark Not Found</h3></div>`;

        // Any authenticated user can manage their Landmarks
        const footer = landmark ? `
            <button id="edit-landmark-btn" class="btn-secondary" style="min-width: 120px;">Edit</button>
            <button id="delete-landmark-btn" class="btn-danger" style="min-width: 120px;">Delete</button>
        ` : '';

        const html = Modal.base('landmark-details-modal', title + extraTitle, content, footer);

        Modal.open('landmark-details-modal', html, () => {
            if (landmark) {
                document.getElementById('edit-landmark-btn').onclick = () => this.openEditModal(landmarkId);
                document.getElementById('delete-landmark-btn').onclick = () => this.showDeleteConfirmModal(landmark);
            }
        });
    },

    openCreateModal(coordinates) {
        const formHtml = `
            <form id="create-landmark-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                    <input type="text" id="landmark-name" required class="form-input" placeholder="Enter name">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                    <textarea id="landmark-description" rows="3" class="form-input form-textarea" placeholder="Optional description"></textarea>
                </div>
                <div class="bg-slate-700/50 rounded-lg p-3 text-sm text-slate-300">
                    Location: ${coordinates[1].toFixed(7)}, ${coordinates[0].toFixed(7)}
                </div>
            </form>`;

        const footer = `
            <button onclick="document.getElementById('landmark-details-modal')?.remove()" class="btn-secondary">Cancel</button>
            <button form="create-landmark-form" type="submit" class="btn-primary">Create</button>
        `;

        const html = Modal.base('create-landmark-modal', 'Create Landmark', formHtml, footer, 'max-w-md');

        Modal.open('create-landmark-modal', html, () => {
            document.getElementById('landmark-name').focus();
            document.getElementById('create-landmark-form').onsubmit = async (e) => {
                e.preventDefault();
                const name = document.getElementById('landmark-name').value.trim();
                if (!name) return;

                try {
                    const landmark = await LandmarkManager.createLandmark({
                        name,
                        description: document.getElementById('landmark-description').value.trim(),
                        latitude: coordinates[1],
                        longitude: coordinates[0]
                    });
                    Utils.showNotification('success', 'Landmark created!');
                    Modal.close('create-landmark-modal');
                    this.openDetailsModal(landmark.id, true);
                } catch (err) {
                    Utils.showNotification('error', err.message);
                }
            };
        });
    },

    openCreateModalManual() {
        const formHtml = `
            <form id="create-landmark-manual-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                    <input type="text" id="landmark-name-manual" required class="form-input" placeholder="Enter landmark name">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                    <textarea id="landmark-description-manual" rows="3" class="form-input form-textarea" placeholder="Optional description"></textarea>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Latitude * <span class="text-xs text-slate-500">(e.g., 38.8977)</span></label>
                        <input type="number" id="landmark-latitude-manual" required step="any" min="-90" max="90" class="form-input" placeholder="Latitude (-90 to 90)">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Longitude * <span class="text-xs text-slate-500">(e.g., -77.0365)</span></label>
                        <input type="number" id="landmark-longitude-manual" required step="any" min="-180" max="180" class="form-input" placeholder="Longitude (-180 to 180)">
                    </div>
                </div>
                <div id="landmark-coord-error" class="hidden text-red-400 text-sm p-2 bg-red-500/10 rounded-lg"></div>
            </form>`;

        const footer = `
            <button data-close-modal="create-landmark-manual-modal" class="btn-secondary">Cancel</button>
            <button form="create-landmark-manual-form" type="submit" class="btn-primary">Create Landmark</button>
        `;

        const html = Modal.base('create-landmark-manual-modal', 'Create Landmark', formHtml, footer, 'max-w-md');

        Modal.open('create-landmark-manual-modal', html, () => {
            document.getElementById('landmark-name-manual').focus();
            document.getElementById('create-landmark-manual-form').onsubmit = async (e) => {
                e.preventDefault();
                const name = document.getElementById('landmark-name-manual').value.trim();
                const description = document.getElementById('landmark-description-manual').value.trim();
                const latStr = document.getElementById('landmark-latitude-manual').value;
                const lonStr = document.getElementById('landmark-longitude-manual').value;
                const errorEl = document.getElementById('landmark-coord-error');

                // Validate name
                if (!name) {
                    errorEl.textContent = 'Please enter a landmark name.';
                    errorEl.classList.remove('hidden');
                    return;
                }

                // Validate coordinates
                const lat = parseFloat(latStr);
                const lon = parseFloat(lonStr);

                if (isNaN(lat) || lat < -90 || lat > 90) {
                    errorEl.textContent = 'Latitude must be a number between -90 and 90.';
                    errorEl.classList.remove('hidden');
                    return;
                }

                if (isNaN(lon) || lon < -180 || lon > 180) {
                    errorEl.textContent = 'Longitude must be a number between -180 and 180.';
                    errorEl.classList.remove('hidden');
                    return;
                }

                errorEl.classList.add('hidden');

                try {
                    const landmark = await LandmarkManager.createLandmark({
                        name,
                        description,
                        latitude: lat,
                        longitude: lon
                    });
                    Utils.showNotification('success', 'Landmark created!');
                    
                    // Close the modal first so user can see the map
                    Modal.close('create-landmark-manual-modal');
                    
                    // Fly to the newly created landmark
                    if (window.goToLandmark) {
                        window.goToLandmark(landmark.id, lat, lon);
                    }
                } catch (err) {
                    errorEl.textContent = err.message || 'Failed to create landmark.';
                    errorEl.classList.remove('hidden');
                }
            };
        });
    },

    openEditModal(landmarkId) {
        const landmark = State.allLandmarks.get(landmarkId);
        if (!landmark) return;

        // Escape HTML for textarea content
        const escapeHtml = (str) => {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        };

        const formHtml = `
            <form id="edit-landmark-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                    <input type="text" id="edit-landmark-name" required value="${escapeHtml(landmark.name)}" class="form-input">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                    <textarea id="edit-landmark-description" rows="3" class="form-input form-textarea">${escapeHtml(landmark.description)}</textarea>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Latitude <span class="text-xs text-slate-500">(-90 to 90)</span></label>
                        <input type="number" id="edit-landmark-latitude" step="any" min="-90" max="90" value="${Number(landmark.latitude).toFixed(7)}" class="form-input" placeholder="Latitude">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Longitude <span class="text-xs text-slate-500">(-180 to 180)</span></label>
                        <input type="number" id="edit-landmark-longitude" step="any" min="-180" max="180" value="${Number(landmark.longitude).toFixed(7)}" class="form-input" placeholder="Longitude">
                    </div>
                </div>
                <div id="edit-landmark-error" class="hidden text-red-400 text-sm p-2 bg-red-500/10 rounded-lg"></div>
            </form>`;

        const footer = `
            <button data-close-modal="edit-landmark-modal" class="btn-secondary">Cancel</button>
            <button form="edit-landmark-form" type="submit" class="btn-primary">Save</button>
        `;

        const html = Modal.base('edit-landmark-modal', 'Edit Landmark', formHtml, footer, 'max-w-md');

        Modal.open('edit-landmark-modal', html, () => {
            document.getElementById('edit-landmark-form').onsubmit = async (e) => {
                e.preventDefault();
                const errorEl = document.getElementById('edit-landmark-error');
                
                const name = document.getElementById('edit-landmark-name').value.trim();
                const description = document.getElementById('edit-landmark-description').value.trim();
                const latStr = document.getElementById('edit-landmark-latitude').value;
                const lonStr = document.getElementById('edit-landmark-longitude').value;

                // Validate name
                if (!name) {
                    errorEl.textContent = 'Please enter a landmark name.';
                    errorEl.classList.remove('hidden');
                    return;
                }

                // Validate coordinates
                const lat = parseFloat(latStr);
                const lon = parseFloat(lonStr);

                if (isNaN(lat) || lat < -90 || lat > 90) {
                    errorEl.textContent = 'Latitude must be a number between -90 and 90.';
                    errorEl.classList.remove('hidden');
                    return;
                }

                if (isNaN(lon) || lon < -180 || lon > 180) {
                    errorEl.textContent = 'Longitude must be a number between -180 and 180.';
                    errorEl.classList.remove('hidden');
                    return;
                }

                errorEl.classList.add('hidden');

                try {
                    await LandmarkManager.updateLandmark(landmarkId, {
                        name,
                        description,
                        latitude: lat,
                        longitude: lon
                    });
                    Utils.showNotification('success', 'Landmark updated');
                    
                    // Close modals first so user can see the map
                    Modal.close('edit-landmark-modal');
                    Modal.close('landmark-details-modal');
                    
                    // Fly to the landmark's (potentially new) location
                    if (window.goToLandmark) {
                        window.goToLandmark(landmarkId, lat, lon);
                    }
                } catch (err) {
                    errorEl.textContent = err.message || 'Failed to update landmark.';
                    errorEl.classList.remove('hidden');
                }
            };
        });
    },

    showDeleteConfirmModal(landmark) {
        const content = `
            <div class="mb-6">
                <p class="text-slate-300 mb-2">Are you sure you want to delete this Landmark?</p>
                <p class="text-white font-semibold text-lg">${landmark.name}</p>
            </div>
            <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
                <p class="text-red-200 text-sm"><strong>Warning:</strong> This action cannot be undone.</p>
            </div>`;

        const footer = `
            <button data-close-modal="delete-landmark-modal" class="btn-secondary">Cancel</button>
            <button id="confirm-delete-landmark" class="btn-danger">Delete</button>
        `;

        const html = Modal.base('delete-landmark-modal', 'Delete Landmark', content, footer, 'max-w-md');

        Modal.open('delete-landmark-modal', html, () => {
            document.getElementById('confirm-delete-landmark').onclick = async () => {
                try {
                    await LandmarkManager.deleteLandmark(landmark.id);
                    Utils.showNotification('success', 'Landmark deleted');
                    Modal.close('delete-landmark-modal');
                    Modal.close('landmark-details-modal');
                } catch (err) {
                    Utils.showNotification('error', 'Failed to delete Landmark');
                }
            };
        });
    }
};
