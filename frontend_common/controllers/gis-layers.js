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

function renderDesktopActions(layer, openIconUrl) {
    const sourceUrl = escapeHtml(routeUrl('api:v2:gis-layer-source', layer.id));
    const detailsUrl = escapeHtml(routeUrl('private:gis_layer_details', layer.id));
    const iconUrl = escapeHtml(sanitizeUrl(openIconUrl));
    return `
        <a class="inline-flex cursor-pointer" href="${sourceUrl}" title="Download original source" aria-label="Download GIS Layer source">
            <svg class="h-6 w-6 stroke-current text-cyan-500 hover:text-cyan-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M5 21h14"></path>
            </svg>
        </a>
        <div class="w-10 aspect-square min-w-0 shrink bg-slate-700 rounded-full">
            <a class="flex items-center justify-center w-full h-full" href="${detailsUrl}" title="Open layer settings" aria-label="Open GIS Layer settings">
                <img class="w-5 h-5" src="${iconUrl}" alt="Icon Open">
            </a>
        </div>`;
}

function renderMobileActions(layer, openIconUrl) {
    const sourceUrl = escapeHtml(routeUrl('api:v2:gis-layer-source', layer.id));
    const detailsUrl = escapeHtml(routeUrl('private:gis_layer_details', layer.id));
    const iconUrl = escapeHtml(sanitizeUrl(openIconUrl));
    return `
        <a class="w-10 h-10 shrink-0 flex items-center justify-center bg-cyan-600 hover:bg-cyan-500 rounded-full transition" href="${sourceUrl}" aria-label="Download GIS Layer source">
            <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor"><path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M5 21h14"></path></svg>
        </a>
        <a class="w-10 h-10 shrink-0 flex items-center justify-center bg-indigo-600 hover:bg-indigo-500 rounded-full transition" href="${detailsUrl}" aria-label="Open GIS Layer settings">
            <img class="ml-1" src="${iconUrl}" width="20" height="20" alt="View">
        </a>`;
}

export function buildGISLayerListMarkup(layers, openIconUrl = '') {
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
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="flex items-center justify-center gap-2">${renderDesktopActions(layer, openIconUrl)}</div></td>
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
                    <div class="track-card-actions">${renderMobileActions(layer, openIconUrl)}</div>
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

    function renderLayers(layers) {
        const { tableHtml, cardsHtml } = buildGISLayerListMarkup(layers, context.openIconUrl);
        $('#gis-layers-table-body').html(tableHtml);
        $('#gis-layers-cards-container').html(cardsHtml);
    }

    const setUploadColor = initColorPicker({
        preview: '#upload-layer-color-preview', hiddenInput: '#upload-layer-color-value',
        nativePicker: '#upload-layer-color-picker', pickerBtn: '#upload-layer-color-picker-btn',
        hexInput: '#upload-layer-color-hex', presets: '.upload-layer-color-preset',
    });

    const listApi = attachTaggedEntityList({
        listEndpoint: context.listEndpoint,
        renderList: renderLayers,
        entityLabel: 'GIS Layer',
        loadFailedMessage: 'Error loading GIS Layers',
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
