import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { SensorInstallRecord } from '../../../../../../ts-types/domain/fleet-records.ts';
import { Utils } from '../utils.ts';

/**
 * Get color class for sensor install status
 */
export function getSensorInstallStatusColor(status: string) {
    const colors = {
        'installed': 'bg-green-500',
        'retrieved': 'bg-blue-500',
        'lost': 'bg-red-500',
        'abandoned': 'bg-orange-500'
    };
    return colors[status?.toLowerCase() as keyof typeof colors] || 'bg-gray-500';
}

/**
 * Get label for sensor install status
 */
export function getSensorInstallStatusLabel(status: string) {
    const labels = {
        'installed': 'Installed',
        'retrieved': 'Retrieved',
        'lost': 'Lost',
        'abandoned': 'Abandoned'
    };
    return labels[status?.toLowerCase() as keyof typeof labels] || Utils.escapeHtml(status);
}

/**
 * Check if sensor install status can be changed
 */
export function canChangeSensorInstallStatus(install: SensorInstallRecord) {
    return install.status === 'installed';
}

/**
 * Format date string without timezone issues
 */
export function formatDateString(dateStr: string | null | undefined) {
    if (!dateStr) return '';

    // Extract just the date part
    const dateOnly = dateStr.split('T')[0]!;
    const parts = dateOnly.split('-');

    if (parts.length === 3) {
        const year = parseInt(parts[0]!, 10);
        const month = parseInt(parts[1]!, 10) - 1;
        const day = parseInt(parts[2]!, 10);
        const date = new Date(year, month, day);
        return date.toLocaleDateString();
    }

    return new Date(dateStr).toLocaleDateString();
}

/**
 * Format expiry date with color coding
 */
export function formatExpiracyDate(dateStr: string | null | undefined) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffTime = (date as unknown as number) - (now as unknown as number);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    let colorClass = 'text-emerald-400';
    if (diffDays < 0) colorClass = 'text-red-400';
    else if (diffDays < 7) colorClass = 'text-amber-400';

    return `<span class="${colorClass}">${date.toLocaleDateString()} (${diffDays > 0 ? 'in ' : ''}${Math.abs(diffDays)} days${diffDays < 0 ? ' ago' : ''})</span>`;
}

/**
 * Validate sensor install dates
 */
export function validateSensorInstallDates() {
    const installDateInput = (document.getElementById('install-date') as HTMLInputElement);
    const expiracyMemoryInput = (document.getElementById('expiracy-memory-date') as HTMLInputElement);
    const expiracyBatteryInput = (document.getElementById('expiracy-battery-date') as HTMLInputElement);

    const installDateError = (document.getElementById('install-date-error') as HTMLElement);
    const expiracyMemoryError = (document.getElementById('expiracy-memory-date-error') as HTMLElement);
    const expiracyBatteryError = (document.getElementById('expiracy-battery-date-error') as HTMLElement);

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

export function renderSensorHistoryHtml(installs: SensorInstallRecord[], stationId: EntityId, projectId: EntityId | null, currentFilter: string, hasWriteAccess: boolean) {
    return `
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
                        class="sensor-subtab px-4 py-2 text-sm font-medium transition-colors text-slate-400 hover:text-slate-300"
                        ${Utils.mapActionAttributes('sensors.loadCurrentInstalls', stationId, projectId)}
                        data-subtab="current">
                        Current Installs
                    </button>
                    <button
                        class="sensor-subtab px-4 py-2 text-sm font-medium transition-colors text-sky-400 border-b-2 border-sky-400"
                        ${Utils.mapActionAttributes('sensors.loadHistory', stationId, projectId)}
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
                            ${Utils.mapActionAttributes('sensors.filterHistory')} data-map-event="change"
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
                            ${Utils.mapActionAttributes('sensors.refreshHistory')}
                            id="refresh-sensor-history-btn"
                            class="btn-secondary text-sm flex items-center gap-2"
                            title="Refresh sensor history">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                            </svg>
                            <span>Refresh</span>
                        </button>
                        <button
                            ${Utils.mapActionAttributes('sensors.exportHistory', stationId)}
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
                            <thead class="bg-srgb-slate-800-50 text-slate-300 text-left">
                                <tr>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-srgb-slate-700-50" ${Utils.mapActionAttributes('sensors.sortHistory', 'sensor_name')}>
                                        <div class="flex items-center gap-1">
                                            Sensor Name
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-srgb-slate-700-50" ${Utils.mapActionAttributes('sensors.sortHistory', 'sensor_fleet_name')}>
                                        <div class="flex items-center gap-1">
                                            Fleet Name
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-srgb-slate-700-50" ${Utils.mapActionAttributes('sensors.sortHistory', 'status')}>
                                        <div class="flex items-center gap-1">
                                            State
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-srgb-slate-700-50" ${Utils.mapActionAttributes('sensors.sortHistory', 'install_date')}>
                                        <div class="flex items-center gap-1">
                                            Install Date
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium">Install User</th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-srgb-slate-700-50" ${Utils.mapActionAttributes('sensors.sortHistory', 'uninstall_date')}>
                                        <div class="flex items-center gap-1">
                                            Retrieval Date
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                    <th class="px-4 py-3 font-medium">Retrieval User</th>
                                    <th class="px-4 py-3 font-medium cursor-pointer hover:bg-srgb-slate-700-50" ${Utils.mapActionAttributes('sensors.sortHistory', 'modified_date')}>
                                        <div class="flex items-center gap-1">
                                            Modified
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5 8l5-5 5 5H5z"></path></svg>
                                        </div>
                                    </th>
                                </tr>
                            </thead>
                            <tbody class="row-divide-y row-divide-slate-700" id="sensor-history-tbody">
                                ${installs.map((install, index) => `
                                    <tr class="hover:bg-srgb-slate-800-30 ${index % 2 === 0 ? 'bg-srgb-slate-900-20' : ''}">
                                        <td class="px-4 py-3 text-white font-medium">${Utils.escapeHtml(install.sensor_name || 'Unknown')}</td>
                                        <td class="px-4 py-3 text-slate-300">${Utils.escapeHtml(install.sensor_fleet_name || 'Unknown')}</td>
                                        <td class="px-4 py-3">
                                            <span class="px-2 py-1 ${getSensorInstallStatusColor(install.status)} text-white text-xs rounded-full font-medium block w-20 text-center">
                                                ${getSensorInstallStatusLabel(install.status)}
                                            </span>
                                        </td>
                                        <td class="px-4 py-3 text-slate-300">${formatDateString(install.install_date)}</td>
                                        <td class="px-4 py-3 text-slate-400 text-xs">${Utils.escapeHtml(install.install_user || '-')}</td>
                                        <td class="px-4 py-3 text-slate-300">${install.uninstall_date ? formatDateString(install.uninstall_date) : '-'}</td>
                                        <td class="px-4 py-3 text-slate-400 text-xs">${Utils.escapeHtml(install.uninstall_user || '-')}</td>
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
                        <svg class="w-16 h-16 text-slate-400 center-x mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
