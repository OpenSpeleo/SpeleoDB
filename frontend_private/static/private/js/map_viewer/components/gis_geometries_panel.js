import { Config, DEFAULTS } from '../config.js';
import { Layers } from '../map/layers.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { positionOverlayPanel } from './panel_position.js';
import { fitGISGeometry } from '../map/geometry_camera.js';
import { beginMapNavigation, cancelMapNavigation } from '../map/navigation_intent.js';

function button(label, className, action) {
    const element = document.createElement('button');
    element.type = 'button';
    element.className = className;
    element.textContent = label;
    element.addEventListener('click', action);
    return element;
}

export const GISGeometriesPanel = {
    editor: null,
    observer: null,
    mutations: null,
    panel: null,
    minimized: null,
    rows: new Map(),
    requests: new Map(),

    init(editor) {
        this.destroy();
        this.editor = editor;
        const container = document.getElementById('map');
        if (!container) return;
        this.panel = document.createElement('section');
        this.panel.id = 'gis-geometries-panel';
        this.panel.className = 'gis-geometries-panel';
        this.panel.setAttribute('aria-label', 'GIS Geometries');
        this.panel.hidden = true;
        const header = document.createElement('header');
        const title = document.createElement('h3');
        title.textContent = 'GIS Geometries';
        const collapse = button('', 'gis-geometries-icon-button', () => this.setExpanded(false));
        collapse.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>';
        collapse.setAttribute('aria-label', 'Minimize GIS Geometries');
        collapse.title = 'Minimize GIS Geometries';
        header.append(title, collapse);
        const list = document.createElement('div');
        list.id = 'gis-geometries-map-list';
        list.className = 'gis-geometries-list';
        this.panel.append(header, list);
        this.minimized = button('', 'gis-geometries-minimized', () => this.setExpanded(true));
        this.minimized.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg><span>GIS Geometries</span>';
        this.minimized.id = 'gis-geometries-panel-minimized';
        this.minimized.setAttribute('aria-label', 'Expand GIS Geometries');
        this.minimized.title = 'Expand GIS Geometries';
        this.minimized.setAttribute('aria-expanded', 'false');
        this.minimized.setAttribute('aria-controls', this.panel.id);
        for (const element of [this.panel, this.minimized]) {
            for (const event of ['click', 'mousedown', 'dblclick', 'touchstart', 'wheel', 'contextmenu']) {
                element.addEventListener(event, e => e.stopPropagation());
            }
            container.append(element);
        }
        this.refreshList();
        this.setupStackListener();
    },

    setExpanded(expanded) {
        const restoreFocus = this.panel.contains(document.activeElement)
            || this.minimized === document.activeElement;
        this.panel.hidden = !expanded;
        this.minimized.hidden = expanded;
        this.minimized.setAttribute('aria-expanded', String(expanded));
        this.positionPanel();
        if (restoreFocus) {
            (expanded ? this.panel.querySelector('.gis-geometries-icon-button') : this.minimized)
                .focus({ preventScroll: true });
        }
    },

    positionPanel() {
        const container = document.getElementById('map');
        positionOverlayPanel([this.panel, this.minimized], this.anchorIds(), container);
        if (!container) return;
        const edge = DEFAULTS.UI.MAP_PANEL_EDGE_PX;
        const height = container.clientHeight || container.getBoundingClientRect().height;
        if (!height) return;
        // The new panel remains reachable even when the established stack fills
        // the map. Expansion grows upward from the capped trigger when needed.
        for (const element of [this.panel, this.minimized]) {
            if (!element) continue;
            element.style.maxHeight = `${Math.max(0, height - edge * 2)}px`;
            if (element.hidden) continue;
            const desiredTop = Number.parseFloat(element.style.top) || edge;
            const visibleHeight = element.getBoundingClientRect().height;
            element.style.top = `${Math.max(edge, Math.min(desiredTop, height - visibleHeight - edge))}px`;
        }
    },

    anchorIds() {
        return ['gis-layers-panel', 'gis-layers-panel-minimized', 'gps-tracks-panel',
            'gps-tracks-panel-minimized', 'project-panel', 'project-panel-minimized'];
    },

    setupStackListener() {
        this.observer?.disconnect();
        this.mutations?.disconnect();
        const reposition = Utils.debounce(() => this.positionPanel(), DEFAULTS.UI.MAP_PANEL_POSITION_DELAY_MS);
        this.observer = new ResizeObserver(reposition);
        this.mutations = new MutationObserver(reposition);
        const container = document.getElementById('map');
        if (container) this.observer.observe(container);
        for (const id of this.anchorIds()) {
            const anchor = document.getElementById(id);
            if (!anchor) continue;
            this.observer.observe(anchor);
            this.mutations.observe(anchor, { attributes: true, attributeFilter: ['style', 'class'] });
        }
        this.positionPanel();
    },

    /** data-geometry-id/action are stable row/control hooks for focus and tests. */
    refreshList(focusTarget = null) {
        const list = document.getElementById('gis-geometries-map-list');
        if (!list) return;
        const focused = list.contains(document.activeElement) ? document.activeElement
            : document.activeElement === document.body ? focusTarget : null;
        const focusedId = focused?.closest('[data-geometry-id]')?.dataset.geometryId;
        const focusedAction = focused?.dataset.geometryAction;
        const records = [...Config.gisGeometries].sort((a, b) => a.name.localeCompare(b.name));
        this.rows.clear();
        const notices = [];
        if (Config.gisGeometriesError) {
            const notice = document.createElement('div');
            notice.className = 'gis-geometries-load-error';
            const message = document.createElement('p');
            message.textContent = 'Unable to load your geometries.';
            message.setAttribute('role', 'alert');
            const retry = button('Retry', 'gis-geometries-retry', async () => {
                retry.disabled = true;
                retry.textContent = 'Loading…';
                list.setAttribute('aria-busy', 'true');
                await Config.loadGISGeometries();
                list.removeAttribute('aria-busy');
                this.refreshList();
            });
            retry.setAttribute('aria-label', 'Retry loading GIS Geometries');
            notice.append(message, retry);
            notices.push(notice);
        }
        if (!records.length) {
            if (notices.length) {
                list.replaceChildren(...notices);
                this.positionPanel();
                return;
            }
            const empty = document.createElement('p');
            empty.className = 'gis-geometries-empty';
            empty.textContent = 'No geometries yet. Choose Create Geometry above the map to draw a line or polygon.';
            list.replaceChildren(empty);
            return;
        }
        list.replaceChildren(...notices, ...records.map(record => {
            const editing = State.gisGeometryEditingId === String(record.id);
            const row = document.createElement('div');
            row.className = 'gis-geometries-row';
            row.dataset.geometryId = record.id;
            this.rows.set(String(record.id), row);
            const color = document.createElement('span');
            color.className = 'gis-geometries-color';
            color.style.backgroundColor = Utils.safeCssColor(record.color);
            const name = button(record.name, 'gis-geometries-name', () => this.activateAndZoom(record.id));
            name.dataset.geometryAction = 'zoom';
            name.title = record.name;
            name.disabled = editing;
            const visibility = document.createElement('label');
            visibility.className = 'toggle-switch m-0 scale-75 origin-right';
            const toggle = document.createElement('input');
            toggle.type = 'checkbox';
            toggle.className = 'gis-geometries-visibility';
            toggle.dataset.geometryAction = 'visibility';
            toggle.checked = Layers.isGISGeometryVisible(record.id);
            toggle.disabled = editing;
            toggle.setAttribute('aria-label', `Show ${record.name}`);
            toggle.addEventListener('change', async () => {
                await this.toggleGeometry(record.id, toggle.checked);
            });
            row.append(color, name);
            if (Config.hasGISGeometryAccess(record.id, 'write')) {
                const edit = button(editing ? 'Editing' : 'Edit', 'gis-geometries-edit', async () => {
                    if (await this.editor.edit(record)) this.setExpanded(false);
                });
                edit.disabled = editing;
                edit.dataset.geometryAction = 'edit';
                edit.setAttribute('aria-label', `Edit ${record.name}`);
                row.append(edit);
            }
            const slider = document.createElement('span');
            slider.className = 'toggle-slider';
            visibility.append(toggle, slider);
            row.append(visibility);
            const loading = document.createElement('span');
            loading.className = 'gis-geometries-loading text-xs text-slate-400';
            loading.textContent = 'Updating…';
            loading.hidden = !this.requests.has(String(record.id));
            loading.setAttribute('role', 'status');
            row.append(loading);
            return row;
        }));
        this.positionPanel();
        if (focusedId && focusedAction && !this.panel.hidden) {
            const row = [...list.children].find(element => element.dataset.geometryId === focusedId);
            const replacement = [...(row?.querySelectorAll('[data-geometry-action]') || [])]
                .find(element => element.dataset.geometryAction === focusedAction);
            if (replacement && !replacement.disabled) replacement.focus({ preventScroll: true });
        }
    },

    async activateAndZoom(id) {
        const map = State.map;
        const navigation = beginMapNavigation(map, `gis-geometry:${id}`);
        const shown = await this.toggleGeometry(id, true);
        if (!shown || !navigation.isCurrent() || State.map !== map) return;
        const bounds = State.gisGeometryBounds.get(String(id));
        fitGISGeometry(map, bounds);
    },

    async toggleGeometry(geometryId, visible) {
        const id = String(geometryId);
        const request = {};
        this.requests.set(id, request);
        if (!visible) cancelMapNavigation(`gis-geometry:${id}`);
        const applying = Layers.toggleGISGeometryVisibility(id, visible);
        this.updateRow(id);
        const applied = await applying;
        if (this.requests.get(id) !== request) return false;
        this.requests.delete(id);
        this.updateRow(id);
        return applied;
    },

    updateRow(id) {
        const row = this.rows.get(String(id));
        if (!row) return;
        const editing = State.gisGeometryEditingId === String(id);
        const pending = this.requests.has(String(id));
        const toggle = row.querySelector('.gis-geometries-visibility');
        toggle.checked = Layers.isGISGeometryVisible(id);
        toggle.disabled = editing;
        row.querySelector('.gis-geometries-name').disabled = editing;
        row.querySelector('.gis-geometries-loading').hidden = !pending;
        row.setAttribute('aria-busy', String(pending));
    },

    destroy() {
        this.requests.clear();
        this.rows.forEach((_, id) => cancelMapNavigation(`gis-geometry:${id}`));
        this.rows.clear();
        this.observer?.disconnect();
        this.mutations?.disconnect();
        this.panel?.remove();
        this.minimized?.remove();
        this.panel = null;
        this.minimized = null;
    },
};
