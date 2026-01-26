import { StationManager } from './manager.js';
import { State } from '../state.js';
import { Config } from '../config.js';
import { Utils } from '../utils.js';
import { StationDetails } from './details.js';
import { Modal } from '../components/modal.js';
import { Geometry } from '../map/geometry.js';

export const StationUI = {
    openManagerModal() {
        console.log('📋 Opening Station Manager');

        const modal = document.getElementById('station-manager-modal');
        if (!modal) {
            console.error('❌ Station Manager modal element not found!');
            return;
        }

        // Show modal
        modal.classList.remove('hidden');

        // Load content
        this.loadStationManagerContent();

        // Setup close handlers
        const closeBtn = document.getElementById('station-manager-close');
        if (closeBtn) {
            closeBtn.onclick = () => {
                modal.classList.add('hidden');
            };
        }

        // Close on backdrop click
        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        };
    },

    loadStationManagerContent() {
        const content = document.getElementById('station-manager-content');
        if (!content) {
            console.error('❌ station-manager-content element not found!');
            return;
        }

        // Gather all stations organized by project
        const stationsByProject = new Map();
        let totalStations = 0;

        // Organize stations by project
        State.allStations.forEach((station, stationId) => {
            const projectId = station.project;
            if (!stationsByProject.has(projectId)) {
                stationsByProject.set(projectId, []);
            }
            stationsByProject.get(projectId).push(station);
            totalStations++;
        });

        // Build HTML
        let html = `
            <div class="p-6 overflow-y-auto" style="max-height: calc(100vh - 200px);">
                <div class="mb-6">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-lg font-medium text-white">All Stations</h3>
                        <span class="text-sm text-slate-400">${totalStations} station${totalStations !== 1 ? 's' : ''} total</span>
                    </div>
                </div>
        `;

        if (totalStations === 0) {
            html += `
                <div class="text-center py-12">
                    <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                    <h3 class="text-white text-lg font-medium mb-2">No Stations Yet</h3>
                    <p class="text-slate-400">Right-click on the map to create your first station.</p>
                </div>
            `;
        } else {
            // Sort projects by name
            const sortedProjects = Array.from(stationsByProject.entries()).sort((a, b) => {
                const projectA = Config.projects.find(p => p.id === a[0]);
                const projectB = Config.projects.find(p => p.id === b[0]);
                const nameA = projectA?.name || 'Unknown Project';
                const nameB = projectB?.name || 'Unknown Project';
                return nameA.localeCompare(nameB);
            });

            // Display stations organized by project
            sortedProjects.forEach(([projectId, projectStations]) => {
                const project = Config.projects.find(p => p.id === projectId);
                const projectName = project?.name || 'Unknown Project';

                // Sort stations by name
                projectStations.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

                html += `
                    <div class="mb-6">
                        <h4 class="text-md font-semibold text-white mb-3 flex items-center">
                            <svg class="w-5 h-5 mr-2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                            </svg>
                            ${projectName}
                            <span class="ml-2 text-sm text-slate-400 font-normal">(${projectStations.length} station${projectStations.length !== 1 ? 's' : ''})</span>
                        </h4>
                        <div class="space-y-2">
                `;

                projectStations.forEach(station => {
                    // Get tag color for marker or use default
                    const markerColor = (station.tag && station.tag.color) ? station.tag.color : '#fb923c';
                    
                    // Station type badge
                    const typeLabels = {
                        'science': { label: 'Science', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.science}" class="w-3.5 h-3.5 align-middle">`, color: 'bg-orange-500/20 text-orange-300 border-orange-500/30' },
                        'biology': { label: 'Biology', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.biology}" class="w-3.5 h-3.5 align-middle">`, color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' },
                        'artifact': { label: 'Artifact', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.artifact}" class="w-3.5 h-3.5 align-middle">`, color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
                        'bone': { label: 'Bones', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.bone}" class="w-3.5 h-3.5 align-middle">`, color: 'bg-slate-500/20 text-slate-200 border-slate-400/30' },
                        'geology': { label: 'Geology', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.geology}" class="w-3.5 h-3.5 align-middle">`, color: 'bg-stone-500/20 text-stone-300 border-stone-500/30' }
                    };
                    const stationType = station.type || 'science';
                    const typeInfo = typeLabels[stationType] || typeLabels['science'];
                    const typeBadge = `<span class="text-xs px-1.5 py-0.5 rounded border ${typeInfo.color}">${typeInfo.icon}</span>`;
                    
                    html += `
                        <div class="bg-slate-700/50 rounded-lg p-3 hover:bg-slate-700 transition-colors group">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-3 flex-1 cursor-pointer" data-station-id="${station.id}" data-project-id="${projectId}">
                                    <div class="w-3 h-3 rounded-full border-2 border-white shadow-md flex-shrink-0" style="background: ${markerColor};"></div>
                                    <div class="flex-1">
                                        <div class="flex items-center gap-2 flex-wrap">
                                            ${typeBadge}
                                            <h5 class="text-white font-medium">${station.name}</h5>
                                            ${station.tag && station.tag.name && station.tag.color ? `
                                                <span class="station-tag text-xs" style="background-color: ${station.tag.color}; padding: 2px 8px;">
                                                    ${station.tag.name}
                                                </span>
                                            ` : ''}
                                        </div>
                                        <p class="text-xs text-slate-400">
                                            ${Number(station.latitude).toFixed(5)}, ${Number(station.longitude).toFixed(5)}
                                            ${station.snapped_to_line ? `• <span class="text-sky-400">📍 ${station.snapped_to_line}</span>` : ''}
                                        </p>
                                    </div>
                                </div>
                                <div class="flex items-center space-x-2">
                                    <button class="p-1.5 text-slate-400 hover:text-sky-400 hover:bg-slate-600 rounded transition-all go-to-station-btn" 
                                            data-station-id="${station.id}"
                                            data-lat="${Number(station.latitude)}"
                                            data-lon="${Number(station.longitude)}"
                                            title="Go to station on map">
                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                                        </svg>
                                    </button>
                                    <svg class="w-5 h-5 text-slate-400 group-hover:text-white transition-colors cursor-pointer open-station-btn"
                                        data-station-id="${station.id}"
                                        data-project-id="${projectId}"
                                        fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                                    </svg>
                                </div>
                            </div>
                        </div>
                    `;
                });

                html += `
                        </div>
                    </div>
                `;
            });
        }

        html += '</div>';
        content.innerHTML = html;

        // Attach event listeners
        content.querySelectorAll('[data-station-id]').forEach(el => {
            el.addEventListener('click', (e) => {
                // Check if it's a go-to button
                if (e.target.closest('.go-to-station-btn')) {
                    const btn = e.target.closest('.go-to-station-btn');
                    const stationId = btn.dataset.stationId;
                    const lat = parseFloat(btn.dataset.lat);
                    const lon = parseFloat(btn.dataset.lon);
                    e.stopPropagation();
                    if (window.goToStation) {
                        window.goToStation(stationId, lat, lon);
                    }
                    return;
                }
                
                // Open station details
                const stationId = el.dataset.stationId;
                const projectId = el.dataset.projectId;
                if (stationId) {
                    document.getElementById('station-manager-modal').classList.add('hidden');
                    StationDetails.openModal(stationId, projectId);
                }
            });
        });
    },

    /**
     * Show modal to create a new station
     * @param {Array} coordinates - [lng, lat] coordinates
     * @param {string} projectId - Project ID
     * @param {string} stationType - Station type: 'science', 'artifact', or 'bone'
     */
    showCreateStationModal(coordinates, projectId, stationType = 'science') {
        // Snap to nearest vertex (start/end point) within radius
        const snap = Geometry.findNearestSnapPointWithinRadius(coordinates, Geometry.getSnapRadius());
        
        if (!snap.snapped) {
            Utils.showNotification('warning', "Can't create a station at this location. Too far from survey line endpoints.");
            return;
        }
        
        // Use snapped coordinates and detected project
        const snappedCoords = snap.coordinates;
        const detectedProjectId = snap.projectId || projectId;
        
        // Determine title and icon based on station type
        const typeLabels = {
            'science': { label: 'Science Station', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.science}" class="w-6 h-6">`, color: 'text-orange-400' },
            'biology': { label: 'Biology Station', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.biology}" class="w-6 h-6">`, color: 'text-cyan-400' },
            'artifact': { label: 'Artifact Station', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.artifact}" class="w-6 h-6">`, color: 'text-amber-400' },
            'bone': { label: 'Bones Station', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.bone}" class="w-6 h-6">`, color: 'text-slate-200' },
            'geology': { label: 'Geology Station', icon: `<img src="${window.MAPVIEWER_CONTEXT.icons.geology}" class="w-6 h-6">`, color: 'text-stone-400' }
        };
        const typeInfo = typeLabels[stationType] || typeLabels['science'];
        
        const formHtml = `
            <form id="create-station-form" class="space-y-4">
                <div class="flex items-center gap-3 mb-4 p-3 bg-slate-700/50 rounded-lg border border-slate-600/50">
                    <span class="text-2xl">${typeInfo.icon}</span>
                    <div>
                        <div class="text-white font-medium">${typeInfo.label}</div>
                        <div class="text-xs text-slate-400">Type cannot be changed after creation</div>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                    <input type="text" id="station-name" required class="form-input" placeholder="Enter station name">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                    <textarea id="station-description" rows="3" class="form-input form-textarea" placeholder="Description"></textarea>
                </div>
                <div class="bg-slate-700/50 rounded-lg p-3 text-sm text-slate-300">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-green-400">🧲</span>
                        <span>Snapped to: ${snap.lineName || 'Survey Line'} (${snap.pointType} point)</span>
                    </div>
                    <div class="text-xs text-slate-400 mt-1">
                        Distance: ${snap.distance.toFixed(1)}m | Lat: ${snappedCoords[1].toFixed(7)}, Lon: ${snappedCoords[0].toFixed(7)}
                    </div>
                </div>
            </form>
        `;

        const footer = `
            <button data-close-modal="create-station-modal" class="btn-secondary">Cancel</button>
            <button form="create-station-form" type="submit" class="btn-primary">Create ${typeInfo.label}</button>
        `;

        const html = Modal.base('create-station-modal', `Create ${typeInfo.label}`, formHtml, footer, 'max-w-md');

        Modal.open('create-station-modal', html, () => {
            document.getElementById('station-name').focus();
            
            document.getElementById('create-station-form').onsubmit = async (e) => {
                e.preventDefault();
                const name = document.getElementById('station-name').value.trim();
                if (!name) return;
                
                try {
                    const station = await StationManager.createStation(detectedProjectId, {
                        name,
                        description: document.getElementById('station-description').value.trim(),
                        latitude: snappedCoords[1],
                        longitude: snappedCoords[0],
                        type: stationType
                    });
                    Utils.showNotification('success', `${typeInfo.label} created!`);
                    Modal.close('create-station-modal');
                    StationDetails.openModal(station.id, detectedProjectId, true);
                } catch (err) {
                    Utils.showNotification('error', err.message);
                }
            };
        });
    },
    
    showDragConfirmModal(snapResult, onConfirm, onCancel) {
        const content = `
            <p class="text-slate-300 mb-4">Move station to new location?</p>
            ${snapResult ? `<div class="bg-emerald-900/30 text-emerald-400 px-3 py-1 rounded-full text-xs inline-block border border-emerald-500/30">Snapped to line</div>` : ''}
        `;
        
        const footer = `
            <button id="drag-cancel-btn" class="btn-secondary">Cancel</button>
            <button id="drag-confirm-btn" class="btn-primary">Move</button>
        `;
        
        const html = Modal.base('drag-confirm-modal', 'Confirm Move', content, footer, 'max-w-sm');
        
        Modal.open('drag-confirm-modal', html, () => {
            document.getElementById('drag-cancel-btn').onclick = () => {
                Modal.close('drag-confirm-modal');
                if (onCancel) onCancel();
            };
            document.getElementById('drag-confirm-btn').onclick = () => {
                Modal.close('drag-confirm-modal');
                if (onConfirm) onConfirm();
            };
        });
    }
};
