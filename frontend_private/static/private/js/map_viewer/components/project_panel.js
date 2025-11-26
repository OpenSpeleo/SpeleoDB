import { Config } from '../config.js';
import { Layers } from '../map/layers.js';
import { State } from '../state.js';
import { Colors } from '../map/colors.js';

export const ProjectPanel = {
    init: function() {
        this.render();
        this.bindEvents();
    },

    render: function() {
        // Create Panel Container if not exists
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
                <div id="project-list" class="space-y-2 overflow-y-auto custom-scrollbar" style="max-height: 400px;">
                    <!-- Project buttons will be inserted here -->
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
            
            // Append to map container's RELATIVE parent
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

    refreshList: function() {
        const list = document.getElementById('project-list');
        if (!list) return;

        list.innerHTML = '';
        
        // Show all projects - GeoJSON availability is checked at load time
        const validProjects = Config.projects;
        
        validProjects.forEach(project => {
            const isVisible = Layers.isProjectVisible(project.id);
            const color = this.getProjectColor(project.id);
            
            const item = document.createElement('div');
            item.className = 'project-button flex items-center justify-between bg-slate-700/50 hover:bg-slate-700 p-2 rounded cursor-pointer transition-all duration-200';
            if (!isVisible) item.classList.add('opacity-50');
            item.dataset.projectId = project.id;
            item.dataset.color = color;
            
            item.innerHTML = `
                <div class="flex items-center gap-2 overflow-hidden flex-1">
                    <div class="project-color-dot w-3 h-3 rounded-full shrink-0 shadow-sm" style="background-color: ${isVisible ? color : '#94a3b8'}"></div>
                    <span class="text-slate-200 text-sm font-medium truncate select-none">${project.name}</span>
                </div>
                <label class="toggle-switch m-0 scale-75 origin-right">
                    <input type="checkbox" ${isVisible ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            `;
            
            // Bind Click (Toggle)
            const checkbox = item.querySelector('input[type="checkbox"]');
            
            // Handle card body click (Zoom)
            item.addEventListener('click', (e) => {
                if (e.target !== checkbox && e.target !== checkbox.nextElementSibling && e.target.closest('.toggle-switch') === null) {
                    // Fly to bounds
                    const bounds = State.projectBounds.get(String(project.id));
                    if (bounds) {
                        State.map.fitBounds(bounds, { padding: 50, maxZoom: 16 });
                    }
                }
            });

            // Handle checkbox click (Visibility)
            checkbox.addEventListener('change', (e) => {
                // Prevent bubbling to item click if necessary, but change event is distinct
                e.stopPropagation(); 
                this.toggleProject(project.id, e.target.checked);
            });
            
            // Stop propagation on toggle switch container click to prevent zoom
            const toggleLabel = item.querySelector('.toggle-switch');
            if (toggleLabel) {
                toggleLabel.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            }

            list.appendChild(item);
        });
    },

    toggleProject: function(projectId, isVisible) {
        Layers.toggleProjectVisibility(projectId, isVisible);
        this.refreshList(); // Refresh to update opacity/colors
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
        // Use centralized color assignment from Colors module
        return Colors.getProjectColor(projectId);
    }
};

