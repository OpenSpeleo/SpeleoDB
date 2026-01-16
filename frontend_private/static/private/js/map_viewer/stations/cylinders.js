/**
 * Cylinder Installation Management Module
 * 
 * Handles cylinder installs at geographic locations including:
 * - Listing available fleets and cylinders
 * - Installing cylinders at locations
 * - Managing pressure checks
 * - Retrieving/uninstalling cylinders
 */

import { API } from '../api.js';
import { Config } from '../config.js';
import { Utils } from '../utils.js';
import { Modal } from '../components/modal.js';

// Cache for cylinder fleets and their cylinders
let fleetCache = {};
let fleetCylindersCache = {};

// Track event listeners for cleanup
let fleetSelectHandler = null;
let cylinderSelectHandler = null;

/**
 * Escape HTML to prevent XSS attacks
 */
function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Format gas mix display based on O2 and He percentages
 * Matches the logic from cylinder_table.html
 */
function formatGasMix(o2Percentage, hePercentage) {
    if (o2Percentage === 100) {
        return 'Oxygen';
    } else if (hePercentage === 0) {
        return `NX${o2Percentage}`;
    } else {
        return `${o2Percentage}/${hePercentage}`;
    }
}

/**
 * Open the cylinder modal
 */
function openCylinderModal(title = 'Safety Cylinder') {
    const modal = document.getElementById('cylinder-modal');
    const titleEl = document.getElementById('cylinder-modal-title');
    
    if (modal) {
        modal.classList.remove('hidden');
    }
    if (titleEl) {
        titleEl.innerHTML = `
            <img src="${window.SPELEO_CONTEXT.icons.cylinderOrange}" class="w-6 h-6">
            ${escapeHtml(title)}
        `;
    }
}

/**
 * Close the cylinder modal
 */
function closeCylinderModal() {
    const modal = document.getElementById('cylinder-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Store the current project ID for cylinder installation
let pendingInstallProjectId = null;

/**
 * Show cylinder installation modal
 */
async function showInstallModal(coordinates, locationName = '', projectId = null) {
    const container = document.getElementById('cylinder-modal-content');
    if (!container) return;

    // Store the project ID for later use
    pendingInstallProjectId = projectId;

    container.innerHTML = `
        <div class="space-y-4">
            <div id="cylinder-install-loading" class="text-center py-8">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-400 mx-auto mb-3"></div>
                <p class="text-slate-400">Loading available cylinders...</p>
            </div>
            
            <div id="cylinder-install-form" class="hidden space-y-4">
                <!-- Hidden coordinates and project -->
                <input type="hidden" id="install-latitude" value="${coordinates[1].toFixed(7)}">
                <input type="hidden" id="install-longitude" value="${coordinates[0].toFixed(7)}">
                <input type="hidden" id="install-project-id" value="${projectId || ''}">
                
                <!-- Fleet Selection -->
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                        Cylinder Fleet <span class="text-rose-500">*</span>
                    </label>
                    <select id="cylinder-fleet-select" 
                        class="form-select w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500">
                        <option value="">Select a fleet...</option>
                    </select>
                </div>
                
                <!-- Cylinder Selection -->
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                        Cylinder <span class="text-rose-500">*</span>
                    </label>
                    <select id="cylinder-select" 
                        class="form-select w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500"
                        disabled>
                        <option value="">Select a fleet first...</option>
                    </select>
                    <p id="cylinder-info" class="text-xs text-slate-500 mt-1"></p>
                </div>
                
                <!-- Location Name -->
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                        Location Name <span class="text-rose-500">*</span>
                    </label>
                    <input type="text" id="install-location-name" 
                        value="${escapeHtml(locationName)}"
                        class="form-input w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500"
                        placeholder="e.g., Wakulla Spring Cave - Station A1">
                </div>
                
                <!-- Install Date -->
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                        Install Date <span class="text-rose-500">*</span>
                    </label>
                    <input type="date" id="install-date" 
                        value="${new Date().toISOString().split('T')[0]}"
                        class="form-input w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500">
                </div>
                
                <!-- Distance from Entry (optional) -->
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">
                            Distance from Entry
                        </label>
                        <input type="number" id="install-distance" 
                            min="0" step="1"
                            class="form-input w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500"
                            placeholder="Optional">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">
                            Unit
                        </label>
                        <select id="install-unit-system" 
                            class="form-select w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500">
                            <option value="metric">Meters</option>
                            <option value="imperial">Feet</option>
                        </select>
                    </div>
                </div>
                
                <!-- Notes (optional) -->
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                        Notes
                    </label>
                    <textarea id="install-notes" rows="1"
                        class="form-textarea w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500"
                        placeholder="Optional notes..."></textarea>
                </div>
                
                <!-- Action Buttons -->
                <div class="flex justify-end gap-3 pt-4 border-t border-slate-700">
                    <button type="button" onclick="window.CylinderInstalls.closeModal()"
                        class="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors">
                        Cancel
                    </button>
                    <button type="button" onclick="window.CylinderInstalls.handleInstall()"
                        class="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors flex items-center gap-2">
                        <img src="${window.SPELEO_CONTEXT.icons.cylinderOrange}" class="w-4 h-4 filter brightness-200">
                        Install Cylinder
                    </button>
                </div>
            </div>
            
            <div id="cylinder-no-fleets" class="hidden text-center py-8">
                <svg class="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z">
                    </path>
                </svg>
                <p class="text-slate-400 text-lg mb-2">No Cylinder Fleets Available</p>
                <p class="text-slate-500 text-sm">You need access to at least one cylinder fleet to install cylinders.</p>
                <a href="/private/cylinder-fleets/" 
                    class="inline-block mt-4 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 transition-colors">
                    Manage Cylinder Fleets
                </a>
            </div>
        </div>
    `;

    // Store coordinates for later use
    window._pendingCylinderCoordinates = coordinates;

    // Open the cylinder modal
    openCylinderModal('Install Safety Cylinder');

    // Load fleets
    await loadFleets();
}

/**
 * Load available cylinder fleets
 */
async function loadFleets() {
    try {
        const response = await API.getCylinderFleets();
        const fleets = response.data || [];

        const loadingEl = document.getElementById('cylinder-install-loading');
        const formEl = document.getElementById('cylinder-install-form');
        const noFleetsEl = document.getElementById('cylinder-no-fleets');

        if (!fleets.length) {
            loadingEl?.classList.add('hidden');
            noFleetsEl?.classList.remove('hidden');
            return;
        }

        // Cache fleets
        fleets.forEach(fleet => {
            fleetCache[fleet.id] = fleet;
        });

        // Populate fleet dropdown
        const fleetSelect = document.getElementById('cylinder-fleet-select');
        if (fleetSelect) {
            fleetSelect.innerHTML = '<option value="">Select a fleet...</option>' +
                fleets.map(fleet => `
                    <option value="${fleet.id}">
                        ${escapeHtml(fleet.name)} (${fleet.cylinder_count || 0} cylinders)
                    </option>
                `).join('');

            // Remove previous handler to prevent memory leak
            if (fleetSelectHandler) {
                fleetSelect.removeEventListener('change', fleetSelectHandler);
            }
            
            // Add change handler
            fleetSelectHandler = (e) => {
                loadFleetCylinders(e.target.value);
            };
            fleetSelect.addEventListener('change', fleetSelectHandler);
        }

        loadingEl?.classList.add('hidden');
        formEl?.classList.remove('hidden');

    } catch (error) {
        console.error('Failed to load cylinder fleets:', error);
        Utils.showNotification('error', 'Failed to load cylinder fleets');
    }
}

/**
 * Load cylinders for a specific fleet
 */
async function loadFleetCylinders(fleetId) {
    const cylinderSelect = document.getElementById('cylinder-select');
    const cylinderInfo = document.getElementById('cylinder-info');
    
    if (!fleetId) {
        if (cylinderSelect) {
            cylinderSelect.innerHTML = '<option value="">Select a fleet first...</option>';
            cylinderSelect.disabled = true;
        }
        if (cylinderInfo) cylinderInfo.textContent = '';
        return;
    }

    // Show loading state
    if (cylinderSelect) {
        cylinderSelect.innerHTML = '<option value="">Loading cylinders...</option>';
        cylinderSelect.disabled = true;
    }

    try {
        // Check cache first
        if (!fleetCylindersCache[fleetId]) {
            const response = await API.getCylinderFleetCylinders(fleetId);
            fleetCylindersCache[fleetId] = response.data || [];
        }

        const cylinders = fleetCylindersCache[fleetId];
        
        // Filter to only show available (not installed) cylinders
        const availableCylinders = cylinders.filter(c => 
            !c.active_installs || c.active_installs.length === 0
        );

        if (cylinderSelect) {
            if (availableCylinders.length === 0) {
                cylinderSelect.innerHTML = '<option value="">No available cylinders in this fleet</option>';
                cylinderSelect.disabled = true;
            } else {
                cylinderSelect.innerHTML = '<option value="">Select a cylinder...</option>' +
                    availableCylinders.map(cyl => {
                        const gasInfo = formatGasMix(cyl.o2_percentage, cyl.he_percentage);
                        const pressureUnit = cyl.unit_system === 'imperial' ? 'PSI' : 'BAR';
                        return `<option value="${cyl.id}" 
                            data-o2="${cyl.o2_percentage}"
                            data-he="${cyl.he_percentage}"
                            data-pressure="${cyl.pressure}"
                            data-unit="${cyl.unit_system}">
                            ${escapeHtml(cyl.name || cyl.serial || 'Unnamed')} (${gasInfo}) - ${cyl.pressure} ${pressureUnit}
                        </option>`;
                    }).join('');
                cylinderSelect.disabled = false;
            }

            // Remove previous handler to prevent memory leak
            if (cylinderSelectHandler) {
                cylinderSelect.removeEventListener('change', cylinderSelectHandler);
            }

            // Add change handler for cylinder info
            cylinderSelectHandler = (e) => {
                const option = e.target.selectedOptions[0];
                if (option && option.value) {
                    const o2 = option.dataset.o2;
                    const he = option.dataset.he;
                    const n2 = 100 - o2 - he;
                    const pressure = option.dataset.pressure;
                    const unit = option.dataset.unit === 'imperial' ? 'PSI' : 'BAR';
                    if (cylinderInfo) {
                        cylinderInfo.textContent = `Gas mix: ${o2}% O₂ / ${he}% He / ${n2}% N₂ • Pressure: ${pressure} ${unit}`;
                    }
                } else {
                    if (cylinderInfo) cylinderInfo.textContent = '';
                }
            };
            cylinderSelect.addEventListener('change', cylinderSelectHandler);
        }

    } catch (error) {
        console.error('Failed to load fleet cylinders:', error);
        if (cylinderSelect) {
            cylinderSelect.innerHTML = '<option value="">Failed to load cylinders</option>';
        }
        Utils.showNotification('error', 'Failed to load cylinders');
    }
}

/**
 * Handle cylinder installation
 */
async function handleInstall() {
    const hiddenProjectId = document.getElementById('install-project-id')?.value;
    let projectId = hiddenProjectId || pendingInstallProjectId;
    
    // Guard against invalid project IDs (string "null" or "undefined")
    if (!projectId || projectId === 'null' || projectId === 'undefined') {
        projectId = null;
    }
    
    const cylinderId = document.getElementById('cylinder-select')?.value;
    const locationName = document.getElementById('install-location-name')?.value?.trim();
    const latitude = document.getElementById('install-latitude')?.value;
    const longitude = document.getElementById('install-longitude')?.value;
    const installDate = document.getElementById('install-date')?.value;
    const distance = document.getElementById('install-distance')?.value;
    const unitSystem = document.getElementById('install-unit-system')?.value;
    const notes = document.getElementById('install-notes')?.value?.trim();

    // Validation
    if (!projectId) {
        Utils.showNotification('error', 'No project context available. Please try again from the map.');
        return;
    }
    if (!cylinderId) {
        Utils.showNotification('error', 'Please select a cylinder');
        return;
    }
    if (!locationName) {
        Utils.showNotification('error', 'Please enter a location name');
        return;
    }
    if (!installDate) {
        Utils.showNotification('error', 'Please enter an install date');
        return;
    }

    const loadingOverlay = Utils.showLoadingOverlay('Installing cylinder...');

    try {
        const installData = {
            project: projectId,
            cylinder: cylinderId,
            latitude: latitude,
            longitude: longitude,
            location_name: locationName,
            install_date: installDate,
            unit_system: unitSystem || 'metric',
        };

        if (distance) {
            installData.distance_from_entry = parseInt(distance, 10);
        }
        if (notes) {
            installData.notes = notes;
        }

        const response = await API.createCylinderInstall(installData);

        Utils.hideLoadingOverlay(loadingOverlay);
        Utils.showNotification('success', 'Cylinder installed successfully!');

        // Clear cache to force reload
        fleetCylindersCache = {};

        // Close modal
        closeCylinderModal();

        // Refresh cylinder layer on map
        refreshCylinderInstallsOnMap();

    } catch (error) {
        Utils.hideLoadingOverlay(loadingOverlay);
        console.error('Failed to install cylinder:', error);
        Utils.showNotification('error', error.message || 'Failed to install cylinder');
    }
}

/**
 * Show cylinder details modal (for clicking on installed cylinder)
 */
async function showCylinderDetails(installId) {
    const container = document.getElementById('cylinder-modal-content');
    if (!container) return;

    container.innerHTML = `
        <div class="flex items-center justify-center py-8">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-400"></div>
        </div>
    `;

    // Open the cylinder modal
    openCylinderModal('Cylinder Details');

    try {
        const response = await API.getCylinderInstallDetails(installId);
        const install = response.data;

        renderCylinderDetails(install);

    } catch (error) {
        console.error('Failed to load cylinder details:', error);
        container.innerHTML = `
            <div class="text-center text-rose-400">
                <p>Failed to load cylinder details</p>
            </div>
        `;
    }
}

/**
 * Render cylinder details with tabs
 */
function renderCylinderDetails(install) {
    const container = document.getElementById('cylinder-modal-content');
    if (!container) return;

    const isInstalled = install.status === 'installed';
    const statusColors = {
        'installed': 'bg-emerald-500/20 text-emerald-400',
        'retrieved': 'bg-sky-500/20 text-sky-400',
        'lost': 'bg-rose-500/20 text-rose-400',
        'abandoned': 'bg-amber-500/20 text-amber-400'
    };

    container.innerHTML = `
        <div class="space-y-5">
            <!-- Header -->
            <div class="flex items-center">
                <div>
                    <h3 class="text-lg font-semibold text-white">${escapeHtml(install.cylinder_name) || 'Unnamed Cylinder'}</h3>
                    <p class="text-slate-400 text-sm">${escapeHtml(install.location_name) || 'Unknown location'}</p>
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-1 ${statusColors[install.status] || 'bg-slate-500/20 text-slate-400'}">
                        ${escapeHtml(install.status?.toUpperCase() || 'UNKNOWN')}
                    </span>
                </div>
            </div>

            <!-- Sub-tabs for cylinder details -->
            <div class="flex space-x-2 border-b border-slate-600">
                <button class="cylinder-subtab px-4 py-2 text-sm font-medium text-sky-400 border-b-2 border-sky-400"
                    data-subtab="info" onclick="window.CylinderInstalls.switchTab('info', '${escapeHtml(install.id)}')">
                    Cylinder Info
                </button>
                <button class="cylinder-subtab px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-300"
                    data-subtab="pressure" onclick="window.CylinderInstalls.switchTab('pressure', '${escapeHtml(install.id)}')">
                    Pressure Checks (${install.pressure_check_count || 0})
                </button>
            </div>

            <!-- Tab Content -->
            <div id="cylinder-tab-content">
                ${renderCylinderInfoTab(install)}
            </div>
        </div>
    `;
}

/**
 * Switch between cylinder detail tabs
 */
function switchTab(tabName, installId) {
    // Update tab styling
    document.querySelectorAll('.cylinder-subtab').forEach(btn => {
        if (btn.dataset.subtab === tabName) {
            btn.classList.remove('text-slate-400', 'hover:text-slate-300');
            btn.classList.add('text-sky-400', 'border-b-2', 'border-sky-400');
        } else {
            btn.classList.remove('text-sky-400', 'border-b-2', 'border-sky-400');
            btn.classList.add('text-slate-400', 'hover:text-slate-300');
        }
    });

    const contentEl = document.getElementById('cylinder-tab-content');
    if (!contentEl) return;

    if (tabName === 'info') {
        // Re-fetch and render info tab
        API.getCylinderInstallDetails(installId).then(response => {
            contentEl.innerHTML = renderCylinderInfoTab(response.data);
        });
    } else if (tabName === 'pressure') {
        renderPressureChecksTab(installId, contentEl);
    }
}

/**
 * Render cylinder info tab content
 */
function renderCylinderInfoTab(install) {
    const pressureUnit = install.cylinder_unit_system === 'imperial' ? 'PSI' : 'BAR';
    const distanceUnit = install.unit_system === 'imperial' ? 'ft' : 'm';
    const isInstalled = install.status === 'installed';

    return `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Cylinder Info -->
            <div class="bg-slate-700/50 rounded-lg p-4">
                <h4 class="text-sm font-medium text-slate-400 mb-3">Cylinder Information</h4>
                <div class="space-y-2">
                    <div class="flex justify-between">
                        <span class="text-slate-400">Name:</span>
                        <span class="text-white">${escapeHtml(install.cylinder_name) || 'N/A'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Serial:</span>
                        <span class="text-white">${escapeHtml(install.cylinder_serial) || 'N/A'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Fleet:</span>
                        <span class="text-white">${escapeHtml(install.cylinder_fleet_name) || 'N/A'}</span>
                    </div>
                </div>
            </div>

            <!-- Location Info -->
            <div class="bg-slate-700/50 rounded-lg p-4">
                <h4 class="text-sm font-medium text-slate-400 mb-3">Installation Details</h4>
                <div class="space-y-2">
                    <div class="flex justify-between">
                        <span class="text-slate-400">Project:</span>
                        <span class="text-white">${escapeHtml(install.project_name) || 'N/A'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Install Date:</span>
                        <span class="text-white">${escapeHtml(install.install_date) || 'N/A'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Installed By:</span>
                        <span class="text-white">${escapeHtml(install.install_user) || 'N/A'}</span>
                    </div>
                    ${install.distance_from_entry ? `
                    <div class="flex justify-between">
                        <span class="text-slate-400">Distance:</span>
                        <span class="text-white">${escapeHtml(install.distance_from_entry)} ${distanceUnit}</span>
                    </div>
                    ` : ''}
                </div>
            </div>

            <!-- Coordinates -->
            <div class="bg-slate-700/50 rounded-lg p-4">
                <h4 class="text-sm font-medium text-slate-400 mb-3">Coordinates</h4>
                <div class="space-y-2">
                    <div class="flex justify-between">
                        <span class="text-slate-400">Latitude:</span>
                        <span class="text-white font-mono">${escapeHtml(install.latitude)}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Longitude:</span>
                        <span class="text-white font-mono">${escapeHtml(install.longitude)}</span>
                    </div>
                </div>
            </div>

            <!-- Notes -->
            ${install.notes ? `
            <div class="bg-slate-700/50 rounded-lg p-4">
                <h4 class="text-sm font-medium text-slate-400 mb-3">Notes</h4>
                <p class="text-white text-sm">${escapeHtml(install.notes)}</p>
            </div>
            ` : ''}
        </div>

        ${isInstalled ? `
        <!-- Actions -->
        <div class="flex flex-wrap justify-end gap-2 pt-6 border-t border-slate-700">
            <button type="button" onclick="window.CylinderInstalls.markAsRetrieved('${escapeHtml(install.id)}')"
                class="px-3 py-2 bg-emerald-500 text-white text-sm rounded-lg hover:bg-emerald-600 transition-colors">
                Mark as Retrieved
            </button>
            <button type="button" onclick="window.CylinderInstalls.markAsAbandoned('${escapeHtml(install.id)}')"
                class="px-3 py-2 bg-slate-500 text-white text-sm rounded-lg hover:bg-slate-600 transition-colors">
                Mark as Abandoned
            </button>
            <button type="button" onclick="window.CylinderInstalls.markAsLost('${escapeHtml(install.id)}')"
                class="px-3 py-2 bg-amber-500 text-white text-sm rounded-lg hover:bg-amber-600 transition-colors">
                Mark as Lost
            </button>
        </div>
        ` : ''}
    `;
}

/**
 * Render pressure checks tab
 */
async function renderPressureChecksTab(installId, contentEl) {
    contentEl.innerHTML = `
        <div class="flex items-center justify-center py-8">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-400"></div>
        </div>
    `;

    try {
        const response = await API.getCylinderPressureChecks(installId);
        const checks = response.data || [];

        contentEl.innerHTML = `
            <div class="space-y-4">
                <!-- Add new check button -->
                <div class="flex justify-between items-center">
                    <h4 class="text-lg font-medium text-white">Pressure Check History</h4>
                    <button type="button" onclick="window.CylinderInstalls.showAddPressureCheck('${escapeHtml(installId)}')"
                        class="px-3 py-1.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 transition-colors flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                        </svg>
                        Record Pressure
                    </button>
                </div>

                ${checks.length === 0 ? `
                    <div class="text-center py-8 bg-slate-700/30 rounded-lg">
                        <svg class="w-12 h-12 mx-auto text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z">
                            </path>
                        </svg>
                        <p class="text-slate-400">No pressure checks recorded yet</p>
                    </div>
                ` : `
                    <div class="overflow-x-auto">
                        <table class="w-full text-sm">
                            <thead class="bg-slate-700/50">
                                <tr>
                                    <th class="px-4 py-2 text-left text-slate-300">Date</th>
                                    <th class="px-4 py-2 text-left text-slate-300">Pressure</th>
                                    <th class="px-4 py-2 text-left text-slate-300">Checked By</th>
                                    <th class="px-4 py-2 text-left text-slate-300">Notes</th>
                                    <th class="px-4 py-2 text-right text-slate-300">Actions</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-700">
                                ${checks.map(check => {
                                    const unit = check.unit_system === 'imperial' ? 'PSI' : 'BAR';
                                    // Use check_date if available, fallback to creation_date
                                    const checkDate = check.check_date 
                                        ? new Date(check.check_date).toLocaleDateString()
                                        : new Date(check.creation_date).toLocaleDateString();
                                    // Escape user-controlled fields to prevent XSS
                                    const safeUser = escapeHtml(check.user) || 'Unknown';
                                    const safeNotes = escapeHtml(check.notes) || '-';
                                    const safeCheckId = escapeHtml(check.id);
                                    return `
                                        <tr class="hover:bg-slate-700/30">
                                            <td class="px-4 py-3 text-white">${checkDate}</td>
                                            <td class="px-4 py-3 text-white font-mono">${check.pressure} ${unit}</td>
                                            <td class="px-4 py-3 text-slate-400">${safeUser}</td>
                                            <td class="px-4 py-3 text-slate-400 max-w-xs truncate">${safeNotes}</td>
                                            <td class="px-4 py-3 text-right">
                                                <button onclick="window.CylinderInstalls.editPressureCheck('${escapeHtml(installId)}', '${safeCheckId}')"
                                                    class="text-sky-400 hover:text-sky-300 mr-2" title="Edit">
                                                    <svg class="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                                            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z">
                                                        </path>
                                                    </svg>
                                                </button>
                                                <button onclick="window.CylinderInstalls.deletePressureCheck('${escapeHtml(installId)}', '${safeCheckId}')"
                                                    class="text-rose-400 hover:text-rose-300" title="Delete">
                                                    <svg class="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16">
                                                        </path>
                                                    </svg>
                                                </button>
                                            </td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                `}
            </div>
        `;

    } catch (error) {
        console.error('Failed to load pressure checks:', error);
        contentEl.innerHTML = `
            <div class="text-center py-8 text-rose-400">
                <p>Failed to load pressure checks</p>
            </div>
        `;
    }
}

/**
 * Show add pressure check form
 */
function showAddPressureCheck(installId) {
    const contentEl = document.getElementById('cylinder-tab-content');
    if (!contentEl) return;

    const today = new Date().toISOString().split('T')[0];

    contentEl.innerHTML = `
        <div class="bg-slate-700/50 rounded-lg p-6 space-y-4">
            <h4 class="text-lg font-medium text-white">Record Pressure Check</h4>
            
            <div class="grid grid-cols-3 gap-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                        Check Date <span class="text-rose-500">*</span>
                    </label>
                    <input type="date" id="new-check-date" value="${today}" required
                        class="form-input w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                        Pressure <span class="text-rose-500">*</span>
                    </label>
                    <input type="number" id="new-check-pressure" min="0" required
                        class="form-input w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500"
                        placeholder="e.g., 2800">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                        Unit <span class="text-rose-500">*</span>
                    </label>
                    <select id="new-check-unit" 
                        class="form-select w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500">
                        <option value="imperial">PSI</option>
                        <option value="metric">BAR</option>
                    </select>
                </div>
            </div>
            
            <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Notes</label>
                <textarea id="new-check-notes" rows="1"
                    class="form-textarea w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500"
                    placeholder="Optional notes..."></textarea>
            </div>
            
            <div class="flex justify-end gap-3">
                <button type="button" onclick="window.CylinderInstalls.switchTab('pressure', '${escapeHtml(installId)}')"
                    class="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-500 transition-colors">
                    Cancel
                </button>
                <button type="button" onclick="window.CylinderInstalls.savePressureCheck('${escapeHtml(installId)}')"
                    class="px-4 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors">
                    Save Check
                </button>
            </div>
        </div>
    `;
}

/**
 * Save new pressure check
 */
async function savePressureCheck(installId) {
    const checkDate = document.getElementById('new-check-date')?.value;
    const pressure = document.getElementById('new-check-pressure')?.value;
    const unitSystem = document.getElementById('new-check-unit')?.value;
    const notes = document.getElementById('new-check-notes')?.value?.trim();

    if (!checkDate) {
        Utils.showNotification('error', 'Please select a check date');
        return;
    }
    if (!pressure) {
        Utils.showNotification('error', 'Please enter a pressure value');
        return;
    }

    const loadingOverlay = Utils.showLoadingOverlay('Recording pressure check...');

    try {
        await API.createCylinderPressureCheck(installId, {
            check_date: checkDate,
            pressure: parseInt(pressure, 10),
            unit_system: unitSystem,
            notes: notes || ''
        });

        Utils.hideLoadingOverlay(loadingOverlay);
        Utils.showNotification('success', 'Pressure check recorded!');

        // Refresh tab
        const contentEl = document.getElementById('cylinder-tab-content');
        if (contentEl) renderPressureChecksTab(installId, contentEl);

    } catch (error) {
        Utils.hideLoadingOverlay(loadingOverlay);
        console.error('Failed to save pressure check:', error);
        Utils.showNotification('error', error.message || 'Failed to save pressure check');
    }
}

/**
 * Show edit pressure check form
 */
async function editPressureCheck(installId, checkId) {
    const contentEl = document.getElementById('cylinder-tab-content');
    if (!contentEl) return;

    // Show loading state
    contentEl.innerHTML = `
        <div class="flex items-center justify-center py-8">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-400"></div>
        </div>
    `;

    try {
        const response = await API.getCylinderPressureCheckDetails(installId, checkId);
        const check = response.data;

        const safeInstallId = escapeHtml(installId);
        const safeCheckId = escapeHtml(checkId);

        // Get the check_date or fallback to today
        const checkDateValue = check.check_date || new Date().toISOString().split('T')[0];

        contentEl.innerHTML = `
            <div class="bg-slate-700/50 rounded-lg p-6 space-y-4">
                <h4 class="text-lg font-medium text-white">Edit Pressure Check</h4>
                
                <div class="grid grid-cols-3 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">
                            Check Date <span class="text-rose-500">*</span>
                        </label>
                        <input type="date" id="edit-check-date" value="${checkDateValue}" required
                            class="form-input w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">
                            Pressure <span class="text-rose-500">*</span>
                        </label>
                        <input type="number" id="edit-check-pressure" min="0" required
                            value="${check.pressure || ''}"
                            class="form-input w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500"
                            placeholder="e.g., 2800">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">
                            Unit <span class="text-rose-500">*</span>
                        </label>
                        <select id="edit-check-unit" 
                            class="form-select w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500">
                            <option value="imperial" ${check.unit_system === 'imperial' ? 'selected' : ''}>PSI</option>
                            <option value="metric" ${check.unit_system === 'metric' ? 'selected' : ''}>BAR</option>
                        </select>
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Notes</label>
                    <textarea id="edit-check-notes" rows="1"
                        class="form-textarea w-full bg-slate-700 border-slate-600 text-white rounded-lg focus:border-sky-500"
                        placeholder="Optional notes...">${escapeHtml(check.notes || '')}</textarea>
                </div>
                
                <div class="flex justify-end gap-3">
                    <button type="button" onclick="window.CylinderInstalls.switchTab('pressure', '${safeInstallId}')"
                        class="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-500 transition-colors">
                        Cancel
                    </button>
                    <button type="button" onclick="window.CylinderInstalls.updatePressureCheck('${safeInstallId}', '${safeCheckId}')"
                        class="px-4 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors">
                        Save Changes
                    </button>
                </div>
            </div>
        `;

    } catch (error) {
        console.error('Failed to load pressure check:', error);
        contentEl.innerHTML = `
            <div class="text-center py-8 text-rose-400">
                <p>Failed to load pressure check</p>
                <button type="button" onclick="window.CylinderInstalls.switchTab('pressure', '${escapeHtml(installId)}')"
                    class="mt-4 px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-500 transition-colors">
                    Back to List
                </button>
            </div>
        `;
    }
}

/**
 * Update an existing pressure check
 */
async function updatePressureCheck(installId, checkId) {
    const checkDate = document.getElementById('edit-check-date')?.value;
    const pressure = document.getElementById('edit-check-pressure')?.value;
    const unitSystem = document.getElementById('edit-check-unit')?.value;
    const notes = document.getElementById('edit-check-notes')?.value?.trim();

    if (!checkDate) {
        Utils.showNotification('error', 'Please select a check date');
        return;
    }
    if (!pressure) {
        Utils.showNotification('error', 'Please enter a pressure value');
        return;
    }

    const loadingOverlay = Utils.showLoadingOverlay('Updating pressure check...');

    try {
        await API.updateCylinderPressureCheck(installId, checkId, {
            check_date: checkDate,
            pressure: parseInt(pressure, 10),
            unit_system: unitSystem,
            notes: notes || ''
        });

        Utils.hideLoadingOverlay(loadingOverlay);
        Utils.showNotification('success', 'Pressure check updated!');

        // Refresh tab
        const contentEl = document.getElementById('cylinder-tab-content');
        if (contentEl) renderPressureChecksTab(installId, contentEl);

    } catch (error) {
        Utils.hideLoadingOverlay(loadingOverlay);
        console.error('Failed to update pressure check:', error);
        Utils.showNotification('error', error.message || 'Failed to update pressure check');
    }
}

/**
 * Delete pressure check
 */
async function deletePressureCheck(installId, checkId) {
    if (!confirm('Are you sure you want to delete this pressure check?')) return;

    const loadingOverlay = Utils.showLoadingOverlay('Deleting...');

    try {
        await API.deleteCylinderPressureCheck(installId, checkId);

        Utils.hideLoadingOverlay(loadingOverlay);
        Utils.showNotification('success', 'Pressure check deleted');

        // Refresh tab
        const contentEl = document.getElementById('cylinder-tab-content');
        if (contentEl) renderPressureChecksTab(installId, contentEl);

    } catch (error) {
        Utils.hideLoadingOverlay(loadingOverlay);
        console.error('Failed to delete pressure check:', error);
        Utils.showNotification('error', error.message || 'Failed to delete pressure check');
    }
}

/**
 * Show styled confirmation modal for status change
 */
function showStatusConfirmModal(installId, status, config) {
    const modalId = 'cylinder-status-confirm-modal';
    
    const content = `
        <div class="text-center">
            <div class="w-16 h-16 rounded-full ${config.iconBg} flex items-center justify-center mx-auto mb-4">
                <svg class="w-10 h-10 ${config.iconColor}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    ${config.iconPath}
                </svg>
            </div>
            <h3 class="text-xl font-bold text-white mb-2">${config.title}</h3>
            <p class="text-slate-300 mb-2">${config.message}</p>
            ${config.warning ? `<p class="text-amber-300 text-sm">${config.warning}</p>` : ''}
        </div>
    `;

    const footer = `
        <button data-close-modal="${modalId}" class="btn-secondary px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg transition-colors">
            Cancel
        </button>
        <button id="confirm-status-change-btn" class="px-4 py-2 ${config.buttonClass} text-white rounded-lg transition-colors flex items-center gap-2">
            <span id="status-btn-text">${config.buttonText}</span>
            <span id="status-btn-loading" class="hidden">
                <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </span>
        </button>
    `;

    const html = Modal.base(modalId, 'Confirm Status Change', content, footer, 'max-w-md');
    
    Modal.open(modalId, html, () => {
        const confirmBtn = document.getElementById('confirm-status-change-btn');
        if (confirmBtn) {
            confirmBtn.onclick = async () => {
                const btnText = document.getElementById('status-btn-text');
                const btnLoading = document.getElementById('status-btn-loading');
                
                // Show loading state
                if (btnText) btnText.classList.add('hidden');
                if (btnLoading) btnLoading.classList.remove('hidden');
                confirmBtn.disabled = true;

                try {
                    await API.updateCylinderInstall(installId, { status });

                    Modal.close(modalId);
                    Utils.showNotification('success', config.successMessage);

                    // Close cylinder modal and refresh map
                    closeCylinderModal();
                    refreshCylinderInstallsOnMap();

                } catch (error) {
                    console.error('Failed to update cylinder:', error);
                    Utils.showNotification('error', error.message || 'Failed to update cylinder');
                    
                    // Reset button state
                    if (btnText) btnText.classList.remove('hidden');
                    if (btnLoading) btnLoading.classList.add('hidden');
                    confirmBtn.disabled = false;
                }
            };
        }
    });
}

/**
 * Mark cylinder as retrieved
 */
function markAsRetrieved(installId) {
    showStatusConfirmModal(installId, 'retrieved', {
        title: 'Mark as Retrieved?',
        message: 'This cylinder will be marked as successfully retrieved from the cave.',
        warning: null,
        iconBg: 'bg-emerald-900/30',
        iconColor: 'text-emerald-400',
        iconPath: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>',
        buttonClass: 'bg-emerald-500 hover:bg-emerald-600',
        buttonText: 'Mark Retrieved',
        successMessage: 'Cylinder marked as retrieved'
    });
}

/**
 * Mark cylinder as abandoned
 */
function markAsAbandoned(installId) {
    showStatusConfirmModal(installId, 'abandoned', {
        title: 'Mark as Abandoned?',
        message: 'This cylinder will remain in the cave but will no longer be actively monitored.',
        warning: '⚠️ The cylinder location will still be visible for reference.',
        iconBg: 'bg-slate-700/50',
        iconColor: 'text-slate-400',
        iconPath: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path>',
        buttonClass: 'bg-slate-500 hover:bg-slate-600',
        buttonText: 'Mark Abandoned',
        successMessage: 'Cylinder marked as abandoned'
    });
}

/**
 * Mark cylinder as lost
 */
function markAsLost(installId) {
    showStatusConfirmModal(installId, 'lost', {
        title: 'Mark as Lost?',
        message: 'This indicates the cylinder cannot be located and may not be recoverable.',
        warning: '⚠️ This should only be used when the cylinder truly cannot be found.',
        iconBg: 'bg-amber-900/30',
        iconColor: 'text-amber-400',
        iconPath: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>',
        buttonClass: 'bg-amber-500 hover:bg-amber-600',
        buttonText: 'Mark Lost',
        successMessage: 'Cylinder marked as lost'
    });
}

/**
 * Refresh cylinder installs on map
 */
function refreshCylinderInstallsOnMap() {
    // Dispatch event that main.js listens for
    document.dispatchEvent(new CustomEvent('speleo:refresh-cylinder-installs'));
}

/**
 * Clear caches
 */
function clearCache() {
    fleetCache = {};
    fleetCylindersCache = {};
}

// Export module
export const CylinderInstalls = {
    showInstallModal,
    showCylinderDetails,
    handleInstall,
    switchTab,
    showAddPressureCheck,
    savePressureCheck,
    deletePressureCheck,
    editPressureCheck,
    updatePressureCheck,
    markAsRetrieved,
    markAsAbandoned,
    markAsLost,
    closeModal: closeCylinderModal,
    clearCache
};

// Set up close button listener when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('cylinder-modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeCylinderModal);
    }
    
    // Also close on backdrop click
    const modal = document.getElementById('cylinder-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeCylinderModal();
            }
        });
    }
});

// Make available globally
window.CylinderInstalls = CylinderInstalls;

