import { API } from '../api.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { Config } from '../config.js';
import { StationLogs } from './logs.js';
import { StationResources } from './resources.js';
import { StationExperiments } from './experiments.js';
import { StationSensors } from './sensors.js';
import { StationManager } from './manager.js';
import { Layers } from '../map/layers.js';
import { StationTags } from './tags.js';

// Track current station state
let currentStationId = null;
let currentProjectId = null;
let activeTab = 'details';

export const StationDetails = {
    currentStationId: null,
    currentTab: 'details',

    async openModal(stationId, projectId = null, isNewlyCreated = false) {
        console.log(`📋 Opening station modal for: ${stationId || 'NEW STATION'}`);

        currentStationId = stationId;
        this.currentStationId = stationId;
        currentProjectId = projectId || (State.allStations.get(stationId)?.project) || Config.projects[0]?.id;

        const modal = document.getElementById('station-modal');
        if (!modal) {
            console.error('❌ Station modal element not found!');
            return;
        }

        // Clear any lingering inline display from previous flows
        try { modal.style.removeProperty('display'); } catch (e) { modal.style.display = ''; }

        // Store the newly created state for later use
        window.currentStationIsNew = isNewlyCreated;

        // Clear modal content first
        const modalContent = document.getElementById('station-modal-content');
        if (modalContent) {
            modalContent.innerHTML = '';
            modalContent.style.cssText = '';
        }

        // Update title
        const titleElement = document.getElementById('station-modal-title');
        const stationManagerModal = document.getElementById('station-manager-modal');
        if (titleElement && stationManagerModal && !stationManagerModal.classList.contains('hidden')) {
            titleElement.innerHTML = `
                <button onclick="window.returnToStationManager()" class="text-sky-400 hover:text-sky-300 mr-2" title="Back to Station Manager">
                    <svg class="w-5 h-5 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                    </svg>
                </button>
                Station Details
            `;
        } else if (titleElement) {
            titleElement.innerHTML = 'Station Details';
        }

        // Initialize tabs
        this.initializeTabs();

        // Setup modal handlers
        this.setupModalHandlers();

        // Show modal
        modal.classList.remove('hidden');

        if (stationId) {
            console.log(`📋 Loading existing station: ${stationId}`);
            this.switchTab('details');
            await this.loadStationDetails(stationId, currentProjectId);

            // Show a special message if newly created
            if (isNewlyCreated) {
                setTimeout(() => {
                    const content = document.getElementById('station-modal-content');
                    if (content && content.innerHTML) {
                        const existingContent = content.innerHTML;
                        content.innerHTML = `
                            <div class="bg-emerald-500/20 border border-emerald-500/50 rounded-lg p-4 m-6 flex items-center justify-between">
                                <div class="flex items-center">
                                    <span class="text-2xl mr-3">🎉</span>
                                    <div>
                                        <div class="text-emerald-200 font-semibold">Station Created Successfully!</div>
                                        <div class="text-emerald-100 text-sm mt-1">You can now add photos, videos, notes, and other resources.</div>
                                    </div>
                                </div>
                                <button onclick="this.parentElement.style.display='none'" class="text-emerald-300 hover:text-emerald-100">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                    </svg>
                                </button>
                            </div>
                            ${existingContent}
                        `;
                    }
                }, 500);
            }
        } else {
            console.log(`📋 Showing empty station details`);
            this.switchTab('details');
        }
    },

    initializeTabs() {
        const tabButtons = document.querySelectorAll('#station-modal-tabs .tab-btn');

        // Remove existing event listeners to prevent duplicates
        tabButtons.forEach(btn => {
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
        });

        // Re-query after cloning
        const freshButtons = document.querySelectorAll('#station-modal-tabs .tab-btn');
        freshButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const tab = btn.dataset.tab;
                if (tab) {
                    this.switchTab(tab);
                }
            });
        });

        // Setup mobile dropdown
        this.setupTabSelect();
    },

    setupTabSelect() {
        const selectEl = document.getElementById('station-tab-select');
        if (!selectEl) return;

        selectEl.value = activeTab || 'details';

        const newSelect = selectEl.cloneNode(true);
        selectEl.parentNode.replaceChild(newSelect, selectEl);
        newSelect.addEventListener('change', (e) => {
            const tab = e.target.value;
            if (tab) this.switchTab(tab);
        });
    },

    setupModalHandlers() {
        const modal = document.getElementById('station-modal');
        const closeBtn = document.getElementById('station-modal-close');

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

    switchTab(tabName) {
        console.log(`📑 Switching to tab: ${tabName}`);
        activeTab = tabName;
        this.currentTab = tabName;

        // Update tab buttons
        document.querySelectorAll('#station-modal-tabs .tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // Update mobile dropdown if present
        const selectEl = document.getElementById('station-tab-select');
        if (selectEl && selectEl.value !== tabName) {
            selectEl.value = tabName;
        }

        // Load tab content
        switch (tabName) {
            case 'details':
                if (currentStationId) {
                    this.loadStationDetails(currentStationId, currentProjectId);
                } else {
                    this.showEmptyDetails();
                }
                break;
            case 'logs':
                if (currentStationId) {
                    StationLogs.render(currentStationId, document.getElementById('station-modal-content'));
                } else {
                    this.showEmptyTab('Journal Entries', 'Select a station to view journal entries.');
                }
                break;
            case 'experiments':
                if (currentStationId) {
                    StationExperiments.render(currentStationId, document.getElementById('station-modal-content'));
                } else {
                    this.showEmptyTab('Experiment Data', 'Select a station to view experiment data.');
                }
                break;
            case 'resources':
                if (currentStationId) {
                    StationResources.render(currentStationId, document.getElementById('station-modal-content'));
                } else {
                    this.showEmptyTab('Station Resources', 'Select a station to view resources.');
                }
                break;
            case 'sensor-management':
                if (currentStationId) {
                    StationSensors.render(currentStationId, document.getElementById('station-modal-content'));
                } else {
                    this.showEmptyTab('Sensor Management', 'Select a station to view sensor data.');
                }
                break;
            default:
                console.error(`❌ Unknown tab: ${tabName}`);
        }
    },

    showEmptyDetails() {
        const content = document.getElementById('station-modal-content');
        content.innerHTML = `
            <div class="tab-content active">
                <div class="flex items-center justify-center min-h-[300px]">
                    <div class="text-center">
                        <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        </svg>
                        <h3 class="text-white text-lg font-medium mb-2">No Station Selected</h3>
                        <p class="text-slate-400 mb-4">Select a station from the map or create a new one.</p>
                    </div>
                </div>
            </div>
        `;
    },

    showEmptyTab(title, message) {
        const content = document.getElementById('station-modal-content');
        content.innerHTML = `
            <div class="tab-content active">
                <div class="flex items-center justify-center min-h-[300px]">
                    <div class="text-center">
                        <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                        </svg>
                        <h3 class="text-white text-lg font-medium mb-2">${title}</h3>
                        <p class="text-slate-400">${message}</p>
                    </div>
                </div>
            </div>
        `;
    },

    async loadStationDetails(stationId, projectId) {
        try {
            // Fetch the full station details from the API
            const response = await API.getStationDetails(stationId);

            let station;
            if (response && response.success && response.data) {
                station = response.data;
            } else if (response && response.id) {
                station = response;
            } else {
                throw new Error('Invalid station response');
            }

            // Update the allStations map with the complete data
            const existingStation = State.allStations.get(stationId);
            if (existingStation) {
                const mergedStation = {
                    ...existingStation,
                    ...station,
                    latitude: Number(station.latitude || existingStation.latitude),
                    longitude: Number(station.longitude || existingStation.longitude),
                    project: existingStation.project || projectId
                };
                State.allStations.set(stationId, mergedStation);
                station = mergedStation;
            } else {
                station = {
                    ...station,
                    latitude: Number(station.latitude),
                    longitude: Number(station.longitude),
                    project: projectId
                };
                State.allStations.set(stationId, station);
            }

            // Display the station details
            this.displayStationDetails(station, projectId);

        } catch (error) {
            console.error('Error loading station details:', error);
            document.getElementById('station-modal-content').innerHTML =
                '<div class="tab-content active"><div class="flex items-center justify-center min-h-[300px]"><div class="text-center text-red-400">Error loading station details</div></div></div>';
        }
    },

    displayStationDetails(station, projectId) {
        const modalTitle = document.getElementById('station-modal-title');
        const modalContent = document.getElementById('station-modal-content');

        if (!modalTitle || !modalContent) {
            console.error('Modal elements not found!');
            return;
        }

        // Update title
        const isDemoStation = station.is_demo || (station.id && String(station.id).startsWith('demo-'));
        modalTitle.innerHTML = `Station: ${station.name}${isDemoStation ? ' <span class="demo-badge">DEMO</span>' : ''}`;

        const hasWriteAccess = Config.hasProjectWriteAccess(projectId);
        const hasAdminAccess = Config.hasProjectAdminAccess ? Config.hasProjectAdminAccess(projectId) : hasWriteAccess;

        // Get project name
        const project = Config.projects.find(p => p.id === String(projectId));
        const projectName = project ? project.name : 'Unknown Project';

        // GPS location info
        const snapInfo = `
            <div class="mt-3 bg-slate-700/50 p-3 rounded-lg border border-slate-500/30">
                <strong class="text-slate-300">📍 Station Location:</strong>
                <div class="text-sm text-slate-200 mt-1">
                    <div>GPS Location: <span class="font-mono text-slate-300">${Number(station.latitude).toFixed(7)}, ${Number(station.longitude).toFixed(7)}</span></div>
                </div>
                ${hasWriteAccess ?
                `<div class="text-xs text-slate-400 mt-2">🖱️ Drag this station to move it or use magnetic snap to nearby survey lines</div>` :
                `<div class="text-xs text-amber-300 mt-2">🔒 Read-only access - moving stations is disabled</div>`
            }
            </div>
        `;

        modalContent.innerHTML = `
            <div class="tab-content active">
                <div class="space-y-8">
                    <div class="bg-slate-700/70 rounded-xl border border-slate-600/50 overflow-hidden">
                        <div class="bg-slate-800/30 p-6">
                            <h3 class="text-2xl font-bold text-white">${station.name}</h3>
                            <div class="grid grid-cols-2 gap-3 mt-4">
                                <button ${hasWriteAccess ? `id="edit-station-btn"` : ''} class="btn-secondary text-sm w-full ${hasWriteAccess ? '' : 'opacity-50 cursor-not-allowed'}" ${hasWriteAccess ? '' : 'disabled'}>✏️ Edit</button>
                                <button ${hasAdminAccess ? `id="delete-station-btn"` : ''} class="btn-danger text-sm w-full ${hasAdminAccess ? '' : 'opacity-50 cursor-not-allowed'}" ${hasAdminAccess ? '' : 'disabled'}>🗑️ Delete</button>
                            </div>
                        </div>
                        
                        <div class="p-8 space-y-6">
                            ${station.description ? `<p class="text-slate-300 text-lg leading-relaxed bg-slate-800/30 p-4 rounded-lg border">${station.description}</p>` : ''}
                            
                            <!-- Tag Section -->
                            ${hasWriteAccess ? `
                            <div class="bg-slate-800/30 p-4 rounded-lg border border-slate-600/50">
                                <div class="flex items-center justify-between mb-3">
                                    <h4 class="text-white font-semibold flex items-center">
                                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"></path>
                                        </svg>
                                        Tag
                                    </h4>
                                    <button id="open-tag-selector-btn" class="text-xs px-3 py-1 bg-sky-500 hover:bg-sky-600 text-white rounded-lg transition-colors">
                                        ${(station.tag && station.tag.name) ? 'Change Tag' : '+ Add Tag'}
                                    </button>
                                </div>
                                <div id="station-tag-display" class="flex gap-2 min-h-[32px]">
                                    ${(station.tag && station.tag.name && station.tag.color) ? `
                                        <span class="station-tag" style="background-color: ${station.tag.color}">
                                            ${station.tag.name}
                                            <span class="remove-tag" onclick="window.removeStationTag('${station.id}')">×</span>
                                        </span>
                                    ` : '<span class="text-slate-400 text-sm">No tag assigned</span>'}
                                </div>
                            </div>
                            ` : (station.tag && station.tag.name && station.tag.color) ? `
                            <div class="bg-slate-800/30 p-4 rounded-lg border border-slate-600/50">
                                <h4 class="text-white font-semibold mb-3 flex items-center">
                                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"></path>
                                    </svg>
                                    Tag
                                </h4>
                                <div>
                                    <span class="station-tag" style="background-color: ${station.tag.color}">
                                        ${station.tag.name}
                                    </span>
                                </div>
                            </div>
                            ` : ''}
                            
                            ${snapInfo}
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Attach event handlers
        if (hasWriteAccess) {
            const editBtn = document.getElementById('edit-station-btn');
            if (editBtn) {
                editBtn.onclick = () => this.openEditForm(station);
            }

            // Tag selector button
            const tagBtn = document.getElementById('open-tag-selector-btn');
            if (tagBtn) {
                tagBtn.onclick = () => StationTags.openTagSelector(station.id);
            }
        }

        if (hasAdminAccess) {
            const deleteBtn = document.getElementById('delete-station-btn');
            if (deleteBtn) {
                deleteBtn.onclick = () => this.confirmDelete(station);
            }
        }
    },

    openEditForm(station) {
        const modalContent = document.getElementById('station-modal-content');

        modalContent.innerHTML = `
            <div class="tab-content active p-6">
                <form id="edit-station-form" class="space-y-6">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Station Name *</label>
                        <input type="text" id="edit-station-name" value="${station.name}" required
                               class="w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:border-sky-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                        <textarea id="edit-station-description" rows="4"
                                  class="w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:border-sky-500 focus:outline-none resize-none">${station.description || ''}</textarea>
                    </div>
                    <div class="flex gap-3 justify-end pt-4 border-t border-slate-600">
                        <button type="button" id="cancel-edit-btn" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary">Save Changes</button>
                    </div>
                </form>
            </div>
        `;

        document.getElementById('cancel-edit-btn').onclick = () => {
            this.displayStationDetails(station, station.project);
        };

        document.getElementById('edit-station-form').onsubmit = async (e) => {
            e.preventDefault();

            const name = document.getElementById('edit-station-name').value.trim();
            const description = document.getElementById('edit-station-description').value.trim();

            if (!name) {
                Utils.showNotification('error', 'Station name is required');
                return;
            }

            try {
                await StationManager.updateStation(station.id, { name, description });
                Utils.showNotification('success', 'Station updated successfully');

                // Refresh the station data
                station.name = name;
                station.description = description;
                State.allStations.set(station.id, station);

                // Update the station label on the map
                Layers.updateStationProperties(station.project, station.id, { name });

                this.displayStationDetails(station, station.project);
            } catch (error) {
                Utils.showNotification('error', 'Failed to update station');
            }
        };
    },

    confirmDelete(station) {
        const modalContent = document.getElementById('station-modal-content');

        modalContent.innerHTML = `
            <div class="tab-content active p-6">
                <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-6 text-center">
                    <svg class="w-16 h-16 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h3 class="text-xl font-bold text-white mb-2">Delete Station?</h3>
                    <p class="text-slate-300 mb-2">Are you sure you want to delete <strong>${station.name}</strong>?</p>
                    <p class="text-red-300 text-sm mb-6">This action cannot be undone. All associated resources, logs, and data will be permanently deleted.</p>
                    <div class="flex gap-3 justify-center">
                        <button id="cancel-delete-btn" class="btn-secondary">Cancel</button>
                        <button id="confirm-delete-btn" class="btn-danger">Delete Station</button>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('cancel-delete-btn').onclick = () => {
            this.displayStationDetails(station, station.project);
        };

        document.getElementById('confirm-delete-btn').onclick = async () => {
            try {
                await StationManager.deleteStation(station.id);
                Utils.showNotification('success', 'Station deleted successfully');

                // Close modal
                document.getElementById('station-modal').classList.add('hidden');

                // Refresh stations layer
                Layers.refreshStationsAfterChange(station.project);
            } catch (error) {
                Utils.showNotification('error', 'Failed to delete station');
            }
        };
    }
};

// Global function for return to station manager button
window.returnToStationManager = function () {
    console.log('↩️ Returning to Station Manager');
    const stationModal = document.getElementById('station-modal');
    if (stationModal) {
        stationModal.classList.add('hidden');
        stationModal.style.display = 'none';
    }
    if (window.openStationManager) {
        window.openStationManager();
    }
};
