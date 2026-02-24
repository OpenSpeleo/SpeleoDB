import { Config } from '../config.js';
import { Utils } from '../utils.js';
import { API } from '../api.js';

// Module state
let sensorHistoryData = [];
let currentStationId = null;
let currentProjectId = null;
let currentSortColumn = 'modified_date';
let currentSortDirection = 'desc';
let currentStatusFilter = 'all';
let pendingSensorStatusChange = null;

// Cache for fleet sensors (populated during loadInstallForm/loadEditForm, used by loadFleetSensors)
let fleetSensorsCache = {};  // { fleetId: [...sensors] }

/**
 * Get color class for sensor install status
 */
function getSensorInstallStatusColor(status) {
    const colors = {
        'installed': 'bg-green-500',
        'retrieved': 'bg-blue-500',
        'lost': 'bg-red-500',
        'abandoned': 'bg-orange-500'
    };
    return colors[status?.toLowerCase()] || 'bg-gray-500';
}

/**
 * Get label for sensor install status
 */
function getSensorInstallStatusLabel(status) {
    const labels = {
        'installed': 'Installed',
        'retrieved': 'Retrieved',
        'lost': 'Lost',
        'abandoned': 'Abandoned'
    };
    return labels[status?.toLowerCase()] || status;
}

/**
 * Check if sensor install status can be changed
 */
function canChangeSensorInstallStatus(install) {
    return install.status === 'installed';
}

/**
 * Format date string without timezone issues
 */
function formatDateString(dateStr) {
    if (!dateStr) return '';

    // Extract just the date part
    const dateOnly = dateStr.split('T')[0];
    const parts = dateOnly.split('-');

    if (parts.length === 3) {
        const year = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10) - 1;
        const day = parseInt(parts[2], 10);
        const date = new Date(year, month, day);
        return date.toLocaleDateString();
    }

    return new Date(dateStr).toLocaleDateString();
}

/**
 * Format expiry date with color coding
 */
function formatExpiracyDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffTime = date - now;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    let colorClass = 'text-emerald-400';
    if (diffDays < 0) colorClass = 'text-red-400';
    else if (diffDays < 7) colorClass = 'text-amber-400';

    return `<span class="${colorClass}">${date.toLocaleDateString()} (${diffDays > 0 ? 'in ' : ''}${Math.abs(diffDays)} days${diffDays < 0 ? ' ago' : ''})</span>`;
}

/**
 * Validate sensor install dates
 */
function validateSensorInstallDates() {
    const installDateInput = document.getElementById('install-date');
    const expiracyMemoryInput = document.getElementById('expiracy-memory-date');
    const expiracyBatteryInput = document.getElementById('expiracy-battery-date');

    const installDateError = document.getElementById('install-date-error');
    const expiracyMemoryError = document.getElementById('expiracy-memory-date-error');
    const expiracyBatteryError = document.getElementById('expiracy-battery-date-error');

    // Reset all errors
    installDateInput?.classList.remove('error');
    expiracyMemoryInput?.classList.remove('error');
    expiracyBatteryInput?.classList.remove('error');
    if (installDateError) installDateError.style.display = 'none';
    if (expiracyMemoryError) expiracyMemoryError.style.display = 'none';
    if (expiracyBatteryError) expiracyBatteryError.style.display = 'none';

    if (!installDateInput || !installDateInput.value) {
        return true;
    }

    const installDate = new Date(installDateInput.value);
    installDate.setHours(0, 0, 0, 0);
    let isValid = true;

    if (expiracyMemoryInput && expiracyMemoryInput.value) {
        const expiracyMemoryDate = new Date(expiracyMemoryInput.value);
        expiracyMemoryDate.setHours(0, 0, 0, 0);
        if (expiracyMemoryDate < installDate) {
            expiracyMemoryInput.classList.add('error');
            if (expiracyMemoryError) {
                expiracyMemoryError.textContent = 'Memory expiry date must be on or after install date';
                expiracyMemoryError.style.display = 'block';
            }
            isValid = false;
        }
    }

    if (expiracyBatteryInput && expiracyBatteryInput.value) {
        const expiracyBatteryDate = new Date(expiracyBatteryInput.value);
        expiracyBatteryDate.setHours(0, 0, 0, 0);
        if (expiracyBatteryDate < installDate) {
            expiracyBatteryInput.classList.add('error');
            if (expiracyBatteryError) {
                expiracyBatteryError.textContent = 'Battery expiry date must be on or after install date';
                expiracyBatteryError.style.display = 'block';
            }
            isValid = false;
        }
    }

    return isValid;
}

/**
 * Render sensor history table
 */
async function renderSensorHistoryTable(installs, stationId, projectId, currentFilter = 'all') {
    const container = document.getElementById('station-modal-content');
    // Determine station type and use appropriate permission check
    const { State } = await import('../state.js');
    const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
    const isSurfaceStation = station?.network || station?.station_type === 'surface';
    const hasWriteAccess = Config.getScopedAccess(
        isSurfaceStation ? 'network' : 'project',
        projectId
    ).write;

    container.innerHTML = `
        <div class="tab-content active">
            <div class="space-y-6">
                <div class="flex justify-between items-center">
                    <h3 class="text-xl font-semibold text-white">Sensor Management</h3>
                    ${hasWriteAccess ? `
                        <button onclick="window.StationSensors.loadInstallForm('${stationId}', '${projectId}')" class="btn-primary text-sm">
                            <svg class="w-4 h-4 fill-current opacity-80 shrink-0" viewBox="0 0 16 16">
                                <path d="M15 7H9V1c0-.6-.4-1-1-1S7 .4 7 1v6H1c-.6 0-1 .4-1 1s.4 1 1 1h6v6c0 .6.4 1 1 1s1-.4 1-1V9h6c.6 0 1-.4 1-1s-.4-1-1-1z"></path>
                            </svg>
                            <span class="ml-2">Install Sensor</span>
                        </button>
                    ` : ''}
                </div>

                <!-- Sub-tabs -->
                <div class="flex space-x-2 border-b border-slate-600">
                    <button
                        class="sensor-subtab px-4 py-2 text-sm font-medium transition-colors text-slate-400 hover:text-slate-300"
                        onclick="window.StationSensors.loadCurrentInstalls('${stationId}', '${projectId}')"
                        data-subtab="current">
                        Current Installs
                    </button>
                    <button
                        class="sensor-subtab px-4 py-2 text-sm font-medium transition-colors text-sky-400 border-b-2 border-sky-400"
                        onclick="window.StationSensors.loadHistory('${stationId}', '${projectId}')"
                        data-subtab="history">
                        History
                    </button>
                </div>

                <!-- Filter and Export Section -->
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div class="flex items-center gap-2">
                        <label class="text-sm text-slate-400">Filter by Status:</label>
                        <select
                            id="status-filter-select"
                            onchange="window.StationSensors.filterHistory()"
                            class="bg-slate-700 text-white text-sm rounded-lg px-3 py-1.5 border border-slate-600 focus:ring-2 focus:ring-sky-500 focus:border-transparent">
                            <option value="all" ${currentFilter === 'all' ? 'selected' : ''}>All Statuses</option>
                            <option value="installed" ${currentFilter === 'installed' ? 'selected' : ''}>Installed</option>
                            <option value="retrieved" ${currentFilter === 'retrieved' ? 'selected' : ''}>Retrieved</option>
                            <option value="lost" ${currentFilter === 'lost' ? 'selected' : ''}>Lost</option>
                            <option value="abandoned" ${currentFilter === 'abandoned' ? 'selected' : ''}>Abandoned</option>
                        </select>
                    </div>
                    <div class="flex items-center gap-2">
                        <button
                            onclick="window.StationSensors.refreshHistory()"
                            id="refresh-sensor-history-btn"
                            class="btn-secondary text-sm flex items-center gap-2"
                            title="Refresh sensor history">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                            </svg>
                            <span>Refresh</span>
                        </button>
                        <button
                            onclick="window.StationSensors.exportHistory('${stationId}')"
                            id="export-sensor-history-btn"
                            class="btn-secondary text-sm flex items-center justify-center gap-2"
                            style="background-color: #16a34a; border-color: #16a34a; color: white; width: 175px;">
                            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                            </svg>
                            <span>Export to Excel</span>
                        </button>
                    </div>
                </div>

                <!-- History Table -->
                ${installs.length > 0 ? `
                    <div class="overflow-x-auto">
                        <table class="w-full text-sm sensor-history-table">
                            <thead class="bg-slate-800/50 text-slate-300 text-left">
                                <tr>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-slate-700/50" onclick="window.StationSensors.sortHistory('sensor_name')">
                                        <div class="flex items-center gap-1">
                                            Sensor Name
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-slate-700/50" onclick="window.StationSensors.sortHistory('sensor_fleet_name')">
                                        <div class="flex items-center gap-1">
                                            Fleet Name
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-slate-700/50" onclick="window.StationSensors.sortHistory('status')">
                                        <div class="flex items-center gap-1">
                                            State
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-slate-700/50" onclick="window.StationSensors.sortHistory('install_date')">
                                        <div class="flex items-center gap-1">
                                            Install Date
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium">Install User</th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-slate-700/50" onclick="window.StationSensors.sortHistory('uninstall_date')">
                                        <div class="flex items-center gap-1">
                                            Retrieval Date
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium">Retrieval User</th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-slate-700/50" onclick="window.StationSensors.sortHistory('modified_date')">
                                        <div class="flex items-center gap-1">
                                            Modified
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-700" id="sensor-history-tbody">
                                ${installs.map((install, index) => `
                                    <tr class="hover:bg-slate-800/30 ${index % 2 === 0 ? 'bg-slate-900/20' : ''}">
                                        <td class="px-4 py-3 text-white font-medium">${install.sensor_name || 'Unknown'}</td>
                                        <td class="px-4 py-3 text-slate-300">${install.sensor_fleet_name || 'Unknown'}</td>
                                        <td class="px-4 py-3">
                                            <span class="px-2 py-1 ${getSensorInstallStatusColor(install.status)} text-white text-xs rounded-full font-medium block w-20 text-center">
                                                ${getSensorInstallStatusLabel(install.status)}
                                            </span>
                                        </td>
                                        <td class="px-4 py-3 text-slate-300">${formatDateString(install.install_date)}</td>
                                        <td class="px-4 py-3 text-slate-400 text-xs">${install.install_user || '-'}</td>
                                        <td class="px-4 py-3 text-slate-300">${install.uninstall_date ? formatDateString(install.uninstall_date) : '-'}</td>
                                        <td class="px-4 py-3 text-slate-400 text-xs">${install.uninstall_user || '-'}</td>
                                        <td class="px-4 py-3 text-slate-400 text-xs">${install.modified_date ? new Date(install.modified_date).toLocaleDateString() : '-'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                    <div class="text-sm text-slate-400">
                        Total records: <span class="font-semibold text-slate-300" id="sensor-history-count">${installs.length}</span>
                    </div>
                ` : `
                    <div class="text-center py-12">
                        <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                        <h3 class="text-white text-lg font-medium mb-2">No History Available</h3>
                        <p class="text-slate-400">This station doesn't have any sensor installation history yet.</p>
                    </div>
                `}
            </div>
        </div>
    `;
}

export const StationSensors = {
    async render(stationId, container) {
        currentStationId = stationId;
        // Get project/network ID from state - check both subsurface and surface stations
        const { State } = await import('../state.js');
        const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        const isSurfaceStation = station?.network || station?.station_type === 'surface';
        currentProjectId = station?.project || station?.network || null;

        await this.loadCurrentInstalls(stationId, currentProjectId, 'current', isSurfaceStation);
    },

    async loadCurrentInstalls(stationId, projectId, subtab = 'current', isSurfaceStation = false) {
        const container = document.getElementById('station-modal-content');
        const hasWriteAccess = Config.getScopedAccess(
            isSurfaceStation ? 'network' : 'project',
            projectId
        ).write;
        const loadingOverlay = Utils.showLoadingOverlay('Loading sensor installations...');

        currentStationId = stationId;
        currentProjectId = projectId;

        try {
            const response = await API.getStationSensorInstallsWithStatus(stationId, 'installed');

            if (!response.success) {
                throw new Error('Failed to load sensor installations');
            }

            const installs = response.data || [];

            Utils.hideLoadingOverlay(loadingOverlay);

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="space-y-6">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xl font-semibold text-white">Sensor Management</h3>
                            ${hasWriteAccess ? `
                                <button onclick="window.StationSensors.loadInstallForm('${stationId}', '${projectId}')" class="btn-primary text-sm">
                                    <svg class="w-4 h-4 fill-current opacity-80 shrink-0" viewBox="0 0 16 16">
                                        <path d="M15 7H9V1c0-.6-.4-1-1-1S7 .4 7 1v6H1c-.6 0-1 .4-1 1s.4 1 1 1h6v6c0 .6.4 1 1 1s1-.4 1-1V9h6c.6 0 1-.4 1-1s-.4-1-1-1z"></path>
                                    </svg>
                                    <span class="ml-2">Install Sensor</span>
                                </button>
                            ` : ''}
                        </div>

                        <!-- Sub-tabs -->
                        <div class="flex space-x-2 border-b border-slate-600">
                            <button
                                class="sensor-subtab px-4 py-2 text-sm font-medium transition-colors ${subtab === 'current' ? 'text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-slate-300'}"
                                onclick="window.StationSensors.loadCurrentInstalls('${stationId}', '${projectId}', 'current')"
                                data-subtab="current">
                                Current Installs
                            </button>
                            <button
                                class="sensor-subtab px-4 py-2 text-sm font-medium transition-colors ${subtab === 'history' ? 'text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-slate-300'}"
                                onclick="window.StationSensors.loadHistory('${stationId}', '${projectId}')"
                                data-subtab="history">
                                History
                            </button>
                        </div>

                        <!-- Current Installs Content -->
                        <div id="sensor-subtab-content">
                            ${installs.length > 0 ? `
                                <div class="space-y-4">
                                    ${installs.map(install => `
                                        <div class="bg-slate-800/20 border border-slate-600/50 rounded-lg p-5 hover:bg-slate-700/30 transition-colors">
                                            <div class="flex justify-between items-start mb-3">
                                                <div class="flex-1">
                                                    <h4 class="text-white font-medium text-lg">${install.sensor_name || 'Unknown Sensor'}</h4>
                                                    <p class="text-slate-400 text-sm mt-1">Fleet: ${install.sensor_fleet_name || 'Unknown Fleet'}</p>
                                                </div>
                                                <span class="px-3 py-1 ${getSensorInstallStatusColor(install.status)} text-white text-xs rounded-full font-medium block w-20 text-center">
                                                    ${getSensorInstallStatusLabel(install.status)}
                                                </span>
                                            </div>

                                            <div class="grid grid-cols-2 gap-4 mt-4 text-sm">
                                                <div>
                                                    <span class="text-slate-400">Installed:</span>
                                                    <span class="text-white ml-2">${formatDateString(install.install_date)}</span>
                                                </div>
                                                <div>
                                                    <span class="text-slate-400">Installer:</span>
                                                    <span class="text-white ml-2">${install.install_user || 'Unknown'}</span>
                                                </div>
                                                ${install.expiracy_memory_date ? `
                                                    <div>
                                                        <span class="text-slate-400">Memory Expires:</span>
                                                        <span class="ml-2">${formatExpiracyDate(install.expiracy_memory_date)}</span>
                                                    </div>
                                                ` : ''}
                                                ${install.expiracy_battery_date ? `
                                                    <div>
                                                        <span class="text-slate-400">Battery Expires:</span>
                                                        <span class="ml-2">${formatExpiracyDate(install.expiracy_battery_date)}</span>
                                                    </div>
                                                ` : ''}
                                            </div>

                                            ${hasWriteAccess ? `
                                                <div class="flex gap-2 mt-4 pt-4 border-t border-slate-600/50">
                                                    ${canChangeSensorInstallStatus(install) ? `
                                                        <button onclick="window.StationSensors.loadEditForm('${install.id}', '${stationId}', '${projectId}')"
                                                            class="btn-secondary text-sm flex-1">
                                                            ✏️ Edit
                                                        </button>
                                                        <button onclick="window.StationSensors.showRetrieveModal('${install.id}', '${stationId}', '${projectId}')"
                                                            class="btn-secondary text-sm flex-1">
                                                            ✓ Mark as Retrieved
                                                        </button>
                                                        <button onclick="window.StationSensors.showInstallStatusChangeModal('${install.id}', 'lost', '${Utils.escapeHtml(install.sensor_name || 'Sensor')}', '${stationId}', '${projectId}')"
                                                            class="btn-secondary text-sm flex-1">
                                                            ⚠ Mark as Lost
                                                        </button>
                                                        <button onclick="window.StationSensors.showInstallStatusChangeModal('${install.id}', 'abandoned', '${Utils.escapeHtml(install.sensor_name || 'Sensor')}', '${stationId}', '${projectId}')"
                                                            class="btn-secondary text-sm flex-1">
                                                            🚫 Mark as Abandoned
                                                        </button>
                                                    ` : `
                                                        <div class="text-slate-400 text-sm text-center w-full py-2">
                                                            Sensor status cannot be changed (${getSensorInstallStatusLabel(install.status)})
                                                        </div>
                                                    `}
                                                </div>
                                            ` : ''}
                                        </div>
                                    `).join('')}
                                </div>
                            ` : `
                                <div class="text-center py-12">
                                    <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                                    </svg>
                                    <h3 class="text-white text-lg font-medium mb-2">No Sensors Currently Installed</h3>
                                    <p class="text-slate-400 mb-4">This station doesn't have any sensors installed yet.</p>
                                    ${hasWriteAccess ? `
                                        <button onclick="window.StationSensors.loadInstallForm('${stationId}', '${projectId}')" class="btn-primary">
                                            Install First Sensor
                                        </button>
                                    ` : ''}
                                </div>
                            `}
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            console.error('Error loading sensor installs:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', 'Failed to load sensor installations. Please try again.');
            this.showEmpty();
        }
    },

    showEmpty() {
        const container = document.getElementById('station-modal-content');
        container.innerHTML = `
            <div class="tab-content active">
                <div class="flex items-center justify-center min-h-[300px]">
                    <div class="text-center">
                        <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                        </svg>
                        <h3 class="text-white text-lg font-medium mb-2">No Sensors Installed</h3>
                        <p class="text-slate-400">Select a station to view and manage its sensor installations.</p>
                    </div>
                </div>
            </div>
        `;
    },

    async loadHistory(stationId, projectId) {
        const container = document.getElementById('station-modal-content');
        const loadingOverlay = Utils.showLoadingOverlay('Loading sensor history...');

        currentStationId = stationId;
        currentProjectId = projectId;

        try {
            const response = await API.getStationSensorInstalls(stationId);

            if (!response.success) {
                throw new Error('Failed to load sensor history');
            }

            const allInstalls = response.data || [];

            Utils.hideLoadingOverlay(loadingOverlay);

            // Store data for filtering
            sensorHistoryData = allInstalls;
            currentSortColumn = 'modified_date';
            currentSortDirection = 'desc';
            currentStatusFilter = 'all';

            renderSensorHistoryTable(allInstalls, stationId, projectId, 'all');
        } catch (error) {
            console.error('Error loading sensor history:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', 'Failed to load sensor history. Please try again.');
        }
    },

    filterHistory() {
        const statusFilter = document.getElementById('status-filter-select').value;
        currentStatusFilter = statusFilter;
        let filteredData = sensorHistoryData;

        if (statusFilter !== 'all') {
            filteredData = sensorHistoryData.filter(install => install.status === statusFilter);
        }

        renderSensorHistoryTable(filteredData, currentStationId, currentProjectId, statusFilter);
    },

    sortHistory(column) {
        if (currentSortColumn === column) {
            currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            currentSortColumn = column;
            currentSortDirection = 'desc';
        }

        const statusFilter = currentStatusFilter || 'all';
        let filteredData = sensorHistoryData;

        if (statusFilter !== 'all') {
            filteredData = sensorHistoryData.filter(install => install.status === statusFilter);
        }

        const sortedData = [...filteredData].sort((a, b) => {
            let aVal = a[column];
            let bVal = b[column];

            if (aVal === null || aVal === undefined) return 1;
            if (bVal === null || bVal === undefined) return -1;

            if (typeof aVal === 'string') aVal = aVal.toLowerCase();
            if (typeof bVal === 'string') bVal = bVal.toLowerCase();

            if (currentSortDirection === 'asc') {
                return aVal > bVal ? 1 : -1;
            } else {
                return aVal < bVal ? 1 : -1;
            }
        });

        renderSensorHistoryTable(sortedData, currentStationId, currentProjectId, statusFilter);
    },

    async exportHistory(stationId) {
        const btn = document.getElementById('export-sensor-history-btn');
        const originalHtml = btn.innerHTML;

        try {
            btn.disabled = true;
            btn.innerHTML = `
                <svg class="animate-spin w-4 h-4 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Exporting...</span>
            `;

            const response = await API.getStationSensorInstallsAsExcel(stationId);

            if (!response.ok) {
                throw new Error(`Export failed: ${response.status} ${response.statusText}`);
            }

            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'sensor_history.xlsx';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename=["']?([^"';]+)["']?/);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1].trim();
                }
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            btn.innerHTML = `
                <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                <span>Exported!</span>
            `;

            setTimeout(() => {
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }, 2000);

        } catch (error) {
            console.error('Export error:', error);
            Utils.showNotification('error', 'Failed to export data: ' + error.message);
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        }
    },

    async refreshHistory() {
        const btn = document.getElementById('refresh-sensor-history-btn');
        const originalHtml = btn.innerHTML;
        const stationId = currentStationId;
        const projectId = currentProjectId;
        const statusFilter = currentStatusFilter || 'all';

        if (!stationId) {
            Utils.showNotification('error', 'Station ID not found. Please reload the page.');
            return;
        }

        try {
            btn.disabled = true;
            btn.innerHTML = `
                <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Refreshing...</span>
            `;

            const response = await API.getStationSensorInstalls(stationId);

            if (!response.success) {
                throw new Error('Failed to refresh sensor history');
            }

            const allInstalls = response.data || [];

            sensorHistoryData = allInstalls;

            let filteredData = allInstalls;
            if (statusFilter !== 'all') {
                filteredData = allInstalls.filter(install => install.status === statusFilter);
            }

            renderSensorHistoryTable(filteredData, stationId, projectId, statusFilter);

            btn.classList.remove('btn-secondary');
            btn.classList.add('bg-green-600', 'hover:bg-green-700');
            btn.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                <span>Refreshed!</span>
            `;

            setTimeout(() => {
                btn.classList.remove('bg-green-600', 'hover:bg-green-700');
                btn.classList.add('btn-secondary');
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }, 2000);

        } catch (error) {
            console.error('Refresh error:', error);
            Utils.showNotification('error', 'Failed to refresh sensor history: ' + error.message);
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        }
    },

    async loadInstallForm(stationId, projectId) {
        const container = document.getElementById('station-modal-content');
        const loadingOverlay = Utils.showLoadingOverlay('Loading sensor fleets...');

        try {
            // Fetch fleets
            const fleetsResponse = await API.getSensorFleets();

            if (!fleetsResponse.success) {
                throw new Error('Failed to load sensor fleets');
            }

            const fleets = fleetsResponse.data || [];

            if (fleets.length === 0) {
                Utils.hideLoadingOverlay(loadingOverlay);
                container.innerHTML = `
                    <div class="tab-content active">
                        <div class="text-center py-12">
                            <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                            </svg>
                            <h3 class="text-white text-lg font-medium mb-2">No Sensor Fleets Available</h3>
                            <p class="text-slate-400 mb-4">You need to create a sensor fleet before installing sensors.</p>
                            <button onclick="window.StationSensors.loadCurrentInstalls('${stationId}', '${projectId}')" class="btn-secondary">
                                ← Back to Sensor Management
                            </button>
                        </div>
                    </div>
                `;
                return;
            }

            // Fetch sensors for all fleets in parallel to calculate available counts
            const fleetSensorsPromises = fleets.map(fleet =>
                API.getSensorFleetSensors(fleet.id).then(
                    res => res.success ? res : { data: [] }
                ).catch(() => ({ data: [] }))
            );

            const fleetSensorsResults = await Promise.all(fleetSensorsPromises);

            // Cache the fleet sensors for use by loadFleetSensors
            fleetSensorsCache = {};
            fleets.forEach((fleet, index) => {
                fleetSensorsCache[fleet.id] = fleetSensorsResults[index]?.data || [];
            });

            // Calculate available sensor count for each fleet
            // A sensor is available if it's functional AND not installed anywhere (active_installs is empty)
            const fleetsWithAvailableCount = fleets.map((fleet, index) => {
                const sensors = fleetSensorsCache[fleet.id] || [];
                const availableCount = sensors.filter(sensor =>
                    sensor.status === 'functional' &&
                    (!sensor.active_installs || sensor.active_installs.length === 0)
                ).length;
                return { ...fleet, availableCount };
            });

            Utils.hideLoadingOverlay(loadingOverlay);

            const today = new Date().toISOString().split('T')[0];

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="space-y-6">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xl font-semibold text-white">Install Sensor</h3>
                            <button onclick="window.StationSensors.loadCurrentInstalls('${stationId}', '${projectId}')" class="btn-secondary text-sm">
                                ← Back
                            </button>
                        </div>

                        <form id="install-sensor-form" class="space-y-6">
                            <div>
                                <label class="form-label">Sensor Fleet *</label>
                                <select id="sensor-fleet-select"
                                    class="form-input" required>
                                    <option value="">Select a fleet...</option>
                                    ${fleetsWithAvailableCount.map(fleet => `
                                        <option value="${fleet.id}">${fleet.name} (${fleet.availableCount} available)</option>
                                    `).join('')}
                                </select>
                            </div>

                            <div>
                                <label class="form-label">Sensor *</label>
                                <select id="sensor-select" class="form-input" required disabled>
                                    <option value="">Select a fleet first...</option>
                                </select>
                            </div>

                            <div>
                                <label class="form-label">Install Date *</label>
                                <input type="date" id="install-date" class="form-input" value="${today}" required>
                                <span id="install-date-error" class="form-error-message" style="display: none;"></span>
                            </div>

                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="form-label">Memory Expiry Date (Optional)</label>
                                    <input type="date" id="expiracy-memory-date" class="form-input">
                                    <span id="expiracy-memory-date-error" class="form-error-message" style="display: none;"></span>
                                </div>
                                <div>
                                    <label class="form-label">Battery Expiry Date (Optional)</label>
                                    <input type="date" id="expiracy-battery-date" class="form-input">
                                    <span id="expiracy-battery-date-error" class="form-error-message" style="display: none;"></span>
                                </div>
                            </div>

                            <div class="flex gap-4">
                                <button type="submit" class="btn-primary flex-1" id="install-sensor-submit-btn">
                                    Install Sensor
                                </button>
                                <button type="button" onclick="window.StationSensors.loadCurrentInstalls('${stationId}', '${projectId}')" class="btn-secondary">
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            `;

            // Setup fleet selector
            const fleetSelect = document.getElementById('sensor-fleet-select');
            fleetSelect.addEventListener('change', () => this.loadFleetSensors(fleetSelect.value, stationId));

            // Setup date validation
            document.getElementById('install-date').addEventListener('change', validateSensorInstallDates);
            document.getElementById('expiracy-memory-date').addEventListener('change', validateSensorInstallDates);
            document.getElementById('expiracy-battery-date').addEventListener('change', validateSensorInstallDates);

            // Setup form submission
            document.getElementById('install-sensor-form').addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleInstall(stationId, projectId, null);
            });

        } catch (error) {
            console.error('Error loading install form:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', 'Failed to load sensor installation form. Please try again.');
        }
    },

    async loadFleetSensors(fleetId, stationId, currentSensorId = null) {
        const sensorSelect = document.getElementById('sensor-select');
        if (!fleetId) {
            sensorSelect.disabled = true;
            sensorSelect.innerHTML = '<option value="">Select a fleet first...</option>';
            return;
        }

        sensorSelect.disabled = true;
        sensorSelect.innerHTML = '<option value="">Loading sensors...</option>';

        try {
            // Use cached data if available, otherwise fetch from API
            let allSensors;
            if (fleetSensorsCache[fleetId]) {
                allSensors = fleetSensorsCache[fleetId];
            } else {
                const sensorsResponse = await API.getSensorFleetSensors(fleetId);

                if (!sensorsResponse.success) {
                    throw new Error('Failed to load fleet sensors');
                }

                allSensors = sensorsResponse.data || [];
                // Store in cache for future use
                fleetSensorsCache[fleetId] = allSensors;
            }

            // Filter out already installed sensors (anywhere) AND non-functional sensors
            // A sensor is available if:
            // - It's functional AND
            // - It's not installed anywhere (active_installs is empty) OR it's the sensor we're editing
            const availableSensors = allSensors.filter(sensor =>
                sensor.status === 'functional' &&
                ((!sensor.active_installs || sensor.active_installs.length === 0) || sensor.id === currentSensorId)
            );

            sensorSelect.disabled = false;
            if (availableSensors.length === 0) {
                sensorSelect.innerHTML = '<option value="">No available sensors in this fleet</option>';
            } else {
                sensorSelect.innerHTML = '<option value="">Select a sensor...</option>' +
                    availableSensors.map(sensor => `
                        <option value="${sensor.id}" ${sensor.id === currentSensorId ? 'selected' : ''}>
                            ${sensor.name}
                        </option>
                    `).join('');
            }

        } catch (error) {
            console.error('Error loading fleet sensors:', error);
            sensorSelect.disabled = false;
            sensorSelect.innerHTML = '<option value="">Error loading sensors</option>';
            Utils.showNotification('error', 'Failed to load sensors. Please try again.');
        }
    },

    async handleInstall(stationId, projectId, installId = null) {
        if (!validateSensorInstallDates()) {
            Utils.showNotification('error', 'Please fix the date validation errors before submitting.');
            return;
        }

        const isEdit = installId !== null;
        const loadingOverlay = Utils.showLoadingOverlay(isEdit ? 'Updating sensor installation...' : 'Installing sensor...');

        try {
            const sensorId = document.getElementById('sensor-select').value;
            const installDate = document.getElementById('install-date').value;
            const expiracyMemoryDate = document.getElementById('expiracy-memory-date').value;
            const expiracyBatteryDate = document.getElementById('expiracy-battery-date').value;

            const formData = new FormData();
            formData.append('sensor', sensorId);
            formData.append('install_date', installDate);

            if (expiracyMemoryDate) {
                formData.append('expiracy_memory_date', expiracyMemoryDate);
            } else if (isEdit) {
                formData.append('expiracy_memory_date', null);
            }

            if (expiracyBatteryDate) {
                formData.append('expiracy_battery_date', expiracyBatteryDate);
            } else if (isEdit) {
                formData.append('expiracy_battery_date', null);
            }

            let response;
            if (isEdit) {
                response = await API.updateStationSensorInstalls(
                    stationId,
                    installId,
                    formData
                );
            } else {
                response = await API.createStationSensorInstalls(
                    stationId,
                    formData
                );
            }

            Utils.hideLoadingOverlay(loadingOverlay);

            // Clear the cache since installed sensors have changed
            fleetSensorsCache = {};

            Utils.showNotification('success', isEdit ? 'Sensor installation updated successfully!' : 'Sensor installed successfully!');
            this.loadCurrentInstalls(stationId, projectId);
        } catch (error) {
            console.error(`Error ${isEdit ? 'updating' : 'installing'} sensor:`, error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', `Error ${isEdit ? 'updating' : 'installing'} sensor. Please try again.`);
        }
    },

    async loadEditForm(installId, stationId, projectId) {
        const container = document.getElementById('station-modal-content');
        const loadingOverlay = Utils.showLoadingOverlay('Loading sensor installation...');

        try {
            const installResponse = await API.getStationSensorInstallDetails(stationId, installId);

            if (!installResponse.success) {
                throw new Error('Failed to load sensor installation details');
            }

            const install = installResponse.data;

            if (install.status !== 'installed') {
                Utils.hideLoadingOverlay(loadingOverlay);
                Utils.showNotification('error', 'Only installed sensors can be edited.');
                this.loadCurrentInstalls(stationId, projectId);
                return;
            }

            // Fetch fleets
            const fleetsResponse = await API.getSensorFleets();

            if (!fleetsResponse.success) {
                throw new Error('Failed to load sensor fleets');
            }

            const fleets = fleetsResponse.data || [];

            const currentFleetId = install.sensor_fleet_id;

            // Fetch sensors for all fleets in parallel to calculate available counts
            const fleetSensorsPromises = fleets.map(fleet =>
                API.getSensorFleetSensors(fleet.id).then(
                    res => res.success ? res : { data: [] }
                ).catch(() => ({ data: [] }))
            );

            const fleetSensorsResults = await Promise.all(fleetSensorsPromises);

            // Cache the fleet sensors for use by loadFleetSensors
            fleetSensorsCache = {};
            fleets.forEach((fleet, index) => {
                fleetSensorsCache[fleet.id] = fleetSensorsResults[index]?.data || [];
            });

            // Calculate available sensor count for each fleet
            // A sensor is available if:
            // - It's functional (or it's the currently installed sensor - to allow keeping a broken sensor)
            // - It's not installed anywhere (active_installs is empty) OR it's the sensor we're editing
            const fleetsWithAvailableCount = fleets.map((fleet, index) => {
                const sensors = fleetSensorsCache[fleet.id] || [];
                const availableCount = sensors.filter(sensor =>
                    (sensor.status === 'functional' || sensor.id === install.sensor_id) &&
                    ((!sensor.active_installs || sensor.active_installs.length === 0) || sensor.id === install.sensor_id)
                ).length;
                return { ...fleet, availableCount };
            });

            // Get available sensors for the current fleet
            const currentFleetIndex = fleets.findIndex(f => f.id === currentFleetId);
            const currentFleetSensors = currentFleetIndex >= 0 ? fleetSensorsCache[fleets[currentFleetIndex].id] : [];
            const availableSensors = currentFleetSensors.filter(sensor =>
                (sensor.status === 'functional' || sensor.id === install.sensor_id) &&
                ((!sensor.active_installs || sensor.active_installs.length === 0) || sensor.id === install.sensor_id)
            );

            Utils.hideLoadingOverlay(loadingOverlay);

            const installDate = install.install_date ? new Date(install.install_date).toISOString().split('T')[0] : '';
            const expiracyMemoryDate = install.expiracy_memory_date ? new Date(install.expiracy_memory_date).toISOString().split('T')[0] : '';
            const expiracyBatteryDate = install.expiracy_battery_date ? new Date(install.expiracy_battery_date).toISOString().split('T')[0] : '';

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="space-y-6">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xl font-semibold text-white">Edit Sensor Installation</h3>
                            <button onclick="window.StationSensors.loadCurrentInstalls('${stationId}', '${projectId}')" class="btn-secondary text-sm">
                                ← Back
                            </button>
                        </div>

                        <form id="install-sensor-form" class="space-y-6">
                            <div>
                                <label class="form-label">Sensor Fleet *</label>
                                <select id="sensor-fleet-select"
                                    class="form-input" required>
                                    <option value="">Select a fleet...</option>
                                    ${fleetsWithAvailableCount.map(fleet => `
                                        <option value="${fleet.id}" ${fleet.id === currentFleetId ? 'selected' : ''}>
                                            ${fleet.name} (${fleet.availableCount} available)
                                        </option>
                                    `).join('')}
                                </select>
                            </div>

                            <div>
                                <label class="form-label">Sensor *</label>
                                <select id="sensor-select" class="form-input" required>
                                    <option value="">Select a sensor...</option>
                                    ${availableSensors.map(sensor => `
                                        <option value="${sensor.id}" ${sensor.id === install.sensor_id ? 'selected' : ''}>
                                            ${sensor.name}
                                        </option>
                                    `).join('')}
                                </select>
                            </div>

                            <div>
                                <label class="form-label">Install Date *</label>
                                <input type="date" id="install-date" class="form-input" value="${installDate}" required>
                                <span id="install-date-error" class="form-error-message" style="display: none;"></span>
                            </div>

                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="form-label">Memory Expiry Date (Optional)</label>
                                    <input type="date" id="expiracy-memory-date" class="form-input" value="${expiracyMemoryDate}">
                                    <span id="expiracy-memory-date-error" class="form-error-message" style="display: none;"></span>
                                </div>
                                <div>
                                    <label class="form-label">Battery Expiry Date (Optional)</label>
                                    <input type="date" id="expiracy-battery-date" class="form-input" value="${expiracyBatteryDate}">
                                    <span id="expiracy-battery-date-error" class="form-error-message" style="display: none;"></span>
                                </div>
                            </div>

                            <div class="flex gap-4">
                                <button type="submit" class="btn-primary flex-1" id="install-sensor-submit-btn">
                                    Update Installation
                                </button>
                                <button type="button" onclick="window.StationSensors.loadCurrentInstalls('${stationId}', '${projectId}')" class="btn-secondary">
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            `;

            // Setup fleet selector
            const fleetSelect = document.getElementById('sensor-fleet-select');
            fleetSelect.addEventListener('change', () => this.loadFleetSensors(fleetSelect.value, stationId, install.sensor_id));

            // Setup date validation
            document.getElementById('install-date').addEventListener('change', validateSensorInstallDates);
            document.getElementById('expiracy-memory-date').addEventListener('change', validateSensorInstallDates);
            document.getElementById('expiracy-battery-date').addEventListener('change', validateSensorInstallDates);

            // Validate dates on load
            setTimeout(() => validateSensorInstallDates(), 100);

            // Setup form submission
            document.getElementById('install-sensor-form').addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleInstall(stationId, projectId, installId);
            });

        } catch (error) {
            console.error('Error loading edit form:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', 'Failed to load sensor installation form. Please try again.');
        }
    },

    showRetrieveModal(installId, stationId, projectId) {
        const today = new Date().toISOString().split('T')[0];
        const container = document.getElementById('station-modal-content');

        container.innerHTML = `
            <div class="tab-content active">
                <div class="space-y-6">
                    <h3 class="text-xl font-semibold text-white">Mark Sensor as Retrieved</h3>

                    <form id="retrieve-sensor-form" class="space-y-6">
                        <div>
                            <label class="form-label">Retrieval Date *</label>
                            <input type="date" id="retrieval-date" class="form-input" value="${today}" required>
                        </div>

                        <div class="flex gap-4">
                            <button type="submit" class="btn-primary flex-1">
                                Mark as Retrieved
                            </button>
                            <button type="button" onclick="window.StationSensors.loadCurrentInstalls('${stationId}', '${projectId}')" class="btn-secondary">
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        document.getElementById('retrieve-sensor-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleRetrieve(installId, stationId, projectId);
        });
    },

    async handleRetrieve(installId, stationId, projectId) {
        const loadingOverlay = Utils.showLoadingOverlay('Updating sensor status...');

        try {
            const retrievalDate = document.getElementById('retrieval-date').value;

            const formData = new FormData();
            formData.append('status', 'retrieved');
            formData.append('uninstall_date', retrievalDate);

            await API.updateStationSensorInstalls(stationId, installId, formData);

            Utils.hideLoadingOverlay(loadingOverlay);

            // Clear the cache since installed sensors have changed
            fleetSensorsCache = {};

            Utils.showNotification('success', 'Sensor marked as retrieved!');
            this.loadCurrentInstalls(stationId, projectId);
        } catch (error) {
            console.error('Error retrieving sensor:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', error.message || 'Error updating sensor status. Please try again.');
        }
    },

    showInstallStatusChangeModal(installId, newStatus, sensorName, stationId, projectId) {
        const statusConfig = {
            'lost': {
                label: 'Lost',
                icon: '⚠️',
                iconBg: 'linear-gradient(135deg, #f59e0b, #d97706)',
                message: `Are you sure you want to mark this sensor as <strong>Lost</strong>?`,
                warning: 'This sensor will be marked as lost and cannot be changed back to installed status.',
                btnClass: 'btn-warning',
                btnText: 'Mark as Lost'
            },
            'abandoned': {
                label: 'Abandoned',
                icon: '🚫',
                iconBg: 'linear-gradient(135deg, #6b7280, #4b5563)',
                message: `Are you sure you want to mark this sensor as <strong>Abandoned</strong>?`,
                warning: 'This sensor will be marked as abandoned and cannot be changed back to installed status.',
                btnClass: 'btn-secondary',
                btnText: 'Mark as Abandoned'
            }
        };

        const config = statusConfig[newStatus];
        if (!config) {
            console.error('Unknown status:', newStatus);
            return;
        }

        pendingSensorStatusChange = {
            installId,
            newStatus,
            stationId,
            projectId
        };

        // Create modal
        const modalHtml = `
            <div id="sensor-status-change-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6 border-b border-slate-600">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center">
                                <div class="w-10 h-10 rounded-full flex items-center justify-center text-xl mr-3" style="background: ${config.iconBg}">
                                    ${config.icon}
                                </div>
                                <h3 class="text-xl font-semibold text-white">Mark Sensor as ${config.label}</h3>
                            </div>
                            <button onclick="window.StationSensors.cancelStatusChange()" class="text-slate-400 hover:text-white transition-colors">
                                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="p-6">
                        <p class="text-slate-300 mb-4">${config.message}</p>
                        <div class="bg-slate-700/50 rounded-lg p-3 mb-4">
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">Sensor:</span>
                                <span class="text-white">${sensorName}</span>
                            </div>
                            <div class="flex justify-between text-sm mt-2">
                                <span class="text-slate-400">New Status:</span>
                                <span class="text-white">${config.label}</span>
                            </div>
                        </div>
                        <div class="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 mb-6">
                            <p class="text-amber-400 text-sm font-medium">⚠️ This action cannot be undone</p>
                            <p class="text-amber-300 text-xs mt-1">${config.warning}</p>
                        </div>
                        <div class="flex gap-3 justify-end">
                            <button onclick="window.StationSensors.cancelStatusChange()" class="btn-secondary">
                                Cancel
                            </button>
                            <button onclick="window.StationSensors.confirmStatusChange()" class="${config.btnClass}">
                                ${config.btnText}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal
        const existingModal = document.getElementById('sensor-status-change-modal');
        if (existingModal) existingModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },

    cancelStatusChange() {
        const modal = document.getElementById('sensor-status-change-modal');
        if (modal) modal.remove();
        pendingSensorStatusChange = null;
    },

    async confirmStatusChange() {
        if (!pendingSensorStatusChange) return;

        const { installId, newStatus, stationId, projectId } = pendingSensorStatusChange;

        const modal = document.getElementById('sensor-status-change-modal');
        if (modal) modal.remove();

        const statusLabels = {
            'lost': 'Lost',
            'abandoned': 'Abandoned'
        };
        const label = statusLabels[newStatus] || newStatus;

        const loadingOverlay = Utils.showLoadingOverlay(`Marking sensor as ${label}...`);

        try {
            const formData = new FormData();
            formData.append('status', newStatus);

            await API.updateStationSensorInstalls(stationId, installId, formData);

            Utils.hideLoadingOverlay(loadingOverlay);

            // Clear the cache since installed sensors have changed
            fleetSensorsCache = {};

            Utils.showNotification('success', `Sensor marked as ${label}!`);
            this.loadCurrentInstalls(stationId, projectId);
        } catch (error) {
            console.error(`Error marking sensor as ${newStatus}:`, error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', error.message || `Error updating sensor status. Please try again.`);
        } finally {
            pendingSensorStatusChange = null;
        }
    }
};

// Expose functions globally for onclick handlers
window.StationSensors = StationSensors;



