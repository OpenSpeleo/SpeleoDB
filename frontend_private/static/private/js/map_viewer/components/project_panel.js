import { Config, DEFAULTS } from '../config.js';
import { Layers } from '../map/layers.js';
import { State } from '../state.js';
import { Colors } from '../map/colors.js';
import { Utils } from '../utils.js';

export const ProjectPanel = {
    init: function() {
        this.render();
        this.bindEvents();
        this._applyInitialCountryVisibility();
    },

    render: function() {
        if (!document.getElementById('project-panel')) {
            const panelHtml = `
            <div id="project-panel" class="absolute top-4 left-4 bg-slate-800/95 backdrop-blur-sm border-2 border-slate-600 rounded-lg shadow-xl p-4 max-w-xs z-[5]" style="min-width: 250px;">
                <div class="flex justify-between items-center mb-3 border-b border-slate-600 pb-2">
                    <h3 class="text-white font-semibold text-sm">Active Projects</h3>
                    <button id="panel-toggle" class="text-slate-400 hover:text-white transition-colors" title="Minimize">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>
                </div>
                <div id="project-list" class="space-y-1 overflow-y-auto custom-scrollbar" style="max-height: 400px;">
                </div>
            </div>
            
            <div id="project-panel-minimized" class="absolute top-4 left-4 bg-slate-800/95 backdrop-blur-sm border-2 border-slate-600 rounded-lg shadow-xl p-3 z-[5]" style="display: none;">
                <button id="panel-expand" class="text-white hover:text-sky-400 transition-colors flex items-center space-x-2" title="Expand">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                    </svg>
                    <span class="text-sm font-medium">Projects</span>
                </button>
            </div>
            `;
            
            const mapContainer = document.querySelector('#map').parentElement;
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
        try {
            const data = localStorage.getItem(DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED);
            if (!data) return {};
            const parsed = JSON.parse(data);
            return (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) ? parsed : {};
        } catch (e) {
            return {};
        }
    },

    _saveCollapsedCountries: function(collapsed) {
        try {
            localStorage.setItem(DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED, JSON.stringify(collapsed));
        } catch (e) {
            // localStorage unavailable
        }
    },

    // ── Country visibility state (layer gate) ───────────────────────

    _loadCountryVisibility: function() {
        try {
            const data = localStorage.getItem(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY);
            if (!data) return {};
            const parsed = JSON.parse(data);
            return (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) ? parsed : {};
        } catch (e) {
            return {};
        }
    },

    _saveCountryVisibility: function(vis) {
        try {
            localStorage.setItem(DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY, JSON.stringify(vis));
        } catch (e) {
            // localStorage unavailable
        }
    },

    isCountryVisible: function(country) {
        const vis = this._loadCountryVisibility();
        return vis[country] !== false;
    },

    // ── Effective visibility ────────────────────────────────────────
    // A project is visible on the map only when BOTH its individual
    // toggle AND its country gate are ON.

    _syncProjectToMap: function(project) {
        const country = project.country || 'Unknown';
        const individualOn = Layers.isProjectVisible(project.id);
        const countryOn = this.isCountryVisible(country);
        const effective = individualOn && countryOn;

        Layers.applyProjectVisibility(project.id, effective);
    },

    _syncCountryToMap: function(country, projects) {
        const countryOn = this.isCountryVisible(country);
        projects.forEach(p => {
            const individualOn = Layers.isProjectVisible(p.id);
            Layers.applyProjectVisibility(p.id, individualOn && countryOn);
        });
        Layers.recomputeActiveDepthDomain();
        if (Layers.colorMode === 'depth') {
            Layers.applyDepthLineColors();
        }
    },

    _applyInitialCountryVisibility: function() {
        if (!this._hasCountryData(Config.projects)) return;

        const vis = this._loadCountryVisibility();
        const hasHiddenCountries = Object.values(vis).some(v => v === false);
        if (!hasHiddenCountries) return;

        Config.projects.forEach(p => {
            const country = p.country || 'Unknown';
            if (vis[country] === false) {
                Layers.applyProjectVisibility(p.id, false);
            }
        });
        Layers.recomputeActiveDepthDomain();
        if (Layers.colorMode === 'depth') {
            Layers.applyDepthLineColors();
        }
    },

    // ── Rendering ───────────────────────────────────────────────────

    _hasCountryData: function(projects) {
        return projects.some(p => p.country);
    },

    refreshList: function() {
        const list = document.getElementById('project-list');
        if (!list) return;

        list.innerHTML = '';

        const validProjects = [...Config.projects].sort((a, b) =>
            a.name.toLowerCase().localeCompare(b.name.toLowerCase())
        );

        if (!this._hasCountryData(validProjects)) {
            this._renderFlat(list, validProjects);
        } else {
            this._renderGrouped(list, validProjects);
        }
    },

    _renderFlat: function(list, projects) {
        projects.forEach(project => {
            list.appendChild(this._createProjectRow(project, true));
        });
    },

    _renderGrouped: function(list, projects) {
        const groups = new Map();
        projects.forEach(project => {
            const country = project.country || 'Unknown';
            if (!groups.has(country)) groups.set(country, []);
            groups.get(country).push(project);
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

    _createCountryGroup: function(country, projects, isCollapsed) {
        const group = document.createElement('div');
        group.className = 'country-group';
        if (isCollapsed) group.classList.add('collapsed');
        group.dataset.country = country;

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

        const groupToggle = header.querySelector('.country-toggle');
        if (groupToggle) {
            groupToggle.addEventListener('change', (e) => {
                e.stopPropagation();
                const checked = e.target.checked;
                const vis = this._loadCountryVisibility();
                if (checked) {
                    delete vis[country];
                } else {
                    vis[country] = false;
                }
                this._saveCountryVisibility(vis);
                this._syncCountryToMap(country, projects);
                this.refreshList();
            });

            const toggleLabel = header.querySelector('.toggle-switch');
            if (toggleLabel) {
                toggleLabel.addEventListener('click', (e) => e.stopPropagation());
            }
        }

        header.addEventListener('click', (e) => {
            if (e.target.closest('.toggle-switch')) return;
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

    _createProjectRow: function(project, countryOn) {
        const individualOn = Layers.isProjectVisible(project.id);
        const effectiveVisible = individualOn && countryOn;
        const color = this.getProjectColor(project.id);

        const item = document.createElement('div');
        item.className = 'project-button flex items-center justify-between bg-slate-700/50 hover:bg-slate-700 p-2 rounded cursor-pointer transition-all duration-200';
        if (!effectiveVisible) item.classList.add('opacity-50');
        item.dataset.projectId = project.id;
        item.dataset.color = color;

        item.innerHTML = Utils.safeHtml`
            <div class="flex items-center gap-2 overflow-hidden flex-1">
                <div class="project-color-dot w-3 h-3 rounded-full shrink-0 shadow-sm" style="background-color: ${Utils.raw(Utils.safeCssColor(effectiveVisible ? color : DEFAULTS.COLORS.FALLBACK))}"></div>
                <span class="text-slate-200 text-sm font-medium truncate select-none">${project.name}</span>
            </div>
            <label class="toggle-switch m-0 scale-75 origin-right">
                <input type="checkbox" ${Utils.raw(individualOn ? 'checked' : '')}>
                <span class="toggle-slider"></span>
            </label>
        `;

        const checkbox = item.querySelector('input[type="checkbox"]');

        item.addEventListener('click', (e) => {
            if (e.target !== checkbox && e.target !== checkbox.nextElementSibling && e.target.closest('.toggle-switch') === null) {
                const bounds = State.projectBounds.get(String(project.id));
                if (bounds) {
                    State.map.fitBounds(bounds, { padding: DEFAULTS.MAP.FIT_BOUNDS_PADDING, maxZoom: DEFAULTS.MAP.FIT_BOUNDS_MAX_ZOOM });
                }
            }
        });

        checkbox.addEventListener('change', (e) => {
            e.stopPropagation();
            this.toggleProject(project.id, e.target.checked);
        });

        const toggleLabel = item.querySelector('.toggle-switch');
        if (toggleLabel) {
            toggleLabel.addEventListener('click', (e) => e.stopPropagation());
        }

        return item;
    },

    toggleProject: function(projectId, isVisible) {
        // Save individual preference (always persisted regardless of country gate)
        Layers.toggleProjectVisibility(projectId, isVisible);

        // If country is OFF, override map back to hidden
        const project = Config.getProjectById(projectId);
        if (project) {
            this._syncProjectToMap(project);
        }

        this.refreshList();
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

    getProjectColor: function(projectId) {
        return Colors.getProjectColor(projectId);
    }
};
