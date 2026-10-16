import { renderPencilIcon } from '../../../../../../frontend_common/presentation/icons.ts';
import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { GeometryPanelEditor } from '../../../../../../ts-types/domain/map-panels.ts';
import { Config } from '../config.ts';
import { Layers } from '../map/layers.ts';
import { State } from '../state.ts';
import { Utils } from '../utils.ts';
import { registerMapPanel, setMapPanelExpanded, unregisterMapPanel } from './panel_stack.ts';
import { fitGISGeometry } from '../map/geometry_camera.ts';
import { beginMapNavigation, cancelMapNavigation } from '../map/navigation_intent.ts';

function button(label: string, className: string, action?: (event: MouseEvent) => unknown) {
    const element = document.createElement('button');
    element.type = 'button';
    element.className = className;
    element.textContent = label;
    if (action) element.addEventListener('click', action);
    return element;
}

export const GISGeometriesPanel = {
    editor: null as GeometryPanelEditor | null,
    panel: null as HTMLElement | null,
    minimized: null as HTMLButtonElement | null,
    rows: new Map<string, HTMLDivElement>(),
    requests: new Map<string, object>(),

    init(editor: GeometryPanelEditor) {
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
        const collapse = button('', 'gis-geometries-icon-button');
        collapse.id = 'gis-geometries-panel-toggle';
        collapse.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>';
        collapse.setAttribute('aria-label', 'Minimize GIS Geometries');
        collapse.title = 'Minimize GIS Geometries';
        header.append(title, collapse);
        const list = document.createElement('div');
        list.id = 'gis-geometries-map-list';
        list.className = 'gis-geometries-list';
        this.panel.append(header, list);
        this.minimized = button('', 'gis-geometries-minimized');
        this.minimized.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg><span>GIS Geometries</span>';
        this.minimized.id = 'gis-geometries-panel-minimized';
        this.minimized.setAttribute('aria-label', 'Expand GIS Geometries');
        this.minimized.title = 'Expand GIS Geometries';
        this.minimized.setAttribute('aria-expanded', 'false');
        this.minimized.setAttribute('aria-controls', this.panel.id);
        container.append(this.panel, this.minimized);
        this.refreshList();
        registerMapPanel(this.panel.id, this.minimized.id, collapse.id);
    },

    setExpanded(expanded: boolean) {
        setMapPanelExpanded('gis-geometries-panel', expanded);
    },

    /** data-geometry-id/action are stable row/control hooks for focus and tests. */
    refreshList(focusTarget: HTMLElement | null = null) {
        const list = document.getElementById('gis-geometries-map-list');
        if (!list) return;
        const focused = list.contains(document.activeElement) ? document.activeElement as HTMLElement
            : document.activeElement === document.body ? focusTarget : null;
        const focusedId = focused?.closest<HTMLElement>('[data-geometry-id]')?.dataset.geometryId;
        const focusedAction = focused?.dataset.geometryAction;
        const records = [...Config.gisGeometries].sort((a, b) => a.name!.localeCompare(b.name!, undefined, { sensitivity: 'base' }));
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
            const name = button(record.name!, 'gis-geometries-name', () => this.activateAndZoom(record.id));
            name.dataset.geometryAction = 'zoom';
            name.title = record.name!;
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
            toggle.addEventListener('change', (async () => {
                await this.toggleGeometry(record.id, toggle.checked);
            }) as EventListener);
            row.append(color, name);
            const actions = document.createElement('div');
            actions.className = 'gis-geometries-actions';
            if (Config.hasGISGeometryAccess(record.id, 'write')) {
                const edit = button('', 'gis-geometries-edit', async () => {
                    if (await this.editor!.edit(record)) this.setExpanded(false);
                });
                edit.innerHTML = renderPencilIcon();
                edit.title = editing ? `Editing ${record.name}` : `Edit ${record.name}`;
                edit.disabled = editing;
                edit.dataset.geometryAction = 'edit';
                edit.setAttribute('aria-label', `Edit ${record.name}`);
                actions.append(edit);
            }
            const slider = document.createElement('span');
            slider.className = 'toggle-slider';
            visibility.append(toggle, slider);
            actions.append(visibility);
            row.append(actions);
            const loading = document.createElement('span');
            loading.className = 'gis-geometries-loading text-xs text-slate-400';
            loading.textContent = 'Updating…';
            loading.hidden = !this.requests.has(String(record.id));
            loading.setAttribute('role', 'status');
            row.append(loading);
            return row;
        }));
        if (focusedId && focusedAction && !this.panel!.hidden) {
            const row = [...list.children].find(element => (element as HTMLElement).dataset.geometryId === focusedId);
            const replacement = [...(row?.querySelectorAll<HTMLInputElement | HTMLButtonElement>('[data-geometry-action]') || [])]
                .find(element => element.dataset.geometryAction === focusedAction);
            if (replacement && !replacement.disabled) replacement.focus({ preventScroll: true });
        }
    },

    async activateAndZoom(id: EntityId) {
        const map = State.map;
        const navigation = beginMapNavigation(map, `gis-geometry:${id}`);
        const shown = await this.toggleGeometry(id, true);
        if (!shown || !navigation.isCurrent() || State.map !== map) return;
        const bounds = State.gisGeometryBounds.get(String(id));
        fitGISGeometry(map!, bounds);
    },

    async toggleGeometry(geometryId: EntityId, visible: boolean) {
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

    updateRow(id: EntityId) {
        const row = this.rows.get(String(id));
        if (!row) return;
        const editing = State.gisGeometryEditingId === String(id);
        const pending = this.requests.has(String(id));
        const toggle = row.querySelector<HTMLInputElement>('.gis-geometries-visibility')!;
        toggle.checked = Layers.isGISGeometryVisible(id);
        toggle.disabled = editing;
        row.querySelector<HTMLButtonElement>('.gis-geometries-name')!.disabled = editing;
        row.querySelector<HTMLElement>('.gis-geometries-loading')!.hidden = !pending;
        row.setAttribute('aria-busy', String(pending));
    },

    destroy() {
        this.requests.clear();
        this.rows.forEach((_, id) => cancelMapNavigation(`gis-geometry:${id}`));
        this.rows.clear();
        unregisterMapPanel('gis-geometries-panel');
        this.panel?.remove();
        this.minimized?.remove();
        this.panel = null;
        this.minimized = null;
    },
};
