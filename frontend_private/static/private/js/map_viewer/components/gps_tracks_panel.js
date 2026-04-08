import { Config, DEFAULTS } from '../config.js';
import { Layers } from '../map/layers.js';
import { State } from '../state.js';
import { Colors } from '../map/colors.js';
import { Utils } from '../utils.js';

export const GPSTracksPanel = {
    init: function() {
        // Only render if user has at least 1 GPS track
        if (Config.gpsTracks.length === 0) {
            console.log('📍 No GPS tracks available - hiding GPS Tracks panel');
            return;
        }
        
        this.render();
        this.bindEvents();
        this.setupLoadingListener();
        this.setupProjectPanelListener();
    },

    render: function() {
        // Create Panel Container if not exists
        if (!document.getElementById('gps-tracks-panel')) {
            const panelHtml = `
            <div id="gps-tracks-panel" class="absolute bg-slate-800/95 backdrop-blur-sm border-2 border-slate-600 rounded-lg shadow-xl p-4 max-w-xs z-[5]" style="min-width: 250px; display: none;">
                <div class="flex justify-between items-center mb-3 border-b border-slate-600 pb-2">
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                        </svg>
                        <h3 class="text-white font-semibold text-sm">GPS Tracks</h3>
                    </div>
                    <button id="gps-panel-toggle" class="text-slate-400 hover:text-white transition-colors" title="Minimize">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>
                </div>
                <div id="gps-tracks-list" class="space-y-2 overflow-y-auto custom-scrollbar" style="max-height: 300px;">
                    <!-- GPS track items will be inserted here -->
                </div>
            </div>
            
            <div id="gps-tracks-panel-minimized" class="absolute bg-slate-800/95 backdrop-blur-sm border-2 border-slate-600 rounded-lg shadow-xl p-3 z-[5]" style="display: block;">
                <button id="gps-panel-expand" class="text-white hover:text-cyan-400 transition-colors flex items-center space-x-2" title="Expand GPS Tracks">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                    </svg>
                    <span class="text-sm font-medium">GPS Tracks</span>
                </button>
            </div>
            `;
            
            // Append to map container's RELATIVE parent
            const mapContainer = document.querySelector('#map').parentElement;
            if (mapContainer) {
                const temp = document.createElement('div');
                temp.innerHTML = panelHtml;
                while (temp.firstChild) {
                    mapContainer.appendChild(temp.firstChild);
                }
            }

            // Position the panel below the project panel
            this.positionPanel();
        }
        
        this.refreshList();
    },

    positionPanel: function() {
        const gpsPanel = document.getElementById('gps-tracks-panel');
        const gpsPanelMinimized = document.getElementById('gps-tracks-panel-minimized');
        const projectPanel = document.getElementById('project-panel');
        const projectPanelMinimized = document.getElementById('project-panel-minimized');

        if (!gpsPanel || !gpsPanelMinimized) return;

        const baseLeft = 16;
        const baseTop = 16;
        const gap = 10;

        // Determine if project panel is expanded or minimized
        const projectPanelExpanded = projectPanel && projectPanel.style.display !== 'none';
        const projectPanelMinimizedVisible = projectPanelMinimized && projectPanelMinimized.style.display !== 'none';

        let gpsTop = baseTop;

        if (projectPanelExpanded && projectPanel) {
            // Project panel is expanded - position below it
            const projectPanelRect = projectPanel.getBoundingClientRect();
            const mapContainerRect = document.querySelector('#map').parentElement.getBoundingClientRect();
            gpsTop = projectPanelRect.bottom - mapContainerRect.top + gap;
        } else if (projectPanelMinimizedVisible && projectPanelMinimized) {
            // Project panel is minimized - position below the minimized button
            const minimizedRect = projectPanelMinimized.getBoundingClientRect();
            const mapContainerRect = document.querySelector('#map').parentElement.getBoundingClientRect();
            gpsTop = minimizedRect.bottom - mapContainerRect.top + gap;
        }

        // Set position - left side, below project panel
        gpsPanel.style.left = `${baseLeft}px`;
        gpsPanel.style.right = 'auto';
        gpsPanel.style.top = `${gpsTop}px`;

        gpsPanelMinimized.style.left = `${baseLeft}px`;
        gpsPanelMinimized.style.right = 'auto';
        gpsPanelMinimized.style.top = `${gpsTop}px`;
    },

    _resizeObserver: null,
    _mutationObserver: null,

    setupProjectPanelListener: function() {
        const projectPanel = document.getElementById('project-panel');
        const projectPanelMinimized = document.getElementById('project-panel-minimized');
        const projectToggleBtn = document.getElementById('panel-toggle');
        const projectExpandBtn = document.getElementById('panel-expand');

        if (projectToggleBtn) {
            projectToggleBtn.addEventListener('click', () => {
                setTimeout(() => this.positionPanel(), 50);
            });
        }

        if (projectExpandBtn) {
            projectExpandBtn.addEventListener('click', () => {
                setTimeout(() => this.positionPanel(), 50);
            });
        }

        // ResizeObserver catches all size changes: content changes from
        // country group collapse/expand, visibility toggles, etc.
        const debouncedPosition = Utils.debounce(() => this.positionPanel(), 50);

        this._resizeObserver = new ResizeObserver(debouncedPosition);

        if (projectPanel) {
            this._resizeObserver.observe(projectPanel);
        }
        if (projectPanelMinimized) {
            this._resizeObserver.observe(projectPanelMinimized);
        }

        // MutationObserver still needed for display:none/block toggling
        // (ResizeObserver doesn't fire when an element is hidden)
        if (projectPanel || projectPanelMinimized) {
            this._mutationObserver = new MutationObserver(debouncedPosition);

            if (projectPanel) {
                this._mutationObserver.observe(projectPanel, { attributes: true, attributeFilter: ['style'] });
            }
            if (projectPanelMinimized) {
                this._mutationObserver.observe(projectPanelMinimized, { attributes: true, attributeFilter: ['style'] });
            }
        }
    },

    destroy: function() {
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
            this._resizeObserver = null;
        }
        if (this._mutationObserver) {
            this._mutationObserver.disconnect();
            this._mutationObserver = null;
        }
        if (this._loadingListener) {
            window.removeEventListener('speleo:gps-track-loading-changed', this._loadingListener);
            this._loadingListener = null;
        }
    },

    refreshList: function() {
        const list = document.getElementById('gps-tracks-list');
        
        if (!list) return;

        list.innerHTML = '';
        
        const tracks = Config.gpsTracks;
        
        // Sort tracks by name (case-insensitive)
        const sortedTracks = [...tracks].sort((a, b) => 
            a.name.toLowerCase().localeCompare(b.name.toLowerCase())
        );
        
        sortedTracks.forEach(track => {
            const isVisible = Layers.isGPSTrackVisible(track.id);
            const isLoading = Layers.isGPSTrackLoading(track.id);
            const color = this.getTrackColor(track.id);
            
            const item = document.createElement('div');
            item.className = 'gps-track-button flex items-center justify-between bg-slate-700/50 hover:bg-slate-700 p-2 rounded cursor-pointer transition-all duration-200';
            if (!isVisible) item.classList.add('opacity-50');
            item.dataset.trackId = track.id;
            item.dataset.trackUrl = track.file;
            item.dataset.color = color;
            
            // Truncate long track names
            const maxLen = DEFAULTS.UI.TRACK_NAME_MAX_LENGTH;
            const displayName = track.name.length > maxLen 
                ? track.name.substring(0, maxLen - 3) + '...' 
                : track.name;
            
            item.innerHTML = Utils.safeHtml`
                <div class="flex items-center gap-2 overflow-hidden flex-1">
                    <div class="gps-track-color-dot w-3 h-3 rounded-full shrink-0 shadow-sm" style="background-color: ${Utils.raw(Utils.safeCssColor(isVisible ? color : DEFAULTS.COLORS.FALLBACK))}; ${Utils.raw(isVisible ? 'border: 2px dashed rgba(255,255,255,0.5);' : '')}"></div>
                    <span class="text-slate-200 text-sm font-medium truncate select-none" title="${track.name}">${displayName}</span>
                </div>
                <div class="flex items-center gap-2">
                    <div class="gps-track-loading-spinner ${Utils.raw(isLoading ? '' : 'hidden')}" style="width: 16px; height: 16px; border: 2px solid rgba(56, 189, 248, 0.3); border-left-color: #38bdf8; border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
                    <label class="toggle-switch m-0 scale-75 origin-right">
                        <input type="checkbox" ${Utils.raw(isVisible ? 'checked' : '')} ${Utils.raw(isLoading ? 'disabled' : '')}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            `;
            
            // Bind checkbox change event
            const checkbox = item.querySelector('input[type="checkbox"]');
            
            // Handle card body click - activate track and fly to it
            item.addEventListener('click', async (e) => {
                // Don't handle if clicking on the toggle switch
                if (e.target !== checkbox && e.target !== checkbox.nextElementSibling && e.target.closest('.toggle-switch') === null) {
                    await this.activateAndFlyToTrack(track.id, track.file);
                }
            });
            
            checkbox.addEventListener('change', async (e) => {
                e.stopPropagation();
                const newState = e.target.checked;
                
                // Disable checkbox while loading
                if (newState && !State.gpsTrackCache.has(String(track.id))) {
                    checkbox.disabled = true;
                }
                
                await this.toggleTrack(track.id, newState, track.file);
                
                // Re-enable checkbox
                checkbox.disabled = false;
            });
            
            // Stop propagation on toggle switch container click
            const toggleLabel = item.querySelector('.toggle-switch');
            if (toggleLabel) {
                toggleLabel.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            }

            list.appendChild(item);
        });
    },

    activateAndFlyToTrack: async function(trackId, trackUrl) {
        const tid = String(trackId);
        const isVisible = Layers.isGPSTrackVisible(tid);
        
        // If track is not visible, activate it first
        if (!isVisible) {
            await this.toggleTrack(trackId, true, trackUrl);
        }
        
        // Now fly to the track (bounds should be available after loading)
        this.flyToTrack(trackId);
    },

    flyToTrack: function(trackId) {
        const tid = String(trackId);
        const bounds = State.gpsTrackBounds.get(tid);
        
        if (bounds && State.map) {
            State.map.fitBounds(bounds, { padding: DEFAULTS.MAP.FIT_BOUNDS_PADDING, maxZoom: DEFAULTS.MAP.FIT_BOUNDS_MAX_ZOOM });
        } else {
            console.log(`📍 GPS track ${trackId} bounds not available yet`);
        }
    },

    toggleTrack: async function(trackId, isVisible, trackUrl) {
        await Layers.toggleGPSTrackVisibility(trackId, isVisible, trackUrl);
        this.refreshList(); // Refresh to update opacity/colors
    },

    bindEvents: function() {
        const panel = document.getElementById('gps-tracks-panel');
        const minimized = document.getElementById('gps-tracks-panel-minimized');
        const toggleBtn = document.getElementById('gps-panel-toggle');
        const expandBtn = document.getElementById('gps-panel-expand');

        if (toggleBtn && panel && minimized) {
            toggleBtn.addEventListener('click', () => {
                panel.style.display = 'none';
                minimized.style.display = 'block';
            });
        }

        if (expandBtn && panel && minimized) {
            expandBtn.addEventListener('click', () => {
                minimized.style.display = 'none';
                panel.style.display = 'block';
            });
        }
    },

    setupLoadingListener: function() {
        // Listen for loading state changes to update UI
        this._loadingListener = (e) => {
            const { trackId, isLoading } = e.detail || {};
            if (!trackId) return;
            const item = document.querySelector(`.gps-track-button[data-track-id="${trackId}"]`);
            if (item) {
                const spinner = item.querySelector('.gps-track-loading-spinner');
                const checkbox = item.querySelector('input[type="checkbox"]');
                
                if (spinner) {
                    if (isLoading) {
                        spinner.classList.remove('hidden');
                    } else {
                        spinner.classList.add('hidden');
                    }
                }
                
                if (checkbox) {
                    checkbox.disabled = isLoading;
                }
            }
        };
        window.addEventListener('speleo:gps-track-loading-changed', this._loadingListener);
    },
    
    getTrackColor: function(trackId) {
        // Use centralized color assignment from Colors module
        return Colors.getGPSTrackColor(trackId);
    }
};
