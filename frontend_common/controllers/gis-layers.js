import { initColorPicker } from '../../frontend_private/static/private/js/color-picker.js';
import { attachTaggedEntityList } from '../../frontend_private/static/private/js/forms/tagged_entity_list.js';
import { FormModals } from '../../frontend_private/static/private/js/forms/modals.js';
import {
    escapeHtml,
    safeCssColor,
    sanitizeUrl,
} from '../../frontend_private/static/private/js/xss-helpers.js';

const FALLBACK_COLOR = '#94a3b8';
const DEFAULT_COLOR = '#377eb8';
const ACCEPTED_EXTENSIONS = new Set(['kml', 'kmz', 'geojson', 'json', 'topojson', 'zip']);
const SUPPORTED_FORMATS_LABEL = 'KML, KMZ, GeoJSON, TopoJSON, or a zipped Shapefile';

function formatDate(dateString) {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return 'Unknown';
    return date.toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
}

function routeUrl(routeName, layerId) {
    const route = globalThis.Urls?.[routeName];
    return typeof route === 'function' ? sanitizeUrl(route(layerId)) : '';
}

function normalizedPermissionLabel(label) {
    if (!label) return 'Unknown';
    return String(label).toLowerCase().split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function permissionPillClass(label) {
    return ({
        READ_ONLY: 'bg-pastel-beige',
        READ_AND_WRITE: 'bg-pastel-navy',
        ADMIN: 'bg-pastel-orange',
    })[label] || 'bg-slate-700 text-slate-300';
}

function renderDesktopActions(layer) {
    const safeLayerId = escapeHtml(layer.id);
    const sourceUrl = escapeHtml(routeUrl('api:v2:gis-layer-source', layer.id));
    const permissionsUrl = escapeHtml(routeUrl('private:gis_layer_user_permissions', layer.id));
    let html = `
        <a class="inline-flex cursor-pointer" href="${sourceUrl}" title="Download original source" aria-label="Download GIS Layer source">
            <svg class="h-6 w-6 stroke-current text-cyan-500 hover:text-cyan-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M5 21h14"></path>
            </svg>
        </a>
        <a class="inline-flex cursor-pointer" href="${permissionsUrl}" title="Manage layer access" aria-label="View GIS Layer access control">
            <svg class="h-6 w-6 stroke-current text-indigo-500 hover:text-indigo-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M19 8v6"></path><path d="M22 11h-6"></path>
            </svg>
        </a>`;
    if (layer.can_write === true) {
        html += `
            <button class="btn-edit-gis-layer cursor-pointer" data-layer-id="${safeLayerId}" title="Edit layer" aria-label="Edit GIS Layer">
                <svg class="h-6 w-6 stroke-current text-amber-500 hover:text-amber-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                    <path stroke="none" d="M0 0h24v24H0z" fill="none"></path><path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"></path><path d="M13.5 6.5l4 4"></path>
                </svg>
            </button>`;
    }
    if (layer.can_delete === true) {
        html += `
            <button class="btn-delete-gis-layer cursor-pointer" data-layer-id="${safeLayerId}" title="Delete layer" aria-label="Delete GIS Layer">
                <svg class="h-6 w-6 stroke-current text-rose-500 hover:text-rose-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                    <path stroke="none" d="M0 0h24v24H0z" fill="none"></path><path d="M18 6l-12 12"></path><path d="M6 6l12 12"></path>
                </svg>
            </button>`;
    }
    return html;
}

function renderMobileActions(layer) {
    const safeLayerId = escapeHtml(layer.id);
    const sourceUrl = escapeHtml(routeUrl('api:v2:gis-layer-source', layer.id));
    const permissionsUrl = escapeHtml(routeUrl('private:gis_layer_user_permissions', layer.id));
    let html = `
        <a class="w-10 h-10 shrink-0 flex items-center justify-center bg-cyan-600 hover:bg-cyan-500 rounded-full transition" href="${sourceUrl}" aria-label="Download GIS Layer source">
            <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor"><path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M5 21h14"></path></svg>
        </a>
        <a class="w-10 h-10 shrink-0 flex items-center justify-center bg-indigo-600 hover:bg-indigo-500 rounded-full transition" href="${permissionsUrl}" aria-label="View GIS Layer access control">
            <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor"><path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M19 8v6"></path><path d="M22 11h-6"></path></svg>
        </a>`;
    if (layer.can_write === true) {
        html += `
            <button class="btn-edit-gis-layer w-10 h-10 shrink-0 flex items-center justify-center bg-amber-600 hover:bg-amber-500 rounded-full transition" data-layer-id="${safeLayerId}" aria-label="Edit GIS Layer">
                <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor"><path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"></path><path d="M13.5 6.5l4 4"></path></svg>
            </button>`;
    }
    if (layer.can_delete === true) {
        html += `
            <button class="btn-delete-gis-layer w-10 h-10 shrink-0 flex items-center justify-center bg-rose-600 hover:bg-rose-500 rounded-full transition" data-layer-id="${safeLayerId}" aria-label="Delete GIS Layer">
                <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor"><path d="M18 6l-12 12"></path><path d="M6 6l12 12"></path></svg>
            </button>`;
    }
    return html;
}

export function buildGISLayerListMarkup(layers) {
    if (!Array.isArray(layers) || layers.length === 0) {
        const emptyStateHtml = `
            <svg class="w-16 h-16 center-x mb-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7l8-4 8 4-8 4-8-4zm0 5l8 4 8-4M4 17l8 4 8-4"></path>
            </svg>
            <p class="text-lg font-medium">No GIS Layers yet</p>
            <p class="text-sm mt-1">Upload ${SUPPORTED_FORMATS_LABEL} to add your first layer</p>`;
        return {
            tableHtml: `<tr><td colspan="7" class="px-2 py-8 text-center text-slate-400">${emptyStateHtml}</td></tr>`,
            cardsHtml: `<div class="text-center py-12 text-slate-400">${emptyStateHtml}</div>`,
        };
    }

    const sortedLayers = [...layers].sort((a, b) => String(a.name).localeCompare(String(b.name), undefined, { sensitivity: 'base' }));
    const tableHtml = sortedLayers.map((layer, index) => {
        const permissionLabel = normalizedPermissionLabel(layer.user_permission_level_label);
        return `
            <tr>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center font-medium text-slate-100">${index + 1}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3">
                    <div class="flex items-start gap-3">
                        <div class="w-3 h-3 mt-1 rounded-full shrink-0" style="background-color: ${safeCssColor(layer.color, FALLBACK_COLOR)}"></div>
                        <div class="min-w-0"><div class="font-medium text-slate-100 break-words">${escapeHtml(layer.name)}</div>${layer.description ? `<div class="text-xs text-slate-400 mt-1 break-words">${escapeHtml(layer.description)}</div>` : ''}</div>
                    </div>
                </td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center text-slate-300 text-sm break-words">${escapeHtml(layer.created_by || '—')}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center"><span class="inline-flex font-medium ${permissionPillClass(layer.user_permission_level_label)} rounded-full px-2.5 py-0.5">${escapeHtml(permissionLabel)}</span></div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center text-sm uppercase text-slate-300">${escapeHtml(layer.source_format || '—')}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center text-slate-400 text-sm">${escapeHtml(formatDate(layer.creation_date))}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="flex items-center justify-center gap-2">${renderDesktopActions(layer)}</div></td>
            </tr>`;
    }).join('');

    const cardsHtml = sortedLayers.map(layer => {
        const permissionLabel = normalizedPermissionLabel(layer.user_permission_level_label);
        return `
            <div class="track-card gis-layer-card">
                <div class="track-card-header">
                    <div class="track-card-title flex items-start gap-3">
                        <div class="w-4 h-4 mt-1 rounded-full shrink-0" style="background-color: ${safeCssColor(layer.color, FALLBACK_COLOR)}"></div>
                        <div class="min-w-0"><div class="text-lg font-semibold text-slate-100 break-words">${escapeHtml(layer.name)}</div>${layer.description ? `<div class="text-xs text-slate-400 mt-1 break-words">${escapeHtml(layer.description)}</div>` : ''}</div>
                    </div>
                    <div class="track-card-actions">${renderMobileActions(layer)}</div>
                </div>
                <div class="track-card-body">
                    <div class="track-card-row"><span class="track-card-label">Creator</span><span class="track-card-value">${escapeHtml(layer.created_by || '—')}</span></div>
                    <div class="track-card-row"><span class="track-card-label">Access</span><span class="inline-flex font-medium ${permissionPillClass(layer.user_permission_level_label)} rounded-full px-2.5 py-0.5">${escapeHtml(permissionLabel)}</span></div>
                    <div class="track-card-row"><span class="track-card-label">Source</span><span class="track-card-value uppercase">${escapeHtml(layer.source_format || '—')}</span></div>
                    <div class="track-card-row"><span class="track-card-label">Created</span><span class="track-card-value">${escapeHtml(formatDate(layer.creation_date))}</span></div>
                </div>
            </div>`;
    }).join('');
    return { tableHtml, cardsHtml };
}

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function init(context) {
    let selectedFile = null;
    let uploadRequest = null;
    let listApi = null;

    function attachEventHandlers() {
        $('.btn-edit-gis-layer').off('click').on('click', function () {
            listApi.openEditModal($(this).data('layer-id'));
        });
        $('.btn-delete-gis-layer').off('click').on('click', function () {
            listApi.openDeleteModal($(this).data('layer-id'));
        });
    }

    function renderLayers(layers) {
        const { tableHtml, cardsHtml } = buildGISLayerListMarkup(layers);
        $('#gis-layers-table-body').html(tableHtml);
        $('#gis-layers-cards-container').html(cardsHtml);
        attachEventHandlers();
    }

    const setEditColor = initColorPicker({
        preview: '#edit-layer-color-preview', hiddenInput: '#edit-layer-color-value',
        nativePicker: '#edit-layer-color-picker', pickerBtn: '#edit-layer-color-picker-btn',
        hexInput: '#edit-layer-color-hex', presets: '.edit-layer-color-preset',
    });
    const setUploadColor = initColorPicker({
        preview: '#upload-layer-color-preview', hiddenInput: '#upload-layer-color-value',
        nativePicker: '#upload-layer-color-picker', pickerBtn: '#upload-layer-color-picker-btn',
        hexInput: '#upload-layer-color-hex', presets: '.upload-layer-color-preset',
    });

    listApi = attachTaggedEntityList({
        listEndpoint: context.listEndpoint,
        detailEndpointBuilder: id => globalThis.Urls['api:v2:gis-layer-detail'](id),
        editMethod: 'PATCH', renderList: renderLayers, entityLabel: 'GIS Layer',
        loadFailedMessage: 'Error loading GIS Layers', editFormSelector: '#edit-layer-form',
        editIdInputSelector: '#edit-layer-id', editModalSelector: '#edit-layer-modal',
        closeEditModalSelectors: '.btn-close-edit-modal', deleteModalSelector: '#delete-layer-modal',
        deleteIdInputSelector: '#delete-layer-id', confirmDeleteSelector: '#btn-confirm-delete',
        closeDeleteModalSelectors: '.btn-close-delete-modal',
        openEditModalForEntity: layer => {
            $('#edit-layer-id').val(layer.id);
            $('#edit-layer-name').val(layer.name);
            $('#edit-layer-description').val(layer.description || '');
            setEditColor(layer.color || FALLBACK_COLOR);
        },
        openDeleteModalForEntity: layer => {
            $('#delete-layer-info').html(
                '<div class="flex items-center gap-2 bg-srgb-slate-700-50 rounded-lg p-3">' +
                '  <div class="track-icon">' +
                '    <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                '      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7l8-4 8 4-8 4-8-4zm0 5l8 4 8-4M4 17l8 4 8-4"></path>' +
                '    </svg>' +
                '  </div>' +
                '  <span class="text-slate-100 font-medium">' + escapeHtml(layer.name) + '</span>' +
                '</div>',
            );
        },
        collectEditPayload: () => {
            const name = $('#edit-layer-name').val().trim();
            if (!name) {
                FormModals.showError('Please enter a layer name');
                return null;
            }
            return {
                name, description: $('#edit-layer-description').val().trim(),
                color: $('#edit-layer-color-value').val(),
            };
        },
    });

    const uploadModal = document.getElementById('upload-layer-modal');
    const uploadForm = document.getElementById('upload-layer-form');
    const fileInput = document.getElementById('upload-layer-file-input');
    const dropZone = document.getElementById('upload-layer-drop-zone');
    const uploadButton = document.getElementById('upload-layer-button');
    const uploadDismissButtons = document.querySelectorAll('[data-layer-upload-action="hide"]');

    function uploadIsActive() {
        return uploadRequest && uploadRequest.readyState !== XMLHttpRequest.DONE;
    }

    function setUploadDismissDisabled(disabled) {
        uploadDismissButtons.forEach(button => { button.disabled = disabled; });
    }

    function showUploadError(message) {
        document.getElementById('upload-layer-error-text').textContent = message;
        document.getElementById('upload-layer-error-message').classList.remove('hidden');
    }

    function clearSelectedFile() {
        selectedFile = null;
        fileInput.value = '';
        dropZone.classList.remove('hidden', 'border-cyan-400', 'bg-srgb-slate-700-50');
        document.getElementById('upload-layer-selected-file').classList.add('hidden');
        document.getElementById('upload-layer-error-message').classList.add('hidden');
        document.getElementById('upload-layer-progress-wrap').classList.add('hidden');
        document.getElementById('upload-layer-progress').style.width = '0%';
        document.getElementById('upload-layer-progress-value').textContent = '0%';
        document.getElementById('upload-layer-progress-label').textContent = 'Uploading…';
        document.getElementById('upload-layer-button-text').textContent = 'Upload Layer';
        document.getElementById('upload-layer-spinner').classList.add('hidden');
        setUploadDismissDisabled(false);
        uploadButton.disabled = true;
    }

    function resetUpload() {
        uploadForm.reset();
        clearSelectedFile();
        setUploadColor(DEFAULT_COLOR);
    }

    function showUploadModal() {
        resetUpload();
        uploadModal.classList.remove('hidden');
    }

    function hideUploadModal() {
        if (uploadIsActive()) return;
        uploadRequest = null;
        uploadModal.classList.add('hidden');
        resetUpload();
    }

    function selectFile(file) {
        clearSelectedFile();
        if (!file) return;
        const extension = file.name.split('.').pop()?.toLowerCase();
        if (!ACCEPTED_EXTENSIONS.has(extension)) {
            showUploadError(`Choose ${SUPPORTED_FORMATS_LABEL}.`);
            return;
        }
        selectedFile = file;
        document.getElementById('upload-layer-file-name').textContent = file.name;
        document.getElementById('upload-layer-file-size').textContent = formatFileSize(file.size);
        dropZone.classList.add('hidden');
        document.getElementById('upload-layer-selected-file').classList.remove('hidden');
        uploadButton.disabled = false;
        const nameInput = document.getElementById('upload-layer-name');
        if (!nameInput.value) nameInput.value = file.name.replace(/\.(kml|kmz|geojson|json|topojson|zip)$/i, '');
    }

    function parseUploadError() {
        try {
            const data = JSON.parse(uploadRequest.responseText);
            const fieldErrors = Object.values(data.errors || {}).flat().join(' ');
            const directFieldErrors = Object.values(data).flat()
                .filter(value => typeof value === 'string').join(' ');
            return data.detail || data.error || data.error_message || fieldErrors || directFieldErrors || 'Upload failed.';
        } catch {
            return 'Upload failed.';
        }
    }

    uploadForm.addEventListener('submit', event => {
        event.preventDefault();
        const name = document.getElementById('upload-layer-name').value.trim();
        if (!selectedFile) return showUploadError(`Choose ${SUPPORTED_FORMATS_LABEL}.`);
        if (!name) return showUploadError('Please enter a layer name.');

        const data = new FormData();
        data.append('source_file', selectedFile, selectedFile.name);
        data.append('name', name);
        data.append('description', document.getElementById('upload-layer-description').value.trim());
        data.append('color', document.getElementById('upload-layer-color-value').value);
        uploadButton.disabled = true;
        document.getElementById('upload-layer-spinner').classList.remove('hidden');
        document.getElementById('upload-layer-button-text').textContent = 'Uploading…';
        document.getElementById('upload-layer-progress-wrap').classList.remove('hidden');
        document.getElementById('upload-layer-error-message').classList.add('hidden');
        setUploadDismissDisabled(true);

        uploadRequest = new XMLHttpRequest();
        uploadRequest.open('POST', context.listEndpoint);
        uploadRequest.setRequestHeader('X-CSRFToken', context.csrfToken);
        uploadRequest.upload.addEventListener('progress', progressEvent => {
            if (!progressEvent.lengthComputable) return;
            const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
            document.getElementById('upload-layer-progress').style.width = `${percent}%`;
            document.getElementById('upload-layer-progress-value').textContent = `${percent}%`;
        });
        uploadRequest.upload.addEventListener('load', () => {
            const directGeoJSON = /\.(geojson|json)$/i.test(selectedFile.name);
            document.getElementById('upload-layer-progress-label').textContent = directGeoJSON
                ? 'Saving layer…'
                : 'Preparing map data…';
            document.getElementById('upload-layer-progress').style.width = '100%';
            document.getElementById('upload-layer-progress-value').textContent = '100%';
            document.getElementById('upload-layer-button-text').textContent = directGeoJSON
                ? 'Saving…'
                : 'Preparing…';
        });
        uploadRequest.addEventListener('load', () => {
            if (uploadRequest.status >= 200 && uploadRequest.status < 300) {
                uploadRequest = null;
                hideUploadModal();
                FormModals.showSuccess('GIS Layer uploaded successfully!');
                listApi.reload();
                return;
            }
            showUploadError(parseUploadError());
            uploadRequest = null;
            setUploadDismissDisabled(false);
            uploadButton.disabled = false;
            document.getElementById('upload-layer-spinner').classList.add('hidden');
            document.getElementById('upload-layer-button-text').textContent = 'Upload Layer';
        });
        uploadRequest.addEventListener('error', () => {
            showUploadError('The upload was interrupted. Try again.');
            uploadRequest = null;
            setUploadDismissDisabled(false);
            uploadButton.disabled = false;
            document.getElementById('upload-layer-spinner').classList.add('hidden');
            document.getElementById('upload-layer-button-text').textContent = 'Upload Layer';
        });
        uploadRequest.addEventListener('abort', () => {
            uploadRequest = null;
            setUploadDismissDisabled(false);
            uploadButton.disabled = false;
            document.getElementById('upload-layer-spinner').classList.add('hidden');
            document.getElementById('upload-layer-button-text').textContent = 'Upload Layer';
        });
        uploadRequest.send(data);
    });

    document.getElementById('upload-layer-open').addEventListener('click', showUploadModal);
    uploadDismissButtons.forEach(button => button.addEventListener('click', hideUploadModal));
    document.querySelectorAll('[data-layer-upload-action="browse"]').forEach(button => button.addEventListener('click', () => fileInput.click()));
    document.querySelectorAll('[data-layer-upload-action="clear"]').forEach(button => button.addEventListener('click', clearSelectedFile));
    fileInput.addEventListener('change', () => selectFile(fileInput.files?.[0]));
    for (const eventName of ['dragenter', 'dragover']) dropZone.addEventListener(eventName, event => {
        event.preventDefault();
        dropZone.classList.add('border-cyan-400', 'bg-srgb-slate-700-50');
    });
    for (const eventName of ['dragleave', 'drop']) dropZone.addEventListener(eventName, event => {
        event.preventDefault();
        dropZone.classList.remove('border-cyan-400', 'bg-srgb-slate-700-50');
    });
    dropZone.addEventListener('drop', event => selectFile(event.dataTransfer?.files?.[0]));
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !uploadModal.classList.contains('hidden')) hideUploadModal();
    });
    window.addEventListener('speleo:refresh-gis-layers', () => listApi.reload());
}
