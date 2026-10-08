import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { ApiError } from '../../../../../../ts-types/domain/map-transport.ts';
import type { LandmarkFormCollection, LandmarkFormPayload, LandmarkCreateOptions, LandmarkEditOptions, LandmarkDeleteOptions, LandmarkBulkOptions, LandmarkBulkPayload, LandmarkErrorData } from '../../../../../../ts-types/domain/landmark-forms.ts';
/**
 * Shared landmark create / edit / delete / bulk modals.
 *
 * Single source of truth used by:
 *   - the map viewer (consumed by `landmarks/ui.ts`)
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

import { listCollections, compareCollections, readLandmarkFormPayload, validateLandmarkFormPayload } from './form_model.ts';
import { getWritableCollectionOptions, renderLandmarkFormHtml, renderSelectedLandmarksList } from './form_presentation.ts';
export { readLandmarkFormPayload, validateLandmarkFormPayload } from './form_model.ts';
export { renderLandmarkFormHtml } from './form_presentation.ts';
import { Modal } from '../components/modal.ts';
import { Utils } from '../utils.ts';

// ---------- Internal helpers ----------

function parseValidationErrorMessage(err: unknown): string {
    if (!err) return 'Operation failed.';
    const data = (err as ApiError).data as LandmarkErrorData | null | undefined;
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
    return (err as Error).message || 'Operation failed.';
}

function showInlineError(errorEl: HTMLElement | null, message: string) {
    if (!errorEl) return;
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
}

function clearInlineError(errorEl: HTMLElement | null) {
    if (!errorEl) return;
    errorEl.textContent = '';
    errorEl.classList.add('hidden');
}

// ---------- Direct API calls (no state, no map dependency) ----------

async function landmarkApiRequest(url: string, method: string, body: LandmarkFormPayload | LandmarkBulkPayload | null): Promise<unknown> {
    const headers: { 'X-CSRFToken': string; 'Content-Type'?: string } = { 'X-CSRFToken': Utils.getCSRFToken() };
    if (body !== undefined && body !== null) {
        headers['Content-Type'] = 'application/json';
    }
    const response = await fetch(url, {
        method,
        headers,
        credentials: 'same-origin',
        body: body == null ? undefined : JSON.stringify(body),
    } as RequestInit);

    let data: unknown = null;
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
            ? (data as LandmarkErrorData).error || (data as LandmarkErrorData).detail
            : null) || response.statusText || 'Request failed';
        const error = new Error(message as string) as ApiError;
        error.status = response.status;
        error.data = data;
        throw error;
    }

    return data;
}

const LandmarkApi = {
    create: (payload: LandmarkFormPayload) => landmarkApiRequest(Urls['api:v2:landmarks'](), 'POST', payload),
    update: (id: EntityId, payload: LandmarkFormPayload) =>
        landmarkApiRequest(Urls['api:v2:landmark-detail'](id), 'PATCH', payload),
    remove: (id: EntityId) =>
        landmarkApiRequest(Urls['api:v2:landmark-detail'](id), 'DELETE', null),
    bulkTransfer: (sourceId: EntityId, payload: LandmarkBulkPayload) =>
        landmarkApiRequest(
            Urls['api:v2:landmark-collection-landmarks-transfer'](sourceId),
            'POST',
            payload,
        ),
    bulkDelete: (sourceId: EntityId, payload: LandmarkBulkPayload) =>
        landmarkApiRequest(
            Urls['api:v2:landmark-collection-landmarks-bulk-delete'](sourceId),
            'POST',
            payload,
        ),
};

// ---------- Modal entrypoints ----------

export function openLandmarkCreateModal({
    collections = [],
    lockedCollectionId = null,
    coordinateDefaults = null,
    onSuccess = null,
}: LandmarkCreateOptions = {}) {
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
                    await onSuccess((response as { landmark?: unknown } | null)?.landmark || response);
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
}: LandmarkEditOptions = {}) {
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
                    await onSuccess((response as { landmark?: unknown } | null)?.landmark || response);
                }
            } catch (err) {
                showInlineError(errorEl, parseValidationErrorMessage(err));
            }
        };
    });
}

export function openLandmarkDeleteModal({ landmark, onSuccess = null }: LandmarkDeleteOptions = {}) {
    if (!landmark) return;
    const modalId = 'delete-landmark-modal';
    const errorElId = 'landmark-delete-error';

    const content = Utils.safeHtml`
        <div class="mb-6">
            <p class="text-slate-300 mb-2">Are you sure you want to delete this landmark?</p>
            <p class="text-white font-semibold text-lg">${landmark.name}</p>
        </div>
        <div class="bg-srgb-red-900-20 border border-srgb-red-500-30 rounded-lg p-4">
            <p class="text-red-200 text-sm"><strong>Warning:</strong> This action cannot be undone.</p>
        </div>
        <div id="${errorElId}" class="hidden text-red-400 text-sm p-2 bg-srgb-red-500-10 rounded-lg mt-3"></div>`;

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

export function openLandmarkBulkTransferModal({
    landmarks = [],
    sourceCollection = null,
    collections = [],
    onSuccess = null,
}: LandmarkBulkOptions = {}) {
    if (!Array.isArray(landmarks) || landmarks.length === 0) return;
    if (!sourceCollection) return;

    const sourceId = String((sourceCollection as LandmarkFormCollection).id ?? sourceCollection);
    const modalId = 'bulk-transfer-landmark-modal';
    const errorElId = 'bulk-transfer-error';
    const selectId = 'bulk-transfer-target';
    const writableTargets = listCollections(collections)
        .filter(c => c.can_write)
        .filter(c => String(c.id) !== sourceId)
        .sort(compareCollections);

    const targetSelectorHtml = writableTargets.length === 0
        ? Utils.safeHtml`
            <div class="bg-srgb-slate-700-40 border border-slate-600 rounded-sm p-3 text-sm text-slate-300">
                You don't have WRITE access to any other landmark collection.
                <a href="${Urls['private:landmark_collection_new']()}" class="text-indigo-400 hover:underline ml-1">Create a new collection</a>
                to enable transfers.
            </div>`
        : Utils.safeHtml`
            <select id="${selectId}" class="form-input w-full">
                ${Utils.raw(getWritableCollectionOptions(writableTargets, writableTargets[0]!.id))}
            </select>`;

    const sourceName = (sourceCollection as LandmarkFormCollection)?.name || 'Source Collection';
    const count = landmarks.length;

    const content = Utils.safeHtml`
        <div class="flow-y-4">
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
            <div id="${errorElId}" class="hidden text-red-400 text-sm p-2 bg-srgb-red-500-10 rounded-lg"></div>
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
                const select = document.getElementById(selectId) as HTMLSelectElement | null;
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
}: LandmarkBulkOptions = {}) {
    if (!Array.isArray(landmarks) || landmarks.length === 0) return;
    if (!sourceCollection) return;

    const sourceId = String((sourceCollection as LandmarkFormCollection).id ?? sourceCollection);
    const modalId = 'bulk-delete-landmark-modal';
    const errorElId = 'bulk-delete-error';
    const count = landmarks.length;

    const content = Utils.safeHtml`
        <div class="flow-y-4">
            <div class="text-sm text-slate-300">You're about to permanently delete ${String(count)} landmark${count === 1 ? '' : 's'} from this collection.</div>
            ${Utils.raw(renderSelectedLandmarksList(landmarks))}
            <div class="bg-srgb-red-900-20 border border-srgb-red-500-30 rounded-lg p-4">
                <p class="text-red-200 text-sm"><strong>Warning:</strong> This action cannot be undone.</p>
            </div>
            <div id="${errorElId}" class="hidden text-red-400 text-sm p-2 bg-srgb-red-500-10 rounded-lg"></div>
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
