import { LandmarkManager } from './manager.js';
import { State } from '../state.js';
import { Config } from '../config.js';
import { Utils } from '../utils.js';
import { Modal } from '../components/modal.js';

export const LandmarkUI = {
    openManagerModal() {
        const modal = document.getElementById('poi-manager-modal');
        if (!modal) {
            console.error('❌ Landmark Manager modal element not found!');
            return;
        }

        // Show modal
        modal.classList.remove('hidden');

        // Load content
        this.loadLandmarkManagerContent();

        // Setup close handlers
        const closeBtn = document.getElementById('poi-manager-close');
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
        const content = document.getElementById('poi-manager-content');
        if (!content) {
            console.error('❌ poi-manager-content element not found!');
            return;
        }

        // Gather all Landmarks
        const pois = Array.from(State.allLandmarks.values());
        const totalPOIs = pois.length;

        // Sort Landmarks by name
        pois.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        // Build HTML
        let html = `
            <div class="p-6 overflow-y-auto" style="max-height: calc(100vh - 200px);">
                <div class="mb-6">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-lg font-medium text-white">All Points of Interest</h3>
                        <span class="text-sm text-slate-400">${totalPOIs} Point${totalPOIs !== 1 ? 's' : ''} of Interest total</span>
                    </div>
                </div>
        `;

        if (totalPOIs === 0) {
            html += `
                <div class="text-center py-12">
                    <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                    <h3 class="text-white text-lg font-medium mb-2">No Points of Interest Yet</h3>
                    <p class="text-slate-400">Right-click on the map to create your first Landmark.</p>
                </div>
            `;
        } else {
            html += `<div class="space-y-2">`;

            pois.forEach(poi => {
                html += `
                    <div class="bg-slate-700/50 rounded-lg p-3 hover:bg-slate-700 transition-colors group">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-3 flex-1 cursor-pointer poi-item" data-poi-id="${poi.id}">
                                <div class="w-4 h-5 flex-shrink-0">
                                    <svg viewBox="0 0 24 32" fill="none">
                                        <path d="M12 14 L12 30" stroke="#6b7280" stroke-width="2.5" stroke-linecap="round"/>
                                        <circle cx="12" cy="8" r="6.5" fill="#ef4444" stroke="#ffffff" stroke-width="1.5"/>
                                        <circle cx="12" cy="8" r="4" fill="#dc2626" opacity="0.6"/>
                                    </svg>
                                </div>
                                <div>
                                    <h5 class="text-white font-medium">${poi.name}</h5>
                                    <p class="text-xs text-slate-400">
                                        ${Number(poi.latitude).toFixed(5)}, ${Number(poi.longitude).toFixed(5)}
                                    </p>
                                </div>
                            </div>
                            <div class="flex items-center space-x-2">
                                <button class="p-1.5 text-slate-400 hover:text-sky-400 hover:bg-slate-600 rounded transition-all go-to-poi-btn" 
                                        data-poi-id="${poi.id}"
                                        data-lat="${Number(poi.latitude)}"
                                        data-lon="${Number(poi.longitude)}"
                                        title="Go to Landmark on map">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                                    </svg>
                                </button>
                                <svg class="w-5 h-5 text-slate-400 group-hover:text-white transition-colors cursor-pointer open-poi-btn"
                                    data-poi-id="${poi.id}"
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
        content.querySelectorAll('.go-to-poi-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const poiId = btn.dataset.poiId;
                const lat = parseFloat(btn.dataset.lat);
                const lon = parseFloat(btn.dataset.lon);
                if (window.goToLandmark) {
                    window.goToLandmark(poiId, lat, lon);
                }
            });
        });

        content.querySelectorAll('.poi-item, .open-poi-btn').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.closest('.go-to-poi-btn')) return; // Skip if clicking go-to button
                const poiId = el.dataset.poiId;
                if (poiId) {
                    document.getElementById('poi-manager-modal').classList.add('hidden');
                    this.openDetailsModal(poiId);
                }
            });
        });
    },

    openDetailsModal(poiId, isNewlyCreated = false) {
        const poi = poiId ? State.allLandmarks.get(poiId) : null;
        if (!poi && poiId) {
            Utils.showNotification('error', 'Landmark not found');
            return;
        }

        const title = poi ? `Landmark: ${poi.name}` : 'Landmark Details';
        const extraTitle = isNewlyCreated ? '<span class="ml-2 text-sm text-emerald-400">✨ Newly Created</span>' : '';

        const content = poi ? `
            <div class="space-y-4">
                <div>
                    <h3 class="text-lg font-semibold text-white mb-2">${poi.name}</h3>
                    ${poi.description ? `<p class="text-slate-300">${poi.description}</p>` : '<p class="text-slate-400 italic">No description</p>'}
                </div>
                <div class="bg-slate-700/50 rounded-lg p-4 space-y-2">
                    <p class="text-slate-300"><strong>Coordinates:</strong> ${Number(poi.latitude).toFixed(7)}, ${Number(poi.longitude).toFixed(7)}</p>
                    <p class="text-slate-300"><strong>Created by:</strong> ${poi.created_by || 'Unknown'}</p>
                    <p class="text-slate-300"><strong>Created:</strong> ${poi.creation_date ? new Date(poi.creation_date).toLocaleDateString() : 'Unknown'}</p>
                </div>
            </div>` :
            `<div class="text-center py-8"><h3 class="text-white text-lg font-medium mb-2">Landmark Not Found</h3></div>`;

        // Any authenticated user can manage their Landmarks
        const footer = poi ? `
            <button id="edit-poi-btn" class="btn-secondary" style="min-width: 120px;">Edit</button>
            <button id="delete-poi-btn" class="btn-danger" style="min-width: 120px;">Delete</button>
        ` : '';

        const html = Modal.base('poi-details-modal', title + extraTitle, content, footer);

        Modal.open('poi-details-modal', html, () => {
            if (poi) {
                document.getElementById('edit-poi-btn').onclick = () => this.openEditModal(poiId);
                document.getElementById('delete-poi-btn').onclick = () => this.showDeleteConfirmModal(poi);
            }
        });
    },

    openCreateModal(coordinates) {
        const formHtml = `
            <form id="create-poi-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                    <input type="text" id="poi-name" required class="form-input" placeholder="Enter name">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                    <textarea id="poi-description" rows="3" class="form-input form-textarea" placeholder="Optional description"></textarea>
                </div>
                <div class="bg-slate-700/50 rounded-lg p-3 text-sm text-slate-300">
                    Location: ${coordinates[1].toFixed(7)}, ${coordinates[0].toFixed(7)}
                </div>
            </form>`;

        const footer = `
            <button onclick="document.getElementById('poi-details-modal')?.remove()" class="btn-secondary">Cancel</button>
            <button form="create-poi-form" type="submit" class="btn-primary">Create</button>
        `;

        const html = Modal.base('create-poi-modal', 'Create Landmark', formHtml, footer, 'max-w-md');

        Modal.open('create-poi-modal', html, () => {
            document.getElementById('poi-name').focus();
            document.getElementById('create-poi-form').onsubmit = async (e) => {
                e.preventDefault();
                const name = document.getElementById('poi-name').value.trim();
                if (!name) return;

                try {
                    const poi = await LandmarkManager.createLandmark({
                        name,
                        description: document.getElementById('poi-description').value.trim(),
                        latitude: coordinates[1],
                        longitude: coordinates[0]
                    });
                    Utils.showNotification('success', 'POI created!');
                    Modal.close('create-poi-modal');
                    this.openDetailsModal(poi.id, true);
                } catch (err) {
                    Utils.showNotification('error', err.message);
                }
            };
        });
    },

    openEditModal(poiId) {
        const poi = State.allLandmarks.get(poiId);
        if (!poi) return;

        const formHtml = `
            <form id="edit-poi-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                    <input type="text" id="edit-poi-name" required value="${poi.name}" class="form-input">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                    <textarea id="edit-poi-description" rows="3" class="form-input form-textarea">${poi.description || ''}</textarea>
                </div>
            </form>`;

        const footer = `
            <button data-close-modal="edit-poi-modal" class="btn-secondary">Cancel</button>
            <button form="edit-poi-form" type="submit" class="btn-primary">Save</button>
        `;

        const html = Modal.base('edit-poi-modal', 'Edit Landmark', formHtml, footer, 'max-w-md');

        Modal.open('edit-poi-modal', html, () => {
            document.getElementById('edit-poi-form').onsubmit = async (e) => {
                e.preventDefault();
                try {
                    await LandmarkManager.updateLandmark(poiId, {
                        name: document.getElementById('edit-poi-name').value.trim(),
                        description: document.getElementById('edit-poi-description').value.trim()
                    });
                    Utils.showNotification('success', 'POI updated');
                    Modal.close('edit-poi-modal');
                    Modal.close('poi-details-modal');
                    this.openDetailsModal(poiId);
                } catch (err) {
                    Utils.showNotification('error', err.message);
                }
            };
        });
    },

    showDeleteConfirmModal(poi) {
        const content = `
            <div class="mb-6">
                <p class="text-slate-300 mb-2">Are you sure you want to delete this Landmark?</p>
                <p class="text-white font-semibold text-lg">${poi.name}</p>
            </div>
            <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
                <p class="text-red-200 text-sm"><strong>Warning:</strong> This action cannot be undone.</p>
            </div>`;

        const footer = `
            <button data-close-modal="delete-poi-modal" class="btn-secondary">Cancel</button>
            <button id="confirm-delete-poi" class="btn-danger">Delete</button>
        `;

        const html = Modal.base('delete-poi-modal', 'Delete Landmark', content, footer, 'max-w-md');

        Modal.open('delete-poi-modal', html, () => {
            document.getElementById('confirm-delete-poi').onclick = async () => {
                try {
                    await LandmarkManager.deleteLandmark(poi.id);
                    Utils.showNotification('success', 'POI deleted');
                    Modal.close('delete-poi-modal');
                    Modal.close('poi-details-modal');
                } catch (err) {
                    Utils.showNotification('error', 'Failed to delete Landmark');
                }
            };
        });
    }
};
