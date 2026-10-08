import type { GISListRecord, GISUploadListContext, GISUploadErrorDetails, GISUploadErrorBody } from '../../ts-types/controllers/gis-lists.ts';
import { initColorPicker } from '../../frontend_private/static/private/ts/color-picker.ts';
import { attachTaggedEntityList } from '../../frontend_private/static/private/ts/forms/tagged_entity_list.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';
import { buildGISLayerListMarkup, SUPPORTED_FORMATS_LABEL } from '../presentation/gis-overlays.ts';

const DEFAULT_COLOR = '#377eb8';
const ACCEPTED_EXTENSIONS = new Set(['kml', 'kmz', 'geojson', 'json', 'topojson', 'zip']);

function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function renderGISLayerUploadError(element: HTMLElement, message: string, details: GISUploadErrorDetails | null = {}) {
    element.textContent = message;
    if (!Number.isInteger(details?.line) || details!.line! < 1) return;

    const location = document.createElement('span');
    location.className = 'block mt-2';
    location.textContent = `Line ${details!.line}`;
    if (Number.isInteger(details!.column) && details!.column! > 0) {
        location.textContent += `, column ${details!.column}`;
    }
    element.append(location);
    if (typeof details!.source_line === 'string' && details!.source_line) {
        const source = document.createElement('code');
        source.className = 'block whitespace-pre-wrap break-words';
        source.textContent = details!.source_line;
        element.append(source);
    }
}

export function attachGISLayerList(context: GISUploadListContext) {
    let selectedFile: File | null = null;
    let uploadRequest: XMLHttpRequest | null = null;

    function renderLayers(layers: GISListRecord[]) {
        const { tableHtml, cardsHtml } = buildGISLayerListMarkup(layers, context.openIconUrl);
        $('#gis-layers-table-body').html(tableHtml);
        $('#gis-layers-cards-container').html(cardsHtml);
    }

    const setUploadColor = initColorPicker({
        preview: '#upload-layer-color-preview', hiddenInput: '#upload-layer-color-value',
        nativePicker: '#upload-layer-color-picker', pickerBtn: '#upload-layer-color-picker-btn',
        hexInput: '#upload-layer-color-hex', presets: '.upload-layer-color-preset',
    });

    const listApi = attachTaggedEntityList<GISListRecord>({
        listEndpoint: context.listEndpoint,
        renderList: renderLayers,
        entityLabel: 'GIS Layer',
        loadFailedMessage: 'Error loading GIS Layers',
    });

    const uploadModal = (document.getElementById('upload-layer-modal') as HTMLElement);
    const uploadForm = (document.getElementById('upload-layer-form') as HTMLFormElement);
    const fileInput = (document.getElementById('upload-layer-file-input') as HTMLInputElement);
    const dropZone = (document.getElementById('upload-layer-drop-zone') as HTMLElement);
    const uploadButton = (document.getElementById('upload-layer-button') as HTMLButtonElement);
    const uploadDismissButtons = document.querySelectorAll<HTMLButtonElement>('[data-layer-upload-action="hide"]');

    function uploadIsActive() {
        return uploadRequest && uploadRequest.readyState !== XMLHttpRequest.DONE;
    }

    function setUploadDismissDisabled(disabled: boolean) {
        uploadDismissButtons.forEach(button => { button.disabled = disabled; });
    }

    function showUploadError(message: string, details?: GISUploadErrorDetails) {
        renderGISLayerUploadError((document.getElementById('upload-layer-error-text') as HTMLElement), message, details);
        (document.getElementById('upload-layer-error-message') as HTMLElement).classList.remove('hidden');
    }

    function clearSelectedFile() {
        selectedFile = null;
        fileInput.value = '';
        dropZone.classList.remove('hidden', 'border-cyan-400', 'bg-srgb-slate-700-50');
        (document.getElementById('upload-layer-selected-file') as HTMLElement).classList.add('hidden');
        (document.getElementById('upload-layer-error-message') as HTMLElement).classList.add('hidden');
        (document.getElementById('upload-layer-progress-wrap') as HTMLElement).classList.add('hidden');
        (document.getElementById('upload-layer-progress') as HTMLElement).style.width = '0%';
        (document.getElementById('upload-layer-progress-value') as HTMLElement).textContent = '0%';
        (document.getElementById('upload-layer-progress-label') as HTMLElement).textContent = 'Uploading…';
        (document.getElementById('upload-layer-button-text') as HTMLElement).textContent = 'Upload Layer';
        (document.getElementById('upload-layer-spinner') as HTMLElement).classList.add('hidden');
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

    function selectFile(file: File | undefined) {
        clearSelectedFile();
        if (!file) return;
        const extension = file.name.split('.').pop()?.toLowerCase();
        if (!ACCEPTED_EXTENSIONS.has(extension!)) {
            showUploadError(`Choose ${SUPPORTED_FORMATS_LABEL}.`);
            return;
        }
        selectedFile = file;
        (document.getElementById('upload-layer-file-name') as HTMLElement).textContent = file.name;
        (document.getElementById('upload-layer-file-size') as HTMLElement).textContent = formatFileSize(file.size);
        dropZone.classList.add('hidden');
        (document.getElementById('upload-layer-selected-file') as HTMLElement).classList.remove('hidden');
        uploadButton.disabled = false;
        const nameInput = (document.getElementById('upload-layer-name') as HTMLInputElement);
        if (!nameInput.value) nameInput.value = file.name.replace(/\.(kml|kmz|geojson|json|topojson|zip)$/i, '');
    }

    function parseUploadError() {
        try {
            const data = JSON.parse(uploadRequest!.responseText) as GISUploadErrorBody;
            const fieldErrors = Object.values(data.errors || {}).flat().join(' ');
            const directFieldErrors = Object.values(data).flat()
                .filter(value => typeof value === 'string').join(' ');
            return {
                message: data.detail || data.error || data.error_message || fieldErrors || directFieldErrors || 'Upload failed.',
                details: data.code === 'XML_INVALID' ? data.details : undefined,
            };
        } catch {
            return { message: 'Upload failed.' };
        }
    }

    uploadForm.addEventListener('submit', event => {
        event.preventDefault();
        const name = (document.getElementById('upload-layer-name') as HTMLInputElement).value.trim();
        if (!selectedFile) return showUploadError(`Choose ${SUPPORTED_FORMATS_LABEL}.`);
        if (!name) return showUploadError('Please enter a layer name.');

        const data = new FormData();
        data.append('source_file', selectedFile, selectedFile.name);
        data.append('name', name);
        data.append('description', (document.getElementById('upload-layer-description') as HTMLTextAreaElement).value.trim());
        data.append('color', (document.getElementById('upload-layer-color-value') as HTMLInputElement).value);
        uploadButton.disabled = true;
        (document.getElementById('upload-layer-spinner') as HTMLElement).classList.remove('hidden');
        (document.getElementById('upload-layer-button-text') as HTMLElement).textContent = 'Uploading…';
        (document.getElementById('upload-layer-progress-wrap') as HTMLElement).classList.remove('hidden');
        (document.getElementById('upload-layer-error-message') as HTMLElement).classList.add('hidden');
        setUploadDismissDisabled(true);

        uploadRequest = new XMLHttpRequest();
        uploadRequest.open('POST', context.listEndpoint);
        uploadRequest.setRequestHeader('X-CSRFToken', context.csrfToken);
        uploadRequest.upload.addEventListener('progress', progressEvent => {
            if (!progressEvent.lengthComputable) return;
            const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
            (document.getElementById('upload-layer-progress') as HTMLElement).style.width = `${percent}%`;
            (document.getElementById('upload-layer-progress-value') as HTMLElement).textContent = `${percent}%`;
        });
        uploadRequest.upload.addEventListener('load', () => {
            const directGeoJSON = /\.(geojson|json)$/i.test(selectedFile!.name);
            (document.getElementById('upload-layer-progress-label') as HTMLElement).textContent = directGeoJSON
                ? 'Saving layer…'
                : 'Preparing map data…';
            (document.getElementById('upload-layer-progress') as HTMLElement).style.width = '100%';
            (document.getElementById('upload-layer-progress-value') as HTMLElement).textContent = '100%';
            (document.getElementById('upload-layer-button-text') as HTMLElement).textContent = directGeoJSON
                ? 'Saving…'
                : 'Preparing…';
        });
        uploadRequest.addEventListener('load', () => {
            if (uploadRequest!.status >= 200 && uploadRequest!.status < 300) {
                uploadRequest = null;
                hideUploadModal();
                FormModals.showSuccess('GIS Layer uploaded successfully!');
                listApi.reload();
                return;
            }
            const { message, details } = parseUploadError();
            showUploadError(message, details);
            uploadRequest = null;
            setUploadDismissDisabled(false);
            uploadButton.disabled = false;
            (document.getElementById('upload-layer-spinner') as HTMLElement).classList.add('hidden');
            (document.getElementById('upload-layer-button-text') as HTMLElement).textContent = 'Upload Layer';
        });
        uploadRequest.addEventListener('error', () => {
            showUploadError('The upload was interrupted. Try again.');
            uploadRequest = null;
            setUploadDismissDisabled(false);
            uploadButton.disabled = false;
            (document.getElementById('upload-layer-spinner') as HTMLElement).classList.add('hidden');
            (document.getElementById('upload-layer-button-text') as HTMLElement).textContent = 'Upload Layer';
        });
        uploadRequest.addEventListener('abort', () => {
            uploadRequest = null;
            setUploadDismissDisabled(false);
            uploadButton.disabled = false;
            (document.getElementById('upload-layer-spinner') as HTMLElement).classList.add('hidden');
            (document.getElementById('upload-layer-button-text') as HTMLElement).textContent = 'Upload Layer';
        });
        uploadRequest.send(data);
    });

    (document.getElementById('upload-layer-open') as HTMLElement).addEventListener('click', showUploadModal);
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
