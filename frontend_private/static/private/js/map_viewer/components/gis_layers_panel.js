import { Config, DEFAULTS } from '../config.js';
import { Layers } from '../map/layers.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { beginMapNavigation, cancelMapNavigation } from '../map/navigation_intent.js';

import { positionOverlayPanel } from './panel_position.js';

export const GISLayersPanel = {
    _resizeObserver: null,
    _mutationObserver: null,
    _loadingListener: null,
    _rows: new Map(),
    _requests: new Map(),

    init() {
        this.destroy();
        if (Config.gisLayers.length === 0) return;
        this.render();
        this.bindEvents();
        this.setupLoadingListener();
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

        positionOverlayPanel([panel, minimized], [
            'gps-tracks-panel', 'gps-tracks-panel-minimized',
            'project-panel', 'project-panel-minimized',
        ], mapContainer);
    },

    /**
     * Stable DOM hooks: data-geometry-type-controls identifies a card's subtype
     * group; data-geometry-type identifies each row by its exact GeoJSON type.
     */
    refreshList() {
        const list = document.getElementById('gis-layers-map-list');
        const panel = document.getElementById('gis-layers-panel');
        const minimized = document.getElementById('gis-layers-panel-minimized');
        const layers = [...Config.gisLayers].sort((first, second) => (
            first.name.localeCompare(second.name, undefined, { sensitivity: 'base' })
        ));

        if (layers.length === 0) {
            if (panel) panel.style.display = 'none';
            if (minimized) minimized.style.display = 'none';
            list?.replaceChildren();
            return;
        }
        if (!list) return;
        this._rows.clear();
        if (panel?.style.display === 'none' && minimized?.style.display === 'none') {
            minimized.style.display = 'block';
        }

        list.replaceChildren(...layers.map(layer => {
            const isVisible = Layers.isGISLayerVisible(layer.id);
            const isLoading = Layers.isGISLayerLoading(layer.id);
            const color = Utils.safeCssColor(layer.color || DEFAULTS.COLORS.FALLBACK);
            const maxLength = DEFAULTS.UI.GIS_LAYER_NAME_MAX_LENGTH;
            const displayName = layer.name.length > maxLength
                ? `${layer.name.substring(0, maxLength - 3)}...`
                : layer.name;
            const item = document.createElement('div');
            item.className = 'gis-layer-button bg-srgb-slate-700-50 hover:bg-slate-700 p-2 rounded-sm cursor-pointer transition-all duration-200';
            if (!isVisible) item.classList.add('opacity-50');
            item.dataset.layerId = layer.id;
            this._rows.set(String(layer.id), item);
            item.innerHTML = Utils.safeHtml`
                <div class="flex items-center justify-between gap-2">
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
                    </div>
                </div>`;

            const checkbox = item.querySelector('input[type="checkbox"]');
            item.addEventListener('click', async event => {
                if (event.target.closest('.toggle-switch')) return;
                await this.activateAndZoom(layer.id);
            });
            checkbox.addEventListener('change', async event => {
                event.stopPropagation();
                await this.toggleLayer(layer.id, checkbox.checked);
            });
            item.querySelector('.toggle-switch').addEventListener('click', event => event.stopPropagation());
            this.updateGeometryControls(item, layer);
            return item;
        }));
    },

    updateGeometryControls(item, layer) {
        const geometryTypes = Layers.getGISLayerGeometryTypes(layer.id);
        const signature = JSON.stringify(geometryTypes);
        if (item.dataset.geometryTypes !== signature) {
            item.querySelector('[data-geometry-type-controls]')?.remove();
            item.dataset.geometryTypes = signature;
            if (geometryTypes.length > 1) {
                const controls = document.createElement('div');
                controls.className = 'ml-5 mt-2 pl-2 border-l border-slate-600 flow-y-1';
                controls.dataset.geometryTypeControls = '';
                controls.addEventListener('click', event => event.stopPropagation());
                for (const type of geometryTypes) {
                    const row = document.createElement('label');
                    row.className = 'flex items-center justify-between gap-2 text-xs text-slate-300 cursor-pointer';
                    row.dataset.geometryType = type;
                    row.innerHTML = Utils.safeHtml`
                        <span>${type}</span>
                        <span class="toggle-switch m-0 scale-[0.6] origin-right">
                            <input type="checkbox" aria-label="Show ${type} in ${layer.name}">
                            <span class="toggle-slider"></span>
                        </span>`;
                    const typeCheckbox = row.querySelector('input');
                    typeCheckbox.checked = Layers.isGISLayerGeometryTypeVisible(layer.id, type);
                    typeCheckbox.disabled = !Layers.isGISLayerVisible(layer.id);
                    typeCheckbox.addEventListener('change', event => {
                        event.stopPropagation();
                        if (typeCheckbox.disabled) return;
                        Layers.setGISLayerGeometryTypeVisibility(layer.id, type, typeCheckbox.checked);
                    });
                    controls.append(row);
                }
                item.append(controls);
            }
        }
        item.querySelectorAll('[data-geometry-type]').forEach(row => {
            const input = row.querySelector('input');
            input.checked = Layers.isGISLayerGeometryTypeVisible(layer.id, row.dataset.geometryType);
            input.disabled = !Layers.isGISLayerVisible(layer.id);
        });
    },

    async activateAndZoom(layerId) {
        const id = String(layerId);
        const map = State.map;
        const navigation = beginMapNavigation(map, `gis-layer:${id}`);
        const displayed = await this.toggleLayer(id, true);
        if (!displayed || !navigation.isCurrent() || State.map !== map) return;
        const bounds = State.gisLayerBounds.get(id);
        if (bounds && map) {
            map.fitBounds(bounds, {
                padding: DEFAULTS.MAP.FIT_BOUNDS_PADDING,
                maxZoom: DEFAULTS.MAP.FIT_BOUNDS_MAX_ZOOM
            });
        }
    },

    async toggleLayer(layerId, visible) {
        const id = String(layerId);
        const request = {};
        this._requests.set(id, request);
        if (!visible) cancelMapNavigation(`gis-layer:${id}`);
        const applying = Layers.toggleGISLayerVisibility(id, visible);
        this.updateRow(id);
        const applied = await applying;
        if (this._requests.get(id) !== request) return false;
        this._requests.delete(id);
        this.updateRow(id);
        return applied;
    },

    updateRow(layerId) {
        const id = String(layerId);
        const row = this._rows.get(id);
        if (!row) return;
        const visible = Layers.isGISLayerVisible(id);
        const loading = Layers.isGISLayerLoading(id) || this._requests.has(id);
        row.querySelector('input').checked = visible;
        row.classList.toggle('opacity-50', !visible);
        row.querySelector('.gis-layer-loading-spinner').classList.toggle('hidden', !loading);
        row.setAttribute('aria-busy', String(loading));
        const layer = Config.getGISLayerById(id);
        if (layer) this.updateGeometryControls(row, layer);
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

    setupLoadingListener() {
        if (this._loadingListener) return;
        this._loadingListener = event => {
            const { layerId } = event.detail || {};
            if (layerId) this.updateRow(layerId);
        };
        window.addEventListener('speleo:gis-layer-loading-changed', this._loadingListener);
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
        this._requests.clear();
        this._rows.forEach((_, id) => cancelMapNavigation(`gis-layer:${id}`));
        this._rows.clear();
        this._resizeObserver?.disconnect();
        this._mutationObserver?.disconnect();
        this._resizeObserver = null;
        this._mutationObserver = null;
        if (this._loadingListener) {
            window.removeEventListener('speleo:gis-layer-loading-changed', this._loadingListener);
            this._loadingListener = null;
        }
    },
};
