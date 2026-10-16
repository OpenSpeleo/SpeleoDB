import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { GPSTracksPanelFacade } from '../../../../../../ts-types/domain/map-panels.ts';
import { Config, DEFAULTS } from '../config.ts';
import { Layers } from '../map/layers.ts';
import { State } from '../state.ts';
import { Colors } from '../map/colors.ts';
import { Utils } from '../utils.ts';
import { beginMapNavigation, cancelMapNavigation } from '../map/navigation_intent.ts';
import { registerMapPanel, unregisterMapPanel } from './panel_stack.ts';

export const GPSTracksPanel: GPSTracksPanelFacade = {
    _rows: new Map(),
    _requests: new Map(),

    init: function() {
        this.destroy();
        // Only render if user has at least 1 GPS track
        if (Config.gpsTracks.length === 0) {
            console.log('📍 No GPS tracks available - hiding GPS Tracks panel');
            return;
        }

        this.render();
        this.bindEvents();
        this.setupLoadingListener();
    },

    render: function() {
        // Create Panel Container if not exists
        if (!document.getElementById('gps-tracks-panel')) {
            const panelHtml = `
            <div id="gps-tracks-panel" class="absolute bg-srgb-slate-800-95 backdrop-blur-xs border-2 border-slate-600 rounded-lg shadow-xl p-4 z-[5]" style="display: none;">
                <div class="flex justify-between items-center mb-3 border-b border-slate-600 pb-2">
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                        </svg>
                        <h3 class="text-white font-semibold text-sm">GPS Tracks</h3>
                    </div>
                    <button id="gps-panel-toggle" class="text-slate-400 hover:text-white transition-colors" title="Minimize GPS Tracks" aria-label="Minimize GPS Tracks">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>
                </div>
                <div id="gps-tracks-list" class="flow-y-2 overflow-y-auto custom-scrollbar" style="max-height: 300px;">
                    <!-- GPS track items will be inserted here -->
                </div>
            </div>

            <div id="gps-tracks-panel-minimized" class="absolute bg-srgb-slate-800-95 backdrop-blur-xs border-2 border-slate-600 rounded-lg shadow-xl p-3 z-[5]" style="display: block;">
                <button id="gps-panel-expand" class="text-white hover:text-cyan-400 transition-colors flex items-center flow-x-2" title="Expand GPS Tracks">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                    </svg>
                    <span class="text-sm font-medium">GPS Tracks</span>
                </button>
            </div>
            `;

            // Append to map container's RELATIVE parent
            const mapContainer = document.querySelector('#map')!.parentElement!;
            if (mapContainer) {
                const temp = document.createElement('div');
                temp.innerHTML = panelHtml;
                while (temp.firstChild) {
                    mapContainer.appendChild(temp.firstChild);
                }
            }
        }

        this.refreshList();
    },

    destroy: function() {
        unregisterMapPanel('gps-tracks-panel');
        this._requests.clear();
        this._rows.forEach((_, id) => cancelMapNavigation(`gps:${id}`));
        this._rows.clear();
        if (this._loadingListener) {
            window.removeEventListener('speleo:gps-track-loading-changed', this._loadingListener);
            this._loadingListener = null;
        }
    },

    refreshList: function() {
        const list = document.getElementById('gps-tracks-list');

        if (!list) return;

        list.innerHTML = '';
        this._rows.clear();

        const tracks = Config.gpsTracks;

        // Sort tracks by name (case-insensitive)
        const sortedTracks = [...tracks].sort((a, b) =>
            a.name!.toLowerCase().localeCompare(b.name!.toLowerCase())
        );

        sortedTracks.forEach(track => {
            const isVisible = Layers.isGPSTrackVisible(track.id);
            const isLoading = Layers.isGPSTrackLoading(track.id);
            const color = this.getTrackColor(track.id);

            const item = document.createElement('div');
            item.className = 'gps-track-button flex items-center justify-between bg-srgb-slate-700-50 hover:bg-slate-700 p-2 rounded-sm cursor-pointer transition-all duration-200';
            if (!isVisible) item.classList.add('opacity-50');
            item.dataset.trackId = track.id;
            item.dataset.trackUrl = track.file!;
            item.dataset.color = color;
            this._rows.set(String(track.id), item);

            item.innerHTML = Utils.safeHtml`
                <div class="flex items-center gap-2 min-w-0 flex-1">
                    <div class="gps-track-color-dot w-3 h-3 rounded-full shrink-0 shadow-xs" style="background-color: ${Utils.raw(Utils.safeCssColor(isVisible ? color : DEFAULTS.COLORS.FALLBACK))}; ${Utils.raw(isVisible ? 'border: 2px dashed rgba(255,255,255,0.5);' : '')}"></div>
                    <span class="text-slate-200 text-sm font-medium map-panel-name select-none" title="${track.name}">${track.name}</span>
                </div>
                <div class="flex items-center gap-2">
                    <div class="gps-track-loading-spinner ${Utils.raw(isLoading ? '' : 'hidden')}" style="width: 16px; height: 16px; border: 2px solid rgba(56, 189, 248, 0.3); border-left-color: #38bdf8; border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
                    <label class="toggle-switch m-0 scale-75 origin-right">
                        <input type="checkbox" ${Utils.raw(isVisible ? 'checked' : '')} aria-label="Show ${track.name}">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            `;

            // Bind checkbox change event
            const checkbox = item.querySelector<HTMLInputElement>('input[type="checkbox"]')!;

            // Handle card body click - activate track and fly to it
            item.addEventListener('click', (async (e: MouseEvent) => {
                // Don't handle if clicking on the toggle switch
                if (e.target !== checkbox && e.target !== checkbox.nextElementSibling && (e.target as Element).closest('.toggle-switch') === null) {
                    await this.activateAndFlyToTrack(track.id);
                }
            }) as (event: MouseEvent) => void);

            checkbox.addEventListener('change', (async (e: Event) => {
                e.stopPropagation();
                const newState = (e.target as HTMLInputElement).checked;

                await this.toggleTrack(track.id, newState);
            }) as EventListener);

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

    activateAndFlyToTrack: async function(trackId) {
        const tid = String(trackId);
        const map = State.map;
        const navigation = beginMapNavigation(map, `gps:${tid}`);
        const shown = await this.toggleTrack(trackId, true);
        if (shown && navigation.isCurrent() && State.map === map) this.flyToTrack(trackId);
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

    toggleTrack: async function(trackId, isVisible) {
        const id = String(trackId);
        const request = {};
        this._requests.set(id, request);
        if (!isVisible) cancelMapNavigation(`gps:${id}`);
        const applying = Layers.toggleGPSTrackVisibility(id, isVisible);
        this.updateRow(id);
        const applied = await applying;
        if (this._requests.get(id) !== request) return false;
        this._requests.delete(id);
        this.updateRow(id);
        return applied;
    },

    updateRow(trackId) {
        const id = String(trackId);
        const row = this._rows.get(id);
        if (!row) return;
        const visible = Layers.isGPSTrackVisible(id);
        const loading = Layers.isGPSTrackLoading(id) || this._requests.has(id);
        row.querySelector('input')!.checked = visible;
        row.classList.toggle('opacity-50', !visible);
        row.querySelector('.gps-track-loading-spinner')!.classList.toggle('hidden', !loading);
        row.setAttribute('aria-busy', String(loading));
        const dot = row.querySelector<HTMLElement>('.gps-track-color-dot')!;
        dot.style.backgroundColor = Utils.safeCssColor(visible ? this.getTrackColor(id) : DEFAULTS.COLORS.FALLBACK);
        dot.style.border = visible ? '2px dashed rgba(255,255,255,0.5)' : '';
    },

    bindEvents() {
        registerMapPanel('gps-tracks-panel', 'gps-panel-expand', 'gps-panel-toggle');
    },

    setupLoadingListener: function() {
        // Listen for loading state changes to update UI
        this._loadingListener = (e) => {
            const { trackId } = (e as CustomEvent<{ trackId?: EntityId }>).detail || {};
            if (!trackId) return;
            this.updateRow(trackId);
        };
        window.addEventListener('speleo:gps-track-loading-changed', this._loadingListener);
    },

    getTrackColor: function(trackId) {
        // Use centralized color assignment from Colors module
        return Colors.getGPSTrackColor(trackId);
    }
};
