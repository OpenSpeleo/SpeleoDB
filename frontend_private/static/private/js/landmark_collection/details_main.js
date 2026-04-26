/**
 * Landmark Collection details page bundle.
 *
 * Wires:
 *   - DataTable initialization (search, sort, sticky header)
 *   - Persistent multi-select (Set-backed, survives DataTables redraws)
 *   - Bulk action bar (transfer + delete + clear)
 *   - Per-row icon handlers (edit / delete via shared modals)
 *   - "+ New Landmark" + empty-state CTA
 *   - Coordinate cell copy-to-clipboard
 *   - Esc to clear selection
 *
 * The shared landmark forms module is the single source of truth for all
 * create/edit/delete/bulk-transfer/bulk-delete modal markup and validation.
 */

import { LandmarkForms } from '../map_viewer/landmarks/forms.js';
import { Utils } from '../map_viewer/utils.js';

const TABLE_SELECTOR = '#collection_landmarks_table';
const TABLE_BODY_SELECTOR = `${TABLE_SELECTOR} tbody`;
const SELECT_ALL_SELECTOR = '#collection_landmarks_table_select_all';
const ROW_CHECKBOX_SELECTOR = '.landmark-row-select';
const ADD_BTN_SELECTOR = '#add-landmark-btn';
const ADD_FIRST_BTN_SELECTOR = '#add-first-landmark-btn';
const BULK_BAR_SELECTOR = '#landmarks-bulk-action-bar';
const BULK_COUNT_SELECTOR = '#landmarks-selection-count';
const BULK_TRANSFER_BTN = '#landmarks-bulk-transfer-btn';
const BULK_DELETE_BTN = '#landmarks-bulk-delete-btn';
const BULK_CLEAR_BTN = '#landmarks-bulk-clear-btn';
const COORD_CELL_SELECTOR = '.landmark-coord-cell';
const EDIT_BTN_SELECTOR = '.landmark-edit-btn';
const DELETE_BTN_SELECTOR = '.landmark-delete-btn';
const LOCATE_BTN_SELECTOR = '.landmark-locate-btn';

const state = {
    canWrite: false,
    sourceCollection: null,
    landmarksById: new Map(),
    collections: [],
    selection: new Set(),
    table: null,
};

function readInlineJson(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return null;
    try {
        return JSON.parse(el.textContent);
    } catch (err) {
        console.error(`Failed to parse inline JSON #${elementId}:`, err);
        return null;
    }
}

function hydrateLandmarks(rows) {
    const map = new Map();
    if (!Array.isArray(rows)) return map;
    rows.forEach(row => {
        if (row && row.id) map.set(String(row.id), { ...row, id: String(row.id) });
    });
    return map;
}

async function loadCollections() {
    const url = window.Urls?.['api:v2:landmark-collections']?.();
    if (!url) return [];
    try {
        const response = await fetch(url, {
            method: 'GET',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': Utils.getCSRFToken() },
        });
        if (!response.ok) return [];
        const payload = await response.json();
        const collections = Array.isArray(payload) ? payload : [];
        return collections.map(c => ({
            ...c,
            id: String(c.id),
            can_write: Number(c.user_permission_level) >= 2,
            can_admin: Number(c.user_permission_level) >= 3,
        }));
    } catch (err) {
        console.error('Failed to load landmark collections:', err);
        return [];
    }
}

// ---------- Selection ----------

function refreshRowVisualState(checkbox) {
    const tr = checkbox.closest('tr');
    if (!tr) return;
    if (checkbox.checked) {
        tr.classList.add('is-selected');
    } else {
        tr.classList.remove('is-selected');
    }
}

function syncCheckboxesFromSelection() {
    document.querySelectorAll(ROW_CHECKBOX_SELECTOR).forEach(cb => {
        const id = cb.dataset.landmarkId;
        cb.checked = state.selection.has(id);
        refreshRowVisualState(cb);
    });
    refreshSelectAllState();
    refreshBulkBar();
}

function refreshSelectAllState() {
    const selectAll = document.querySelector(SELECT_ALL_SELECTOR);
    if (!selectAll) return;
    const visible = Array.from(document.querySelectorAll(ROW_CHECKBOX_SELECTOR));
    if (visible.length === 0) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
        return;
    }
    const checkedCount = visible.filter(cb => cb.checked).length;
    if (checkedCount === 0) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
    } else if (checkedCount === visible.length) {
        selectAll.checked = true;
        selectAll.indeterminate = false;
    } else {
        selectAll.checked = false;
        selectAll.indeterminate = true;
    }
}

function refreshBulkBar() {
    const bar = document.querySelector(BULK_BAR_SELECTOR);
    if (!bar) return;
    const count = state.selection.size;
    const countLabel = document.querySelector(BULK_COUNT_SELECTOR);
    if (countLabel) countLabel.textContent = String(count);
    if (count === 0) {
        bar.setAttribute('hidden', '');
    } else {
        bar.removeAttribute('hidden');
    }
}

function clearSelection() {
    state.selection.clear();
    syncCheckboxesFromSelection();
}

function toggleRow(landmarkId, shouldSelect) {
    if (shouldSelect) {
        state.selection.add(landmarkId);
    } else {
        state.selection.delete(landmarkId);
    }
}

function getSelectedLandmarks() {
    const selected = [];
    state.selection.forEach(id => {
        const lm = state.landmarksById.get(id);
        if (lm) selected.push(lm);
    });
    return selected;
}

// ---------- Modal handlers ----------

function reloadAfterMutation() {
    window.location.reload();
}

function openCreateModal() {
    LandmarkForms.openLandmarkCreateModal({
        collections: state.collections,
        lockedCollectionId: state.sourceCollection.id,
        onSuccess: reloadAfterMutation,
    });
}

function openEditModalForRow(landmarkId) {
    const landmark = state.landmarksById.get(String(landmarkId));
    if (!landmark) return;
    LandmarkForms.openLandmarkEditModal({
        landmark,
        collections: state.collections,
        lockedCollectionId: state.sourceCollection.id,
        onSuccess: reloadAfterMutation,
    });
}

function openDeleteModalForRow(landmarkId) {
    const landmark = state.landmarksById.get(String(landmarkId));
    if (!landmark) return;
    LandmarkForms.openLandmarkDeleteModal({
        landmark,
        onSuccess: reloadAfterMutation,
    });
}

function openBulkTransferModal() {
    const landmarks = getSelectedLandmarks();
    if (landmarks.length === 0) return;
    LandmarkForms.openLandmarkBulkTransferModal({
        landmarks,
        sourceCollection: state.sourceCollection,
        collections: state.collections,
        onSuccess: response => {
            const target = response?.target_collection?.name || 'the new collection';
            Utils.showNotification(
                'success',
                `${response?.transferred ?? landmarks.length} landmark(s) moved to ${target}.`,
            );
            reloadAfterMutation();
        },
    });
}

function openBulkDeleteModal() {
    const landmarks = getSelectedLandmarks();
    if (landmarks.length === 0) return;
    LandmarkForms.openLandmarkBulkDeleteModal({
        landmarks,
        sourceCollection: state.sourceCollection,
        onSuccess: response => {
            Utils.showNotification(
                'success',
                `${response?.deleted ?? landmarks.length} landmark(s) deleted.`,
            );
            reloadAfterMutation();
        },
    });
}

// ---------- DOM event wiring ----------

function attachRowCheckboxHandlers(scope = document) {
    scope.querySelectorAll(ROW_CHECKBOX_SELECTOR).forEach(cb => {
        cb.onclick = event => event.stopPropagation();
        cb.onchange = () => {
            toggleRow(cb.dataset.landmarkId, cb.checked);
            refreshRowVisualState(cb);
            refreshSelectAllState();
            refreshBulkBar();
        };
        // Restore checked state from in-memory selection.
        cb.checked = state.selection.has(cb.dataset.landmarkId);
        refreshRowVisualState(cb);
    });
}

function attachActionHandlers(scope = document) {
    scope.querySelectorAll(EDIT_BTN_SELECTOR).forEach(btn => {
        btn.onclick = event => {
            event.preventDefault();
            event.stopPropagation();
            openEditModalForRow(btn.dataset.landmarkId);
        };
    });
    scope.querySelectorAll(DELETE_BTN_SELECTOR).forEach(btn => {
        btn.onclick = event => {
            event.preventDefault();
            event.stopPropagation();
            openDeleteModalForRow(btn.dataset.landmarkId);
        };
    });
    scope.querySelectorAll(LOCATE_BTN_SELECTOR).forEach(btn => {
        btn.addEventListener('click', event => event.stopPropagation());
    });
    scope.querySelectorAll(COORD_CELL_SELECTOR).forEach(cell => {
        cell.addEventListener('click', () => {
            const value = cell.getAttribute('data-coord');
            if (value) Utils.copyToClipboard(value);
        });
    });
}

function bindSelectAll() {
    const selectAll = document.querySelector(SELECT_ALL_SELECTOR);
    if (!selectAll) return;
    selectAll.addEventListener('change', () => {
        const checked = selectAll.checked;
        document.querySelectorAll(ROW_CHECKBOX_SELECTOR).forEach(cb => {
            cb.checked = checked;
            toggleRow(cb.dataset.landmarkId, checked);
            refreshRowVisualState(cb);
        });
        refreshSelectAllState();
        refreshBulkBar();
    });
}

function bindBulkBar() {
    const transferBtn = document.querySelector(BULK_TRANSFER_BTN);
    if (transferBtn) transferBtn.onclick = () => openBulkTransferModal();
    const deleteBtn = document.querySelector(BULK_DELETE_BTN);
    if (deleteBtn) deleteBtn.onclick = () => openBulkDeleteModal();
    const clearBtn = document.querySelector(BULK_CLEAR_BTN);
    if (clearBtn) clearBtn.onclick = () => clearSelection();
}

function bindAddButtons() {
    const addBtn = document.querySelector(ADD_BTN_SELECTOR);
    if (addBtn) addBtn.onclick = () => openCreateModal();
    const addFirstBtn = document.querySelector(ADD_FIRST_BTN_SELECTOR);
    if (addFirstBtn) addFirstBtn.onclick = () => openCreateModal();
}

function bindKeyboard() {
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && state.selection.size > 0
            && !document.querySelector('.fixed.inset-0')) {
            // Only clear the table selection when no modal is open
            // (modal Escape close has priority).
            clearSelection();
        }
    });
}

function initDataTable() {
    if (typeof window.$ !== 'function') return;
    const $table = window.$(TABLE_SELECTOR);
    if (!$table.length) return;

    const orderColumn = state.canWrite ? 1 : 0;
    state.table = $table.DataTable({
        order: [[orderColumn, 'asc']],
        searching: false,
        ordering: true,
        paging: false,
        info: false,
        columnDefs: [
            ...(state.canWrite ? [{ targets: 0, orderable: false, searchable: false }] : []),
            { targets: -1, orderable: false, searchable: false },
        ],
    });

    state.table.on('draw', () => {
        attachRowCheckboxHandlers(document.querySelector(TABLE_BODY_SELECTOR));
        attachActionHandlers(document.querySelector(TABLE_BODY_SELECTOR));
        syncCheckboxesFromSelection();
    });
}

export function initLandmarkCollectionDetails() {
    const context = readInlineJson('landmark_collection_context');
    const tableData = readInlineJson('landmark_table_data') || [];
    if (!context) return;

    // Reset module-level state so re-initialization (e.g. in tests) starts
    // clean. In production this runs exactly once per page load.
    state.selection.clear();
    state.collections = [];
    state.table = null;

    state.canWrite = window.LANDMARK_DETAILS_CONTEXT?.canWrite === true;
    state.sourceCollection = {
        id: String(context.id),
        name: context.name,
        color: context.color,
        is_personal: context.is_personal === true,
        can_write: state.canWrite,
    };
    state.landmarksById = hydrateLandmarks(tableData);

    bindAddButtons();

    if (!state.canWrite) {
        // Read-only viewer: still allow locate icons + DataTable init for
        // search/sort + coordinate copy. Nothing else needed.
        attachActionHandlers();
        initDataTable();
        return;
    }

    bindSelectAll();
    bindBulkBar();
    bindKeyboard();
    attachRowCheckboxHandlers();
    attachActionHandlers();
    initDataTable();
    refreshBulkBar();

    // Eagerly fetch writable collections so the create modal's locked badge
    // can render the collection name + color even though the form keeps the
    // selection invisible. The bulk transfer modal also needs this list.
    loadCollections().then(collections => {
        state.collections = collections;
    });
}

if (typeof window !== 'undefined') {
    window.addEventListener('load', () => {
        initLandmarkCollectionDetails();
    });
}
