import { SurfaceStationManager } from './manager.js';
import { State } from '../state.js';
import { Config } from '../config.js';
import { Utils } from '../utils.js';
import { StationDetails } from '../stations/details.js';
import { Modal } from '../components/modal.js';

export const SurfaceStationUI = {
    openManagerModal() {
        console.log('📋 Opening Surface Station Manager');

        const modal = document.getElementById('surface-station-manager-modal');
        if (!modal) {
            console.error('❌ Surface Station Manager modal element not found!');
            return;
        }

        // Show modal
        modal.classList.remove('hidden');

        // Load content
        this.loadSurfaceStationManagerContent();

        // Setup close handlers
        const closeBtn = document.getElementById('surface-station-manager-close');
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

    loadSurfaceStationManagerContent() {
        const content = document.getElementById('surface-station-manager-content');
        if (!content) {
            console.error('❌ surface-station-manager-content element not found!');
            return;
        }

        // Gather all surface stations organized by network
        const stationsByNetwork = new Map();
        let totalStations = 0;

        // Organize stations by network
        State.allSurfaceStations.forEach((station, stationId) => {
            const networkId = station.network;
            if (!stationsByNetwork.has(networkId)) {
                stationsByNetwork.set(networkId, []);
            }
            stationsByNetwork.get(networkId).push(station);
            totalStations++;
        });

        // Build HTML
        let html = `
            <div class="p-6 overflow-y-auto" style="max-height: calc(100vh - 200px);">
                <div class="mb-6">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-lg font-medium text-white">All Surface Stations</h3>
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
                    <h3 class="text-white text-lg font-medium mb-2">No Surface Stations Yet</h3>
                    <p class="text-slate-400 mb-4">Create your first surface station by clicking the button below.</p>
                    ${this.getCreateStationButtons()}
                </div>
            `;
        } else {
            // Add create station buttons at top
            html += this.getCreateStationButtons();
            html += '<div class="mt-4"></div>';

            // Sort networks by name
            const sortedNetworks = Array.from(stationsByNetwork.entries()).sort((a, b) => {
                const networkA = Config.networks.find(n => n.id === a[0]);
                const networkB = Config.networks.find(n => n.id === b[0]);
                const nameA = networkA?.name || 'Unknown Network';
                const nameB = networkB?.name || 'Unknown Network';
                return nameA.localeCompare(nameB);
            });

            // Display stations organized by network
            sortedNetworks.forEach(([networkId, networkStations]) => {
                const network = Config.networks.find(n => n.id === networkId);
                const networkName = network?.name || 'Unknown Network';

                // Sort stations by name
                networkStations.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

                html += `
                    <div class="mb-6">
                        <h4 class="text-md font-semibold text-white mb-3 flex items-center">
                            <svg class="w-5 h-5 mr-2 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                            </svg>
                            ${networkName}
                            <span class="ml-2 text-sm text-slate-400 font-normal">(${networkStations.length} station${networkStations.length !== 1 ? 's' : ''})</span>
                        </h4>
                        <div class="space-y-2">
                `;

                networkStations.forEach(station => {
                    // Get tag color for marker or use default
                    const markerColor = (station.tag && station.tag.color) ? station.tag.color : '#fb923c';

                    html += `
                        <div class="bg-slate-700/50 rounded-lg p-3 hover:bg-slate-700 transition-colors group">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-3 flex-1 cursor-pointer" data-station-id="${station.id}" data-network-id="${networkId}">
                                    <div class="w-3 h-3 flex-shrink-0 border-2 border-white shadow-md" style="background: ${markerColor}; transform: rotate(45deg);"></div>
                                    <div class="flex-1">
                                        <div class="flex items-center gap-2 flex-wrap">
                                            <h5 class="text-white font-medium">${station.name}</h5>
                                            ${station.tag && station.tag.name && station.tag.color ? `
                                                <span class="station-tag text-xs" style="background-color: ${station.tag.color}; padding: 2px 8px;">
                                                    ${station.tag.name}
                                                </span>
                                            ` : ''}
                                        </div>
                                        <p class="text-xs text-slate-400">
                                            ${Number(station.latitude).toFixed(5)}, ${Number(station.longitude).toFixed(5)}
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
                                        data-network-id="${networkId}"
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
                const networkId = el.dataset.networkId;
                if (stationId) {
                    document.getElementById('surface-station-manager-modal').classList.add('hidden');
                    StationDetails.openModal(stationId, networkId, false, 'surface');
                }
            });
        });

        // Attach create station button listener
        const createBtn = content.querySelector('#open-create-surface-station-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => {
                this.showCreateStationModal();
            });
        }
    },

    getCreateStationButtons() {
        const networks = Config.networks.filter(n => Config.hasNetworkAccess(n.id, 'write'));

        if (networks.length === 0) {
            return '<p class="text-sm text-slate-500">You need write access to a network to create surface stations.</p>';
        }

        // Single button that opens the create modal
        return `
            <button id="open-create-surface-station-btn" class="btn bg-emerald-600 hover:bg-emerald-700 text-white" style="width: 14rem;">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                </svg>
                Create Surface Station
            </button>
        `;
    },

    showCreateStationModal(preselectedNetworkId = null) {
        // Get networks with write access
        const networks = Config.networks.filter(n => Config.hasNetworkAccess(n.id, 'write'));

        if (networks.length === 0) {
            Utils.showNotification('error', 'You need write access to a network to create surface stations.');
            return;
        }

        // Build network dropdown options
        const networkOptionsHtml = networks.map(n => {
            const selected = (preselectedNetworkId && n.id === preselectedNetworkId) || (networks.length === 1);
            return `<option value="${n.id}" ${selected ? 'selected' : ''}>${n.name}</option>`;
        }).join('');

        const formHtml = `
            <form id="create-surface-station-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Monitoring Network *</label>
                    <select id="surface-station-network" required class="form-select w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:border-emerald-500 focus:outline-none" style="background-image: url(&quot;data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%2394a3b8' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e&quot;); background-position: right 0.75rem center; background-repeat: no-repeat; background-size: 1.25rem 1.25rem; padding-right: 2.5rem;">
                        <option value="">Select a network...</option>
                        ${networkOptionsHtml}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                    <input type="text" id="surface-station-name" required class="form-input" placeholder="Enter station name">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                    <textarea id="surface-station-description" rows="3" class="form-input form-textarea" placeholder="Description"></textarea>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Latitude *</label>
                        <input type="number" id="surface-station-latitude" required step="any" min="-90" max="90" class="form-input" placeholder="-90 to 90">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Longitude *</label>
                        <input type="number" id="surface-station-longitude" required step="any" min="-180" max="180" class="form-input" placeholder="-180 to 180">
                    </div>
                </div>
            </form>
        `;

        const footer = `
            <button data-close-modal="create-surface-station-modal" class="btn-secondary">Cancel</button>
            <button form="create-surface-station-form" type="submit" class="btn bg-emerald-600 hover:bg-emerald-700 text-white">Create Station</button>
        `;

        const html = Modal.base('create-surface-station-modal', 'Create Surface Station', formHtml, footer, 'max-w-md');

        Modal.open('create-surface-station-modal', html, () => {
            // Focus on network dropdown if multiple networks, otherwise on name
            if (networks.length > 1 && !preselectedNetworkId) {
                document.getElementById('surface-station-network').focus();
            } else {
                document.getElementById('surface-station-name').focus();
            }

            document.getElementById('create-surface-station-form').onsubmit = async (e) => {
                e.preventDefault();

                const networkId = document.getElementById('surface-station-network').value;
                const name = document.getElementById('surface-station-name').value.trim();
                const latitude = parseFloat(document.getElementById('surface-station-latitude').value);
                const longitude = parseFloat(document.getElementById('surface-station-longitude').value);

                if (!networkId) {
                    Utils.showNotification('error', 'Please select a monitoring network.');
                    return;
                }
                if (!name) return;
                if (isNaN(latitude) || latitude < -90 || latitude > 90) {
                    Utils.showNotification('error', 'Invalid latitude. Must be between -90 and 90.');
                    return;
                }
                if (isNaN(longitude) || longitude < -180 || longitude > 180) {
                    Utils.showNotification('error', 'Invalid longitude. Must be between -180 and 180.');
                    return;
                }

                try {
                    const station = await SurfaceStationManager.createStation(networkId, {
                        name,
                        description: document.getElementById('surface-station-description').value.trim(),
                        latitude,
                        longitude
                    });
                    Utils.showNotification('success', 'Surface station created!');
                    
                    // Close both the create modal and the surface station manager
                    Modal.close('create-surface-station-modal');
                    const managerModal = document.getElementById('surface-station-manager-modal');
                    if (managerModal) {
                        managerModal.classList.add('hidden');
                    }
                    
                    // Open station details
                    StationDetails.openModal(station.id, networkId, true, 'surface');
                } catch (err) {
                    Utils.showNotification('error', err.message || 'Failed to create surface station');
                }
            };
        });
    }
};

