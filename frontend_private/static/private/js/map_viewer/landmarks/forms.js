/**
 * Shared landmark create / edit / delete / bulk modals.
 *
 * Single source of truth used by:
 *   - the map viewer (consumed by `landmarks/ui.js`)
 *   - the landmark collection details page bundle
 *
 * Responsibilities:
 *   - render landmark form HTML (with optional `lockedCollectionId` to hide
 *     the picker and pin the create/edit collection)
 *   - validate inputs inline (name required, lat -90..90, lon -180..180)
 *   - call the backend via fetch + CSRF and surface errors inline
 *   - notify callers via an `onSuccess` callback so consumers refresh state
 *     in the way that fits their page (map layers vs. table reload)
 *
 * No `State.*` reads. Data flows in via parameters and out via callbacks.
 */

import { Modal } from '../components/modal.js';
import { Utils } from '../utils.js';

// ---------- Internal helpers ----------

const COLLECTION_FALLBACK_COLOR = '#94a3b8';

function getCollectionLabel(collection) {
    if (!collection) return 'Personal Landmarks';
    if (collection.is_personal) {
        return `${collection.name || 'Personal Landmarks'} (Private)`;
    }
    return collection.name || 'Unnamed Collection';
}

function getCollectionColor(collection) {
    return Utils.safeCssColor(collection?.color || COLLECTION_FALLBACK_COLOR);
}

function findCollection(collections, id) {
    if (!collections || id == null) return null;
    const needle = String(id);
    if (collections instanceof Map) {
        return collections.get(needle) || null;
    }
    return collections.find(c => String(c.id) === needle) || null;
}

function listCollections(collections) {
    if (!collections) return [];
    if (collections instanceof Map) return Array.from(collections.values());
    return [...collections];
}

function compareCollections(a, b) {
    if (a.is_personal !== b.is_personal) return a.is_personal ? -1 : 1;
    return (a.name || '').localeCompare(b.name || '');
}

function getWritableCollectionOptions(collections, selectedId, excludeId = null) {
    const writable = listCollections(collections)
        .filter(c => c.can_write)
        .filter(c => excludeId == null || String(c.id) !== String(excludeId))
        .sort(compareCollections);

    return writable
        .map(c => Utils.safeHtml`
            <option value="${String(c.id)}" ${String(c.id) === String(selectedId) ? 'selected' : ''}>
                ${getCollectionLabel(c)}
            </option>`)
        .join('');
}

function renderCollectionField({ id, collections, selectedId, lockedCollection }) {
    if (lockedCollection) {
        const swatch = getCollectionColor(lockedCollection);
        return Utils.safeHtml`
            <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Collection</label>
                <div class="flex items-center gap-2 bg-slate-700/40 border border-slate-600 rounded px-3 py-2 text-slate-200 text-sm">
                    <span class="inline-block w-3 h-3 rounded-full border border-slate-500 shrink-0" style="background-color: ${Utils.raw(swatch)}"></span>
                    <span class="truncate">${getCollectionLabel(lockedCollection)}</span>
                </div>
                <input type="hidden" id="${id}" value="${String(lockedCollection.id)}">
            </div>`;
    }

    const writable = listCollections(collections).filter(c => c.can_write);
    const personal = writable.find(c => c.is_personal) || null;
    const effectiveSelected = selectedId || personal?.id || null;
    const options = getWritableCollectionOptions(collections, effectiveSelected);
    const fallbackPersonalOption = personal
        ? ''
        : '<option value="">Personal Landmarks</option>';
    return Utils.safeHtml`
        <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">Collection</label>
            <select id="${id}" class="form-input">
                ${Utils.raw(fallbackPersonalOption)}
                ${Utils.raw(options)}
            </select>
        </div>`;
}

function getSelectedCollection(id, lockedCollectionId) {
    if (lockedCollectionId) return String(lockedCollectionId);
    const select = document.getElementById(id);
    if (!select || !select.value) return null;
    return select.value;
}

function parseValidationErrorMessage(err) {
    if (!err) return 'Operation failed.';
    const data = err.data;
    if (data && typeof data === 'object') {
        if (typeof data.error === 'string' && data.error) return data.error;
        if (data.errors && typeof data.errors === 'object') {
            const firstKey = Object.keys(data.errors)[0];
            if (firstKey) {
                const value = data.errors[firstKey];
                if (Array.isArray(value) && value.length > 0) return String(value[0]);
                if (typeof value === 'string') return value;
            }
        }
    }
    return err.message || 'Operation failed.';
}

function showInlineError(errorEl, message) {
    if (!errorEl) return;
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
}

function clearInlineError(errorEl) {
    if (!errorEl) return;
    errorEl.textContent = '';
    errorEl.classList.add('hidden');
}

// ---------- Direct API calls (no state, no map dependency) ----------

async function landmarkApiRequest(url, method, body) {
    const headers = { 'X-CSRFToken': Utils.getCSRFToken() };
    if (body !== undefined && body !== null) {
        headers['Content-Type'] = 'application/json';
    }
    const response = await fetch(url, {
        method,
        headers,
        credentials: 'same-origin',
        body: body == null ? undefined : JSON.stringify(body),
    });

    let data = null;
    if (response.status !== 204) {
        const text = await response.text();
        if (text) {
            try {
                data = JSON.parse(text);
            } catch {
                data = text;
            }
        }
    }

    if (!response.ok) {
        const message = (data && typeof data === 'object'
            ? data.error || data.detail
            : null) || response.statusText || 'Request failed';
        const error = new Error(message);
        error.status = response.status;
        error.data = data;
        throw error;
    }

    return data;
}

const LandmarkApi = {
    create: payload => landmarkApiRequest(Urls['api:v2:landmarks'](), 'POST', payload),
    update: (id, payload) =>
        landmarkApiRequest(Urls['api:v2:landmark-detail'](id), 'PATCH', payload),
    remove: id =>
        landmarkApiRequest(Urls['api:v2:landmark-detail'](id), 'DELETE', null),
    bulkTransfer: (sourceId, payload) =>
        landmarkApiRequest(
            Urls['api:v2:landmark-collection-landmarks-transfer'](sourceId),
            'POST',
            payload,
        ),
    bulkDelete: (sourceId, payload) =>
        landmarkApiRequest(
            Urls['api:v2:landmark-collection-landmarks-bulk-delete'](sourceId),
            'POST',
            payload,
        ),
};

// ---------- HTML renderers (pure, exported for tests) ----------

export function renderLandmarkFormHtml({
    mode,
    landmark = null,
    collections = [],
    lockedCollectionId = null,
    formId,
    errorElId,
    coordinateDefaults = null,
}) {
    const isEdit = mode === 'edit';
    const lockedCollection = lockedCollectionId
        ? findCollection(collections, lockedCollectionId)
        : null;

    const name = isEdit ? (landmark?.name ?? '') : '';
    const description = isEdit ? (landmark?.description ?? '') : '';
    const lat = isEdit
        ? Number(landmark?.latitude ?? 0).toFixed(7)
        : (coordinateDefaults?.latitude != null
            ? String(coordinateDefaults.latitude)
            : '');
    const lon = isEdit
        ? Number(landmark?.longitude ?? 0).toFixed(7)
        : (coordinateDefaults?.longitude != null
            ? String(coordinateDefaults.longitude)
            : '');
    const selectedCollectionId = isEdit ? landmark?.collection : null;

    return Utils.safeHtml`
        <form id="${formId}" class="space-y-4" novalidate>
            <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                <input type="text" id="${formId}-name" required value="${name}" class="form-input" placeholder="Landmark name">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                <textarea id="${formId}-description" rows="3" class="form-input form-textarea" placeholder="Optional description">${description}</textarea>
            </div>
            ${Utils.raw(renderCollectionField({
                id: `${formId}-collection`,
                collections,
                selectedId: selectedCollectionId,
                lockedCollection,
            }))}
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Latitude * <span class="text-xs text-slate-500">(-90 to 90)</span></label>
                    <input type="number" id="${formId}-latitude" required step="any" min="-90" max="90" value="${lat}" class="form-input" placeholder="Latitude">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Longitude * <span class="text-xs text-slate-500">(-180 to 180)</span></label>
                    <input type="number" id="${formId}-longitude" required step="any" min="-180" max="180" value="${lon}" class="form-input" placeholder="Longitude">
                </div>
            </div>
            <div id="${errorElId}" class="hidden text-red-400 text-sm p-2 bg-red-500/10 rounded-lg"></div>
        </form>`;
}

export function readLandmarkFormPayload(formId, lockedCollectionId) {
    const name = document.getElementById(`${formId}-name`).value.trim();
    const description = document.getElementById(`${formId}-description`).value.trim();
    const latStr = document.getElementById(`${formId}-latitude`).value;
    const lonStr = document.getElementById(`${formId}-longitude`).value;
    return {
        name,
        description,
        collection: getSelectedCollection(`${formId}-collection`, lockedCollectionId),
        latitude: parseFloat(latStr),
        longitude: parseFloat(lonStr),
    };
}

export function validateLandmarkFormPayload(payload) {
    if (!payload.name) return 'Please enter a landmark name.';
    if (Number.isNaN(payload.latitude) || payload.latitude < -90 || payload.latitude > 90) {
        return 'Latitude must be a number between -90 and 90.';
    }
    if (Number.isNaN(payload.longitude) || payload.longitude < -180 || payload.longitude > 180) {
        return 'Longitude must be a number between -180 and 180.';
    }
    return null;
}

// ---------- Modal entrypoints ----------

export function openLandmarkCreateModal({
    collections = [],
    lockedCollectionId = null,
    coordinateDefaults = null,
    onSuccess = null,
} = {}) {
    const formId = 'landmark-create-form';
    const errorElId = 'landmark-create-error';
    const modalId = 'create-landmark-modal';

    const formHtml = renderLandmarkFormHtml({
        mode: 'create',
        collections,
        lockedCollectionId,
        formId,
        errorElId,
        coordinateDefaults,
    });

    const footer = Utils.safeHtml`
        <button data-close-modal="${modalId}" class="btn-secondary">Cancel</button>
        <button form="${formId}" type="submit" class="btn-primary">Create Landmark</button>`;

    Modal.open(modalId, Modal.base(modalId, 'Create Landmark', formHtml, footer, 'max-w-md'), () => {
        const nameField = document.getElementById(`${formId}-name`);
        if (nameField) nameField.focus();

        const errorEl = document.getElementById(errorElId);
        const form = document.getElementById(formId);
        if (!form) return;

        form.onsubmit = async event => {
            event.preventDefault();
            clearInlineError(errorEl);
            const payload = readLandmarkFormPayload(formId, lockedCollectionId);
            const validation = validateLandmarkFormPayload(payload);
            if (validation) {
                showInlineError(errorEl, validation);
                return;
            }
            try {
                const response = await LandmarkApi.create(payload);
                Modal.close(modalId);
                if (typeof onSuccess === 'function') {
                    await onSuccess(response?.landmark || response);
                }
            } catch (err) {
                showInlineError(errorEl, parseValidationErrorMessage(err));
            }
        };
    });
}

export function openLandmarkEditModal({
    landmark,
    collections = [],
    lockedCollectionId = null,
    onSuccess = null,
} = {}) {
    if (!landmark) return;
    const formId = 'landmark-edit-form';
    const errorElId = 'landmark-edit-error';
    const modalId = 'edit-landmark-modal';

    const formHtml = renderLandmarkFormHtml({
        mode: 'edit',
        landmark,
        collections,
        lockedCollectionId,
        formId,
        errorElId,
    });

    const footer = Utils.safeHtml`
        <button data-close-modal="${modalId}" class="btn-secondary">Cancel</button>
        <button form="${formId}" type="submit" class="btn-primary">Save</button>`;

    Modal.open(modalId, Modal.base(modalId, 'Edit Landmark', formHtml, footer, 'max-w-md'), () => {
        const errorEl = document.getElementById(errorElId);
        const form = document.getElementById(formId);
        if (!form) return;

        form.onsubmit = async event => {
            event.preventDefault();
            clearInlineError(errorEl);
            const payload = readLandmarkFormPayload(formId, lockedCollectionId);
            const validation = validateLandmarkFormPayload(payload);
            if (validation) {
                showInlineError(errorEl, validation);
                return;
            }
            try {
                const response = await LandmarkApi.update(landmark.id, payload);
                Modal.close(modalId);
                if (typeof onSuccess === 'function') {
                    await onSuccess(response?.landmark || response);
                }
            } catch (err) {
                showInlineError(errorEl, parseValidationErrorMessage(err));
            }
        };
    });
}

export function openLandmarkDeleteModal({ landmark, onSuccess = null } = {}) {
    if (!landmark) return;
    const modalId = 'delete-landmark-modal';
    const errorElId = 'landmark-delete-error';

    const content = Utils.safeHtml`
        <div class="mb-6">
            <p class="text-slate-300 mb-2">Are you sure you want to delete this landmark?</p>
            <p class="text-white font-semibold text-lg">${landmark.name}</p>
        </div>
        <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
            <p class="text-red-200 text-sm"><strong>Warning:</strong> This action cannot be undone.</p>
        </div>
        <div id="${errorElId}" class="hidden text-red-400 text-sm p-2 bg-red-500/10 rounded-lg mt-3"></div>`;

    const footer = Utils.safeHtml`
        <button data-close-modal="${modalId}" class="btn-secondary">Cancel</button>
        <button id="confirm-delete-landmark" class="btn-danger">Delete</button>`;

    Modal.open(modalId, Modal.base(modalId, 'Delete Landmark', content, footer, 'max-w-md'), () => {
        const errorEl = document.getElementById(errorElId);
        const confirmBtn = document.getElementById('confirm-delete-landmark');
        if (!confirmBtn) return;

        confirmBtn.onclick = async () => {
            clearInlineError(errorEl);
            try {
                await LandmarkApi.remove(landmark.id);
                Modal.close(modalId);
                if (typeof onSuccess === 'function') {
                    await onSuccess(landmark.id);
                }
            } catch (err) {
                showInlineError(errorEl, parseValidationErrorMessage(err));
            }
        };
    });
}

function renderSelectedLandmarksList(landmarks) {
    const visible = landmarks.slice(0, 10);
    const overflow = landmarks.length - visible.length;
    const items = visible
        .map(lm => Utils.safeHtml`<li class="truncate">${lm.name || 'Unnamed Landmark'}</li>`)
        .join('');
    const overflowHtml = overflow > 0
        ? Utils.safeHtml`<li class="text-slate-400 italic">... and ${String(overflow)} more</li>`
        : '';
    return Utils.safeHtml`
        <ul class="list-disc pl-5 text-sm text-slate-300 space-y-0.5 max-h-40 overflow-y-auto">
            ${Utils.raw(items)}
            ${Utils.raw(overflowHtml)}
        </ul>`;
}

export function openLandmarkBulkTransferModal({
    landmarks = [],
    sourceCollection = null,
    collections = [],
    onSuccess = null,
} = {}) {
    if (!Array.isArray(landmarks) || landmarks.length === 0) return;
    if (!sourceCollection) return;

    const sourceId = String(sourceCollection.id ?? sourceCollection);
    const modalId = 'bulk-transfer-landmark-modal';
    const errorElId = 'bulk-transfer-error';
    const selectId = 'bulk-transfer-target';
    const writableTargets = listCollections(collections)
        .filter(c => c.can_write)
        .filter(c => String(c.id) !== sourceId)
        .sort(compareCollections);

    const targetSelectorHtml = writableTargets.length === 0
        ? Utils.safeHtml`
            <div class="bg-slate-700/40 border border-slate-600 rounded p-3 text-sm text-slate-300">
                You don't have WRITE access to any other landmark collection.
                <a href="${Urls['private:landmark_collection_new']()}" class="text-indigo-400 hover:underline ml-1">Create a new collection</a>
                to enable transfers.
            </div>`
        : Utils.safeHtml`
            <select id="${selectId}" class="form-input w-full">
                ${Utils.raw(getWritableCollectionOptions(writableTargets, writableTargets[0].id))}
            </select>`;

    const sourceName = sourceCollection?.name || 'Source Collection';
    const count = landmarks.length;

    const content = Utils.safeHtml`
        <div class="space-y-4">
            <div class="text-sm text-slate-300">
                From <span class="font-semibold text-white">${sourceName}</span>
            </div>
            <div>
                <div class="text-sm font-medium text-slate-300 mb-2">Selected (${String(count)}):</div>
                ${Utils.raw(renderSelectedLandmarksList(landmarks))}
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Move them to:</label>
                ${Utils.raw(targetSelectorHtml)}
            </div>
            <div id="${errorElId}" class="hidden text-red-400 text-sm p-2 bg-red-500/10 rounded-lg"></div>
        </div>`;

    const submitDisabled = writableTargets.length === 0 ? 'disabled' : '';
    const footer = Utils.safeHtml`
        <button data-close-modal="${modalId}" class="btn-secondary">Cancel</button>
        <button id="bulk-transfer-confirm" class="btn-primary" ${Utils.raw(submitDisabled)}>Transfer ${String(count)} Landmark${count === 1 ? '' : 's'}</button>`;

    Modal.open(
        modalId,
        Modal.base(modalId, `Transfer ${count} Landmark${count === 1 ? '' : 's'}`, content, footer, 'max-w-md'),
        () => {
            const errorEl = document.getElementById(errorElId);
            const confirmBtn = document.getElementById('bulk-transfer-confirm');
            if (!confirmBtn) return;
            confirmBtn.onclick = async () => {
                clearInlineError(errorEl);
                const select = document.getElementById(selectId);
                const targetId = select?.value;
                if (!targetId) {
                    showInlineError(errorEl, 'Please pick a target collection.');
                    return;
                }
                try {
                    const response = await LandmarkApi.bulkTransfer(sourceId, {
                        landmark_ids: landmarks.map(lm => lm.id),
                        target_collection: targetId,
                    });
                    Modal.close(modalId);
                    if (typeof onSuccess === 'function') {
                        await onSuccess(response);
                    }
                } catch (err) {
                    showInlineError(errorEl, parseValidationErrorMessage(err));
                }
            };
        },
    );
}

export function openLandmarkBulkDeleteModal({
    landmarks = [],
    sourceCollection = null,
    onSuccess = null,
} = {}) {
    if (!Array.isArray(landmarks) || landmarks.length === 0) return;
    if (!sourceCollection) return;

    const sourceId = String(sourceCollection.id ?? sourceCollection);
    const modalId = 'bulk-delete-landmark-modal';
    const errorElId = 'bulk-delete-error';
    const count = landmarks.length;

    const content = Utils.safeHtml`
        <div class="space-y-4">
            <div class="text-sm text-slate-300">You're about to permanently delete ${String(count)} landmark${count === 1 ? '' : 's'} from this collection.</div>
            ${Utils.raw(renderSelectedLandmarksList(landmarks))}
            <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
                <p class="text-red-200 text-sm"><strong>Warning:</strong> This action cannot be undone.</p>
            </div>
            <div id="${errorElId}" class="hidden text-red-400 text-sm p-2 bg-red-500/10 rounded-lg"></div>
        </div>`;

    const footer = Utils.safeHtml`
        <button data-close-modal="${modalId}" class="btn-secondary">Cancel</button>
        <button id="bulk-delete-confirm" class="btn-danger">Delete ${String(count)} Landmark${count === 1 ? '' : 's'}</button>`;

    Modal.open(
        modalId,
        Modal.base(modalId, `Delete ${count} Landmark${count === 1 ? '' : 's'}`, content, footer, 'max-w-md'),
        () => {
            const errorEl = document.getElementById(errorElId);
            const confirmBtn = document.getElementById('bulk-delete-confirm');
            if (!confirmBtn) return;
            confirmBtn.onclick = async () => {
                clearInlineError(errorEl);
                try {
                    const response = await LandmarkApi.bulkDelete(sourceId, {
                        landmark_ids: landmarks.map(lm => lm.id),
                    });
                    Modal.close(modalId);
                    if (typeof onSuccess === 'function') {
                        await onSuccess(response);
                    }
                } catch (err) {
                    showInlineError(errorEl, parseValidationErrorMessage(err));
                }
            };
        },
    );
}

// Bundled namespace export so consumers can import a single object.
export const LandmarkForms = {
    renderLandmarkFormHtml,
    readLandmarkFormPayload,
    validateLandmarkFormPayload,
    openLandmarkCreateModal,
    openLandmarkEditModal,
    openLandmarkDeleteModal,
    openLandmarkBulkTransferModal,
    openLandmarkBulkDeleteModal,
};
