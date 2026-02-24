import { API } from '../api.js';
import { Config } from '../config.js';
import { Utils } from '../utils.js';

// Mandatory field UUIDs (matching backend MandatoryFieldUuid)
const MANDATORY_FIELD_UUIDS = {
    MEASUREMENT_DATE: '00000000-0000-0000-0000-000000000001',
    SUBMITTER_EMAIL: '00000000-0000-0000-0000-000000000002'
};

/**
 * Check if a field is the submitter email field (auto-filled by backend)
 */
function isSubmitterEmailField(field) {
    if (!field) return false;
    return field.id === MANDATORY_FIELD_UUIDS.SUBMITTER_EMAIL;
}

// Module state
let selectedExperimentId = null;
let experimentDataRows = [];
let currentStationId = null;
let currentProjectId = null;

function getExperimentScopeAccess(parentId, isSurfaceStation) {
    return Config.getScopedAccess(isSurfaceStation ? 'network' : 'project', parentId);
}

/**
 * Sort experiment fields by their order property
 */
function sortExperimentFields(fields) {
    let fieldsArray = [];

    if (Array.isArray(fields)) {
        fieldsArray = fields.map(field => ({
            id: field.id,
            ...field
        }));
    } else if (fields && typeof fields === 'object') {
        fieldsArray = Object.entries(fields).map(([uuid, field]) => ({
            id: uuid,
            ...field
        }));
    }

    fieldsArray.sort((a, b) => {
        const orderA = a.order !== undefined ? a.order : 999;
        const orderB = b.order !== undefined ? b.order : 999;
        return orderA - orderB;
    });

    return fieldsArray;
}

/**
 * Validate an experiment field value
 */
function validateExperimentField(value, fieldType, required, fieldId = '') {
    if (required && (value === null || value === undefined || value === '')) {
        return { valid: false, message: 'This field is required' };
    }
    if (!required && (value === null || value === undefined || value === '')) {
        return { valid: true };
    }

    switch (fieldType) {
        case 'number':
            const num = parseFloat(value);
            if (isNaN(num)) {
                return { valid: false, message: 'Must be a valid number' };
            }
            return { valid: true };
        case 'date':
            const date = new Date(value);
            if (isNaN(date.getTime())) {
                return { valid: false, message: 'Must be a valid date' };
            }
            // For measurement_date, ensure it's not in the future
            if (fieldId === MANDATORY_FIELD_UUIDS.MEASUREMENT_DATE) {
                const today = new Date();
                today.setHours(23, 59, 59, 999);
                if (date > today) {
                    return { valid: false, message: 'Measurement date cannot be in the future' };
                }
            }
            return { valid: true };
        case 'text':
        case 'boolean':
        case 'select':
        default:
            return { valid: true };
    }
}

/**
 * Render the experiment data table
 */
function renderExperimentTable(experiment, dataRows, stationId, projectId, isSurfaceStation = false) {
    const sortedFields = sortExperimentFields(experiment.experiment_fields || {});
    const access = getExperimentScopeAccess(projectId, isSurfaceStation);
    const hasWriteAccess = access.write;
    const isAdmin = access.delete;

    if (!dataRows || dataRows.length === 0) {
        return `
            <div class="text-center py-12 bg-slate-800/30 rounded-lg border border-slate-600/50">
                <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <h3 class="text-white text-lg font-medium mb-2">No Data Records Yet</h3>
                <p class="text-slate-400 mb-4">Start recording data for this experiment.</p>
                ${hasWriteAccess ? `
                    <button onclick="window.StationExperiments.openAddRowModal('${stationId}', '${projectId}', '${experiment.id}')" class="btn-primary">
                        <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                        </svg>
                        Add First Record
                    </button>
                ` : ''}
            </div>
        `;
    }

    return `
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead class="text-xs font-semibold uppercase text-slate-400 bg-slate-900/50 border-b border-slate-600">
                    <tr>
                        ${sortedFields.map(field => `
                            <th class="px-4 py-3 whitespace-nowrap text-center">
                                ${field.name}
                                ${field.required ? '<span class="text-red-400 ml-1">*</span>' : ''}
                            </th>
                        `).join('')}
                        ${hasWriteAccess ? '<th class="px-4 py-3 whitespace-nowrap text-center">Actions</th>' : ''}
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-700">
                    ${dataRows.map((row, idx) => {
        const rowData = row.data || {};

        return `
                        <tr class="hover:bg-slate-700/30 transition-colors">
                            ${sortedFields.map(field => {
            let value = rowData[field.id];

            let displayValue = '';
            if (value === null || value === undefined) {
                displayValue = '<span class="text-slate-500 italic">—</span>';
            } else if (field.type === 'date') {
                try {
                    const date = new Date(value);
                    displayValue = date.toLocaleDateString();
                } catch (e) {
                    displayValue = value;
                }
            } else if (field.type === 'number') {
                displayValue = typeof value === 'number' ? value.toLocaleString() : value;
            } else if (field.type === 'boolean') {
                displayValue = value ? 'Yes' : 'No';
            } else {
                displayValue = String(value);
            }
            return `<td class="px-4 py-3 text-slate-300 text-center">${displayValue}</td>`;
        }).join('')}
                            ${hasWriteAccess ? `
                                <td class="px-4 py-3 text-center">
                                    ${isAdmin ? `
                                        <button onclick="window.StationExperiments.openDeleteRowModal('${stationId}', '${experiment.id}', '${row.id || idx}')" class="text-red-400 hover:text-red-300 inline-flex items-center justify-center" title="Delete">
                                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                            </svg>
                                        </button>
                                    ` : `
                                        <button disabled class="text-slate-500 cursor-not-allowed inline-flex items-center justify-center" title="Only admins can delete records">
                                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                            </svg>
                                        </button>
                                    `}
                                </td>
                            ` : ''}
                        </tr>
                        `;
    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

export const StationExperiments = {
    async render(stationId, container) {
        currentStationId = stationId;
        // Get project/network ID from state - check both subsurface and surface stations
        const { State } = await import('../state.js');
        const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
        const isSurfaceStation = station?.network || station?.station_type === 'surface';
        currentProjectId = station?.project || station?.network || null;

        const stationAccess = Config.getStationAccess(station);
        const hasWriteAccess = stationAccess.write;

        // Show loading overlay
        const loadingOverlay = Utils.showLoadingOverlay('Loading experiments...');

        try {
            const experimentsResponse = await API.getExperiments();
            const experiments = experimentsResponse?.data || experimentsResponse || [];
            const activeExperiments = experiments.filter(exp => exp.is_active);

            if (activeExperiments.length === 0) {
                Utils.hideLoadingOverlay(loadingOverlay);
                container.innerHTML = `
                    <div class="tab-content active">
                        <div class="space-y-6">
                            <div class="flex items-center justify-between">
                                <h3 class="text-xl font-semibold text-white">Scientific Experiments</h3>
                            </div>
                            <div class="text-center py-12 bg-slate-800/30 rounded-lg border border-slate-600/50">
                                <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                                </svg>
                                <h3 class="text-white text-lg font-medium mb-2">No Active Experiments</h3>
                                <p class="text-slate-400">There are no active experiments available. Contact an administrator to create one.</p>
                            </div>
                        </div>
                    </div>
                `;
                return;
            }

            // Reset state
            selectedExperimentId = null;
            experimentDataRows = [];

            const renderContent = () => {
                const selectedExperiment = activeExperiments.find(exp => exp.id === selectedExperimentId);

                container.innerHTML = `
                    <div class="tab-content active">
                        <div class="space-y-6">
                            <div class="flex items-center justify-between flex-wrap gap-4">
                                <h3 class="text-xl font-semibold text-white">Scientific Experiments</h3>
                                ${selectedExperiment && hasWriteAccess ? `
                                    <button onclick="window.StationExperiments.openAddRowModal('${stationId}', '${currentProjectId}', '${selectedExperiment.id}')" class="btn-primary">
                                        <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                                        </svg>
                                        Add Record
                                    </button>
                                ` : ''}
                            </div>

                            <div class="bg-slate-800/30 rounded-lg border border-slate-600/50 p-4">
                                <label class="block text-sm font-medium text-slate-300 mb-2">Select Experiment</label>
                                <select id="experiment-selector" class="bg-slate-700 text-white rounded-lg p-2 w-full focus:ring-2 focus:ring-sky-500 focus:border-transparent">
                                    <option value="">-- Choose an experiment --</option>
                                    ${activeExperiments.map(exp => `
                                        <option value="${exp.id}" ${exp.id === selectedExperimentId ? 'selected' : ''}>
                                            ${exp.name}${exp.code ? ` (${exp.code})` : ''}
                                        </option>
                                    `).join('')}
                                </select>
                                ${selectedExperiment ? `
                                    <div class="mt-3 text-sm text-slate-400">
                                        ${selectedExperiment.description ? `<p class="mb-2">${selectedExperiment.description}</p>` : ''}
                                        ${selectedExperiment.start_date ? `<p>Period: ${new Date(selectedExperiment.start_date).toLocaleDateString()}${selectedExperiment.end_date ? ` - ${new Date(selectedExperiment.end_date).toLocaleDateString()}` : ''}</p>` : ''}
                                    </div>
                                ` : ''}
                            </div>

                            ${selectedExperiment ? `
                                <div class="bg-slate-800/30 rounded-lg border border-slate-600/50 p-6">
                                    <h4 class="text-lg font-semibold text-white mb-4">Data Records</h4>
                                    ${renderExperimentTable(selectedExperiment, experimentDataRows, stationId, currentProjectId, isSurfaceStation)}
                                </div>
                            ` : `
                                <div class="text-center py-12 bg-slate-800/30 rounded-lg border border-slate-600/50">
                                    <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                                    </svg>
                                    <h3 class="text-white text-lg font-medium mb-2">Select an Experiment</h3>
                                    <p class="text-slate-400">Choose an experiment from the dropdown above to view and record data.</p>
                                </div>
                            `}
                        </div>
                    </div>
                `;

                // Setup experiment selector change handler
                const selector = document.getElementById('experiment-selector');
                if (selector) {
                    selector.addEventListener('change', async (e) => {
                        selectedExperimentId = e.target.value || null;
                        if (selectedExperimentId) {
                            const dataLoadingOverlay = Utils.showLoadingOverlay('Loading experiment data...');
                            try {
                                const response = await API.getExperimentData(stationId, selectedExperimentId);
                                experimentDataRows = response?.data || response || [];
                            } catch (err) {
                                console.error('Error fetching experiment data:', err);
                                experimentDataRows = [];
                            }
                            Utils.hideLoadingOverlay(dataLoadingOverlay);
                            renderContent();
                        } else {
                            experimentDataRows = [];
                            renderContent();
                        }
                    });
                }
            };

            // Store update functions
            window.updateExperimentTable = (newRow) => {
                if (selectedExperimentId && newRow) {
                    if (!newRow.id) {
                        newRow.id = 'temp-' + Date.now();
                    }
                    experimentDataRows.push(newRow);
                    renderContent();
                }
            };

            window.deleteExperimentTableRow = (rowId) => {
                if (selectedExperimentId && rowId) {
                    experimentDataRows = experimentDataRows.filter(row => {
                        const id = row.id || row._id || String(row);
                        return String(id) !== String(rowId);
                    });
                    renderContent();
                }
            };

            // Hide loading overlay and render content
            Utils.hideLoadingOverlay(loadingOverlay);
            renderContent();
        } catch (error) {
            console.error('Error loading experiments:', error);
            Utils.hideLoadingOverlay(loadingOverlay);
            container.innerHTML = `
                <div class="tab-content active">
                    <div class="space-y-6">
                        <div class="flex items-center justify-between">
                            <h3 class="text-xl font-semibold text-white">Scientific Experiments</h3>
                        </div>
                        <div class="text-center py-12 bg-red-900/20 rounded-lg border border-red-600/50">
                            <svg class="w-16 h-16 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            <h3 class="text-white text-lg font-medium mb-2">Error Loading Experiments</h3>
                            <p class="text-slate-400">${error.message || 'An error occurred while loading experiments.'}</p>
                        </div>
                    </div>
                </div>
            `;
        }
    },

    async openAddRowModal(stationId, projectId, experimentId) {
        try {
            const experimentsResponse = await API.getExperiments();
            const experiments = experimentsResponse?.data || experimentsResponse || [];
            const experiment = experiments.find(exp => exp.id === experimentId);

            if (!experiment) {
                Utils.showNotification('error', 'Experiment not found');
                return;
            }

            const sortedFields = sortExperimentFields(experiment.experiment_fields || {});
            
            // Determine station type and use appropriate permission check
            const { State } = await import('../state.js');
            const station = State.allStations.get(stationId) || State.allSurfaceStations.get(stationId);
            const isSurfaceStation = station?.network || station?.station_type === 'surface';
            const hasWriteAccess = getExperimentScopeAccess(projectId, isSurfaceStation).write;

            if (!hasWriteAccess) {
                Utils.showNotification('warning', 'You have read access and cannot add records.');
                return;
            }

            // Build field inputs
            const fieldInputs = sortedFields.map(field => {
                // Skip submitter_email field - it's auto-filled by the backend
                if (isSubmitterEmailField(field)) {
                    return '';
                }

                let inputHtml = '';
                const fieldId = `field-${field.id}`;
                const isRequired = field.required;

                switch (field.type) {
                    case 'number':
                        inputHtml = `
                            <input type="number" 
                                   id="${fieldId}" 
                                   name="${field.id}" 
                                   step="any"
                                   ${isRequired ? 'required' : ''}
                                   class="w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:ring-2 focus:ring-sky-500 focus:border-transparent"
                                   placeholder="Enter ${field.name.toLowerCase()}">
                        `;
                        break;
                    case 'date':
                        const today = new Date().toISOString().split('T')[0];
                        const maxDate = field.id === MANDATORY_FIELD_UUIDS.MEASUREMENT_DATE ? today : '';
                        inputHtml = `
                            <input type="date" 
                                   id="${fieldId}" 
                                   name="${field.id}" 
                                   ${isRequired ? 'required' : ''}
                                   ${maxDate ? `max="${maxDate}"` : ''}
                                   class="w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:ring-2 focus:ring-sky-500 focus:border-transparent">
                        `;
                        break;
                    case 'boolean':
                        inputHtml = `
                            <select id="${fieldId}" 
                                    name="${field.id}" 
                                    ${isRequired ? 'required' : ''}
                                    class="w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:ring-2 focus:ring-sky-500 focus:border-transparent">
                                <option value="">-- Select --</option>
                                <option value="true">Yes</option>
                                <option value="false">No</option>
                            </select>
                        `;
                        break;
                    case 'select':
                        const options = field.options || [];
                        inputHtml = `
                            <select id="${fieldId}" 
                                    name="${field.id}" 
                                    ${isRequired ? 'required' : ''}
                                    class="w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:ring-2 focus:ring-sky-500 focus:border-transparent">
                                <option value="">-- Select --</option>
                                ${options.map(opt => `
                                    <option value="${opt}">${opt}</option>
                                `).join('')}
                            </select>
                        `;
                        break;
                    case 'text':
                    default:
                        inputHtml = `
                            <input type="text" 
                                   id="${fieldId}" 
                                   name="${field.id}" 
                                   ${isRequired ? 'required' : ''}
                                   class="w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:ring-2 focus:ring-sky-500 focus:border-transparent"
                                   placeholder="Enter ${field.name.toLowerCase()}">
                        `;
                }

                return `
                    <div class="field-group">
                        <label for="${fieldId}" class="block text-sm font-medium text-slate-300 mb-2">
                            ${field.name}
                            ${isRequired ? '<span class="text-red-400">*</span>' : ''}
                        </label>
                        ${inputHtml}
                        <div id="${fieldId}-error" class="text-red-400 text-sm mt-1 hidden"></div>
                    </div>
                `;
            }).join('');

            const modalHtml = `
                <div id="experiment-row-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-3xl max-h-[90vh] overflow-y-auto">
                        <div class="p-6 border-b border-slate-600">
                            <div class="flex items-center justify-between">
                                <h3 class="text-xl font-semibold text-white">Add Data Record</h3>
                                <button onclick="window.StationExperiments.closeAddRowModal()" class="text-slate-400 hover:text-white transition-colors">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                    </svg>
                                </button>
                            </div>
                            <p class="text-slate-400 text-sm mt-2">${experiment.name}</p>
                        </div>
                        <form id="experiment-row-form" class="p-6 space-y-6">
                            ${fieldInputs}
                            <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-600">
                                <button type="button" onclick="window.StationExperiments.closeAddRowModal()" class="btn-secondary">Cancel</button>
                                <button type="submit" class="btn-primary">
                                    <span class="submit-text">Save Record</span>
                                    <span class="submit-loading hidden">
                                        <span class="loading-spinner-inline"></span> Saving...
                                    </span>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            `;

            // Remove existing modal
            const existingModal = document.getElementById('experiment-row-modal');
            if (existingModal) existingModal.remove();

            document.body.insertAdjacentHTML('beforeend', modalHtml);
            document.body.style.overflow = 'hidden';

            // Setup form
            const form = document.getElementById('experiment-row-form');
            const sortedFieldsForValidation = sortExperimentFields(experiment.experiment_fields || {});

            // Real-time validation
            sortedFieldsForValidation.forEach(field => {
                if (isSubmitterEmailField(field)) return;



                const input = document.getElementById(`field-${field.id}`);
                const errorDiv = document.getElementById(`field-${field.id}-error`);
                if (input && errorDiv) {
                    input.addEventListener('blur', () => {
                        const value = input.value;
                        const isRequired = field.required;
                        const validation = validateExperimentField(value, field.type, isRequired, field.id);
                        if (!validation.valid) {
                            errorDiv.textContent = validation.message;
                            errorDiv.classList.remove('hidden');
                            input.classList.add('border-red-500');
                        } else {
                            errorDiv.classList.add('hidden');
                            input.classList.remove('border-red-500');
                        }
                    });
                }
            });

            // Form submission
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const submitBtn = form.querySelector('button[type="submit"]');
                const submitText = submitBtn.querySelector('.submit-text');
                const submitLoading = submitBtn.querySelector('.submit-loading');

                // Validate all fields
                let isValid = true;
                sortedFieldsForValidation.forEach(field => {
                    if (isSubmitterEmailField(field)) return;

                    const input = document.getElementById(`field-${field.id}`);
                    const errorDiv = document.getElementById(`field-${field.id}-error`);
                    const isRequired = field.required;
                    const value = input ? input.value : '';
                    const validation = validateExperimentField(value, field.type, isRequired, field.id);

                    if (!validation.valid) {
                        isValid = false;
                        if (errorDiv) {
                            errorDiv.textContent = validation.message;
                            errorDiv.classList.remove('hidden');
                        }
                        if (input) {
                            input.classList.add('border-red-500');
                        }
                    } else {
                        if (errorDiv) errorDiv.classList.add('hidden');
                        if (input) input.classList.remove('border-red-500');
                    }
                });

                if (!isValid) {
                    Utils.showNotification('error', 'Please fix validation errors before submitting');
                    return;
                }

                // Collect form data
                const formData = new FormData(form);
                const rowData = {};

                sortedFieldsForValidation.forEach(field => {
                    if (isSubmitterEmailField(field)) return;

                    const value = formData.get(field.id);
                    if (field.type === 'number' && value !== '') {
                        rowData[field.id] = parseFloat(value);
                    } else if (field.type === 'boolean' && value !== '') {
                        rowData[field.id] = value === 'true';
                    } else if (value !== '') {
                        rowData[field.id] = value;
                    }
                });

                // Show loading state
                submitBtn.disabled = true;
                submitText.classList.add('hidden');
                submitLoading.classList.remove('hidden');

                try {
                    const url = Urls["api:v1:experiment-records"](stationId, experimentId);

                    const response = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': Utils.getCSRFToken()
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify(rowData)
                    });

                    if (response.ok) {
                        const responseData = await response.json();

                        if (responseData && responseData.success) {
                            let savedRow = null;
                            if (responseData.data) {
                                savedRow = Array.isArray(responseData.data)
                                    ? responseData.data[0] || responseData.data
                                    : responseData.data;
                            }

                            if (!savedRow) savedRow = rowData;

                            if (typeof window.updateExperimentTable === 'function') {
                                window.updateExperimentTable(savedRow);
                            }

                            Utils.showNotification('success', 'Data record added successfully');
                            this.closeAddRowModal();
                        } else {
                            const errorMsg = responseData.errors ? Object.values(responseData.errors).flat().join(', ') : 'Failed to save record';
                            Utils.showNotification('error', errorMsg);
                        }
                    } else {
                        let errorMsg = 'Failed to save record';
                        try {
                            const errorData = await response.json();
                            if (errorData.errors) {
                                errorMsg = Object.values(errorData.errors).flat().join(', ');
                            } else if (errorData.message) {
                                errorMsg = errorData.message;
                            }
                        } catch (e) {
                            errorMsg = `Server error (${response.status})`;
                        }
                        Utils.showNotification('error', errorMsg);
                    }
                } catch (error) {
                    console.error('Error submitting experiment row:', error);
                    Utils.showNotification('error', 'Network error. Please try again.');
                } finally {
                    submitBtn.disabled = false;
                    submitText.classList.remove('hidden');
                    submitLoading.classList.add('hidden');
                }
            });

        } catch (error) {
            console.error('Error opening add row modal:', error);
            Utils.showNotification('error', 'Failed to load experiment details');
        }
    },

    closeAddRowModal() {
        const modal = document.getElementById('experiment-row-modal');
        if (modal) {
            modal.remove();
            document.body.style.overflow = '';
        }
    },

    openDeleteRowModal(stationId, experimentId, rowId) {
        const modalHtml = `
            <div id="delete-experiment-row-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                    <div class="p-6">
                        <div class="flex items-center justify-center w-12 h-12 mx-auto mb-4 bg-red-500/10 rounded-full">
                            <svg class="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                            </svg>
                        </div>
                        <h3 class="text-xl font-semibold text-white text-center mb-2">Delete Record</h3>
                        <p class="text-slate-400 text-center mb-6">Are you sure you want to delete this record? This action cannot be undone.</p>
                        <div class="flex items-center justify-end gap-3">
                            <button onclick="window.StationExperiments.closeDeleteRowModal()" class="btn-secondary">Cancel</button>
                            <button onclick="window.StationExperiments.confirmDeleteRow('${stationId}', '${experimentId}', '${rowId}')" class="btn-danger">
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal
        const existingModal = document.getElementById('delete-experiment-row-modal');
        if (existingModal) existingModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.body.style.overflow = 'hidden';
    },

    closeDeleteRowModal() {
        const modal = document.getElementById('delete-experiment-row-modal');
        if (modal) {
            modal.remove();
            document.body.style.overflow = '';
        }
    },

    async confirmDeleteRow(stationId, experimentId, rowId) {
        this.closeDeleteRowModal();

        try {
            const url = Urls["api:v1:experiment-records-detail"](rowId);

            const response = await fetch(url, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': Utils.getCSRFToken()
                },
                credentials: 'same-origin'
            });

            if (response.ok) {
                if (typeof window.deleteExperimentTableRow === 'function') {
                    window.deleteExperimentTableRow(rowId);
                }
                Utils.showNotification('success', 'Record deleted successfully');
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.message || 'Failed to delete record';
                Utils.showNotification('error', errorMessage);
            }
        } catch (error) {
            console.error('Error deleting experiment row:', error);
            Utils.showNotification('error', 'Error deleting record. Please try again.');
        }
    }
};

// Expose functions globally for onclick handlers
window.StationExperiments = StationExperiments;



