import { API } from '../api.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { Layers } from '../map/layers.js';

// Default colors if API fails
const FALLBACK_COLORS = [
    "#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16",
    "#22c55e", "#10b981", "#14b8a6", "#06b6d4", "#0ea5e9",
    "#3b82f6", "#6366f1", "#8b5cf6", "#a855f7", "#d946ef",
    "#ec4899", "#f43f5e", "#fb7185", "#fb923c", "#facc15"
];

export const StationTags = {
    // Load user's tags from API
    async loadUserTags() {
        try {
            const response = await API.getUserTags();
            State.userTags = response.data || [];
            console.log(`✅ Loaded ${State.userTags.length} user tags`);
        } catch (error) {
            console.error('Error loading user tags:', error);
            State.userTags = [];
        }
    },

    // Load predefined colors
    async loadTagColors() {
        try {
            const response = await API.getTagColors();
            State.tagColors = response.data?.colors || FALLBACK_COLORS;
            console.log(`✅ Loaded ${State.tagColors.length} tag colors`);
        } catch (error) {
            console.error('Error loading tag colors:', error);
            State.tagColors = FALLBACK_COLORS;
        }
    },

    // Initialize - load both tags and colors
    async init() {
        await Promise.all([
            this.loadUserTags(),
            this.loadTagColors()
        ]);
    },

    // Open tag selector modal
    openTagSelector(stationId) {
        State.currentStationForTagging = stationId;
        // Check both subsurface and surface stations
        const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        if (!station) {
            console.error('❌ Station not found for tagging:', stationId);
            return;
        }

        const currentTagId = station.tag ? station.tag.id : null;

        const html = `
            <div class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" id="tag-selector-overlay" style="z-index: 100;">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="flex items-center justify-between p-6 border-b border-slate-600">
                        <h3 class="text-lg font-semibold text-white">${station.tag ? 'Change Station Tag' : 'Add Tag to Station'}</h3>
                        <button onclick="window.closeTagSelector()" class="text-slate-400 hover:text-white transition-colors">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    <div class="p-6 max-h-96 overflow-y-auto">
                        ${State.userTags.length > 0 ? `
                            <div class="space-y-2">
                                ${State.userTags.map(tag => `
                                    <button onclick="window.setStationTag('${stationId}', '${tag.id}')" 
                                            class="w-full text-left px-4 py-2 rounded-lg ${currentTagId === tag.id ? 'bg-sky-600' : 'bg-slate-700'} hover:bg-slate-600 transition-colors flex items-center justify-between">
                                        <span class="station-tag" style="background-color: ${tag.color}">${tag.name}</span>
                                        ${currentTagId === tag.id ? '<span class="text-white text-sm">✓ Current</span>' : ''}
                                    </button>
                                `).join('')}
                            </div>
                            ${currentTagId ? `
                                <div class="mt-4 pt-4 border-t border-slate-600">
                                    <button onclick="window.removeStationTag('${stationId}')" 
                                            class="w-full px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 transition-colors text-sm">
                                        Remove Tag from Station
                                    </button>
                                </div>
                            ` : ''}
                        ` : '<p class="text-slate-400 text-center">No tags available. Create one below!</p>'}
                    </div>
                    <div class="flex justify-between items-center p-6 border-t border-slate-600">
                        <button onclick="window.openTagCreationModal()" class="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors text-sm">
                            + Create New Tag
                        </button>
                        <button onclick="window.closeTagSelector()" class="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors">
                            Close
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', html);
    },

    // Close tag selector
    closeTagSelector() {
        const overlay = document.getElementById('tag-selector-overlay');
        if (overlay) overlay.remove();
    },

    // Open tag creation modal
    openTagCreationModal() {
        this.closeTagSelector();

        // Ensure colors are available
        if (State.tagColors.length === 0) {
            State.tagColors = FALLBACK_COLORS;
        }

        const html = `
            <div class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" id="tag-creation-overlay" style="z-index: 100;">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="flex items-center justify-between p-6 border-b border-slate-600">
                        <h2 class="text-xl font-semibold text-white">Create New Tag</h2>
                        <button onclick="window.closeTagCreationModal()" class="text-slate-400 hover:text-white transition-colors">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    <div class="p-6 space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-slate-300 mb-2">Tag Name</label>
                            <input type="text" id="new-tag-name" 
                                   class="w-full bg-slate-700 text-white rounded-lg p-2 border border-slate-600 focus:border-sky-500 focus:outline-none" 
                                   placeholder="e.g., Active, Completed, High Priority">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-slate-300 mb-2">Color</label>
                            <div class="tag-color-picker" id="tag-color-picker">
                                ${State.tagColors.map(color => `
                                    <div class="tag-color-option" 
                                         style="background-color: ${color}" 
                                         data-color="${color}"
                                         onclick="window.selectTagColor('${color}')" 
                                         title="${color}"></div>
                                `).join('')}
                            </div>
                            <input type="hidden" id="new-tag-color" value="${State.tagColors[0] || '#ef4444'}">
                            
                            <!-- Custom Color Picker -->
                            <div class="mt-4 flex items-center gap-3 flex-wrap">
                                <label class="text-sm text-slate-400">Or pick a custom color:</label>
                                <input type="color" id="new-tag-custom-color" 
                                       value="${State.tagColors[0] || '#ef4444'}"
                                       onchange="window.useCustomColorForNewTag()"
                                       class="h-10 w-20 rounded cursor-pointer border border-slate-600"
                                       title="Pick custom color">
                            </div>
                        </div>
                    </div>
                    <div class="flex justify-end gap-3 p-6 border-t border-slate-600">
                        <button onclick="window.closeTagCreationModal()" class="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors">
                            Cancel
                        </button>
                        <button onclick="window.createNewTag()" class="px-4 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors">
                            Create Tag
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', html);

        // Auto-select first color
        setTimeout(() => this.selectTagColor(State.tagColors[0] || '#ef4444'), 0);
    },

    // Close tag creation modal
    closeTagCreationModal() {
        const overlay = document.getElementById('tag-creation-overlay');
        if (overlay) overlay.remove();
    },

    // Select a color for new tag
    selectTagColor(color) {
        const colorInput = document.getElementById('new-tag-color');
        if (colorInput) colorInput.value = color;

        document.querySelectorAll('.tag-color-option').forEach(opt => {
            opt.classList.remove('selected');
            if (opt.getAttribute('data-color') === color) {
                opt.classList.add('selected');
            }
        });

        // Update custom color input to match
        const customInput = document.getElementById('new-tag-custom-color');
        if (customInput) customInput.value = color;
    },

    // Use custom color from color picker
    useCustomColorForNewTag() {
        const customColorInput = document.getElementById('new-tag-custom-color');
        if (!customColorInput) return;

        const customColor = customColorInput.value.toUpperCase();
        const colorInput = document.getElementById('new-tag-color');
        if (colorInput) colorInput.value = customColor;

        // Deselect all preset colors
        document.querySelectorAll('.tag-color-option').forEach(opt => {
            opt.classList.remove('selected');
        });
    },

    // Create a new tag
    async createNewTag() {
        const name = document.getElementById('new-tag-name').value.trim();
        const color = document.getElementById('new-tag-color').value;

        if (!name) {
            Utils.showNotification('error', 'Please enter a tag name');
            return;
        }

        if (!color) {
            Utils.showNotification('error', 'Please select a color');
            return;
        }

        try {
            const response = await API.createTag(name, color);
            const newTag = response.data;
            State.userTags.push(newTag);
            Utils.showNotification('success', `Tag "${name}" created successfully`);
            this.closeTagCreationModal();

            // If we're tagging a station, reopen the tag selector
            if (State.currentStationForTagging) {
                this.openTagSelector(State.currentStationForTagging);
            }
        } catch (error) {
            console.error('Error creating tag:', error);
            Utils.showNotification('error', error.message || 'Failed to create tag');
        }
    },

    // Set tag on station
    async setStationTag(stationId, tagId) {
        try {
            const response = await API.setStationTag(stationId, tagId);

            // Check both subsurface and surface stations
            const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
            if (station) {
                // response.data is the tag object
                station.tag = response.data;

                // Update marker color on map
                this.updateStationMarkerColor(stationId, station);

                // Refresh tag display in modal
                this.refreshStationTagDisplay(stationId, station);
            }

            Utils.showNotification('success', 'Tag set on station');
            this.closeTagSelector();
        } catch (error) {
            console.error('Error setting tag:', error);
            Utils.showNotification('error', error.message || 'Failed to set tag');
        }
    },

    // Remove tag from station
    async removeStationTag(stationId) {
        try {
            await API.removeStationTag(stationId);

            // Check both subsurface and surface stations
            const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
            if (station) {
                station.tag = null;
                this.updateStationMarkerColor(stationId, station);
                this.refreshStationTagDisplay(stationId, station);
            }

            Utils.showNotification('success', 'Tag removed from station');
            this.closeTagSelector();
        } catch (error) {
            console.error('Error removing tag:', error);
            Utils.showNotification('error', error.message || 'Failed to remove tag');
        }
    },

    // Update station marker color based on tag
    updateStationMarkerColor(stationId, stationObj = null) {
        const station = stationObj || State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        if (!station) return;

        // Use the tag's color if available, otherwise default
        const color = station.tag ? station.tag.color : '#fb923c';

        // Determine if this is a surface or subsurface station
        if (station.network || station.station_type === 'surface') {
            // Surface station - update surface station layer
            Layers.updateSurfaceStationColor(station.network, stationId, color);
        } else if (station.project) {
            // Subsurface station - update station layer
            Layers.updateStationColor(station.project, stationId, color);
        }
    },

    // Refresh station tag display in modal
    refreshStationTagDisplay(stationId, stationObj = null) {
        const tagContainer = document.getElementById('station-tag-display');
        if (!tagContainer) {
            console.log('⚠️ Tag container not found');
            return;
        }

        const station = stationObj || State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        if (!station) {
            console.log('⚠️ Station not found:', stationId);
            return;
        }

        if (station.tag && station.tag.name && station.tag.color) {
            tagContainer.innerHTML = `
                <span class="station-tag" style="background-color: ${station.tag.color}">
                    ${station.tag.name}
                    <span class="remove-tag" onclick="window.removeStationTag('${stationId}')">×</span>
                </span>
            `;
        } else {
            tagContainer.innerHTML = '<span class="text-slate-400 text-sm">No tag assigned</span>';
        }

        // Update the button text
        const tagBtn = document.getElementById('open-tag-selector-btn');
        if (tagBtn) {
            tagBtn.textContent = station.tag ? 'Change Tag' : '+ Add Tag';
        }
    }
};

// Expose functions globally for onclick handlers
window.openTagSelector = (stationId) => StationTags.openTagSelector(stationId);
window.closeTagSelector = () => StationTags.closeTagSelector();
window.openTagCreationModal = () => StationTags.openTagCreationModal();
window.closeTagCreationModal = () => StationTags.closeTagCreationModal();
window.selectTagColor = (color) => StationTags.selectTagColor(color);
window.useCustomColorForNewTag = () => StationTags.useCustomColorForNewTag();
window.createNewTag = () => StationTags.createNewTag();
window.setStationTag = (stationId, tagId) => StationTags.setStationTag(stationId, tagId);
window.removeStationTag = (stationId) => StationTags.removeStationTag(stationId);

