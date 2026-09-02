import { DEFAULTS } from '../config.js';
import { GISLayerStore } from '../gis_layer_store.js';
import { getGISLayerRuntime } from '../gis_layers_runtime.js';
import { Utils } from '../utils.js';

function visibleAnchor(...elementIds) {
    return elementIds
        .map(elementId => document.getElementById(elementId))
        .find(element => element && element.style.display !== 'none');
}

export const GISLayersPanel = {
    _resizeObserver: null,
    _mutationObserver: null,
    _stateListener: null,

    init() {
        if (GISLayerStore.layers.length === 0) return;
        this.render();
        this.bindEvents();
        this.setupStateListener();
        this.setupStackListener();
    },

    render() {
        if (!document.getElementById('gis-layers-panel')) {
            const panelHtml = `
                <div id="gis-layers-panel" class="absolute bg-srgb-slate-800-95 backdrop-blur-xs border-2 border-slate-600 rounded-lg shadow-xl p-4 max-w-xs z-[5]" style="min-width: 250px; display: none;">
                    <div class="flex justify-between items-center mb-3 border-b border-slate-600 pb-2">
                        <div class="flex items-center gap-2">
                            <svg class="w-4 h-4 text-indigo-400 fill-none stroke-current" viewBox="0 0 24 24" stroke-width="1.8" aria-hidden="true">
                                <path d="M12 3l8 4-8 4-8-4 8-4z"></path>
                                <path d="M4 12l8 4 8-4"></path>
                                <path d="M4 17l8 4 8-4"></path>
                            </svg>
                            <h3 class="text-white font-semibold text-sm">GIS Layers</h3>
                        </div>
                        <button id="gis-panel-toggle" class="text-slate-400 hover:text-white transition-colors" title="Minimize GIS Layers" aria-label="Minimize GIS Layers">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                            </svg>
                        </button>
                    </div>
                    <div id="gis-layers-map-list" class="flow-y-2 overflow-y-auto custom-scrollbar" style="max-height: 300px;"></div>
                </div>
                <div id="gis-layers-panel-minimized" class="absolute bg-srgb-slate-800-95 backdrop-blur-xs border-2 border-slate-600 rounded-lg shadow-xl p-3 z-[5]" style="display: block;">
                    <button id="gis-panel-expand" class="text-white hover:text-indigo-400 transition-colors flex items-center flow-x-2" title="Expand GIS Layers" aria-label="Expand GIS Layers">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                        <span class="text-sm font-medium">GIS Layers</span>
                    </button>
                </div>`;
            const mapContainer = document.querySelector('#map')?.parentElement;
            if (!mapContainer) return;
            const template = document.createElement('template');
            template.innerHTML = panelHtml;
            mapContainer.appendChild(template.content);
        }
        this.positionPanel();
        this.refreshList();
    },

    positionPanel() {
        const panel = document.getElementById('gis-layers-panel');
        const minimized = document.getElementById('gis-layers-panel-minimized');
        const mapContainer = document.querySelector('#map')?.parentElement;
        if (!panel || !minimized || !mapContainer) return;

        const anchor = visibleAnchor(
            'gps-tracks-panel',
            'gps-tracks-panel-minimized',
            'project-panel',
            'project-panel-minimized',
        );
        let top = DEFAULTS.UI.MAP_PANEL_EDGE_PX;
        if (anchor) {
            const anchorRect = anchor.getBoundingClientRect();
            const mapRect = mapContainer.getBoundingClientRect();
            top = anchorRect.bottom - mapRect.top + DEFAULTS.UI.MAP_PANEL_GAP_PX;
        }
        for (const element of [panel, minimized]) {
            element.style.left = `${DEFAULTS.UI.MAP_PANEL_EDGE_PX}px`;
            element.style.right = 'auto';
            element.style.top = `${top}px`;
        }
    },

    refreshList() {
        const list = document.getElementById('gis-layers-map-list');
        const panel = document.getElementById('gis-layers-panel');
        const minimized = document.getElementById('gis-layers-panel-minimized');
        const layers = [...GISLayerStore.layers].sort((first, second) => (
            first.name.localeCompare(second.name, undefined, { sensitivity: 'base' })
        ));

        if (layers.length === 0) {
            if (panel) panel.style.display = 'none';
            if (minimized) minimized.style.display = 'none';
            list?.replaceChildren();
            return;
        }
        if (!list) return;
        if (panel?.style.display === 'none' && minimized?.style.display === 'none') {
            minimized.style.display = 'block';
        }

        const runtime = getGISLayerRuntime();
        list.replaceChildren(...layers.map(layer => {
            const isVisible = runtime.isDesired(layer.id);
            const isLoading = runtime.isLoading(layer.id);
            const color = Utils.safeCssColor(layer.color || DEFAULTS.COLORS.FALLBACK);
            const maxLength = DEFAULTS.UI.GIS_LAYER_NAME_MAX_LENGTH;
            const displayName = layer.name.length > maxLength
                ? `${layer.name.substring(0, maxLength - 3)}...`
                : layer.name;
            const item = document.createElement('div');
            item.className = 'gis-layer-button flex items-center justify-between bg-srgb-slate-700-50 hover:bg-slate-700 p-2 rounded-sm cursor-pointer transition-all duration-200';
            if (!isVisible) item.classList.add('opacity-50');
            item.dataset.layerId = layer.id;
            item.innerHTML = Utils.safeHtml`
                <div class="flex items-center gap-2 overflow-hidden flex-1">
                    <div class="gis-layer-color-dot w-3 h-3 rounded-full shrink-0 shadow-xs" style="background-color: ${Utils.raw(color)}"></div>
                    <span class="text-slate-200 text-sm font-medium truncate select-none" title="${layer.name}">${displayName}</span>
                </div>
                <div class="flex items-center gap-2">
                    <div class="gis-layer-loading-spinner ${Utils.raw(isLoading ? '' : 'hidden')}" aria-label="Loading GIS Layer"></div>
                    <label class="toggle-switch m-0 scale-75 origin-right">
                        <input type="checkbox" ${Utils.raw(isVisible ? 'checked' : '')} aria-label="Show ${layer.name}">
                        <span class="toggle-slider"></span>
                    </label>
                </div>`;

            const checkbox = item.querySelector('input[type="checkbox"]');
            item.addEventListener('click', async event => {
                if (event.target.closest('.toggle-switch')) return;
                await runtime.setDesired(layer, true);
                this.refreshList();
            });
            checkbox.addEventListener('change', async event => {
                event.stopPropagation();
                await runtime.setDesired(layer, checkbox.checked);
                this.refreshList();
            });
            item.querySelector('.toggle-switch').addEventListener('click', event => event.stopPropagation());
            return item;
        }));
    },

    bindEvents() {
        const panel = document.getElementById('gis-layers-panel');
        const minimized = document.getElementById('gis-layers-panel-minimized');
        document.getElementById('gis-panel-toggle')?.addEventListener('click', () => {
            panel.style.display = 'none';
            minimized.style.display = 'block';
        });
        document.getElementById('gis-panel-expand')?.addEventListener('click', () => {
            minimized.style.display = 'none';
            panel.style.display = 'block';
        });
    },

    setupStateListener() {
        if (this._stateListener) return;
        this._stateListener = () => this.refreshList();
        window.addEventListener('speleo:gis-layer-state-changed', this._stateListener);
    },

    setupStackListener() {
        this._resizeObserver?.disconnect();
        this._mutationObserver?.disconnect();
        const anchors = [
            'project-panel',
            'project-panel-minimized',
            'gps-tracks-panel',
            'gps-tracks-panel-minimized',
        ].map(elementId => document.getElementById(elementId)).filter(Boolean);
        const reposition = Utils.debounce(() => this.positionPanel(), DEFAULTS.UI.MAP_PANEL_POSITION_DELAY_MS);
        this._resizeObserver = new ResizeObserver(reposition);
        this._mutationObserver = new MutationObserver(reposition);
        anchors.forEach(anchor => {
            this._resizeObserver.observe(anchor);
            this._mutationObserver.observe(anchor, { attributes: true, attributeFilter: ['style'] });
        });
        this.positionPanel();
    },

    destroy() {
        this._resizeObserver?.disconnect();
        this._mutationObserver?.disconnect();
        this._resizeObserver = null;
        this._mutationObserver = null;
        if (this._stateListener) {
            window.removeEventListener('speleo:gis-layer-state-changed', this._stateListener);
            this._stateListener = null;
        }
    },
};
