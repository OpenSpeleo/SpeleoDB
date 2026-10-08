import { getSensorInstallStatusColor, getSensorInstallStatusLabel, canChangeSensorInstallStatus, formatDateString, formatExpiracyDate, validateSensorInstallDates, renderSensorHistoryHtml } from './sensor_presentation.ts';
import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { SensorInstallRecord, SensorRecord } from '../../../../../../ts-types/domain/fleet-records.ts';
import type { PendingSensorStatusChange } from '../../../../../../ts-types/domain/station-sensors.ts';
import { getMapOverlayHost } from '../components/overlay_host.ts';
import { Config } from '../config.ts';
import { Utils } from '../utils.ts';
import { API } from '../api.ts';

// Module state
let sensorHistoryData: SensorInstallRecord[] = [];
let currentStationId: EntityId | null = null;
let currentProjectId: EntityId | null = null;
let currentSortColumn: keyof SensorInstallRecord = 'modified_date';
let currentSortDirection = 'desc';
let currentStatusFilter = 'all';
let pendingSensorStatusChange: PendingSensorStatusChange | null = null;

// Cache for fleet sensors (populated during loadInstallForm/loadEditForm, used by loadFleetSensors)
let fleetSensorsCache: Record<string, SensorRecord[]> = {};  // { fleetId: [...sensors] }

/**
 * Render sensor history table
 */
async function renderSensorHistoryTable(installs: SensorInstallRecord[], stationId: EntityId, projectId: EntityId | null, currentFilter = 'all') {
    const container = (document.getElementById('station-modal-content') as HTMLElement);
    // Determine station type and use appropriate permission check
    const { State } = await import('../state.ts');
    const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
    const isSurfaceStation = station?.network || station?.station_type === 'surface';
    const hasWriteAccess = Config.getScopedAccess(
        isSurfaceStation ? 'network' : 'project',
        projectId
    ).write;

    container.innerHTML = renderSensorHistoryHtml(installs, stationId, projectId, currentFilter, hasWriteAccess);
}

export const StationSensors = {
    async render(stationId: EntityId, container: HTMLElement) {
        currentStationId = stationId;
        // Get project/network ID from state - check both subsurface and surface stations
        const { State } = await import('../state.ts');
        const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        const isSurfaceStation = station?.network || station?.station_type === 'surface';
        currentProjectId = station?.project || station?.network || null;

        await this.loadCurrentInstalls(stationId, currentProjectId, 'current', isSurfaceStation);
    },

    async loadCurrentInstalls(stationId: EntityId, projectId: EntityId | null, subtab = 'current', isSurfaceStation: boolean | EntityId = false) {
        const container = (document.getElementById('station-modal-content') as HTMLElement);
        const hasWriteAccess = Config.getScopedAccess(
            isSurfaceStation ? 'network' : 'project',
            projectId
        ).write;
        const loadingOverlay = Utils.showLoadingOverlay('Loading sensor installations...');

        currentStationId = stationId;
        currentProjectId = projectId;

        try {
            const response = await API.getStationSensorInstallsWithStatus(stationId, 'installed');

            const installs = Array.isArray(response) ? response : [];

            Utils.hideLoadingOverlay(loadingOverlay);

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="flow-y-6">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xl font-semibold text-white">Sensor Management</h3>
                            ${hasWriteAccess ? `
                                <button ${Utils.mapActionAttributes('sensors.loadInstallForm', stationId, projectId)} class="btn-primary text-sm">
                                    <svg class="w-4 h-4 fill-current opacity-80 shrink-0" viewBox="0 0 16 16">
                                        <path d="M15 7H9V1c0-.6-.4-1-1-1S7 .4 7 1v6H1c-.6 0-1 .4-1 1s.4 1 1 1h6v6c0 .6.4 1 1 1s1-.4 1-1V9h6c.6 0 1-.4 1-1s-.4-1-1-1z"></path>
                                    </svg>
                                    <span class="ml-2">Install Sensor</span>
                                </button>
                            ` : ''}
                        </div>

                        <!-- Sub-tabs -->
                        <div class="flex flow-x-2 border-b border-slate-600">
                            <button
                                class="sensor-subtab px-4 py-2 text-sm font-medium transition-colors ${subtab === 'current' ? 'text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-slate-300'}"
                                ${Utils.mapActionAttributes('sensors.loadCurrentInstalls', stationId, projectId, 'current')}
                                data-subtab="current">
                                Current Installs
                            </button>
                            <button
                                class="sensor-subtab px-4 py-2 text-sm font-medium transition-colors ${subtab === 'history' ? 'text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-slate-300'}"
                                ${Utils.mapActionAttributes('sensors.loadHistory', stationId, projectId)}
                                data-subtab="history">
                                History
                            </button>
                        </div>

                        <!-- Current Installs Content -->
                        <div id="sensor-subtab-content">
                            ${installs.length > 0 ? `
                                <div class="flow-y-4">
                                    ${installs.map(install => `
                                        <div class="bg-srgb-slate-800-20 border border-srgb-slate-600-50 rounded-lg p-5 hover:bg-srgb-slate-700-30 transition-colors">
                                            <div class="flex justify-between items-start mb-3">
                                                <div class="flex-1">
                                                    <h4 class="text-white font-medium text-lg">${Utils.escapeHtml(install.sensor_name || 'Unknown Sensor')}</h4>
                                                    <p class="text-slate-400 text-sm mt-1">Fleet: ${Utils.escapeHtml(install.sensor_fleet_name || 'Unknown Fleet')}</p>
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
                                                    <span class="text-white ml-2">${Utils.escapeHtml(install.install_user || 'Unknown')}</span>
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
                                                <div class="flex gap-2 mt-4 pt-4 border-t border-srgb-slate-600-50">
                                                    ${canChangeSensorInstallStatus(install) ? `
                                                        <button ${Utils.mapActionAttributes('sensors.loadEditForm', install.id, stationId, projectId)}
                                                            class="btn-secondary text-sm flex-1">
                                                            ✏️ Edit
                                                        </button>
                                                        <button ${Utils.mapActionAttributes('sensors.showRetrieveModal', install.id, stationId, projectId)}
                                                            class="btn-secondary text-sm flex-1">
                                                            ✓ Mark as Retrieved
                                                        </button>
                                                        <button ${Utils.mapActionAttributes('sensors.showInstallStatusChangeModal', install.id, 'lost', install.sensor_name || 'Sensor', stationId, projectId)}
                                                            class="btn-secondary text-sm flex-1">
                                                            ⚠ Mark as Lost
                                                        </button>
                                                        <button ${Utils.mapActionAttributes('sensors.showInstallStatusChangeModal', install.id, 'abandoned', install.sensor_name || 'Sensor', stationId, projectId)}
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
                                    <svg class="w-16 h-16 text-slate-400 center-x mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                                    </svg>
                                    <h3 class="text-white text-lg font-medium mb-2">No Sensors Currently Installed</h3>
                                    <p class="text-slate-400 mb-4">This station doesn't have any sensors installed yet.</p>
                                    ${hasWriteAccess ? `
                                        <button ${Utils.mapActionAttributes('sensors.loadInstallForm', stationId, projectId)} class="btn-primary">
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
        const container = (document.getElementById('station-modal-content') as HTMLElement);
        container.innerHTML = `
            <div class="tab-content active">
                <div class="flex items-center justify-center min-h-[300px]">
                    <div class="text-center">
                        <svg class="w-16 h-16 text-slate-400 center-x mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                        </svg>
                        <h3 class="text-white text-lg font-medium mb-2">No Sensors Installed</h3>
                        <p class="text-slate-400">Select a station to view and manage its sensor installations.</p>
                    </div>
                </div>
            </div>
        `;
    },

    async loadHistory(stationId: EntityId, projectId: EntityId | null) {
        const container = (document.getElementById('station-modal-content') as HTMLElement);
        const loadingOverlay = Utils.showLoadingOverlay('Loading sensor history...');

        currentStationId = stationId;
        currentProjectId = projectId;

        try {
            const response = await API.getStationSensorInstalls(stationId);

            const allInstalls = Array.isArray(response) ? response : [];

            Utils.hideLoadingOverlay(loadingOverlay);

            // Store data for filtering
            sensorHistoryData = allInstalls;
            currentSortColumn = 'modified_date';
            currentSortDirection = 'desc';
            currentStatusFilter = 'all';

            void renderSensorHistoryTable(allInstalls, stationId, projectId, 'all');
        } catch (error) {
            console.error('Error loading sensor history:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', 'Failed to load sensor history. Please try again.');
        }
    },

    filterHistory() {
        const statusFilter = (document.getElementById('status-filter-select') as HTMLSelectElement).value;
        currentStatusFilter = statusFilter;
        let filteredData = sensorHistoryData;

        if (statusFilter !== 'all') {
            filteredData = sensorHistoryData.filter(install => install.status === statusFilter);
        }

        void renderSensorHistoryTable(filteredData, currentStationId as EntityId, currentProjectId, statusFilter);
    },

    sortHistory(column: keyof SensorInstallRecord) {
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

        void renderSensorHistoryTable(sortedData, currentStationId as EntityId, currentProjectId, statusFilter);
    },

    async exportHistory(stationId: EntityId) {
        const btn = (document.getElementById('export-sensor-history-btn') as HTMLButtonElement);
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
            Utils.showNotification('error', 'Failed to export data: ' + (error as Error).message);
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        }
    },

    async refreshHistory() {
        const btn = (document.getElementById('refresh-sensor-history-btn') as HTMLButtonElement);
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

            const allInstalls = Array.isArray(response) ? response : [];

            sensorHistoryData = allInstalls;

            let filteredData = allInstalls;
            if (statusFilter !== 'all') {
                filteredData = allInstalls.filter(install => install.status === statusFilter);
            }

            void renderSensorHistoryTable(filteredData, stationId, projectId, statusFilter);

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
            Utils.showNotification('error', 'Failed to refresh sensor history: ' + (error as Error).message);
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        }
    },

    async loadInstallForm(stationId: EntityId, projectId: EntityId | null) {
        const container = (document.getElementById('station-modal-content') as HTMLElement);
        const loadingOverlay = Utils.showLoadingOverlay('Loading sensor fleets...');

        try {
            // Fetch fleets
            const fleetsResponse = await API.getSensorFleets();

            const fleets = Array.isArray(fleetsResponse) ? fleetsResponse : [];

            if (fleets.length === 0) {
                Utils.hideLoadingOverlay(loadingOverlay);
                container.innerHTML = `
                    <div class="tab-content active">
                        <div class="text-center py-12">
                            <svg class="w-16 h-16 text-slate-400 center-x mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                            </svg>
                            <h3 class="text-white text-lg font-medium mb-2">No Sensor Fleets Available</h3>
                            <p class="text-slate-400 mb-4">You need to create a sensor fleet before installing sensors.</p>
                            <button ${Utils.mapActionAttributes('sensors.loadCurrentInstalls', stationId, projectId)} class="btn-secondary">
                                ← Back to Sensor Management
                            </button>
                        </div>
                    </div>
                `;
                return;
            }

            // Fetch sensors for all fleets in parallel to calculate available counts
            const fleetSensorsPromises = fleets.map(fleet =>
                API.getSensorFleetSensors(fleet.id)
                    .then(res => Array.isArray(res) ? res : [])
                    .catch(() => [])
            );

            const fleetSensorsResults = await Promise.all(fleetSensorsPromises);

            // Cache the fleet sensors for use by loadFleetSensors
            fleetSensorsCache = {};
            fleets.forEach((fleet, index) => {
                fleetSensorsCache[fleet.id] = fleetSensorsResults[index] || [];
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
                    <div class="flow-y-6">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xl font-semibold text-white">Install Sensor</h3>
                            <button ${Utils.mapActionAttributes('sensors.loadCurrentInstalls', stationId, projectId)} class="btn-secondary text-sm">
                                ← Back
                            </button>
                        </div>

                        <form id="install-sensor-form" class="flow-y-6">
                            <div>
                                <label class="form-label">Sensor Fleet *</label>
                                <select id="sensor-fleet-select"
                                    class="form-input" required>
                                    <option value="">Select a fleet...</option>
                                    ${fleetsWithAvailableCount.map(fleet => `
                                        <option value="${fleet.id}">${Utils.escapeHtml(fleet.name)} (${fleet.availableCount} available)</option>
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
                                <button type="button" ${Utils.mapActionAttributes('sensors.loadCurrentInstalls', stationId, projectId)} class="btn-secondary">
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            `;

            // Setup fleet selector
            const fleetSelect = (document.getElementById('sensor-fleet-select') as HTMLSelectElement);
            // Preserve the ordinary listener returning the receiver's loading promise.
            // eslint-disable-next-line @typescript-eslint/no-misused-promises
            fleetSelect.addEventListener('change', () => this.loadFleetSensors(fleetSelect.value, stationId));

            // Setup date validation
            (document.getElementById('install-date') as HTMLInputElement).addEventListener('change', validateSensorInstallDates);
            (document.getElementById('expiracy-memory-date') as HTMLInputElement).addEventListener('change', validateSensorInstallDates);
            (document.getElementById('expiracy-battery-date') as HTMLInputElement).addEventListener('change', validateSensorInstallDates);

            // Setup form submission
            (document.getElementById('install-sensor-form') as HTMLElement).addEventListener('submit', (e) => {
                e.preventDefault();
                void this.handleInstall(stationId, projectId, null);
            });

        } catch (error) {
            console.error('Error loading install form:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', 'Failed to load sensor installation form. Please try again.');
        }
    },

    async loadFleetSensors(fleetId: EntityId, stationId: EntityId, currentSensorId: EntityId | null = null) {
        const sensorSelect = (document.getElementById('sensor-select') as HTMLSelectElement);
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

                allSensors = Array.isArray(sensorsResponse) ? sensorsResponse : [];
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
                            ${Utils.escapeHtml(sensor.name)}
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

    async handleInstall(stationId: EntityId, projectId: EntityId | null, installId: EntityId | null = null) {
        if (!validateSensorInstallDates()) {
            Utils.showNotification('error', 'Please fix the date validation errors before submitting.');
            return;
        }

        const isEdit = installId !== null;
        const loadingOverlay = Utils.showLoadingOverlay(isEdit ? 'Updating sensor installation...' : 'Installing sensor...');

        try {
            const sensorId = (document.getElementById('sensor-select') as HTMLSelectElement).value;
            const installDate = (document.getElementById('install-date') as HTMLInputElement).value;
            const expiracyMemoryDate = (document.getElementById('expiracy-memory-date') as HTMLInputElement).value;
            const expiracyBatteryDate = (document.getElementById('expiracy-battery-date') as HTMLInputElement).value;

            const formData = new FormData();
            formData.append('sensor', sensorId);
            formData.append('install_date', installDate);

            if (expiracyMemoryDate) {
                formData.append('expiracy_memory_date', expiracyMemoryDate);
            } else if (isEdit) {
                // Keep FormData's existing null-to-string coercion for clearing an expiry.
                formData.append('expiracy_memory_date', null as unknown as string);
            }

            if (expiracyBatteryDate) {
                formData.append('expiracy_battery_date', expiracyBatteryDate);
            } else if (isEdit) {
                formData.append('expiracy_battery_date', null as unknown as string);
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
            void this.loadCurrentInstalls(stationId, projectId);
        } catch (error) {
            console.error(`Error ${isEdit ? 'updating' : 'installing'} sensor:`, error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', `Error ${isEdit ? 'updating' : 'installing'} sensor. Please try again.`);
        }
    },

    async loadEditForm(installId: EntityId, stationId: EntityId, projectId: EntityId | null) {
        const container = (document.getElementById('station-modal-content') as HTMLElement);
        const loadingOverlay = Utils.showLoadingOverlay('Loading sensor installation...');

        try {
            const install = await API.getStationSensorInstallDetails(stationId, installId);

            if (!install || !install.id) {
                throw new Error('Failed to load sensor installation details');
            }

            if (install.status !== 'installed') {
                Utils.hideLoadingOverlay(loadingOverlay);
                Utils.showNotification('error', 'Only installed sensors can be edited.');
                void this.loadCurrentInstalls(stationId, projectId);
                return;
            }

            // Fetch fleets
            const fleetsResponse = await API.getSensorFleets();

            const fleets = Array.isArray(fleetsResponse) ? fleetsResponse : [];

            const currentFleetId = install.sensor_fleet_id;

            // Fetch sensors for all fleets in parallel to calculate available counts
            const fleetSensorsPromises = fleets.map(fleet =>
                API.getSensorFleetSensors(fleet.id)
                    .then(res => Array.isArray(res) ? res : [])
                    .catch(() => [])
            );

            const fleetSensorsResults = await Promise.all(fleetSensorsPromises);

            // Cache the fleet sensors for use by loadFleetSensors
            fleetSensorsCache = {};
            fleets.forEach((fleet, index) => {
                fleetSensorsCache[fleet.id] = fleetSensorsResults[index] || [];
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
            const currentFleetSensors = currentFleetIndex >= 0 ? fleetSensorsCache[fleets[currentFleetIndex]!.id]! : [];
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
                    <div class="flow-y-6">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xl font-semibold text-white">Edit Sensor Installation</h3>
                            <button ${Utils.mapActionAttributes('sensors.loadCurrentInstalls', stationId, projectId)} class="btn-secondary text-sm">
                                ← Back
                            </button>
                        </div>

                        <form id="install-sensor-form" class="flow-y-6">
                            <div>
                                <label class="form-label">Sensor Fleet *</label>
                                <select id="sensor-fleet-select"
                                    class="form-input" required>
                                    <option value="">Select a fleet...</option>
                                    ${fleetsWithAvailableCount.map(fleet => `
                                        <option value="${fleet.id}" ${fleet.id === currentFleetId ? 'selected' : ''}>
                                            ${Utils.escapeHtml(fleet.name)} (${fleet.availableCount} available)
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
                                            ${Utils.escapeHtml(sensor.name)}
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
                                <button type="button" ${Utils.mapActionAttributes('sensors.loadCurrentInstalls', stationId, projectId)} class="btn-secondary">
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            `;

            // Setup fleet selector
            const fleetSelect = (document.getElementById('sensor-fleet-select') as HTMLSelectElement);
            // Preserve the ordinary listener returning the receiver's loading promise.
            // eslint-disable-next-line @typescript-eslint/no-misused-promises
            fleetSelect.addEventListener('change', () => this.loadFleetSensors(fleetSelect.value, stationId, install.sensor_id));

            // Setup date validation
            (document.getElementById('install-date') as HTMLInputElement).addEventListener('change', validateSensorInstallDates);
            (document.getElementById('expiracy-memory-date') as HTMLInputElement).addEventListener('change', validateSensorInstallDates);
            (document.getElementById('expiracy-battery-date') as HTMLInputElement).addEventListener('change', validateSensorInstallDates);

            // Validate dates on load
            setTimeout(() => validateSensorInstallDates(), 100);

            // Setup form submission
            (document.getElementById('install-sensor-form') as HTMLElement).addEventListener('submit', (e) => {
                e.preventDefault();
                void this.handleInstall(stationId, projectId, installId);
            });

        } catch (error) {
            console.error('Error loading edit form:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', 'Failed to load sensor installation form. Please try again.');
        }
    },

    showRetrieveModal(installId: EntityId, stationId: EntityId, projectId: EntityId | null) {
        const today = new Date().toISOString().split('T')[0];
        const container = (document.getElementById('station-modal-content') as HTMLElement);

        container.innerHTML = `
            <div class="tab-content active">
                <div class="flow-y-6">
                    <h3 class="text-xl font-semibold text-white">Mark Sensor as Retrieved</h3>

                    <form id="retrieve-sensor-form" class="flow-y-6">
                        <div>
                            <label class="form-label">Retrieval Date *</label>
                            <input type="date" id="retrieval-date" class="form-input" value="${today}" required>
                        </div>

                        <div class="flex gap-4">
                            <button type="submit" class="btn-primary flex-1">
                                Mark as Retrieved
                            </button>
                            <button type="button" ${Utils.mapActionAttributes('sensors.loadCurrentInstalls', stationId, projectId)} class="btn-secondary">
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        (document.getElementById('retrieve-sensor-form') as HTMLElement).addEventListener('submit', (e) => {
            e.preventDefault();
            void this.handleRetrieve(installId, stationId, projectId);
        });
    },

    async handleRetrieve(installId: EntityId, stationId: EntityId, projectId: EntityId | null) {
        const loadingOverlay = Utils.showLoadingOverlay('Updating sensor status...');

        try {
            const retrievalDate = (document.getElementById('retrieval-date') as HTMLInputElement).value;

            const formData = new FormData();
            formData.append('status', 'retrieved');
            formData.append('uninstall_date', retrievalDate);

            await API.updateStationSensorInstalls(stationId, installId, formData);

            Utils.hideLoadingOverlay(loadingOverlay);

            // Clear the cache since installed sensors have changed
            fleetSensorsCache = {};

            Utils.showNotification('success', 'Sensor marked as retrieved!');
            void this.loadCurrentInstalls(stationId, projectId);
        } catch (error) {
            console.error('Error retrieving sensor:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', (error as Error).message || 'Error updating sensor status. Please try again.');
        }
    },

    showInstallStatusChangeModal(installId: EntityId, newStatus: string, sensorName: string, stationId: EntityId, projectId: EntityId | null) {
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

        const config = statusConfig[newStatus as keyof typeof statusConfig];
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
            <div id="sensor-status-change-modal" class="fixed inset-0 bg-srgb-black-50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6 border-b border-slate-600">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center">
                                <div class="w-10 h-10 rounded-full flex items-center justify-center text-xl mr-3" style="background: ${config.iconBg}">
                                    ${config.icon}
                                </div>
                                <h3 class="text-xl font-semibold text-white">Mark Sensor as ${config.label}</h3>
                            </div>
                            <button ${Utils.mapActionAttributes('sensors.cancelStatusChange')} class="text-slate-400 hover:text-white transition-colors">
                                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="p-6">
                        <p class="text-slate-300 mb-4">${config.message}</p>
                        <div class="bg-srgb-slate-700-50 rounded-lg p-3 mb-4">
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-400">Sensor:</span>
                                <span class="text-white">${Utils.escapeHtml(sensorName)}</span>
                            </div>
                            <div class="flex justify-between text-sm mt-2">
                                <span class="text-slate-400">New Status:</span>
                                <span class="text-white">${config.label}</span>
                            </div>
                        </div>
                        <div class="bg-srgb-amber-500-10 border border-srgb-amber-500-30 rounded-lg p-3 mb-6">
                            <p class="text-amber-400 text-sm font-medium">⚠️ This action cannot be undone</p>
                            <p class="text-amber-300 text-xs mt-1">${config.warning}</p>
                        </div>
                        <div class="flex gap-3 justify-end">
                            <button ${Utils.mapActionAttributes('sensors.cancelStatusChange')} class="btn-secondary">
                                Cancel
                            </button>
                            <button ${Utils.mapActionAttributes('sensors.confirmStatusChange')} class="${config.btnClass}">
                                ${config.btnText}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal
        const existingModal = (document.getElementById('sensor-status-change-modal') as HTMLElement);
        if (existingModal) existingModal.remove();

        getMapOverlayHost().insertAdjacentHTML('beforeend', modalHtml);
    },

    cancelStatusChange() {
        const modal = (document.getElementById('sensor-status-change-modal') as HTMLElement);
        if (modal) modal.remove();
        pendingSensorStatusChange = null;
    },

    async confirmStatusChange() {
        if (!pendingSensorStatusChange) return;

        const { installId, newStatus, stationId, projectId } = pendingSensorStatusChange;

        const modal = (document.getElementById('sensor-status-change-modal') as HTMLElement);
        if (modal) modal.remove();

        const statusLabels = {
            'lost': 'Lost',
            'abandoned': 'Abandoned'
        };
        const label = statusLabels[newStatus as keyof typeof statusLabels] || newStatus;

        const loadingOverlay = Utils.showLoadingOverlay(`Marking sensor as ${label}...`);

        try {
            const formData = new FormData();
            formData.append('status', newStatus);

            await API.updateStationSensorInstalls(stationId, installId, formData);

            Utils.hideLoadingOverlay(loadingOverlay);

            // Clear the cache since installed sensors have changed
            fleetSensorsCache = {};

            Utils.showNotification('success', `Sensor marked as ${label}!`);
            void this.loadCurrentInstalls(stationId, projectId);
        } catch (error) {
            console.error(`Error marking sensor as ${newStatus}:`, error);
            Utils.hideLoadingOverlay(loadingOverlay);
            Utils.showNotification('error', (error as Error).message || `Error updating sensor status. Please try again.`);
        } finally {
            pendingSensorStatusChange = null;
        }
    }
};

// Expose functions globally for onclick handlers
