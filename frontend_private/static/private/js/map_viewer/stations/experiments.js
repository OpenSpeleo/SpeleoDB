import { API } from '../api.js';
import { Utils } from '../utils.js';

const MANDATORY_FIELD_UUIDS = {
    MEASUREMENT_DATE: '00000000-0000-0000-0000-000000000001',
    SUBMITTER_EMAIL: '00000000-0000-0000-0000-000000000002'
};

const RECORD_MODAL_ID = 'experiment-record-modal';
const DELETE_MODAL_ID = 'delete-experiment-row-modal';

// Record actions are exposed from the selected experiment's permission flags.
// Station visibility is already implied by this station-scoped page and is
// enforced again by the backend record-detail endpoint.
const experimentsState = {
    selectedExperimentId: null,
    experimentDataRows: [],
    activeExperiments: [],
    experimentsById: new Map(),
    currentContainer: null,
    currentStationId: null,
    experimentAccess: { write: false, delete: false },
    rowsLoadState: 'idle',
    rowsLoadErrorMessage: '',
    activeRowsRequestToken: 0,
};

let modalKeydownHandler = null;

function isSubmitterEmailField(field) {
    return Boolean(field) && field.id === MANDATORY_FIELD_UUIDS.SUBMITTER_EMAIL;
}

function getExperimentAccess(experiment) {
    return {
        write: Boolean(experiment?.can_write),
        delete: Boolean(experiment?.can_delete)
    };
}

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

function getEditableExperimentFields(experiment) {
    return sortExperimentFields(experiment?.experiment_fields || {}).filter(field => !isSubmitterEmailField(field));
}

function validateExperimentField(value, fieldType, required, fieldId = '') {
    if (required && (value === null || value === undefined || value === '')) {
        return { valid: false, message: 'This field is required' };
    }
    if (!required && (value === null || value === undefined || value === '')) {
        return { valid: true };
    }

    switch (fieldType) {
        case 'number': {
            const num = parseFloat(value);
            if (Number.isNaN(num)) {
                return { valid: false, message: 'Must be a valid number' };
            }
            return { valid: true };
        }
        case 'date': {
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) {
                return { valid: false, message: 'Must be a valid date' };
            }

            if (fieldId === MANDATORY_FIELD_UUIDS.MEASUREMENT_DATE) {
                const today = new Date();
                today.setHours(23, 59, 59, 999);
                if (date > today) {
                    return { valid: false, message: 'Measurement date cannot be in the future' };
                }
            }
            return { valid: true };
        }
        case 'text':
        case 'boolean':
        case 'select':
        default:
            return { valid: true };
    }
}

function setActiveExperiments(experiments) {
    experimentsState.activeExperiments = experiments;
    experimentsState.experimentsById = new Map(
        experiments.map(experiment => [experiment.id, experiment])
    );

    if (!experimentsState.experimentsById.has(experimentsState.selectedExperimentId)) {
        experimentsState.selectedExperimentId = null;
        experimentsState.experimentDataRows = [];
        experimentsState.experimentAccess = { write: false, delete: false };
        setRowsLoadState('idle');
    }
}

function setRowsLoadState(status, errorMessage = '') {
    experimentsState.rowsLoadState = status;
    experimentsState.rowsLoadErrorMessage = errorMessage;
}

async function loadActiveExperiments() {
    const experimentsResponse = await API.getExperiments();
    const experiments = Array.isArray(experimentsResponse) ? experimentsResponse : [];
    const activeExperiments = experiments.filter(experiment => experiment.is_active);
    setActiveExperiments(activeExperiments);
    return activeExperiments;
}

function getSelectedExperiment() {
    if (!experimentsState.selectedExperimentId) {
        return null;
    }
    return experimentsState.experimentsById.get(experimentsState.selectedExperimentId) || null;
}

async function ensureExperimentLoaded(experimentId) {
    const cachedExperiment = experimentsState.experimentsById.get(experimentId);
    if (cachedExperiment) {
        return cachedExperiment;
    }

    await loadActiveExperiments();
    return experimentsState.experimentsById.get(experimentId) || null;
}

function replaceCachedExperiment(experimentId, updates) {
    const cachedExperiment = experimentsState.experimentsById.get(experimentId);
    if (!cachedExperiment) {
        return;
    }

    const updatedExperiment = {
        ...cachedExperiment,
        ...updates
    };
    experimentsState.experimentsById.set(experimentId, updatedExperiment);
    experimentsState.activeExperiments = experimentsState.activeExperiments.map(experiment =>
        experiment.id === experimentId ? updatedExperiment : experiment
    );
}

function syncSelectedExperimentAccess() {
    experimentsState.experimentAccess = getExperimentAccess(getSelectedExperiment());
}

async function refreshExperimentAccessState(experimentId) {
    try {
        await loadActiveExperiments();
    } catch (error) {
        console.error('Error refreshing experiment access after 403:', error);
        replaceCachedExperiment(experimentId, {
            can_write: false,
            can_delete: false
        });
    }

    syncSelectedExperimentAccess();
}

async function handleExperimentPermissionDenied({ experimentId, actionLabel, closeModal: closeHandler = null }) {
    if (typeof closeHandler === 'function') {
        closeHandler();
    }

    await refreshExperimentAccessState(experimentId);
    renderCurrentState();
    Utils.showNotification(
        'error',
        `Your access to this experiment changed. ${actionLabel} is no longer permitted.`
    );
}

function getExperimentRowId(row) {
    if (!row) {
        return '';
    }
    return String(row.id || row._id || '');
}

function assertValidSavedRow(row) {
    if (!row || typeof row !== 'object' || Array.isArray(row)) {
        throw new Error('Server returned an invalid experiment record.');
    }

    const rowId = getExperimentRowId(row);
    if (!rowId) {
        throw new Error('Server returned an experiment record without an id.');
    }

    if (!row.data || typeof row.data !== 'object' || Array.isArray(row.data)) {
        throw new Error('Server returned an experiment record without data.');
    }

    return row;
}

function getExperimentRowById(rowId) {
    return experimentsState.experimentDataRows.find(
        row => getExperimentRowId(row) === String(rowId)
    ) || null;
}

function prependExperimentRow(row) {
    const rowId = getExperimentRowId(row);
    const remainingRows = experimentsState.experimentDataRows.filter(
        currentRow => getExperimentRowId(currentRow) !== rowId
    );
    experimentsState.experimentDataRows = [row, ...remainingRows];
}

function upsertExperimentRow(row) {
    const rowId = getExperimentRowId(row);
    let rowUpdated = false;

    experimentsState.experimentDataRows = experimentsState.experimentDataRows.map(currentRow => {
        if (getExperimentRowId(currentRow) === rowId) {
            rowUpdated = true;
            return row;
        }
        return currentRow;
    });

    if (!rowUpdated) {
        prependExperimentRow(row);
    }
}

function removeExperimentRow(rowId) {
    experimentsState.experimentDataRows = experimentsState.experimentDataRows.filter(
        row => getExperimentRowId(row) !== String(rowId)
    );
}

function formatDateDisplay(value) {
    if (!value) {
        return '';
    }

    try {
        return new Date(value).toLocaleDateString();
    } catch (error) {
        return String(value);
    }
}

function normalizeDateInputValue(value) {
    if (!value) {
        return '';
    }

    const valueAsString = String(value);
    const matchedDate = valueAsString.match(/^\d{4}-\d{2}-\d{2}/);
    if (matchedDate) {
        return matchedDate[0];
    }

    const parsedDate = new Date(valueAsString);
    if (Number.isNaN(parsedDate.getTime())) {
        return '';
    }

    return parsedDate.toISOString().split('T')[0];
}

function normalizeFieldValueForInput(field, value) {
    if (value === null || value === undefined) {
        return '';
    }

    if (field.type === 'boolean') {
        return value ? 'true' : 'false';
    }

    if (field.type === 'date') {
        return normalizeDateInputValue(value);
    }

    return String(value);
}

function parseFieldInputValue(field, value) {
    if (value === '') {
        return undefined;
    }

    switch (field.type) {
        case 'number':
            return parseFloat(value);
        case 'boolean':
            return value === 'true';
        case 'date':
        case 'select':
        case 'text':
        default:
            return value;
    }
}

function getFieldInputId(fieldId) {
    return `field-${fieldId}`;
}

function getFieldErrorId(fieldId) {
    return `${getFieldInputId(fieldId)}-error`;
}

function getFieldInputElement(field) {
    return document.getElementById(getFieldInputId(field.id));
}

function getFieldErrorElement(field) {
    return document.getElementById(getFieldErrorId(field.id));
}

function setFieldValidationState(field, input, validationResult) {
    const errorElement = getFieldErrorElement(field);
    if (!input || !errorElement) {
        return validationResult.valid;
    }

    if (validationResult.valid) {
        errorElement.textContent = '';
        errorElement.classList.add('hidden');
        input.classList.remove('border-red-500');
        return true;
    }

    errorElement.textContent = validationResult.message;
    errorElement.classList.remove('hidden');
    input.classList.add('border-red-500');
    return false;
}

function validateFieldInput(field) {
    const input = getFieldInputElement(field);
    const value = input ? input.value : '';
    const validationResult = validateExperimentField(
        value,
        field.type,
        field.required,
        field.id
    );

    return setFieldValidationState(field, input, validationResult);
}

function validateRecordForm(fields) {
    return fields.every(field => validateFieldInput(field));
}

function collectRecordFormData(fields) {
    const rowData = {};

    fields.forEach(field => {
        const input = getFieldInputElement(field);
        const parsedValue = parseFieldInputValue(field, input ? input.value : '');
        if (parsedValue !== undefined) {
            rowData[field.id] = parsedValue;
        }
    });

    return rowData;
}

function flattenErrorMessages(errors) {
    if (!errors) {
        return [];
    }
    if (Array.isArray(errors)) {
        return errors.flatMap(flattenErrorMessages);
    }
    if (typeof errors === 'object') {
        return Object.values(errors).flatMap(flattenErrorMessages);
    }
    return [String(errors)];
}

function getApiErrorMessage(error, fallbackMessage) {
    const nestedErrors = flattenErrorMessages(error?.data?.errors);
    if (nestedErrors.length > 0) {
        return nestedErrors.join(', ');
    }
    if (error?.data?.message) {
        return error.data.message;
    }
    if (error?.message) {
        return error.message;
    }
    return fallbackMessage;
}

function renderStateCard({ title, message, actionHtml = '', tone = 'default', iconSvg }) {
    const cardClasses = tone === 'error'
        ? 'bg-red-900/20 border border-red-600/50'
        : 'bg-slate-800/30 border border-slate-600/50';
    const iconClasses = tone === 'error' ? 'text-red-400' : 'text-slate-400';

    return `
        <div class="text-center py-12 rounded-lg ${cardClasses}">
            <svg class="w-16 h-16 ${iconClasses} mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                ${iconSvg}
            </svg>
            <h3 class="text-white text-lg font-medium mb-2">${Utils.escapeHtml(title)}</h3>
            <p class="text-slate-400 ${actionHtml ? 'mb-4' : ''}">${Utils.escapeHtml(message)}</p>
            ${actionHtml}
        </div>
    `;
}

function renderAddRecordButton({ buttonId = '', experimentId, label }) {
    const idAttribute = buttonId ? `id="${buttonId}"` : '';

    return `
        <button type="button"
                ${idAttribute}
                data-experiment-action="add-record"
                data-station-id="${Utils.escapeHtml(experimentsState.currentStationId || '')}"
                data-experiment-id="${Utils.escapeHtml(experimentId)}"
                class="btn-primary">
            <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
            </svg>
            ${Utils.escapeHtml(label)}
        </button>
    `;
}

function renderExperimentSelectorOptions() {
    return experimentsState.activeExperiments.map(experiment => {
        const selectedAttribute = experiment.id === experimentsState.selectedExperimentId
            ? 'selected'
            : '';
        const codeSuffix = experiment.code
            ? ` (${Utils.escapeHtml(experiment.code)})`
            : '';

        return `
            <option value="${Utils.escapeHtml(experiment.id)}" ${selectedAttribute}>
                ${Utils.escapeHtml(experiment.name)}${codeSuffix}
            </option>
        `;
    }).join('');
}

function renderExperimentSummary(experiment) {
    if (!experiment) {
        return '';
    }

    const parts = [];
    if (experiment.description) {
        parts.push(`<p class="mb-2">${Utils.escapeHtml(experiment.description)}</p>`);
    }
    if (experiment.start_date) {
        const period = `${formatDateDisplay(experiment.start_date)}${experiment.end_date ? ` - ${formatDateDisplay(experiment.end_date)}` : ''}`;
        parts.push(`<p>Period: ${Utils.escapeHtml(period)}</p>`);
    }

    if (parts.length === 0) {
        return '';
    }

    return `
        <div class="mt-3 text-sm text-slate-400">
            ${parts.join('')}
        </div>
    `;
}

function renderFieldDisplayValue(field, value) {
    if (value === null || value === undefined) {
        return '<span class="text-slate-500 italic">—</span>';
    }

    if (field.type === 'date') {
        return Utils.escapeHtml(formatDateDisplay(value));
    }

    if (field.type === 'number') {
        const displayValue = typeof value === 'number' ? value.toLocaleString() : String(value);
        return Utils.escapeHtml(displayValue);
    }

    if (field.type === 'boolean') {
        return value ? 'Yes' : 'No';
    }

    return Utils.escapeHtml(String(value));
}

function renderRecordActions(row) {
    if (!experimentsState.experimentAccess.write) {
        return '';
    }

    const rowId = Utils.escapeHtml(getExperimentRowId(row));
    const experimentId = Utils.escapeHtml(experimentsState.selectedExperimentId || '');
    const editButton = `
        <button type="button"
                data-experiment-action="edit-record"
                data-row-id="${rowId}"
                data-experiment-id="${experimentId}"
                class="text-sky-400 hover:text-sky-300 inline-flex items-center justify-center"
                title="Edit">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
            </svg>
        </button>
    `;

    const deleteButton = experimentsState.experimentAccess.delete
        ? `
            <button type="button"
                    data-experiment-action="delete-record"
                    data-row-id="${rowId}"
                    data-experiment-id="${experimentId}"
                    class="text-red-400 hover:text-red-300 inline-flex items-center justify-center"
                    title="Delete">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
            </button>
        `
        : `
            <button type="button"
                    disabled
                    class="text-slate-500 cursor-not-allowed inline-flex items-center justify-center"
                    title="Only admins can delete records">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
            </button>
        `;

    return `
        <td class="px-4 py-3 text-center">
            <div class="inline-flex items-center gap-3">
                ${editButton}
                ${deleteButton}
            </div>
        </td>
    `;
}

/**
 * Renders the "Read-only access" banner shown above the records table when
 * the selected experiment denies write access (``experiment.can_write ===
 * false``).
 *
 * Contract on the ``data-experiment-readonly-notice`` attribute:
 *   - STABLE test hook. Safe to query in vitest specs and DOM diagnostics.
 *   - DO NOT take a CSS dependency on this attribute. Style the banner via
 *     the surrounding utility classes instead. Removing or renaming this
 *     hook is a breaking change for anyone polling for the banner.
 *   - DO NOT remove without coordinating with every caller (currently only
 *     ``experiments.test.js``).
 */
function renderReadOnlyExperimentNotice() {
    if (experimentsState.experimentAccess.write) {
        return '';
    }
    return `
        <div data-experiment-readonly-notice
             class="mb-4 rounded-lg border border-slate-600/50 bg-slate-800/40 px-4 py-3 text-sm text-slate-300">
            <span class="font-semibold text-slate-200">Read-only access.</span>
            You can view records on this experiment but not add or edit them.
            Contact an experiment admin to request write access.
        </div>
    `;
}

function renderExperimentTable(experiment) {
    const sortedFields = sortExperimentFields(experiment.experiment_fields || {});
    const readOnlyNotice = renderReadOnlyExperimentNotice();

    if (experimentsState.rowsLoadState === 'loading') {
        return readOnlyNotice + renderStateCard({
            title: 'Loading Data Records',
            message: 'Fetching the latest records for this experiment.',
            iconSvg: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6l4 2m6-2a10 10 0 11-20 0 10 10 0 0120 0z"></path>'
        });
    }

    if (experimentsState.rowsLoadState === 'error') {
        return readOnlyNotice + renderStateCard({
            title: 'Error Loading Records',
            message: experimentsState.rowsLoadErrorMessage || 'Failed to load experiment data.',
            tone: 'error',
            iconSvg: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>'
        });
    }

    if (experimentsState.experimentDataRows.length === 0) {
        const actionHtml = experimentsState.experimentAccess.write
            ? renderAddRecordButton({
                experimentId: experiment.id,
                label: 'Add First Record'
            })
            : '';

        return readOnlyNotice + renderStateCard({
            title: 'No Data Records Yet',
            message: 'Start recording data for this experiment.',
            actionHtml,
            iconSvg: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>'
        });
    }

    return readOnlyNotice + `
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead class="text-xs font-semibold uppercase text-slate-400 bg-slate-900/50 border-b border-slate-600">
                    <tr>
                        ${sortedFields.map(field => `
                            <th class="px-4 py-3 whitespace-nowrap text-center">
                                ${Utils.escapeHtml(field.name)}
                                ${field.required ? '<span class="text-red-400 ml-1">*</span>' : ''}
                            </th>
                        `).join('')}
                        ${experimentsState.experimentAccess.write ? '<th class="px-4 py-3 whitespace-nowrap text-center">Actions</th>' : ''}
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-700">
                    ${experimentsState.experimentDataRows.map(row => {
        const rowData = row.data || {};

        return `
                        <tr class="hover:bg-slate-700/30 transition-colors">
                            ${sortedFields.map(field => `
                                <td class="px-4 py-3 text-slate-300 text-center">
                                    ${renderFieldDisplayValue(field, rowData[field.id])}
                                </td>
                            `).join('')}
                            ${renderRecordActions(row)}
                        </tr>
                    `;
    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function renderExperimentsContent() {
    const selectedExperiment = getSelectedExperiment();
    const headerAction = selectedExperiment && experimentsState.experimentAccess.write
        ? renderAddRecordButton({
            buttonId: 'add-experiment-row-btn',
            experimentId: selectedExperiment.id,
            label: 'Add Record'
        })
        : '';

    let contentBody = '';

    if (experimentsState.activeExperiments.length === 0) {
        contentBody = renderStateCard({
            title: 'No Active Experiments',
            message: 'There are no active experiments available. Contact an administrator to create one.',
            iconSvg: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>'
        });
    } else {
        contentBody = `
            <div class="bg-slate-800/30 rounded-lg border border-slate-600/50 p-4">
                <label class="block text-sm font-medium text-slate-300 mb-2">Select Experiment</label>
                <select id="experiment-selector" class="bg-slate-700 text-white rounded-lg p-2 w-full focus:ring-2 focus:ring-sky-500 focus:border-transparent">
                    <option value="">-- Choose an experiment --</option>
                    ${renderExperimentSelectorOptions()}
                </select>
                ${renderExperimentSummary(selectedExperiment)}
            </div>
            ${selectedExperiment
        ? `
                <div class="bg-slate-800/30 rounded-lg border border-slate-600/50 p-6">
                    <h4 class="text-lg font-semibold text-white mb-4">Data Records</h4>
                    ${renderExperimentTable(selectedExperiment)}
                </div>
            `
        : renderStateCard({
            title: 'Select an Experiment',
            message: 'Choose an experiment from the dropdown above to view and record data.',
            iconSvg: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>'
        })}
        `;
    }

    return `
        <div class="tab-content active">
            <div class="space-y-6">
                <div class="flex items-center justify-between flex-wrap gap-4">
                    <h3 class="text-xl font-semibold text-white">Scientific Experiments</h3>
                    ${headerAction}
                </div>
                ${contentBody}
            </div>
        </div>
    `;
}

function renderLoadError(error) {
    return `
        <div class="tab-content active">
            <div class="space-y-6">
                <div class="flex items-center justify-between">
                    <h3 class="text-xl font-semibold text-white">Scientific Experiments</h3>
                </div>
                ${renderStateCard({
        title: 'Error Loading Experiments',
        message: error?.message || 'An error occurred while loading experiments.',
        tone: 'error',
        iconSvg: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>'
    })}
            </div>
        </div>
    `;
}

function renderCurrentState() {
    if (!experimentsState.currentContainer) {
        return;
    }

    experimentsState.currentContainer.innerHTML = renderExperimentsContent();
    bindContainerEvents(experimentsState.currentContainer);
}

async function loadExperimentRows(stationId, experimentId) {
    const response = await API.getExperimentData(stationId, experimentId);
    return Array.isArray(response) ? response : [];
}

async function handleExperimentSelection(experimentId) {
    experimentsState.selectedExperimentId = experimentId || null;

    if (!experimentsState.selectedExperimentId) {
        experimentsState.experimentDataRows = [];
        experimentsState.experimentAccess = { write: false, delete: false };
        setRowsLoadState('idle');
        renderCurrentState();
        return;
    }

    // Access is per-experiment; refresh it every time the selection changes.
    experimentsState.experimentAccess = getExperimentAccess(getSelectedExperiment());
    experimentsState.experimentDataRows = [];
    setRowsLoadState('loading');
    renderCurrentState();

    const requestToken = ++experimentsState.activeRowsRequestToken;
    const stationId = experimentsState.currentStationId;
    const selectedExperimentId = experimentsState.selectedExperimentId;

    const loadingOverlay = Utils.showLoadingOverlay('Loading experiment data...');
    try {
        const rows = await loadExperimentRows(
            stationId,
            selectedExperimentId
        );
        if (requestToken !== experimentsState.activeRowsRequestToken) {
            return;
        }
        experimentsState.experimentDataRows = rows;
        setRowsLoadState('loaded');
    } catch (error) {
        if (requestToken !== experimentsState.activeRowsRequestToken) {
            return;
        }
        console.error('Error fetching experiment data:', error);
        experimentsState.experimentDataRows = [];
        const errorMessage = getApiErrorMessage(error, 'Failed to load experiment data');
        setRowsLoadState('error', errorMessage);
        Utils.showNotification('error', errorMessage);
    } finally {
        Utils.hideLoadingOverlay(loadingOverlay);
        if (requestToken === experimentsState.activeRowsRequestToken) {
            renderCurrentState();
        }
    }
}

function bindContainerEvents(container) {
    const selector = container.querySelector('#experiment-selector');
    if (selector) {
        selector.addEventListener('change', event => {
            void handleExperimentSelection(event.target.value || null);
        });
    }

    container.querySelectorAll('[data-experiment-action="add-record"]').forEach(button => {
        button.addEventListener('click', () => {
            void StationExperiments.openAddRowModal(
                button.dataset.stationId,
                button.dataset.experimentId
            );
        });
    });

    container.querySelectorAll('[data-experiment-action="edit-record"]').forEach(button => {
        button.addEventListener('click', () => {
            void StationExperiments.openEditRowModal(
                experimentsState.currentStationId,
                button.dataset.experimentId,
                button.dataset.rowId
            );
        });
    });

    container.querySelectorAll('[data-experiment-action="delete-record"]').forEach(button => {
        button.addEventListener('click', () => {
            StationExperiments.openDeleteRowModal(button.dataset.rowId);
        });
    });
}

function removeModalKeydownHandler() {
    if (modalKeydownHandler) {
        document.removeEventListener('keydown', modalKeydownHandler);
        modalKeydownHandler = null;
    }
}

function setModalKeydownHandler(closeHandler) {
    removeModalKeydownHandler();
    modalKeydownHandler = event => {
        if (event.key === 'Escape') {
            closeHandler();
        }
    };
    document.addEventListener('keydown', modalKeydownHandler);
}

// Capture document.body.style.overflow the first time this module locks
// scroll, and restore exactly that value once the last owned modal closes.
// Avoids clobbering overflow set by unrelated code (e.g. another modal
// system) that happened to be active when the experiments modal opened.
let savedBodyOverflow = null;

function lockBodyScroll() {
    if (savedBodyOverflow === null) {
        savedBodyOverflow = document.body.style.overflow || '';
    }
    document.body.style.overflow = 'hidden';
}

function restoreBodyScroll() {
    if (savedBodyOverflow !== null) {
        document.body.style.overflow = savedBodyOverflow;
        savedBodyOverflow = null;
    }
}

function openModal(modalId, html, closeHandler) {
    closeModal(RECORD_MODAL_ID);
    closeModal(DELETE_MODAL_ID);

    document.body.insertAdjacentHTML('beforeend', html);
    lockBodyScroll();
    setModalKeydownHandler(closeHandler);
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.remove();
    }

    if (!document.getElementById(RECORD_MODAL_ID) && !document.getElementById(DELETE_MODAL_ID)) {
        restoreBodyScroll();
        removeModalKeydownHandler();
    }
}

function renderFieldInput(field, initialValue) {
    const fieldInputId = getFieldInputId(field.id);
    const value = normalizeFieldValueForInput(field, initialValue);
    const requiredAttribute = field.required ? 'required' : '';
    const sharedClasses = 'w-full bg-slate-700 text-white rounded-lg p-3 border border-slate-600 focus:ring-2 focus:ring-sky-500 focus:border-transparent';
    const placeholder = `Enter ${field.name.toLowerCase()}`;

    let inputHtml = '';
    switch (field.type) {
        case 'number':
            inputHtml = `
                <input type="number"
                       id="${fieldInputId}"
                       name="${field.id}"
                       step="any"
                       value="${Utils.escapeHtml(value)}"
                       ${requiredAttribute}
                       class="${sharedClasses}"
                       placeholder="${Utils.escapeHtml(placeholder)}">
            `;
            break;
        case 'date': {
            const today = new Date().toISOString().split('T')[0];
            const maxDate = field.id === MANDATORY_FIELD_UUIDS.MEASUREMENT_DATE
                ? `max="${today}"`
                : '';
            inputHtml = `
                <input type="date"
                       id="${fieldInputId}"
                       name="${field.id}"
                       value="${Utils.escapeHtml(value)}"
                       ${requiredAttribute}
                       ${maxDate}
                       class="${sharedClasses}">
            `;
            break;
        }
        case 'boolean':
            inputHtml = `
                <select id="${fieldInputId}"
                        name="${field.id}"
                        ${requiredAttribute}
                        class="${sharedClasses}">
                    <option value="" ${value === '' ? 'selected' : ''}>-- Select --</option>
                    <option value="true" ${value === 'true' ? 'selected' : ''}>Yes</option>
                    <option value="false" ${value === 'false' ? 'selected' : ''}>No</option>
                </select>
            `;
            break;
        case 'select':
            inputHtml = `
                <select id="${fieldInputId}"
                        name="${field.id}"
                        ${requiredAttribute}
                        class="${sharedClasses}">
                    <option value="" ${value === '' ? 'selected' : ''}>-- Select --</option>
                    ${(field.options || []).map(option => `
                        <option value="${Utils.escapeHtml(option)}" ${option === value ? 'selected' : ''}>
                            ${Utils.escapeHtml(option)}
                        </option>
                    `).join('')}
                </select>
            `;
            break;
        case 'text':
        default:
            inputHtml = `
                <input type="text"
                       id="${fieldInputId}"
                       name="${field.id}"
                       value="${Utils.escapeHtml(value)}"
                       ${requiredAttribute}
                       class="${sharedClasses}"
                       placeholder="${Utils.escapeHtml(placeholder)}">
            `;
            break;
    }

    return `
        <div class="field-group">
            <label for="${fieldInputId}" class="block text-sm font-medium text-slate-300 mb-2">
                ${Utils.escapeHtml(field.name)}
                ${field.required ? '<span class="text-red-400">*</span>' : ''}
            </label>
            ${inputHtml}
            <div id="${getFieldErrorId(field.id)}" class="text-red-400 text-sm mt-1 hidden"></div>
        </div>
    `;
}

function bindRecordFormValidation(fields) {
    fields.forEach(field => {
        const input = getFieldInputElement(field);
        if (!input) {
            return;
        }

        const events = input.tagName === 'SELECT'
            ? ['change']
            : ['input', 'blur'];

        events.forEach(eventName => {
            input.addEventListener(eventName, () => {
                validateFieldInput(field);
            });
        });
    });
}

function setRecordSubmitLoading(submitButton, isLoading) {
    const submitText = submitButton.querySelector('.submit-text');
    const submitLoading = submitButton.querySelector('.submit-loading');

    submitButton.disabled = isLoading;
    submitText?.classList.toggle('hidden', isLoading);
    submitLoading?.classList.toggle('hidden', !isLoading);
}

function buildRecordModalHtml({ mode, experiment, fields, row }) {
    const modalTitle = mode === 'edit' ? 'Edit Data Record' : 'Add Data Record';
    const submitLabel = mode === 'edit' ? 'Save Changes' : 'Save Record';
    const loadingLabel = mode === 'edit' ? 'Saving changes...' : 'Saving...';
    const fieldInputs = fields.map(field => renderFieldInput(field, row?.data?.[field.id])).join('');

    return `
        <div id="${RECORD_MODAL_ID}" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-3xl max-h-[90vh] overflow-y-auto">
                <div class="p-6 border-b border-slate-600">
                    <div class="flex items-center justify-between">
                        <h3 class="text-xl font-semibold text-white">${Utils.escapeHtml(modalTitle)}</h3>
                        <button type="button"
                                data-modal-close="record"
                                class="text-slate-400 hover:text-white transition-colors">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    <p class="text-slate-400 text-sm mt-2">${Utils.escapeHtml(experiment.name)}</p>
                </div>
                <form id="experiment-row-form" class="p-6 space-y-6" data-record-mode="${Utils.escapeHtml(mode)}">
                    ${fieldInputs}
                    <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-600">
                        <button type="button" data-modal-close="record" class="btn-secondary">Cancel</button>
                        <button type="submit" class="btn-primary">
                            <span class="submit-text">${Utils.escapeHtml(submitLabel)}</span>
                            <span class="submit-loading hidden">
                                <span class="loading-spinner-inline"></span> ${Utils.escapeHtml(loadingLabel)}
                            </span>
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
}

async function openRecordModal({ mode, stationId, experimentId, rowId = null }) {
    try {
        const experiment = await ensureExperimentLoaded(experimentId);
        if (!experiment) {
            Utils.showNotification('error', 'Experiment not found');
            return;
        }

        const access = getExperimentAccess(experiment);
        if (!access.write) {
            Utils.showNotification('warning', `You have read access and cannot ${mode === 'edit' ? 'edit' : 'add'} records.`);
            return;
        }

        const row = mode === 'edit' ? getExperimentRowById(rowId) : null;
        if (mode === 'edit' && !row) {
            Utils.showNotification('error', 'Record not found');
            return;
        }

        experimentsState.currentStationId = stationId;
        experimentsState.experimentAccess = access;

        const fields = getEditableExperimentFields(experiment);
        const modalHtml = buildRecordModalHtml({
            mode,
            experiment,
            fields,
            row
        });

        openModal(RECORD_MODAL_ID, modalHtml, () => {
            StationExperiments.closeRecordModal();
        });

        const modal = document.getElementById(RECORD_MODAL_ID);
        const form = document.getElementById('experiment-row-form');
        const submitButton = form?.querySelector('button[type="submit"]');

        modal?.addEventListener('click', event => {
            if (event.target === modal || event.target.closest('[data-modal-close="record"]')) {
                StationExperiments.closeRecordModal();
            }
        });

        bindRecordFormValidation(fields);

        form?.addEventListener('submit', async event => {
            event.preventDefault();

            if (!submitButton) {
                return;
            }

            if (!validateRecordForm(fields)) {
                Utils.showNotification('error', 'Please fix validation errors before submitting');
                return;
            }

            setRecordSubmitLoading(submitButton, true);

            try {
                const rowData = collectRecordFormData(fields);
                if (mode === 'edit') {
                    const savedRow = assertValidSavedRow(
                        await API.updateExperimentRecord(row.id, rowData)
                    );
                    upsertExperimentRow(savedRow);
                    Utils.showNotification('success', 'Data record updated successfully');
                } else {
                    const savedRow = assertValidSavedRow(
                        await API.createExperimentRecord(stationId, experiment.id, rowData)
                    );
                    prependExperimentRow(savedRow);
                    Utils.showNotification('success', 'Data record added successfully');
                }

                setRowsLoadState('loaded');
                StationExperiments.closeRecordModal();
                renderCurrentState();
            } catch (error) {
                console.error(`Error submitting experiment row (${mode}):`, error);

                // Permission was lost between modal-open and submit (e.g. an
                // in-flight permission change, or a deploy that tightened the
                // gating contract while a stale modal was still open). The
                // explanatory banner lives in the table behind the modal, so
                // close the modal first and surface a permission-specific
                // notification instead of the generic "failed to save" path.
                if (error?.status === 403) {
                    await handleExperimentPermissionDenied({
                        experimentId,
                        actionLabel: mode === 'edit' ? 'Edit' : 'Add',
                        closeModal: () => {
                            StationExperiments.closeRecordModal();
                        }
                    });
                    return;
                }

                Utils.showNotification(
                    'error',
                    getApiErrorMessage(
                        error,
                        mode === 'edit'
                            ? 'Failed to update record'
                            : 'Failed to save record'
                    )
                );
            } finally {
                setRecordSubmitLoading(submitButton, false);
            }
        });
    } catch (error) {
        console.error('Error opening record modal:', error);
        Utils.showNotification('error', 'Failed to load experiment details');
    }
}

function buildDeleteModalHtml(rowId) {
    return `
        <div id="${DELETE_MODAL_ID}" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
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
                        <button type="button" data-modal-close="delete" class="btn-secondary">Cancel</button>
                        <button type="button"
                                data-delete-record-id="${Utils.escapeHtml(rowId)}"
                                class="btn-danger">
                            Delete
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

export const StationExperiments = {
    async render(stationId, container) {
        experimentsState.currentContainer = container;
        experimentsState.currentStationId = stationId;
        experimentsState.selectedExperimentId = null;
        experimentsState.experimentDataRows = [];
        experimentsState.experimentAccess = { write: false, delete: false };
        setRowsLoadState('idle');
        experimentsState.activeRowsRequestToken += 1;

        const loadingOverlay = Utils.showLoadingOverlay('Loading experiments...');

        try {
            await loadActiveExperiments();
            renderCurrentState();
        } catch (error) {
            console.error('Error loading experiments:', error);
            container.innerHTML = renderLoadError(error);
        } finally {
            Utils.hideLoadingOverlay(loadingOverlay);
        }
    },

    async openAddRowModal(stationId, experimentId) {
        await openRecordModal({
            mode: 'add',
            stationId,
            experimentId
        });
    },

    async openEditRowModal(stationId, experimentId, rowId) {
        await openRecordModal({
            mode: 'edit',
            stationId,
            experimentId,
            rowId
        });
    },

    closeRecordModal() {
        closeModal(RECORD_MODAL_ID);
    },

    openDeleteRowModal(rowId) {
        if (!getExperimentRowById(rowId)) {
            Utils.showNotification('error', 'Record not found');
            return;
        }

        const modalHtml = buildDeleteModalHtml(rowId);
        openModal(DELETE_MODAL_ID, modalHtml, () => {
            StationExperiments.closeDeleteRowModal();
        });

        const modal = document.getElementById(DELETE_MODAL_ID);
        modal?.addEventListener('click', event => {
            if (event.target === modal || event.target.closest('[data-modal-close="delete"]')) {
                StationExperiments.closeDeleteRowModal();
                return;
            }

            const deleteButton = event.target.closest('[data-delete-record-id]');
            if (deleteButton) {
                void StationExperiments.confirmDeleteRow(deleteButton.dataset.deleteRecordId);
            }
        });
    },

    closeDeleteRowModal() {
        closeModal(DELETE_MODAL_ID);
    },

    async confirmDeleteRow(rowId) {
        this.closeDeleteRowModal();

        try {
            await API.deleteExperimentRecord(rowId);
            removeExperimentRow(rowId);
            renderCurrentState();
            Utils.showNotification('success', 'Record deleted successfully');
        } catch (error) {
            console.error('Error deleting experiment row:', error);
            if (error?.status === 403) {
                await handleExperimentPermissionDenied({
                    experimentId: experimentsState.selectedExperimentId,
                    actionLabel: 'Delete'
                });
                return;
            }
            Utils.showNotification(
                'error',
                getApiErrorMessage(error, 'Error deleting record. Please try again.')
            );
        }
    }
};

window.StationExperiments = StationExperiments;
