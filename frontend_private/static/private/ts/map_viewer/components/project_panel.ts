import { isEffectivelyVisible } from '@speleodb/map-core/visibility';
import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { ViewerProject } from '../../../../../../ts-types/domain/map-config.ts';
import { Config, DEFAULTS } from '../config.ts';
import { Layers } from '../map/layers.ts';
import { State } from '../state.ts';
import { Colors } from '../map/colors.ts';
import { Utils } from '../utils.ts';
import { flushPreferenceWrites, schedulePreferenceWrite } from '../display_preference_storage.ts';
import { beginMapNavigation, cancelMapNavigation } from '../map/navigation_intent.ts';

function readRecord(key: string): Record<string, unknown> {
    try {
        const value: unknown = JSON.parse(localStorage.getItem(key) as string);
        return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
    } catch {
        return {};
    }
}

export const ProjectPanel = {
    _countryVisibility: null as Record<string, unknown> | null,
    _collapsedCountries: null as Record<string, unknown> | null,
    _rows: new Map<string, HTMLDivElement>(),
    _groups: new Map<string, { group: HTMLDivElement; projects: ViewerProject[] }>(),

    init: function() {
        this.destroy();
        this.render();
        this.bindEvents();
        this._applyInitialCountryVisibility();
    },

    refreshVisibilityState: function() {
        this.refreshList();
        this._applyInitialCountryVisibility();
    },

    render: function() {
        if (!document.getElementById('project-panel')) {
            const panelHtml = `
            <div id="project-panel" class="absolute top-4 left-4 bg-srgb-slate-800-95 backdrop-blur-xs border-2 border-slate-600 rounded-lg shadow-xl p-4 max-w-xs z-[5]" style="min-width: 250px;">
                <div class="flex justify-between items-center mb-3 border-b border-slate-600 pb-2">
                    <h3 class="text-white font-semibold text-sm">Active Projects</h3>
                    <button id="panel-toggle" class="text-slate-400 hover:text-white transition-colors" title="Minimize">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>
                </div>
                <div id="project-list" class="flow-y-1 overflow-y-auto custom-scrollbar" style="max-height: 400px;">
                </div>
            </div>

            <div id="project-panel-minimized" class="absolute top-4 left-4 bg-srgb-slate-800-95 backdrop-blur-xs border-2 border-slate-600 rounded-lg shadow-xl p-3 z-[5]" style="display: none;">
                <button id="panel-expand" class="text-white hover:text-sky-400 transition-colors flex items-center flow-x-2" title="Expand">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                    </svg>
                    <span class="text-sm font-medium">Projects</span>
                </button>
            </div>
            `;

            const mapContainer = document.querySelector('#map')!.parentElement;
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

    // ── Country collapsed state (UI accordion) ─────────────────────

    _loadCollapsedCountries: function() {
        this._collapsedCountries ??= readRecord(DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED);
        return this._collapsedCountries;
    },

    _saveCollapsedCountries: function(collapsed: Record<string, unknown>) {
        this._collapsedCountries = collapsed;
        schedulePreferenceWrite(DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED, () => this._collapsedCountries);
    },

    // ── Country visibility state (layer gate) ───────────────────────

    _loadCountryVisibility: function() {
        this._countryVisibility ??= readRecord(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY);
        return this._countryVisibility;
    },

    _saveCountryVisibility: function(vis: Record<string, unknown>) {
        this._countryVisibility = vis;
        schedulePreferenceWrite(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY, () => this._countryVisibility);
    },

    isCountryVisible: function(country: string) {
        const vis = this._loadCountryVisibility();
        return vis[country] !== false;
    },

    // ── Effective visibility ────────────────────────────────────────
    // A project is visible on the map only when BOTH its individual
    // toggle AND its country gate are ON.

    _syncCountryToMap: function(country: string, projects: ViewerProject[]) {
        const countryOn = this.isCountryVisible(country);
        void Layers.setProjectVisibilityBatch(projects.map(project => ({
            projectId: project.id,
            visible: isEffectivelyVisible({ individual: Layers.isProjectVisible(project.id), country: countryOn }),
        })));
        if (!countryOn) projects.forEach(project => cancelMapNavigation(`project:${project.id}`));
    },

    /** Explicit navigation opens the country gate without replacing other choices. */
    revealProject: function(projectId: EntityId) {
        const project = Config.getProjectById(projectId);
        if (!project) return;
        const country = project.country || 'Unknown';
        const visibility = this._loadCountryVisibility();
        delete visibility[country];
        this._saveCountryVisibility(visibility);
        Layers.saveProjectVisibilityPref(project.id, true);
        this._syncCountryToMap(country, Config.projects.filter(candidate => (candidate.country || 'Unknown') === country));
        this.updateCountryRows(country);
    },

    _applyInitialCountryVisibility: function() {
        if (!this._hasCountryData(Config.projects)) return;

        const vis = this._loadCountryVisibility();
        const hasHiddenCountries = Object.values(vis).some(v => v === false);
        if (!hasHiddenCountries) return;

        void Layers.setProjectVisibilityBatch(Config.projects
            .filter(project => vis[project.country || 'Unknown'] === false)
            .map(project => ({ projectId: project.id, visible: false })));
    },

    // ── Rendering ───────────────────────────────────────────────────

    _hasCountryData: function(projects: ViewerProject[]) {
        return projects.some(p => p.country);
    },

    refreshList: function() {
        const list = document.getElementById('project-list');
        if (!list) return;

        list.innerHTML = '';
        this._rows.clear();
        this._groups.clear();

        const validProjects = [...Config.projects].sort((a, b) =>
            a.name!.toLowerCase().localeCompare(b.name!.toLowerCase())
        );

        if (!this._hasCountryData(validProjects)) {
            this._renderFlat(list, validProjects);
        } else {
            this._renderGrouped(list, validProjects);
        }
    },

    _renderFlat: function(list: HTMLElement, projects: ViewerProject[]) {
        projects.forEach(project => {
            list.appendChild(this._createProjectRow(project, true));
        });
    },

    _renderGrouped: function(list: HTMLElement, projects: ViewerProject[]) {
        const groups = new Map<string, ViewerProject[]>();
        projects.forEach(project => {
            const country = project.country || 'Unknown';
            if (!groups.has(country)) groups.set(country, []);
            groups.get(country)!.push(project);
        });

        const sortedGroups = [...groups.entries()].sort((a, b) =>
            a[0].toLowerCase().localeCompare(b[0].toLowerCase())
        );

        const collapsed = this._loadCollapsedCountries();

        sortedGroups.forEach(([country, countryProjects]) => {
            const isCollapsed = !!collapsed[country];
            const groupEl = this._createCountryGroup(country, countryProjects, isCollapsed);
            list.appendChild(groupEl);
        });
    },

    _createCountryGroup: function(country: string, projects: ViewerProject[], isCollapsed: boolean) {
        const group = document.createElement('div');
        group.className = 'country-group';
        if (isCollapsed) group.classList.add('collapsed');
        group.dataset.country = country;
        this._groups.set(country, { group, projects });

        const countryOn = this.isCountryVisible(country);
        const flag = Utils.countryFlag(country);

        const header = document.createElement('div');
        header.className = 'country-group-header';
        header.innerHTML = Utils.safeHtml`
            <svg class="country-group-chevron w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
            <span class="country-group-flag">${Utils.raw(flag)}</span>
            <span class="country-group-name">${country}</span>
            <span class="country-group-count">(${Utils.raw(String(projects.length))})</span>
            <label class="toggle-switch m-0 scale-[0.6] origin-right ml-auto">
                <input type="checkbox" class="country-toggle" ${Utils.raw(countryOn ? 'checked' : '')}>
                <span class="toggle-slider"></span>
            </label>
        `;

        const groupToggle = header.querySelector<HTMLInputElement>('.country-toggle');
        if (groupToggle) {
            groupToggle.addEventListener('change', (e) => {
                e.stopPropagation();
                const checked = (e.target as HTMLInputElement).checked;
                const vis = this._loadCountryVisibility();
                if (checked) {
                    delete vis[country];
                } else {
                    vis[country] = false;
                }
                this._saveCountryVisibility(vis);
                this._syncCountryToMap(country, projects);
                this.updateCountryRows(country);
            });

            const toggleLabel = header.querySelector('.toggle-switch');
            if (toggleLabel) {
                toggleLabel.addEventListener('click', (e) => e.stopPropagation());
            }
        }

        header.addEventListener('click', (e) => {
            if ((e.target as Element).closest('.toggle-switch')) return;
            group.classList.toggle('collapsed');
            const current = this._loadCollapsedCountries();
            if (group.classList.contains('collapsed')) {
                current[country] = true;
            } else {
                delete current[country];
            }
            this._saveCollapsedCountries(current);
        });

        const content = document.createElement('div');
        content.className = 'country-group-content';

        projects.forEach(project => {
            content.appendChild(this._createProjectRow(project, countryOn));
        });

        group.appendChild(header);
        group.appendChild(content);
        return group;
    },

    _createProjectRow: function(project: ViewerProject, countryOn: boolean) {
        const individualOn = Layers.isProjectVisible(project.id);
        const effectiveVisible = individualOn && countryOn;
        const color = this.getProjectColor(project.id);

        const item = document.createElement('div');
        item.className = 'project-button flex items-center justify-between bg-srgb-slate-700-50 hover:bg-slate-700 p-2 rounded-sm cursor-pointer transition-all duration-200';
        if (!effectiveVisible) item.classList.add('opacity-50');
        item.dataset.projectId = project.id;
        item.dataset.color = color;
        this._rows.set(String(project.id), item);

        item.innerHTML = Utils.safeHtml`
            <div class="flex items-center gap-2 overflow-hidden flex-1">
                <div class="project-color-dot w-3 h-3 rounded-full shrink-0 shadow-xs" style="background-color: ${Utils.raw(Utils.safeCssColor(effectiveVisible ? color : DEFAULTS.COLORS.FALLBACK))}"></div>
                <span class="text-slate-200 text-sm font-medium truncate select-none">${project.name}</span>
            </div>
            <label class="toggle-switch m-0 scale-75 origin-right">
                <input type="checkbox" ${Utils.raw(individualOn ? 'checked' : '')}>
                <span class="toggle-slider"></span>
            </label>
        `;

        const checkbox = item.querySelector<HTMLInputElement>('input[type="checkbox"]')!;

        // The browser ignores this existing async listener's returned promise.
        item.addEventListener('click', (async (e: MouseEvent) => {
            if (e.target !== checkbox && e.target !== checkbox.nextElementSibling && (e.target as Element).closest('.toggle-switch') === null) {
                const map = State.map;
                const navigation = beginMapNavigation(map, `project:${project.id}`);
                if (document.getElementById('map-viewer-shell')) {
                    this.revealProject(project.id);
                }
                await Layers.whenDisplayApplied();
                if (!navigation.isCurrent() || State.map !== map || !item.isConnected) return;
                const bounds = State.projectBounds.get(String(project.id));
                if (bounds) {
                    map!.fitBounds(bounds, { padding: DEFAULTS.MAP.FIT_BOUNDS_PADDING, maxZoom: DEFAULTS.MAP.FIT_BOUNDS_MAX_ZOOM });
                }
            }
        }) as (event: MouseEvent) => void);

        checkbox.addEventListener('change', (e) => {
            e.stopPropagation();
            this.toggleProject(project.id, (e.target as HTMLInputElement).checked);
        });

        const toggleLabel = item.querySelector('.toggle-switch');
        if (toggleLabel) {
            toggleLabel.addEventListener('click', (e) => e.stopPropagation());
        }

        return item;
    },

    toggleProject: function(projectId: EntityId, isVisible: boolean) {
        const project = Config.getProjectById(projectId);
        const countryOn = !project || this.isCountryVisible(project.country || 'Unknown');
        // Publish only the final visibility so depth domains never include a gated project.
        void Layers.toggleProjectVisibility(projectId, isVisible, isEffectivelyVisible({ individual: isVisible, country: countryOn }));
        if (!isVisible) cancelMapNavigation(`project:${projectId}`);
        this.updateRow(projectId, isVisible);
    },

    updateRow(projectId: EntityId, individualOn = Layers.isProjectVisible(projectId)) {
        const row = this._rows.get(String(projectId));
        if (!row) return;
        const project = Config.getProjectById(projectId);
        const visible = isEffectivelyVisible({ individual: individualOn, country: !project || this.isCountryVisible(project.country || 'Unknown') });
        row.querySelector('input')!.checked = individualOn;
        row.classList.toggle('opacity-50', !visible);
        row.querySelector<HTMLElement>('.project-color-dot')!.style.backgroundColor = Utils.safeCssColor(
            visible ? this.getProjectColor(projectId) : DEFAULTS.COLORS.FALLBACK,
        );
    },

    updateCountryRows(country: string) {
        const entry = this._groups.get(country);
        if (!entry) return;
        entry.group.querySelector<HTMLInputElement>('.country-toggle')!.checked = this.isCountryVisible(country);
        entry.projects.forEach(project => this.updateRow(project.id));
    },

    destroy() {
        flushPreferenceWrites(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY);
        flushPreferenceWrites(DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED);
        this._countryVisibility = null;
        this._collapsedCountries = null;
        this._rows.clear();
        this._groups.clear();
    },

    bindEvents: function() {
        const panel = document.getElementById('project-panel');
        const minimized = document.getElementById('project-panel-minimized');
        const toggleBtn = document.getElementById('panel-toggle');
        const expandBtn = document.getElementById('panel-expand');

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

    getProjectColor: function(projectId: EntityId) {
        return Colors.getProjectColor(projectId);
    }
};
