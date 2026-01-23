import { API } from '../api.js';
import { Utils } from '../utils.js';
import { Config } from '../config.js';
import { State } from '../state.js';
import { createProgressBarHTML, UploadProgressController } from '../components/upload.js';

// Photo lightbox state
let currentPhotoUrl = null;
let currentPhotoTitle = null;

// Note viewer state
let currentNoteContent = null;

// Current station for refresh
let currentStationId = null;
let currentProjectId = null;

// Cache resources to avoid re-fetching
let cachedResources = [];

export const StationResources = {
    async render(stationId, container) {
        currentStationId = stationId;
        // Check both subsurface and surface stations
        const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        const isSurfaceStation = station?.network || station?.station_type === 'surface';
        currentProjectId = station?.project || station?.network;

        // Use appropriate permission check based on station type
        let hasWriteAccess, hasAdminAccess;
        if (isSurfaceStation) {
            hasWriteAccess = Config.hasNetworkWriteAccess(station?.network);
            hasAdminAccess = Config.hasNetworkAdminAccess(station?.network);
        } else {
            hasWriteAccess = Config.hasProjectWriteAccess(currentProjectId);
            hasAdminAccess = Config.hasProjectAdminAccess ? Config.hasProjectAdminAccess(currentProjectId) : hasWriteAccess;
        }

        // Show loading overlay
        const loadingOverlay = Utils.showLoadingOverlay('Loading station resources...');

        try {
            // Fetch resources from API
            const response = await API.getStationResources(stationId);
            let resources = [];

            if (response && response.success && response.data) {
                resources = response.data;
            } else if (Array.isArray(response)) {
                resources = response;
            }

            // Sort resources by modified date (newest first)
            resources.sort((a, b) => new Date(b.modified_date || b.creation_date) - new Date(a.modified_date || a.creation_date));

            // Cache resources for quick access in edit/delete operations
            cachedResources = resources;

            // Build HTML
            container.innerHTML = `
                <div class="tab-content active">
                    <div class="space-y-6 p-6">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xl font-semibold text-white">Resources for ${station?.name || 'Station'}</h3>
                            ${hasWriteAccess ? `
                                <button id="add-resource-btn" class="btn-primary text-sm">
                                    <svg class="w-4 h-4 fill-current opacity-80 shrink-0" viewBox="0 0 16 16">
                                        <path d="M15 7H9V1c0-.6-.4-1-1-1S7 .4 7 1v6H1c-.6 0-1 .4-1 1s.4 1 1 1h6v6c0 .6.4 1 1 1s1-.4 1-1V9h6c.6 0 1-.4 1-1s-.4-1-1-1z"></path>
                                    </svg>
                                    <span class="ml-2">Add Resource</span>
                                </button>
                            ` : ''}
                        </div>
                        
                        ${resources.length > 0 ? `
                            <div class="resource-grid">
                                ${resources.map(resource => this.renderResourceCard(resource, hasWriteAccess, hasAdminAccess)).join('')}
                            </div>
                        ` : `
                            <div class="text-center py-12">
                                ${window.currentStationIsNew ? `
                                    <div class="bg-blue-500/20 border border-blue-500/50 rounded-lg p-6 mb-6 max-w-md mx-auto">
                                        <span class="text-3xl mb-3 block">🎊</span>
                                        <h4 class="text-blue-200 font-semibold mb-2">Station Ready for Resources!</h4>
                                        <p class="text-blue-100 text-sm">Your station has been created. Now you can start adding resources to document this location.</p>
                                    </div>
                                ` : ''}
                                <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                                </svg>
                                <h3 class="text-white text-lg font-medium mb-2">No Resources Yet</h3>
                                <p class="text-slate-400 mb-4">Start documenting this station by adding photos, notes, or videos.</p>
                                ${hasWriteAccess ? `<p class="text-sky-400 text-sm">Click the "Add Resource" button above to add your first resource.</p>` : ''}
                            </div>
                        `}
                    </div>
                </div>
            `;

            // Hide loading overlay
            Utils.hideLoadingOverlay(loadingOverlay);

            // Wire up the add button
            if (hasWriteAccess) {
                const addBtn = document.getElementById('add-resource-btn');
                if (addBtn) {
                    addBtn.onclick = () => this.openAddForm(stationId);
                }
            }

            // Setup event delegation for resource actions
            this.setupEventDelegation(container, stationId, hasWriteAccess, hasAdminAccess);

        } catch (error) {
            console.error('Error loading resources:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            container.innerHTML = `
                <div class="tab-content active p-6 text-center">
                    <div class="text-red-400 mb-4">Error loading resources</div>
                    <button onclick="location.reload()" class="btn-secondary text-sm">Retry</button>
                </div>
            `;
        }
    },

    renderResourceCard(resource, hasWriteAccess, hasAdminAccess) {
        const isDemoStation = resource.is_demo || (resource.id && String(resource.id).startsWith('demo-'));

        return `
            <div class="resource-card p-5 bg-slate-800/20 border border-slate-600/50 rounded-lg hover:bg-slate-700/30 transition-colors">
                <div class="flex justify-between items-start mb-3">
                    <div>
                        <h4 class="text-white font-medium">${resource.title || 'Untitled'}
                            ${isDemoStation ? '<span class="demo-badge">DEMO</span>' : ''}
                        </h4>
                        <span class="px-2 py-1 bg-sky-500 text-white text-xs rounded mt-1 inline-block">${resource.resource_type}</span>
                    </div>
                    ${hasWriteAccess ? `
                        <div class="flex space-x-1">
                            <button class="edit-resource-btn text-slate-400 hover:text-white" data-resource-id="${resource.id}" title="Edit">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                                </svg>
                            </button>
                            <button class="delete-resource-btn text-red-400 ${hasAdminAccess ? 'hover:text-red-300' : 'opacity-50 cursor-not-allowed'}" 
                                    data-resource-id="${resource.id}" 
                                    title="${hasAdminAccess ? 'Delete' : 'Only admins can delete'}" 
                                    ${hasAdminAccess ? '' : 'disabled'}>
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                            </button>
                        </div>
                    ` : ''}
                </div>
                
                ${resource.description ? `<p class="text-slate-300 text-sm mb-3">${resource.description}</p>` : ''}
                
                ${this.getResourcePreview(resource)}
                
                <div class="flex justify-between items-center mt-3 text-xs text-slate-400">
                    <span>${new Date(resource.creation_date).toLocaleDateString()}</span>
                    <span>${resource.created_by || 'Unknown'}</span>
                </div>
            </div>
        `;
    },

    getResourcePreview(resource) {
        switch (resource.resource_type) {
            case 'photo':
                return resource.file ?
                    `<div class="resource-preview">
                        <img src="${resource.miniature || resource.file}" alt="${resource.title}" 
                             class="photo-preview cursor-zoom-in"
                             data-photo-url="${resource.file}"
                             data-photo-title="${resource.title}"
                             title="Click to view full size"
                             loading="lazy">
                    </div>` :
                    '<div class="text-slate-400 text-sm">No image available</div>';

            case 'video':
                return resource.file ?
                    resource.miniature ?
                        `<div class="resource-preview video-preview cursor-pointer" 
                              data-video-url="${resource.file}" 
                              data-video-title="${resource.title}">
                            <img src="${resource.miniature}" alt="${resource.title}" 
                                 title="Click to play video"
                                 loading="lazy">
                            <div class="play-overlay">
                                <svg class="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                          d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                          d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                            </div>
                        </div>` :
                        `<div class="resource-preview">
                            <video controls class="w-full">
                                <source src="${resource.file}" type="video/mp4">
                                Your browser does not support the video tag.
                            </video>
                        </div>` :
                    '<div class="text-slate-400 text-sm">No video available</div>';

            case 'note':
                return resource.text_content ?
                    `<div class="text-slate-300 text-sm bg-slate-900 p-3 rounded cursor-pointer hover:bg-slate-800 transition-colors note-preview" 
                         data-note-title="${resource.title}"
                         data-note-content="${Utils.escapeHtml(resource.text_content)}"
                         data-note-description="${resource.description || ''}"
                         data-note-author="${resource.created_by || 'Unknown'}"
                         data-note-date="${resource.creation_date}">
                        <div class="flex items-start gap-2">
                            <svg class="w-5 h-5 text-sky-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                            </svg>
                            <div class="line-clamp-3 overflow-hidden">${Utils.escapeHtml(resource.text_content.substring(0, 200))}${resource.text_content.length > 200 ? '...' : ''}</div>
                        </div>
                        <div class="text-xs text-sky-400 mt-2">Click to read full note</div>
                    </div>` :
                    '<div class="text-slate-400 text-sm">No content available</div>';

            case 'document':
                if (!resource.file) {
                    return '<div class="text-slate-400 text-sm">No document available</div>';
                }
                // Show miniature if available, otherwise show icon with link
                if (resource.miniature) {
                    return `
                        <div class="resource-preview">
                            <a href="${resource.file}" target="_blank" class="block relative group">
                                <img src="${resource.miniature}" alt="${resource.title}" 
                                     class="w-full h-40 object-contain bg-slate-900 rounded"
                                     loading="lazy">
                                <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                    <span class="text-white text-sm font-medium">Open Document</span>
                                </div>
                            </a>
                        </div>`;
                }
                return `
                    <div class="text-sm">
                        <a href="${resource.file}" target="_blank" class="text-sky-400 hover:text-sky-300 underline flex items-center gap-2">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                            </svg>
                            View Document
                        </a>
                    </div>`;

            default:
                return '<div class="text-slate-400 text-sm">Unknown resource type</div>';
        }
    },

    setupEventDelegation(container, stationId, hasWriteAccess, hasAdminAccess) {
        container.addEventListener('click', async (e) => {
            // Photo preview click
            const photoPreview = e.target.closest('.photo-preview');
            if (photoPreview) {
                e.preventDefault();
                const url = photoPreview.dataset.photoUrl;
                const title = photoPreview.dataset.photoTitle;
                if (url) this.openPhotoLightbox(url, title);
                return;
            }

            // Video preview click
            const videoPreview = e.target.closest('.video-preview');
            if (videoPreview) {
                e.preventDefault();
                const url = videoPreview.dataset.videoUrl;
                const title = videoPreview.dataset.videoTitle;
                if (url) this.openVideoModal(url, title);
                return;
            }

            // Note preview click
            const notePreview = e.target.closest('.note-preview');
            if (notePreview) {
                e.preventDefault();
                const noteData = {
                    title: notePreview.dataset.noteTitle,
                    content: notePreview.dataset.noteContent,
                    description: notePreview.dataset.noteDescription,
                    author: notePreview.dataset.noteAuthor,
                    date: notePreview.dataset.noteDate
                };
                this.openNoteViewer(noteData);
                return;
            }

            // Edit button click
            const editBtn = e.target.closest('.edit-resource-btn');
            if (editBtn && hasWriteAccess) {
                e.preventDefault();
                const resourceId = editBtn.dataset.resourceId;
                this.openEditForm(stationId, resourceId);
                return;
            }

            // Delete button click
            const deleteBtn = e.target.closest('.delete-resource-btn');
            if (deleteBtn && hasAdminAccess && !deleteBtn.disabled) {
                e.preventDefault();
                const resourceId = deleteBtn.dataset.resourceId;
                this.openDeleteConfirm(stationId, resourceId);
                return;
            }
        });
    },

    // ===== ADD RESOURCE FORM =====
    openAddForm(stationId, preselectedType = '') {
        const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        const container = document.getElementById('station-modal-content');

        container.innerHTML = `
            <div class="tab-content active">
                <div class="space-y-6 p-6">
                    <div class="flex justify-between items-center">
                        <h3 class="text-xl font-semibold text-white">Add Resource to ${station?.name || 'Station'}</h3>
                    </div>
                    
                    <div class="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                        <h4 class="text-blue-300 font-semibold mb-2">💡 Tips</h4>
                        <ul class="text-blue-200 text-sm space-y-1">
                            <li>• Photos and videos help document visual features</li>
                            <li>• Notes can capture detailed observations</li>
                            <li>• All resources are automatically associated with this station</li>
                        </ul>
                    </div>
                    
                    <div class="bg-slate-700/70 p-6 rounded-xl border border-slate-600/50">
                        <form id="resource-form" enctype="multipart/form-data" class="space-y-4">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-slate-300 text-sm font-medium mb-2">Resource Type <span class="text-red-400">*</span></label>
                                    <select name="resource_type" id="resource-type-select" class="form-input" required>
                                        <option value="">Select type...</option>
                                        <option value="photo" ${preselectedType === 'photo' ? 'selected' : ''}>📷 Photo</option>
                                        <option value="video" ${preselectedType === 'video' ? 'selected' : ''}>🎥 Video</option>
                                        <option value="note" ${preselectedType === 'note' ? 'selected' : ''}>📝 Note</option>
                                        <option value="document" ${preselectedType === 'document' ? 'selected' : ''}>📄 Document</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text-slate-300 text-sm font-medium mb-2">Title <span class="text-red-400">*</span></label>
                                    <input type="text" name="title" id="resource-title" class="form-input" placeholder="Descriptive title..." required>
                                </div>
                            </div>
                            
                            <div>
                                <label class="block text-slate-300 text-sm font-medium mb-2">Description (optional)</label>
                                <textarea name="description" id="resource-description" class="form-input form-textarea" rows="3" placeholder="Additional details about this resource..."></textarea>
                            </div>
                            
                            <div id="file-input-container" class="file-upload-area">
                                <div class="text-center">
                                    <svg class="w-12 h-12 text-slate-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                                    </svg>
                                    <p class="text-slate-300 text-sm mb-2">Click to select file or drag and drop</p>
                                    <input type="file" name="file" class="hidden" accept="image/*,video/*,.pdf,.doc,.docx,.mp4,.mov,.avi,.webm">
                                    <p class="text-slate-400 text-xs">Max file size: 500MB • Images, videos, documents accepted</p>
                                </div>
                            </div>
                            
                            <div id="text-input-container" class="hidden">
                                <label class="block text-slate-300 text-sm font-medium mb-2">Content <span class="text-red-400">*</span></label>
                                <textarea id="text-content" name="text_content" class="form-input form-textarea" rows="6" placeholder="Enter your notes..."></textarea>
                            </div>
                            
                            ${createProgressBarHTML('resource-upload')}
                            
                            <div id="resource-form-buttons" class="flex gap-3">
                                <button type="submit" id="resource-submit-btn" class="btn-primary">
                                    <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                                    </svg>
                                    Save Resource
                                </button>
                                <button type="button" id="cancel-resource-btn" class="btn-secondary">Cancel</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        this.setupAddFormHandlers(stationId, preselectedType);
    },

    setupAddFormHandlers(stationId, preselectedType) {
        const resourceTypeSelect = document.getElementById('resource-type-select');
        const fileContainer = document.getElementById('file-input-container');
        const textContainer = document.getElementById('text-input-container');
        const form = document.getElementById('resource-form');
        const cancelBtn = document.getElementById('cancel-resource-btn');

        // Handle resource type change
        resourceTypeSelect.addEventListener('change', (e) => {
            const type = e.target.value;

            if (['photo', 'video', 'document'].includes(type)) {
                fileContainer.classList.remove('hidden');
                textContainer.classList.add('hidden');
            } else if (type === 'note') {
                fileContainer.classList.add('hidden');
                textContainer.classList.remove('hidden');
            } else {
                fileContainer.classList.remove('hidden');
                textContainer.classList.add('hidden');
            }
        });

        // Trigger change for preselected type
        if (preselectedType) {
            resourceTypeSelect.dispatchEvent(new Event('change'));
        }

        // File upload handling
        const fileInput = fileContainer.querySelector('input[type="file"]');
        fileContainer.addEventListener('click', (e) => {
            if (e.target !== fileInput) fileInput.click();
        });
        fileContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileContainer.classList.add('border-sky-500', 'bg-sky-500/10');
        });
        fileContainer.addEventListener('dragleave', () => {
            fileContainer.classList.remove('border-sky-500', 'bg-sky-500/10');
        });
        fileContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            fileContainer.classList.remove('border-sky-500', 'bg-sky-500/10');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                this.updateFileDisplay(fileContainer, files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                this.updateFileDisplay(fileContainer, e.target.files[0]);
            }
        });

        // Cancel button
        cancelBtn.addEventListener('click', () => {
            this.render(stationId, document.getElementById('station-modal-content'));
        });

        // Form submission
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveResource(stationId, form);
        });
    },

    updateFileDisplay(fileContainer, file) {
        const maxSize = 500 * 1024 * 1024; // 500MB
        if (file.size > maxSize) {
            Utils.showNotification('error', 'File size cannot exceed 500MB');
            const fileInput = fileContainer.querySelector('input[type="file"]');
            if (fileInput) fileInput.value = '';
            return;
        }

        const fileSize = file.size < 1024 * 1024
            ? (file.size / 1024).toFixed(1) + ' KB'
            : (file.size / (1024 * 1024)).toFixed(1) + ' MB';

        fileContainer.classList.add('border-green-500');
        fileContainer.classList.remove('border-slate-600');

        // Keep the existing file input (which has the file) and just update the visual display
        const existingFileInput = fileContainer.querySelector('input[type="file"]');

        // Clear the container but preserve the file input
        const textDiv = fileContainer.querySelector('.text-center');
        if (textDiv) {
            // Remove the file input from textDiv temporarily
            if (existingFileInput && existingFileInput.parentNode === textDiv) {
                textDiv.removeChild(existingFileInput);
            }

            textDiv.innerHTML = `
                <svg class="w-12 h-12 text-green-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
                <p class="text-green-400 font-medium text-sm mb-1">File Selected</p>
                <p class="text-slate-300 text-sm truncate max-w-xs mx-auto">${file.name}</p>
                <p class="text-slate-400 text-xs">${fileSize}</p>
                <p class="text-sky-400 text-xs mt-2 cursor-pointer hover:underline" id="change-file-link">Click to change file</p>
            `;

            // Re-append the original file input (with the file still attached)
            if (existingFileInput) {
                textDiv.appendChild(existingFileInput);
            }

            // Add click handler for "change file" link
            const changeLink = textDiv.querySelector('#change-file-link');
            if (changeLink && existingFileInput) {
                changeLink.addEventListener('click', (e) => {
                    e.stopPropagation();
                    existingFileInput.click();
                });
            }
        }
    },

    async saveResource(stationId, form) {
        const submitBtn = document.getElementById('resource-submit-btn');
        const buttonsContainer = document.getElementById('resource-form-buttons');
        const originalContent = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = 'Saving...';

        const formData = new FormData(form);
        
        // Check if this is a file upload (photo, video, document) vs text-only (note)
        const resourceType = formData.get('resource_type');
        const hasFile = formData.get('file') && formData.get('file').size > 0;

        try {
            let response;
            
            // Use progress upload for file-based resources
            if (hasFile && ['photo', 'video', 'document'].includes(resourceType)) {
                const uploadController = new UploadProgressController('resource-upload');
                buttonsContainer.classList.add('hidden');
                
                response = await uploadController.upload(
                    Urls['api:v1:station-resources'](stationId),
                    formData,
                    'POST'
                );
            } else {
                response = await API.createStationResource(stationId, formData);
            }

            if (response && (response.success || response.data || response.id)) {
                Utils.showNotification('success', 'Resource saved successfully!');
                this.render(stationId, document.getElementById('station-modal-content'));
            } else {
                throw new Error('Failed to save resource');
            }
        } catch (error) {
            console.error('Error saving resource:', error);
            Utils.showNotification('error', error.message || 'Failed to save resource');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalContent;
            buttonsContainer.classList.remove('hidden');
        }
    },

    // ===== EDIT RESOURCE FORM =====
    openEditForm(stationId, resourceId) {
        const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        const container = document.getElementById('station-modal-content');

        // Use cached resources for instant access
        const resource = cachedResources.find(r => String(r.id) === String(resourceId));

        if (!resource) {
            Utils.showNotification('error', 'Resource not found');
            return;
        }

        container.innerHTML = `
            <div class="tab-content active">
                <div class="space-y-6 p-6">
                    <div class="flex items-center justify-between">
                        <h3 class="text-xl font-semibold text-white">Edit Resource</h3>
                    </div>
                    
                    <div class="bg-slate-700/70 p-6 rounded-xl border border-slate-600/50">
                        <form id="resource-edit-form" enctype="multipart/form-data" class="space-y-4">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-slate-300 text-sm font-medium mb-2">Resource Type</label>
                                    <select name="resource_type" class="form-input" disabled>
                                        <option value="${resource.resource_type}" selected>${this.getResourceTypeLabel(resource.resource_type)}</option>
                                    </select>
                                    <p class="text-xs text-slate-400 mt-1">Type cannot be changed</p>
                                </div>
                                <div>
                                    <label class="block text-slate-300 text-sm font-medium mb-2">Title</label>
                                    <input type="text" name="title" class="form-input" value="${resource.title || ''}" required>
                                </div>
                            </div>
                            
                            <div>
                                <label class="block text-slate-300 text-sm font-medium mb-2">Description (optional)</label>
                                <textarea name="description" class="form-input form-textarea" placeholder="Additional details...">${resource.description || ''}</textarea>
                            </div>
                            
                            ${['photo', 'video', 'document'].includes(resource.resource_type) ? `
                                <div id="edit-file-container" class="file-upload-area">
                                    <div class="text-center">
                                        <svg class="w-12 h-12 text-slate-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                                        </svg>
                                        <p class="text-slate-300 text-sm mb-2">Click to upload new file (optional)</p>
                                        <input type="file" name="file" class="hidden" accept="${this.getFileAccept(resource.resource_type)}">
                                        <p class="text-slate-400 text-xs">Leave empty to keep current file</p>
                                        ${resource.file ? `<p class="text-sky-400 text-xs mt-2">Current file: ${this.getFileName(resource.file)}</p>` : ''}
                                    </div>
                                </div>
                            ` : ''}
                            
                            ${resource.resource_type === 'note' ? `
                                <div>
                                    <label class="block text-slate-300 text-sm font-medium mb-2">Content</label>
                                    <textarea name="text_content" class="form-input form-textarea" rows="6" required>${resource.text_content || ''}</textarea>
                                </div>
                            ` : ''}
                            
                            ${createProgressBarHTML('resource-edit-upload')}
                            
                            <div id="edit-form-buttons" class="flex gap-3">
                                <button type="submit" id="edit-resource-submit-btn" class="btn-primary">💾 Save Changes</button>
                                <button type="button" id="cancel-edit-btn" class="btn-secondary">Cancel</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        this.setupEditFormHandlers(stationId, resourceId, resource);
    },

    setupEditFormHandlers(stationId, resourceId, resource) {
        const form = document.getElementById('resource-edit-form');
        const cancelBtn = document.getElementById('cancel-edit-btn');

        // File upload handling for edit form
        const fileContainer = document.getElementById('edit-file-container');
        if (fileContainer) {
            const fileInput = fileContainer.querySelector('input[type="file"]');
            fileContainer.addEventListener('click', (e) => {
                if (e.target !== fileInput) fileInput.click();
            });
            fileInput?.addEventListener('change', (e) => {
                if (e.target.files && e.target.files.length > 0) {
                    this.updateFileDisplay(fileContainer, e.target.files[0]);
                }
            });
        }

        // Cancel button
        cancelBtn.addEventListener('click', () => {
            this.render(stationId, document.getElementById('station-modal-content'));
        });

        // Form submission
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.updateResource(stationId, resourceId, form);
        });
    },

    async updateResource(stationId, resourceId, form) {
        const submitBtn = document.getElementById('edit-resource-submit-btn');
        const buttonsContainer = document.getElementById('edit-form-buttons');
        const originalContent = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = 'Saving...';

        const formData = new FormData(form);
        
        // Check if a new file is being uploaded
        const hasFile = formData.get('file') && formData.get('file').size > 0;

        try {
            let response;
            
            // Use progress upload if there's a file being uploaded
            if (hasFile) {
                const uploadController = new UploadProgressController('resource-edit-upload');
                buttonsContainer.classList.add('hidden');
                
                response = await uploadController.upload(
                    Urls['api:v1:resource-detail'](resourceId),
                    formData,
                    'PATCH'
                );
            } else {
                response = await API.updateStationResource(resourceId, formData);
            }

            if (response && (response.success || response.data || response.id)) {
                Utils.showNotification('success', 'Resource updated successfully!');
                this.render(stationId, document.getElementById('station-modal-content'));
            } else {
                throw new Error('Failed to update resource');
            }
        } catch (error) {
            console.error('Error updating resource:', error);
            Utils.showNotification('error', error.message || 'Failed to update resource');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalContent;
            buttonsContainer.classList.remove('hidden');
        }
    },

    // ===== DELETE CONFIRMATION =====
    openDeleteConfirm(stationId, resourceId) {
        const self = this;

        // Use cached resources for instant access
        const resource = cachedResources.find(r => String(r.id) === String(resourceId));

        // Remove any existing delete modal
        const existingModal = document.getElementById('resource-delete-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.id = 'resource-delete-modal';
        modal.className = 'fixed inset-0 flex items-center justify-center p-4 bg-black/80';
        modal.style.cssText = 'z-index: 9999; pointer-events: auto;';
        modal.innerHTML = `
            <div class="bg-slate-800 rounded-xl border border-red-500/30 p-6 max-w-md w-full" data-modal-content>
                <div class="text-center mb-6">
                    <div class="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-bold text-white mb-2">Delete Resource?</h3>
                    <p class="text-slate-300">Are you sure you want to delete this resource?</p>
                </div>
                
                ${resource ? `
                    <div class="bg-slate-700/50 rounded-lg p-4 mb-6 space-y-2 text-sm">
                        <div class="flex justify-between">
                            <span class="text-slate-400">Type:</span>
                            <span class="text-white">${this.getResourceTypeLabel(resource.resource_type)}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-400">Title:</span>
                            <span class="text-white">${resource.title || 'Untitled'}</span>
                        </div>
                    </div>
                ` : ''}
                
                <p class="text-red-300 text-sm text-center mb-6">⚠️ This action cannot be undone!</p>
                
                <div class="flex gap-3">
                    <button data-action="cancel" class="btn-secondary flex-1">Cancel</button>
                    <button data-action="confirm" class="btn-danger flex-1">Delete</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        document.body.style.overflow = 'hidden';

        // Handle all clicks via event delegation on the modal
        modal.addEventListener('click', async (e) => {
            e.stopPropagation();

            // Backdrop click to close
            if (e.target === modal) {
                modal.remove();
                document.body.style.overflow = '';
                return;
            }

            // Cancel button
            const cancelBtn = e.target.closest('[data-action="cancel"]');
            if (cancelBtn) {
                modal.remove();
                document.body.style.overflow = '';
                return;
            }

            // Confirm delete button
            const confirmBtn = e.target.closest('[data-action="confirm"]');
            if (confirmBtn) {
                confirmBtn.disabled = true;
                confirmBtn.innerHTML = 'Deleting...';

                try {
                    await API.deleteStationResource(resourceId);
                    Utils.showNotification('success', 'Resource deleted successfully');
                    modal.remove();
                    document.body.style.overflow = '';
                    self.render(stationId, document.getElementById('station-modal-content'));
                } catch (error) {
                    console.error('Error deleting resource:', error);
                    Utils.showNotification('error', 'Failed to delete resource');
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = 'Delete';
                }
            }
        });

        // ESC key to close
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                document.body.style.overflow = '';
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    },

    // ===== LIGHTBOX & VIEWERS =====
    openPhotoLightbox(url, title) {
        // Store reference to this for event handlers
        const self = this;

        // Remove any existing lightbox first to prevent conflicts
        const existingLightbox = document.getElementById('photo-lightbox');
        if (existingLightbox) {
            existingLightbox.remove();
        }

        currentPhotoUrl = url;
        currentPhotoTitle = title || 'Photo';

        const lightbox = document.createElement('div');
        lightbox.id = 'photo-lightbox';
        lightbox.className = 'fixed inset-0 flex items-center justify-center p-4 bg-black/95';
        lightbox.style.cssText = 'z-index: 200;';
        lightbox.innerHTML = `
            <div class="relative max-w-5xl max-h-full" data-lightbox-container>
                <img src="${url}" alt="${title}" class="max-w-full max-h-[85vh] object-contain rounded-lg">
                <div class="absolute top-4 right-4 flex gap-2">
                    <button data-download-photo class="bg-slate-700 hover:bg-slate-600 text-white p-2 rounded-lg" title="Download">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                        </svg>
                    </button>
                    <button data-open-new-tab class="bg-slate-700 hover:bg-slate-600 text-white p-2 rounded-lg" title="Open in new tab">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                        </svg>
                    </button>
                    <button data-close-lightbox class="bg-slate-700 hover:bg-slate-600 text-white p-2 rounded-lg" title="Close">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                <div class="absolute bottom-4 left-4 text-white text-sm bg-black/50 px-3 py-1 rounded">${title}</div>
            </div>
        `;

        document.body.appendChild(lightbox);
        document.body.style.overflow = 'hidden';

        // Close on backdrop click
        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox) {
                self.closePhotoLightbox();
            }
        });

        // Button handlers using data attributes
        const closeBtn = lightbox.querySelector('[data-close-lightbox]');
        const downloadBtn = lightbox.querySelector('[data-download-photo]');
        const newTabBtn = lightbox.querySelector('[data-open-new-tab]');

        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                self.closePhotoLightbox();
            });
        }
        if (downloadBtn) {
            downloadBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                self.downloadPhoto();
            });
        }
        if (newTabBtn) {
            newTabBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                self.openPhotoInNewTab();
            });
        }

        // ESC key to close
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                self.closePhotoLightbox();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    },

    closePhotoLightbox() {
        const lightbox = document.getElementById('photo-lightbox');
        if (lightbox) {
            lightbox.remove();
            document.body.style.overflow = '';
            currentPhotoUrl = null;
            currentPhotoTitle = null;
        }
    },

    downloadPhoto() {
        if (!currentPhotoUrl) return;
        const link = document.createElement('a');
        link.href = currentPhotoUrl;
        link.download = (currentPhotoTitle || 'photo') + '.jpg';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },

    openPhotoInNewTab() {
        if (!currentPhotoUrl) return;
        window.open(currentPhotoUrl, '_blank');
    },

    openVideoModal(url, title) {
        // Store reference to this for event handlers
        const self = this;

        const modal = document.createElement('div');
        modal.id = 'video-modal';
        modal.className = 'fixed inset-0 flex items-center justify-center p-4 bg-black/95';
        modal.style.cssText = 'z-index: 200;';
        modal.innerHTML = `
            <div class="relative" data-video-container style="max-width: 90vw; max-height: 90vh;">
                <video controls autoplay class="rounded-lg bg-black" style="max-width: 90vw; max-height: 85vh; min-width: 320px;">
                    <source src="${url}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <div class="absolute top-4 right-4 flex gap-2">
                    <button data-close-video class="bg-slate-700 hover:bg-slate-600 text-white p-2 rounded-lg" title="Close">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                <div class="absolute bottom-4 left-4 text-white text-sm bg-black/50 px-3 py-1 rounded">${title || 'Video'}</div>
            </div>
        `;

        document.body.appendChild(modal);
        document.body.style.overflow = 'hidden';

        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                self.closeVideoModal();
            }
        });

        // Close button
        const closeBtn = modal.querySelector('[data-close-video]');
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                self.closeVideoModal();
            });
        }

        // ESC key to close
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                self.closeVideoModal();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    },

    closeVideoModal() {
        const modal = document.getElementById('video-modal');
        if (modal) {
            const video = modal.querySelector('video');
            if (video) {
                video.pause();
                video.currentTime = 0;
            }
            modal.remove();
            document.body.style.overflow = '';
        }
    },

    openNoteViewer(noteData) {
        // Store reference to this for event handlers
        const self = this;

        currentNoteContent = noteData.content;

        const modal = document.createElement('div');
        modal.id = 'note-viewer-modal';
        modal.className = 'fixed inset-0 flex items-center justify-center p-4 bg-black/80';
        modal.style.cssText = 'z-index: 200;';
        modal.innerHTML = `
            <div class="bg-slate-800 rounded-xl border border-slate-600 max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
                <div class="p-6 border-b border-slate-700 flex justify-between items-start">
                    <div>
                        <h3 class="text-xl font-bold text-white">${noteData.title || 'Note'}</h3>
                        <div class="flex gap-4 text-sm text-slate-400 mt-2">
                            <span>By ${noteData.author}</span>
                            <span>${new Date(noteData.date).toLocaleDateString()}</span>
                        </div>
                        ${noteData.description ? `<p class="text-slate-300 mt-2 text-sm">${noteData.description}</p>` : ''}
                    </div>
                    <button data-close-note class="text-slate-400 hover:text-white p-2">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                <div class="p-6 overflow-y-auto flex-1 bg-slate-900/50">
                    <div class="prose prose-invert max-w-none">
                        ${this.formatNoteContent(noteData.content)}
                    </div>
                </div>
                <div class="p-4 border-t border-slate-700 flex justify-between items-center">
                    <span class="text-xs text-slate-400">${noteData.content.length} characters</span>
                    <button data-copy-note class="btn-secondary text-sm">
                        <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                        </svg>
                        Copy to Clipboard
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        document.body.style.overflow = 'hidden';

        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                self.closeNoteViewer();
            }
        });

        // Button handlers
        const closeBtn = modal.querySelector('[data-close-note]');
        const copyBtn = modal.querySelector('[data-copy-note]');

        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                self.closeNoteViewer();
            });
        }
        if (copyBtn) {
            copyBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                self.copyNoteToClipboard();
            });
        }

        // ESC key to close
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                self.closeNoteViewer();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    },

    closeNoteViewer() {
        const modal = document.getElementById('note-viewer-modal');
        if (modal) {
            modal.remove();
            document.body.style.overflow = '';
            currentNoteContent = null;
        }
    },

    formatNoteContent(content) {
        // Escape HTML
        const escaped = content
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Convert line breaks to paragraphs
        const paragraphs = escaped.split(/\n\n+/).filter(p => p.trim());

        return paragraphs.map(paragraph => {
            const formatted = paragraph.replace(/\n/g, '<br>');
            return `<p class="mb-4 text-slate-300 leading-relaxed">${formatted}</p>`;
        }).join('');
    },

    copyNoteToClipboard() {
        if (!currentNoteContent) return;

        navigator.clipboard.writeText(currentNoteContent).then(() => {
            const btn = document.querySelector('[data-copy-note]');
            if (!btn) return;

            const originalHTML = btn.innerHTML;
            btn.innerHTML = `
                <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
                Copied!
            `;
            btn.classList.add('bg-green-600');
            btn.classList.remove('bg-slate-600');

            setTimeout(() => {
                btn.innerHTML = originalHTML;
                btn.classList.remove('bg-green-600');
                btn.classList.add('bg-slate-600');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
            Utils.showNotification('error', 'Failed to copy to clipboard');
        });
    },

    // ===== HELPER FUNCTIONS =====
    getResourceTypeLabel(type) {
        const labels = {
            'photo': '📷 Photo',
            'video': '🎥 Video',
            'note': '📝 Note',
            'document': '📄 Document'
        };
        return labels[type] || type;
    },

    getFileAccept(type) {
        const accepts = {
            'photo': 'image/*',
            'video': 'video/*,.mp4,.mov,.avi,.webm',
            'document': '.pdf,.doc,.docx'
        };
        return accepts[type] || '*/*';
    },

    getFileName(url) {
        if (!url) return 'Unknown';
        const parts = url.split('/');
        return parts[parts.length - 1] || 'File';
    }
};



