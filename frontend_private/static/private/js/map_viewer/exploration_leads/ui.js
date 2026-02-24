import { State } from '../state.js';
import { Utils } from '../utils.js';
import { Modal } from '../components/modal.js';
import { Layers } from '../map/layers.js';
import { ExplorationLeadManager } from './manager.js';
import { Config } from '../config.js';

export const ExplorationLeadUI = {
    /**
     * Show modal to create a new exploration lead
     * @param {Array} coordinates - [lng, lat] snapped coordinates
     * @param {string} lineName - Name of the survey line
     * @param {string} projectId - The project UUID for API call
     */
    showCreateModal(coordinates, lineName, projectId) {
        const formHtml = `
            <form id="create-lead-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description *</label>
                    <textarea id="lead-description" rows="4" required
                        class="form-input form-textarea"
                        placeholder="Describe the exploration lead..."></textarea>
                    <p class="text-xs text-slate-400 mt-2">
                        💡 <strong>Tip:</strong> Describe how the lead looks like - direction (N/S/E/W), 
                        up or down, big or small passage, sidemount or backmount access, water flow, etc.
                    </p>
                </div>
                <div class="bg-slate-700/50 rounded-lg p-3 text-sm text-slate-300">
                    <div class="flex items-center gap-2 mb-1">
                        <img src="${window.MAPVIEWER_CONTEXT.icons.explorationLead}" class="w-4 h-4">
                        <span>Location: ${lineName}</span>
                    </div>
                    <div class="text-xs text-slate-400 mt-1">
                        Lat: ${coordinates[1].toFixed(7)}, Lon: ${coordinates[0].toFixed(7)}
                    </div>
                </div>
            </form>
        `;

        const footer = `
            <button data-close-modal="create-lead-modal" class="btn-secondary">Cancel</button>
            <button form="create-lead-form" type="submit" class="btn-primary">
                <span id="create-lead-btn-text">Mark Lead</span>
                <span id="create-lead-btn-loading" class="hidden">
                    <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                </span>
            </button>
        `;

        const html = Modal.base('create-lead-modal', 'Mark Exploration Lead', formHtml, footer, 'max-w-md');

        Modal.open('create-lead-modal', html, () => {
            document.getElementById('lead-description').focus();

            document.getElementById('create-lead-form').onsubmit = async (e) => {
                e.preventDefault();
                const description = document.getElementById('lead-description').value.trim();
                if (!description) return;

                // Show loading state
                const btnText = document.getElementById('create-lead-btn-text');
                const btnLoading = document.getElementById('create-lead-btn-loading');
                btnText.classList.add('hidden');
                btnLoading.classList.remove('hidden');

                try {
                    // Create via API
                    const lead = await ExplorationLeadManager.createLead(projectId, coordinates, description);

                    // Update state with lineName
                    const stateData = State.explorationLeads.get(lead.id);
                    if (stateData) {
                        stateData.lineName = lineName;
                        State.explorationLeads.set(lead.id, stateData);
                    }

                    // Refresh the layer
                    Layers.refreshExplorationLeadsLayer();
                    Layers.reorderLayers();

                    Utils.showNotification('success', 'Exploration lead marked!');
                    Modal.close('create-lead-modal');
                } catch (error) {
                    console.error('Error creating exploration lead:', error);
                    Utils.showNotification('error', error.message || 'Failed to create exploration lead');

                    // Reset button
                    btnText.classList.remove('hidden');
                    btnLoading.classList.add('hidden');
                }
            };
        });
    },

    /**
     * Show details modal for an existing exploration lead
     * @param {string} leadId - The lead ID
     */
    showDetailsModal(leadId) {
        const lead = State.explorationLeads.get(leadId);
        if (!lead) {
            Utils.showNotification('error', 'Exploration lead not found');
            return;
        }

        const coords = lead.coordinates;
        const lat = coords[1].toFixed(7);
        const lng = coords[0].toFixed(7);
        const access = Config.getScopedAccess('project', lead.projectId);
        const hasWriteAccess = access.write;
        const hasAdminAccess = access.delete;

        const content = `
            <div class="space-y-4">
                <!-- Location info -->
                <div class="bg-slate-700/50 rounded-lg p-4">
                    <div class="flex items-center gap-2 mb-2">
                        <img src="${window.MAPVIEWER_CONTEXT.icons.explorationLead}" class="w-6 h-6">
                        <span class="text-white font-medium">Exploration Lead</span>
                    </div>
                    <div class="text-sm text-slate-300">
                        <div class="flex justify-between">
                            <span class="text-slate-400">Survey Line:</span>
                            <span>${lead.lineName || 'Unknown'}</span>
                        </div>
                        <div class="flex justify-between mt-1">
                            <span class="text-slate-400">Coordinates:</span>
                            <span class="font-mono text-xs">${lat}, ${lng}</span>
                        </div>
                        <div class="flex justify-between mt-1">
                            <span class="text-slate-400">Created:</span>
                            <span>${lead.createdAt ? new Date(lead.createdAt).toLocaleDateString() : 'Unknown'}</span>
                        </div>
                        ${lead.createdBy ? `
                        <div class="flex justify-between mt-1">
                            <span class="text-slate-400">Created by:</span>
                            <span class="text-xs">${lead.createdBy}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>

                <!-- Description (editable if has write access) -->
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                    <textarea id="lead-description-edit" rows="4"
                        class="form-input form-textarea"
                        placeholder="Describe the exploration lead..."
                        ${!hasWriteAccess ? 'disabled' : ''}>${lead.description || ''}</textarea>
                    <p class="text-xs text-slate-400 mt-2">
                        💡 Direction, size, access type (sidemount/backmount), water flow, etc.
                    </p>
                </div>
            </div>
        `;

        let footer = `
            <button data-close-modal="lead-details-modal" class="btn-secondary">Close</button>
        `;

        if (hasWriteAccess) {
            footer = `
                ${hasAdminAccess ? '<button id="delete-lead-btn" class="btn-danger mr-auto">🗑️ Delete</button>' : ''}
                <button data-close-modal="lead-details-modal" class="btn-secondary">Cancel</button>
                <button id="save-lead-btn" class="btn-primary">
                    <span id="save-lead-btn-text">Save Changes</span>
                    <span id="save-lead-btn-loading" class="hidden">
                        <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                    </span>
                </button>
            `;
        }

        const html = Modal.base('lead-details-modal', 'Exploration Lead Details', content, footer, 'max-w-md');

        Modal.open('lead-details-modal', html, () => {
            // Delete handler (admin only)
            const deleteBtn = document.getElementById('delete-lead-btn');
            if (deleteBtn) {
                deleteBtn.onclick = () => {
                    this.showDeleteConfirmModal(leadId, lead.lineName);
                };
            }

            // Save handler (write access)
            const saveBtn = document.getElementById('save-lead-btn');
            if (saveBtn) {
                saveBtn.onclick = async () => {
                    const newDescription = document.getElementById('lead-description-edit').value.trim();

                    // Show loading state
                    const btnText = document.getElementById('save-lead-btn-text');
                    const btnLoading = document.getElementById('save-lead-btn-loading');
                    btnText.classList.add('hidden');
                    btnLoading.classList.remove('hidden');

                    try {
                        // Update via API
                        await ExplorationLeadManager.updateLead(leadId, { description: newDescription });

                        Utils.showNotification('success', 'Exploration lead updated!');
                        Modal.close('lead-details-modal');
                    } catch (error) {
                        console.error('Error updating exploration lead:', error);
                        Utils.showNotification('error', error.message || 'Failed to update exploration lead');

                        // Reset button
                        btnText.classList.remove('hidden');
                        btnLoading.classList.add('hidden');
                    }
                };
            }
        });
    },

    /**
     * Show delete confirmation modal
     * @param {string} leadId - The lead ID
     * @param {string} lineName - The line name for display
     */
    showDeleteConfirmModal(leadId, lineName) {
        Modal.close('lead-details-modal');

        const content = `
            <div class="text-center">
                <div class="w-16 h-16 rounded-full bg-red-900/30 flex items-center justify-center mx-auto mb-4">
                    <svg class="w-10 h-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                </div>
                <h3 class="text-xl font-bold text-white mb-2">Delete Exploration Lead?</h3>
                <p class="text-slate-300 mb-2">Are you sure you want to delete this exploration lead on <strong>${lineName}</strong>?</p>
                <p class="text-red-300 text-sm">This action cannot be undone.</p>
            </div>
        `;

        const footer = `
            <button data-close-modal="delete-lead-modal" class="btn-secondary">Cancel</button>
            <button id="confirm-delete-lead-btn" class="btn-danger">
                <span id="delete-lead-btn-text">Delete Lead</span>
                <span id="delete-lead-btn-loading" class="hidden">
                    <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                </span>
            </button>
        `;

        const html = Modal.base('delete-lead-modal', 'Confirm Delete', content, footer, 'max-w-sm');

        Modal.open('delete-lead-modal', html, () => {
            document.getElementById('confirm-delete-lead-btn').onclick = async () => {
                // Show loading state
                const btnText = document.getElementById('delete-lead-btn-text');
                const btnLoading = document.getElementById('delete-lead-btn-loading');
                btnText.classList.add('hidden');
                btnLoading.classList.remove('hidden');

                try {
                    // Delete via API
                    await ExplorationLeadManager.deleteLead(leadId);

                    // Refresh the layer
                    Layers.refreshExplorationLeadsLayer();

                    Utils.showNotification('success', 'Exploration lead deleted');
                    Modal.close('delete-lead-modal');
                } catch (error) {
                    console.error('Error deleting exploration lead:', error);
                    Utils.showNotification('error', error.message || 'Failed to delete exploration lead');

                    // Reset button
                    btnText.classList.remove('hidden');
                    btnLoading.classList.add('hidden');
                }
            };
        });
    }
};
