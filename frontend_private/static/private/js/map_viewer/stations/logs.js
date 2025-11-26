import { API } from '../api.js';
import { Utils } from '../utils.js';
import { Config } from '../config.js';
import { State } from '../state.js';

// Track current context for log operations
let currentStationId = null;
let currentProjectId = null;

export const StationLogs = {
    async render(stationId, container) {
        currentStationId = stationId;
        const station = State.allStations.get(stationId);
        currentProjectId = station?.project;
        
        const hasWriteAccess = Config.hasProjectWriteAccess(currentProjectId);
        const hasAdminAccess = Config.hasProjectAdminAccess ? Config.hasProjectAdminAccess(currentProjectId) : hasWriteAccess;

        // Show loading skeleton
        container.innerHTML = `
            <div class="tab-content active">
                <div class="space-y-4 p-6">
                    <div class="flex items-center justify-end">
                        ${hasWriteAccess ? `
                            <button id="new-log-entry-btn" class="btn-primary w-full sm:w-auto">
                                <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                                </svg>
                                New Journal Entry
                            </button>
                        ` : `
                            <button class="btn-primary w-full sm:w-auto opacity-50 cursor-not-allowed" title="You need write access" disabled>
                                <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                                </svg>
                                New Journal Entry
                            </button>
                        `}
                    </div>
                    <div class="journal-skeleton">
                        <div class="row"></div>
                        <div class="row"></div>
                        <div class="row"></div>
                    </div>
                </div>
            </div>
        `;

        // Wire up button immediately
        if (hasWriteAccess) {
            const btn = document.getElementById('new-log-entry-btn');
            if (btn) btn.onclick = () => this.openCreateModal(stationId);
        }

        try {
            const response = await API.getStationLogs(stationId);
            let logs = [];
            if (Array.isArray(response)) {
                logs = response;
            } else if (response.data && Array.isArray(response.data)) {
                logs = response.data;
            } else if (response.results && Array.isArray(response.results)) {
                logs = response.results;
            }

            console.log(`📝 Loaded ${logs.length} journal entries for station ${stationId}`);

            // Render the entries
            const entriesHtml = logs.length > 0 ? `
                <div class="journal-container">
                    <div class="journal-entries">
                        ${logs.map(log => this.renderEntry(log, hasWriteAccess, hasAdminAccess)).join('')}
                    </div>
                </div>
            ` : `
                <div class="text-center py-12">
                    <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                    </svg>
                    <h3 class="text-white text-lg font-medium mb-2">No Journal Entries Yet</h3>
                    <p class="text-slate-400">Record scientific observations, measurements, archeological finds, biological observations and notes for this station.</p>
                </div>
            `;

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="space-y-4 p-6">
                        <div class="flex items-center justify-end">
                            ${hasWriteAccess ? `
                                <button id="new-log-entry-btn" class="btn-primary w-full sm:w-auto">
                                    <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                                    </svg>
                                    New Journal Entry
                                </button>
                            ` : `
                                <button class="btn-primary w-full sm:w-auto opacity-50 cursor-not-allowed" title="You need write access" disabled>
                                    <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                                    </svg>
                                    New Journal Entry
                                </button>
                            `}
                        </div>
                        <div>
                            ${entriesHtml}
                        </div>
                    </div>
                </div>
            `;

            // Wire up event handlers
            if (hasWriteAccess) {
                const btn = document.getElementById('new-log-entry-btn');
                if (btn) btn.onclick = () => this.openCreateModal(stationId);
            }

            // Wire up edit/delete buttons
            this.wireUpEntryButtons(container);

        } catch (error) {
            console.error('Error loading logs:', error);
            container.innerHTML = `
                <div class="tab-content active p-6">
                    <div class="text-center py-12">
                        <p class="text-red-400">Failed to load journal entries.</p>
                        <button onclick="window.StationLogs.render('${stationId}', document.getElementById('station-modal-content'))" class="btn-secondary mt-4">Retry</button>
                    </div>
                </div>
            `;
        }
    },

    renderEntry(log, hasWriteAccess, hasAdminAccess) {
        const escapedNotes = (log.notes || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        return `
            <article class="journal-entry" data-log-id="${log.id}">
                <header class="journal-entry-header">
                    <h4 class="journal-entry-title">${log.title || 'Untitled Entry'}</h4>
                    <div class="journal-entry-meta">
                        <span>${Utils.formatJournalDate(log.creation_date)}</span>
                        <span class="journal-dot"></span>
                        <span>${log.created_by || 'Unknown'}</span>
                    </div>
                    <div class="flex items-center gap-2">
                        ${hasWriteAccess ? `
                            <button class="text-slate-300 hover:text-white edit-log-btn" title="Edit entry" 
                                    data-log-id="${log.id}"
                                    data-title="${(log.title || '').replace(/"/g, '&quot;')}"
                                    data-notes="${(log.notes || '').replace(/"/g, '&quot;')}">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                                </svg>
                            </button>
                        ` : `
                            <button class="text-slate-500 opacity-50 cursor-not-allowed" title="You need write access" disabled>
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                                </svg>
                            </button>
                        `}
                        ${hasAdminAccess ? `
                            <button class="text-red-400 hover:text-red-300 delete-log-btn" title="Delete entry"
                                    data-log-id="${log.id}"
                                    data-title="${(log.title || '').replace(/"/g, '&quot;')}">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                            </button>
                        ` : `
                            <button class="text-red-400 opacity-50 cursor-not-allowed" title="Only admins can delete" disabled>
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                            </button>
                        `}
                    </div>
                </header>
                <div class="journal-entry-body">${escapedNotes}</div>
                ${log.attachment ? `
                    <div class="journal-attachment">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"></path>
                        </svg>
                        <span class="uppercase tracking-wide text-xs font-semibold">ATTACHMENT</span>
                        <span class="text-sky-200">•</span>
                        <a href="${log.attachment}" target="_blank" class="underline decoration-sky-400 hover:text-white">${Utils.filenameFromUrl(log.attachment)}</a>
                    </div>
                ` : ''}
            </article>
        `;
    },

    wireUpEntryButtons(container) {
        // Wire up edit buttons
        container.querySelectorAll('.edit-log-btn').forEach(btn => {
            btn.onclick = () => {
                const logId = btn.dataset.logId;
                const title = btn.dataset.title;
                const notes = btn.dataset.notes;
                this.openEditModal(logId, { title, notes });
            };
        });

        // Wire up delete buttons
        container.querySelectorAll('.delete-log-btn').forEach(btn => {
            btn.onclick = () => {
                const logId = btn.dataset.logId;
                const title = btn.dataset.title;
                this.openDeleteConfirm(logId, title);
            };
        });
    },

    openCreateModal(stationId) {
        const html = `
            <div id="log-entry-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-start justify-center p-4 overflow-y-auto">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-2xl my-8 flex flex-col">
                    <div class="flex items-center justify-between p-6 border-b border-slate-600">
                        <h3 class="text-lg font-semibold text-white">New Journal Entry</h3>
                        <button id="close-log-modal" class="text-slate-400 hover:text-white transition-colors">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    <div class="flex-1 p-6">
                        <form id="log-entry-form" class="space-y-4">
                            <div>
                                <label class="block text-slate-300 text-sm font-medium mb-2">Title <span class="text-red-400">*</span></label>
                                <input id="log-title" type="text" class="form-input" placeholder="Concise scientific title..." required>
                            </div>
                            <div>
                                <label class="block text-slate-300 text-sm font-medium mb-2">Notes <span class="text-red-400">*</span></label>
                                <textarea id="log-notes" class="form-input form-textarea" rows="6" placeholder="Observations, measurements, methods, interpretation..." required></textarea>
                            </div>
                            <div>
                                <label class="block text-slate-300 text-sm font-medium mb-2">Attachment (optional)</label>
                                <div id="log-file-container" class="file-upload-area cursor-pointer">
                                    <div class="text-center" id="log-file-placeholder">
                                        <svg class="w-12 h-12 text-slate-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                                        </svg>
                                        <p class="text-slate-300 text-sm mb-2">Click to select file or drag and drop</p>
                                        <p class="text-slate-400 text-xs">Images, videos, documents accepted</p>
                                    </div>
                                    <input id="log-attachment" type="file" class="hidden" accept="image/*,video/*,.pdf,.csv,.txt,.doc,.docx">
                                </div>
                            </div>
                            <div class="flex items-center justify-end gap-3 pt-2">
                                <button type="button" id="cancel-log-btn" class="btn-secondary">Cancel</button>
                                <button id="log-submit-btn" type="submit" class="btn-primary">
                                    <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                                    </svg>
                                    Submit Entry
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', html);
        
        const modal = document.getElementById('log-entry-modal');
        const form = document.getElementById('log-entry-form');
        const fileContainer = document.getElementById('log-file-container');
        const fileInput = document.getElementById('log-attachment');

        // Close handlers
        document.getElementById('close-log-modal').onclick = () => modal.remove();
        document.getElementById('cancel-log-btn').onclick = () => modal.remove();
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

        // File upload handlers
        fileContainer.onclick = () => fileInput.click();
        fileInput.onchange = () => {
            if (fileInput.files.length > 0) {
                this.updateFileDisplay(fileContainer, fileInput.files[0]);
            }
        };

        // Drag and drop
        fileContainer.ondragover = (e) => { e.preventDefault(); fileContainer.classList.add('dragover'); };
        fileContainer.ondragleave = () => fileContainer.classList.remove('dragover');
        fileContainer.ondrop = (e) => {
            e.preventDefault();
            fileContainer.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                this.updateFileDisplay(fileContainer, e.dataTransfer.files[0]);
            }
        };

        // Form submission
        form.onsubmit = async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('log-submit-btn');
            const originalContent = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Submitting...';

            const formData = new FormData();
            formData.append('title', document.getElementById('log-title').value.trim());
            formData.append('notes', document.getElementById('log-notes').value.trim());
            
            if (fileInput.files.length > 0) {
                formData.append('attachment', fileInput.files[0]);
            }

            try {
                await API.createStationLog(stationId, formData);
                Utils.showNotification('success', 'Journal entry created successfully');
                modal.remove();
                
                // Refresh the logs tab
                this.render(stationId, document.getElementById('station-modal-content'));
            } catch (error) {
                console.error('Error creating log:', error);
                Utils.showNotification('error', error.message || 'Failed to create journal entry');
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalContent;
            }
        };

        // Focus title input
        document.getElementById('log-title').focus();
    },

    openEditModal(logId, logData) {
        const html = `
            <div id="log-edit-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-start justify-center p-4 overflow-y-auto">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-2xl my-8 flex flex-col">
                    <div class="flex items-center justify-between p-6 border-b border-slate-600">
                        <h3 class="text-lg font-semibold text-white">Edit Journal Entry</h3>
                        <button id="close-edit-modal" class="text-slate-400 hover:text-white transition-colors">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    <div class="flex-1 p-6">
                        <form id="log-edit-form" class="space-y-4">
                            <div>
                                <label class="block text-slate-300 text-sm font-medium mb-2">Title <span class="text-red-400">*</span></label>
                                <input id="edit-log-title" type="text" class="form-input" value="${logData.title.replace(/"/g, '&quot;')}" required>
                            </div>
                            <div>
                                <label class="block text-slate-300 text-sm font-medium mb-2">Notes <span class="text-red-400">*</span></label>
                                <textarea id="edit-log-notes" class="form-input form-textarea" rows="6" required>${logData.notes}</textarea>
                            </div>
                            <div class="flex items-center justify-end gap-3 pt-2">
                                <button type="button" id="cancel-edit-btn" class="btn-secondary">Cancel</button>
                                <button id="edit-submit-btn" type="submit" class="btn-primary">
                                    <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                                    </svg>
                                    Save Changes
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', html);
        
        const modal = document.getElementById('log-edit-modal');
        const form = document.getElementById('log-edit-form');

        // Close handlers
        document.getElementById('close-edit-modal').onclick = () => modal.remove();
        document.getElementById('cancel-edit-btn').onclick = () => modal.remove();
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

        // Form submission
        form.onsubmit = async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('edit-submit-btn');
            submitBtn.disabled = true;

            const formData = new FormData();
            formData.append('title', document.getElementById('edit-log-title').value.trim());
            formData.append('notes', document.getElementById('edit-log-notes').value.trim());

            try {
                await API.updateStationLog(logId, formData);
                Utils.showNotification('success', 'Journal entry updated');
                modal.remove();
                
                // Refresh the logs tab
                this.render(currentStationId, document.getElementById('station-modal-content'));
            } catch (error) {
                console.error('Error updating log:', error);
                Utils.showNotification('error', error.message || 'Failed to update journal entry');
                submitBtn.disabled = false;
            }
        };

        // Focus title input
        document.getElementById('edit-log-title').focus();
    },

    openDeleteConfirm(logId, title) {
        const html = `
            <div id="log-delete-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6">
                        <div class="flex items-center justify-center mb-4">
                            <div class="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                                <svg class="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                            </div>
                        </div>
                        <h3 class="text-lg font-semibold text-white text-center mb-2">Delete Journal Entry?</h3>
                        <p class="text-slate-300 text-center mb-2">Are you sure you want to delete this entry?</p>
                        <p class="text-white font-medium text-center mb-4">"${title}"</p>
                        <p class="text-red-300 text-sm text-center mb-6">This action cannot be undone.</p>
                        <div class="flex gap-3">
                            <button id="cancel-delete-btn" class="flex-1 btn-secondary">Cancel</button>
                            <button id="confirm-delete-btn" class="flex-1 btn-danger">Delete</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', html);
        
        const modal = document.getElementById('log-delete-modal');

        document.getElementById('cancel-delete-btn').onclick = () => modal.remove();
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

        document.getElementById('confirm-delete-btn').onclick = async () => {
            try {
                await API.deleteStationLog(logId);
                Utils.showNotification('success', 'Journal entry deleted');
                modal.remove();
                
                // Refresh the logs tab
                this.render(currentStationId, document.getElementById('station-modal-content'));
            } catch (error) {
                console.error('Error deleting log:', error);
                Utils.showNotification('error', error.message || 'Failed to delete journal entry');
            }
        };
    },

    updateFileDisplay(container, file) {
        const placeholder = container.querySelector('#log-file-placeholder');
        if (placeholder) {
            placeholder.innerHTML = `
                <svg class="w-8 h-8 text-emerald-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <p class="text-emerald-300 text-sm font-medium">${file.name}</p>
                <p class="text-slate-400 text-xs mt-1">${(file.size / 1024).toFixed(1)} KB</p>
            `;
        }
    }
};

// Expose for global access if needed
window.StationLogs = StationLogs;
