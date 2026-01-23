import { API } from '../api.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { Config } from '../config.js';
import { StationLogs } from './logs.js';
import { StationResources } from './resources.js';
import { StationExperiments } from './experiments.js';
import { StationSensors } from './sensors.js';
import { StationManager } from './manager.js';
import { SurfaceStationManager } from '../surface_stations/manager.js';
import { Layers } from '../map/layers.js';
import { StationTags } from './tags.js';

// Track current station state
let currentStationId = null;
let currentProjectId = null;
let currentNetworkId = null;
let currentStationType = 'subsurface';  // 'subsurface' or 'surface'
let currentSubsurfaceType = null;  // 'science', 'biology', 'bone', or 'artifact' (only for subsurface)
let activeTab = 'details';

// Helper to get station type label and icon
function getStationTypeInfo(subsurfaceType) {
    const typeLabels = {
        'science': { label: 'Science', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.science}" class="w-4 h-4 align-middle inline">`, color: 'bg-orange-500/20 text-orange-300 border-orange-500/30' },
        'biology': { label: 'Biology', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.biology}" class="w-4 h-4 align-middle inline">`, color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' },
        'artifact': { label: 'Artifact', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.artifact}" class="w-4 h-4 align-middle inline">`, color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
        'bone': { label: 'Bones', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.bone}" class="w-4 h-4 align-middle inline">`, color: 'bg-slate-500/20 text-slate-200 border-slate-400/30' }
    };
    return typeLabels[subsurfaceType] || typeLabels['science'];
}

export const StationDetails = {
    currentStationId: null,
    currentTab: 'details',

    /**
     * Open the station details modal.
     * @param {string} stationId - The station ID
     * @param {string} parentId - Project ID for subsurface, Network ID for surface
     * @param {boolean} isNewlyCreated - Whether this is a newly created station
     * @param {string} stationType - 'subsurface' or 'surface'
     */
    async openModal(stationId, parentId = null, isNewlyCreated = false, stationType = 'subsurface') {
        console.log(`📋 Opening ${stationType} station modal for: ${stationId || 'NEW STATION'}`);

        currentStationId = stationId;
        this.currentStationId = stationId;
        currentStationType = stationType;

        // Pre-set subsurface type from State if available (will be confirmed in loadStationDetails)
        // For surface stations, subsurface type is always null
        if (stationType === 'surface') {
            currentSubsurfaceType = null;
            currentNetworkId = parentId || (State.allSurfaceStations.get(stationId)?.network) || Config.networks[0]?.id;
            currentProjectId = null;
        } else {
            // Try to get type from State to avoid flicker
            const stationFromState = stationId ? State.allStations.get(stationId) : null;
            currentSubsurfaceType = stationFromState?.type || 'science';
            currentProjectId = parentId || stationFromState?.project || Config.projects[0]?.id;
            currentNetworkId = null;
        }

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
            console.log(`📋 Loading existing ${stationType} station: ${stationId}`);
            this.switchTab('details');
            await this.loadStationDetails(stationId, stationType === 'surface' ? currentNetworkId : currentProjectId, stationType);

     
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

        // Update tab visibility based on station type
        this.updateTabVisibility();
    },

    /**
     * Update tab visibility based on current station type.
     * Biology, Bone, and Artifact stations should not show Experiments and Sensor Management tabs.
     */
    updateTabVisibility() {
        const hideTabs = currentSubsurfaceType === 'biology' || currentSubsurfaceType === 'bone' || currentSubsurfaceType === 'artifact';
        const tabsToHide = ['experiments', 'sensor-management'];

        // Update button tabs
        const tabButtons = document.querySelectorAll('#station-modal-tabs .tab-btn');
        tabButtons.forEach(btn => {
            const tab = btn.dataset.tab;
            if (tabsToHide.includes(tab)) {
                btn.style.display = hideTabs ? 'none' : '';
            }
        });

        // Update mobile dropdown
        const selectEl = document.getElementById('station-tab-select');
        if (selectEl) {
            Array.from(selectEl.options).forEach(option => {
                if (tabsToHide.includes(option.value)) {
                    option.style.display = hideTabs ? 'none' : '';
                    option.disabled = hideTabs;
                }
            });
        }
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
                    // Show inline loading state in the modal content, then load data
                    this.showDetailsLoading();
                    const parentId = currentStationType === 'surface' ? currentNetworkId : currentProjectId;
                    this.loadStationDetails(currentStationId, parentId, currentStationType);
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

    showDetailsLoading() {
        const content = document.getElementById('station-modal-content');
        content.innerHTML = `
            <div class="tab-content active">
                <div class="space-y-8">
                    <div class="bg-slate-700/70 rounded-xl border border-slate-600/50 overflow-hidden">
                        <div class="bg-slate-800/30 p-6">
                            <!-- Title skeleton -->
                            <div class="h-8 w-48 bg-slate-600/50 rounded animate-pulse"></div>
                            <!-- Buttons skeleton -->
                            <div class="grid grid-cols-2 gap-3 mt-4">
                                <div class="h-10 bg-slate-600/50 rounded animate-pulse"></div>
                                <div class="h-10 bg-slate-600/50 rounded animate-pulse"></div>
                            </div>
                        </div>
                        
                        <div class="p-8 space-y-6">
                            <!-- Loading spinner -->
                            <div class="flex items-center justify-center py-8">
                                <div class="text-center">
                                    <div class="loading-spinner mx-auto mb-4"></div>
                                    <p class="text-slate-400">Loading station details...</p>
                                </div>
                            </div>
                        </div>
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

    async loadStationDetails(stationId, parentId, stationType = 'subsurface') {
        try {
            // Fetch the full station details from the API (same endpoint for both types)
            const response = await API.getStationDetails(stationId);

            let station;
            if (response && response.success && response.data) {
                station = response.data;
            } else if (response && response.id) {
                station = response;
            } else {
                throw new Error('Invalid station response');
            }

            // Update the appropriate state map with the complete data
            const stateMap = stationType === 'surface' ? State.allSurfaceStations : State.allStations;
            const existingStation = stateMap.get(stationId);

            if (existingStation) {
                const mergedStation = {
                    ...existingStation,
                    ...station,
                    latitude: Number(station.latitude || existingStation.latitude),
                    longitude: Number(station.longitude || existingStation.longitude),
                    station_type: stationType
                };

                if (stationType === 'surface') {
                    mergedStation.network = existingStation.network || parentId;
                } else {
                    mergedStation.project = existingStation.project || parentId;
                }

                stateMap.set(stationId, mergedStation);
                station = mergedStation;
            } else {
                station = {
                    ...station,
                    latitude: Number(station.latitude),
                    longitude: Number(station.longitude),
                    station_type: stationType
                };

                if (stationType === 'surface') {
                    station.network = parentId;
                } else {
                    station.project = parentId;
                }

                stateMap.set(stationId, station);
            }

            // Track subsurface station type for tab visibility
            if (stationType === 'subsurface') {
                currentSubsurfaceType = station.type || 'science';
            } else {
                currentSubsurfaceType = null;  // Surface stations don't have this type
            }

            // Update tab visibility based on station type
            this.updateTabVisibility();

            // Display the station details
            this.displayStationDetails(station, parentId, stationType);

        } catch (error) {
            console.error('Error loading station details:', error);
            document.getElementById('station-modal-content').innerHTML =
                '<div class="tab-content active"><div class="flex items-center justify-center min-h-[300px]"><div class="text-center text-red-400">Error loading station details</div></div></div>';
        }
    },

    displayStationDetails(station, parentId, stationType = 'subsurface') {
        const modalTitle = document.getElementById('station-modal-title');
        const modalContent = document.getElementById('station-modal-content');

        if (!modalTitle || !modalContent) {
            console.error('Modal elements not found!');
            return;
        }

        const isSurfaceStation = stationType === 'surface';

        // Update title with station type badge for subsurface stations
        const isDemoStation = station.is_demo || (station.id && String(station.id).startsWith('demo-'));
        let stationTypeLabel = isSurfaceStation ? 'Surface Station' : 'Station';
        let typeBadge = '';

        if (!isSurfaceStation && station.type) {
            const typeInfo = getStationTypeInfo(station.type);
            typeBadge = `<span class="ml-2 px-2 py-0.5 rounded text-xs font-medium border ${typeInfo.color}">${typeInfo.icon} ${typeInfo.label}</span>`;
        }

        modalTitle.innerHTML = `${stationTypeLabel}: ${station.name}${typeBadge}${isDemoStation ? ' <span class="demo-badge">DEMO</span>' : ''}`;

        // Determine access based on station type
        let hasWriteAccess, hasAdminAccess, parentName, parentType;

        if (isSurfaceStation) {
            hasWriteAccess = Config.hasNetworkWriteAccess(parentId);
            hasAdminAccess = Config.hasNetworkAdminAccess(parentId);
            const network = Config.networks.find(n => n.id === String(parentId));
            parentName = network ? network.name : 'Unknown Network';
            parentType = 'Network';
        } else {
            hasWriteAccess = Config.hasProjectWriteAccess(parentId);
            hasAdminAccess = Config.hasProjectAdminAccess ? Config.hasProjectAdminAccess(parentId) : hasWriteAccess;
            const project = Config.projects.find(p => p.id === String(parentId));
            parentName = project ? project.name : 'Unknown Project';
            parentType = 'Project';
        }

        // GPS location info - different message for surface vs subsurface
        const dragInfo = isSurfaceStation
            ? '<div class="text-xs text-slate-400 mt-2">📍 Surface stations have fixed GPS coordinates</div>'
            : (hasWriteAccess
                ? '<div class="text-xs text-slate-400 mt-2">🖱️ Drag this station to move it or use magnetic snap to nearby survey lines</div>'
                : '<div class="text-xs text-amber-300 mt-2">🔒 Read-only access - moving stations is disabled</div>');

        // Station type info section (only for subsurface stations)
        let stationTypeSection = '';
        if (!isSurfaceStation && station.type) {
            const typeInfo = getStationTypeInfo(station.type);
            stationTypeSection = `
                <div class="bg-slate-700/50 p-4 rounded-lg border border-slate-600/50 mb-4">
                    <h4 class="text-white font-semibold mb-2 flex items-center">
                        <span class="mr-2">${typeInfo.icon}</span>
                        Station Type
                    </h4>
                    <div class="flex items-center gap-2">
                        <span class="px-3 py-1 rounded-full text-sm font-medium border ${typeInfo.color}">
                            ${typeInfo.label} Station
                        </span>
                        <span class="text-xs text-slate-400">(cannot be modified)</span>
                    </div>
                </div>
            `;
        }

        const snapInfo = `
            <div class="mt-3 bg-slate-700/50 p-3 rounded-lg border border-slate-500/30">
                <strong class="text-slate-300">📍 Station Location:</strong>
                <div class="text-sm text-slate-200 mt-1">
                    <div>GPS Location: <span class="font-mono text-slate-300">${Number(station.latitude).toFixed(7)}, ${Number(station.longitude).toFixed(7)}</span></div>
                    <div class="mt-1">${parentType}: <span class="text-slate-300">${parentName}</span></div>
                </div>
                ${dragInfo}
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
                            ${stationTypeSection}
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
                editBtn.onclick = () => this.openEditForm(station, stationType);
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
                deleteBtn.onclick = () => this.confirmDelete(station, stationType);
            }
        }
    },

    openEditForm(station, stationType = 'subsurface') {
        const modalContent = document.getElementById('station-modal-content');
        const isSurfaceStation = stationType === 'surface';

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

        const parentId = isSurfaceStation ? station.network : station.project;

        document.getElementById('cancel-edit-btn').onclick = () => {
            this.displayStationDetails(station, parentId, stationType);
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
                // Use the same API for both station types (polymorphic on backend)
                await StationManager.updateStation(station.id, { name, description });
                Utils.showNotification('success', 'Station updated successfully');

                // Refresh the station data
                station.name = name;
                station.description = description;

                // Update the appropriate state map
                if (isSurfaceStation) {
                    State.allSurfaceStations.set(station.id, station);
                    // Update the station label on the map
                    Layers.updateSurfaceStationProperties(station.network, station.id, { name });
                } else {
                    State.allStations.set(station.id, station);
                    // Update the station label on the map
                    Layers.updateStationProperties(station.project, station.id, { name });
                }

                this.displayStationDetails(station, parentId, stationType);
            } catch (error) {
                Utils.showNotification('error', 'Failed to update station');
            }
        };
    },

    confirmDelete(station, stationType = 'subsurface') {
        const stationModal = document.getElementById('station-modal');
        const isStationModalOpen = stationModal && !stationModal.classList.contains('hidden');
        const isSurfaceStation = stationType === 'surface';
        const parentId = isSurfaceStation ? station.network : station.project;

        if (isStationModalOpen) {
            // Station modal is open - show confirmation in modal content
            const modalContent = document.getElementById('station-modal-content');
            const stationTypeLabel = isSurfaceStation ? 'Surface Station' : 'Station';

            modalContent.innerHTML = `
                <div class="tab-content active p-6">
                    <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-6 text-center">
                        <svg class="w-16 h-16 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                        <h3 class="text-xl font-bold text-white mb-2">Delete ${stationTypeLabel}?</h3>
                        <p class="text-slate-300 mb-2">Are you sure you want to delete <strong>${station.name}</strong>?</p>
                        <p class="text-red-300 text-sm mb-6">This action cannot be undone. All associated resources, logs, and data will be permanently deleted.</p>
                        <div class="flex gap-3 justify-center">
                            <button id="cancel-delete-btn" class="btn-secondary">Cancel</button>
                            <button id="confirm-delete-btn" class="btn-danger">Delete ${stationTypeLabel}</button>
                        </div>
                    </div>
                </div>
            `;

            document.getElementById('cancel-delete-btn').onclick = () => {
                this.displayStationDetails(station, parentId, stationType);
            };

            document.getElementById('confirm-delete-btn').onclick = async () => {
                try {
                    if (isSurfaceStation) {
                        await SurfaceStationManager.deleteStation(station.id);
                    } else {
                        await StationManager.deleteStation(station.id);
                    }
                    Utils.showNotification('success', `${stationTypeLabel} deleted successfully`);

                    // Close modal
                    document.getElementById('station-modal').classList.add('hidden');
                } catch (error) {
                    Utils.showNotification('error', `Failed to delete ${stationTypeLabel.toLowerCase()}`);
                }
            };
        } else {
            // Called from context menu - show standalone confirmation modal
            this.showStandaloneDeleteModal(station, stationType);
        }
    },

    showStandaloneDeleteModal(station, stationType = 'subsurface') {
        // Remove any existing standalone delete modal
        const existingModal = document.getElementById('station-delete-confirm-modal');
        if (existingModal) existingModal.remove();

        const isSurfaceStation = stationType === 'surface';
        const stationTypeLabel = isSurfaceStation ? 'Surface Station' : 'Station';

        const modalHtml = `
            <div id="station-delete-confirm-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6">
                        <div class="flex items-center justify-center mb-4">
                            <div class="w-16 h-16 rounded-full bg-red-900/30 flex items-center justify-center">
                                <svg class="w-10 h-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                                </svg>
                            </div>
                        </div>
                        <h3 class="text-xl font-bold text-white text-center mb-2">Delete ${stationTypeLabel}?</h3>
                        <p class="text-slate-300 text-center mb-2">Are you sure you want to delete <strong>${station.name}</strong>?</p>
                        <p class="text-red-300 text-sm text-center mb-6">This action cannot be undone. All associated resources, logs, and data will be permanently deleted.</p>
                        <div class="flex gap-3 justify-center">
                            <button id="standalone-cancel-delete-btn" class="btn-secondary px-6">Cancel</button>
                            <button id="standalone-confirm-delete-btn" class="btn-danger px-6">Delete ${stationTypeLabel}</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

        const modal = document.getElementById('station-delete-confirm-modal');

        // Cancel button
        document.getElementById('standalone-cancel-delete-btn').onclick = () => {
            modal.remove();
        };

        // Confirm delete button
        document.getElementById('standalone-confirm-delete-btn').onclick = async () => {
            try {
                if (isSurfaceStation) {
                    await SurfaceStationManager.deleteStation(station.id);
                } else {
                    await StationManager.deleteStation(station.id);
                }
                Utils.showNotification('success', `${stationTypeLabel} deleted successfully`);
                modal.remove();
            } catch (error) {
                Utils.showNotification('error', `Failed to delete ${stationTypeLabel.toLowerCase()}`);
            }
        };

        // Close on backdrop click
        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        };

        // Close on Escape key
        const escHandler = (e) => {
            if (e.key === 'Escape' && document.getElementById('station-delete-confirm-modal')) {
                modal.remove();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
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
    if (window.openSurveyStationManager) {
        window.openSurveyStationManager();
    }
};
