import { Config, DEFAULTS } from '../config.js';
import { Layers } from '../map/layers.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { positionOverlayPanel } from './panel_position.js';
import { fitGISGeometry } from '../map/geometry_camera.js';

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

    init(editor) {
        this.destroy();
        this.editor = editor;
        const container = document.getElementById('map');
        if (!container) return;
        this.panel = document.createElement('section');
        this.panel.id = 'gis-geometries-panel';
        this.panel.className = 'gis-geometries-panel';
        this.panel.setAttribute('aria-label', 'GIS Geometry');
        this.panel.hidden = true;
        const header = document.createElement('header');
        const title = document.createElement('h3');
        title.textContent = 'GIS Geometry';
        const collapse = button('', 'gis-geometries-icon-button', () => this.setExpanded(false));
        collapse.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>';
        collapse.setAttribute('aria-label', 'Minimize GIS Geometry');
        collapse.title = 'Minimize GIS Geometry';
        header.append(title, collapse);
        const list = document.createElement('div');
        list.id = 'gis-geometries-map-list';
        list.className = 'gis-geometries-list';
        this.panel.append(header, list);
        this.minimized = button('', 'gis-geometries-minimized', () => this.setExpanded(true));
        this.minimized.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg><span>GIS Geometry</span>';
        this.minimized.id = 'gis-geometries-panel-minimized';
        this.minimized.setAttribute('aria-label', 'Expand GIS Geometry');
        this.minimized.title = 'Expand GIS Geometry';
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
        const notices = [];
        if (Config.gisGeometriesError) {
            const notice = document.createElement('div');
            notice.className = 'gis-geometries-load-error';
            const message = document.createElement('p');
            message.textContent = 'Unable to load your geometry.';
            message.setAttribute('role', 'alert');
            const retry = button('Retry', 'gis-geometries-retry', async () => {
                retry.disabled = true;
                retry.textContent = 'Loading…';
                list.setAttribute('aria-busy', 'true');
                await Config.loadGISGeometries();
                list.removeAttribute('aria-busy');
                this.refreshList();
            });
            retry.setAttribute('aria-label', 'Retry loading GIS Geometry');
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
            empty.textContent = 'No geometry yet. Choose Create Geometry above the map to draw a line or polygon.';
            list.replaceChildren(empty);
            return;
        }
        list.replaceChildren(...notices, ...records.map(record => {
            const editing = State.gisGeometryEditingId === String(record.id);
            const row = document.createElement('div');
            row.className = 'gis-geometries-row';
            row.dataset.geometryId = record.id;
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
            toggle.disabled = editing || State.gisGeometryLoading.has(record.id);
            toggle.setAttribute('aria-label', `Show ${record.name}`);
            toggle.addEventListener('change', async () => {
                const requested = toggle.checked;
                const hadFocus = document.activeElement === toggle;
                toggle.disabled = true;
                const shown = await Layers.toggleGISGeometryVisibility(record.id, requested);
                this.refreshList(hadFocus ? toggle : null);
                if (requested && !shown) Utils.showNotification('error', `Unable to show ${record.name}.`);
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
        const shown = await Layers.toggleGISGeometryVisibility(id, true);
        this.refreshList();
        if (!shown) {
            Utils.showNotification('error', 'Unable to show this geometry.');
            return;
        }
        const bounds = State.gisGeometryBounds.get(String(id));
        fitGISGeometry(State.map, bounds);
    },

    destroy() {
        this.observer?.disconnect();
        this.mutations?.disconnect();
        this.panel?.remove();
        this.minimized?.remove();
        this.panel = null;
        this.minimized = null;
    },
};
