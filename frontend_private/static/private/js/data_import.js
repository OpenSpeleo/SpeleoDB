import { openMapDialog, closeMapDialog } from './map_viewer/components/dialog_lifecycle.js';
import { uploadWithProgress } from './map_viewer/components/upload.js';
import { refreshImportedMapData, showImportedMapData } from './map_viewer/components/map_import_navigation.js';
import { LandmarkManager } from './map_viewer/landmarks/manager.js';
import { State } from './map_viewer/state.js';

const count = value => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
const plural = (value, singular, multiple = `${singular}s`) => `${count(value)} ${count(value) === 1 ? singular : multiple}`;

/** Stable review IDs and intent values are shared by the template and controller. */
export function renderImportReview(report, mode, root = document) {
    const review = root.querySelector('#kml-review');
    review.hidden = !report;
    if (!report) return;
    const places = report.places;
    const overlay = report.overlay;
    const summary = root.querySelector('#kml-review-summary');
    const detail = root.querySelector('#kml-review-detail');
    if (mode === 'places') {
        summary.textContent = count(places.unique_coordinate_count)
            ? `${plural(places.unique_coordinate_count, 'place')} available to import as landmarks.` : 'No editable places found.';
        detail.textContent = !count(places.unique_coordinate_count) && count(overlay.feature_count)
            ? 'Choose Map Overlay to import the supported lines and areas in this file.'
            : `${plural(places.duplicate_coordinate_count, 'repeated coordinate')} in this file. Places already in the selected collection will be skipped when importing.`;
    } else if (mode === 'overlay') {
        summary.textContent = count(overlay.feature_count)
            ? `One GIS layer with ${plural(overlay.point_parts, 'point')}, ${plural(overlay.line_parts, 'line')}, and ${plural(overlay.polygon_parts, 'area')}.`
            : 'No supported map geometry found.';
        detail.textContent = !count(overlay.feature_count) && count(places.unique_coordinate_count)
            ? 'Choose Placemarks to import the points in this file.'
            : 'All folders stay together. The original KML or KMZ file is preserved for download.';
    } else {
        summary.textContent = `${plural(places.unique_coordinate_count, 'editable place')} · ${plural(overlay.feature_count, 'map feature')}`;
        detail.textContent = 'Choose how you want to import this file above.';
    }
    const warnings = root.querySelector('#kml-review-warnings');
    warnings.replaceChildren();
    if (mode === 'places' && count(places.skipped_placemarks)) {
        const item = document.createElement('li');
        item.textContent = `${plural(places.skipped_placemarks, 'item')} containing paths, areas, or other content will not become editable places.`;
        warnings.append(item);
    }
    for (const warning of report.warnings || []) {
        if (mode && !warning.modes?.includes(mode)) continue;
        if (mode === 'places' && count(places.skipped_placemarks) && warning.code === 'PLACEMARKS_NOT_IMPORTED') continue;
        const item = document.createElement('li');
        item.textContent = String(warning.message || 'Some content cannot be displayed.');
        warnings.append(item);
    }
    warnings.hidden = !warnings.children.length;
}

export function canImportKML({ file, report, mode, collectionId, layerName, busy = false, uncertain = false }) {
    if (!file || !report || busy || uncertain) return false;
    if (mode === 'places') return count(report.places?.unique_coordinate_count) > 0 && Boolean(collectionId);
    if (mode === 'overlay') return count(report.overlay?.feature_count) > 0 && Boolean(layerName?.trim());
    return false;
}

export function renderImportCollections(collections, root = document) {
    const writable = [...collections].filter(collection => collection.can_write)
        .sort((a, b) => Number(b.is_personal) - Number(a.is_personal) || a.name.localeCompare(b.name));
    for (const type of ['gpx', 'kml']) {
        const select = root.querySelector(`#${type}-landmark-collection`);
        const selected = select.value;
        select.replaceChildren();
        for (const collection of writable) {
            const option = document.createElement('option');
            option.value = collection.id;
            option.textContent = collection.is_personal ? `${collection.name} (Private)` : collection.name;
            select.append(option);
        }
        if (writable.some(collection => String(collection.id) === selected)) select.value = selected;
    }
    return writable.length > 0;
}

export function renderImportError(errors, tab, root = document) {
    const error = root.querySelector('#import-error');
    error.textContent = errors[tab] || '';
    error.hidden = !errors[tab];
}

export function applySuggestedLayerName(input, name, edited) {
    if (edited || typeof name !== 'string') return;
    input.value = input.maxLength > 0 ? name.slice(0, input.maxLength) : name;
}

function validReport(report) {
    return report?.places && report?.overlay && Array.isArray(report.warnings)
        && Number.isFinite(report.places.unique_coordinate_count)
        && Number.isFinite(report.overlay.feature_count);
}

/** One transient dialog session; inspection never creates an import or background job. */
export const DataImport = (() => {
    let token = '';
    let modal = null;
    let listeners = [];
    let session = null;
    let inspection = null;
    let generation = 0;
    const element = id => document.getElementById(id);
    const query = selector => modal.querySelector(selector);
    const listen = (target, name, handler) => {
        target?.addEventListener(name, handler);
        listeners.push(() => target?.removeEventListener(name, handler));
    };
    const beforeUnload = event => { event.preventDefault(); event.returnValue = ''; };
    const interactionLocked = () => Boolean(session?.busy || session?.showing);

    function resetSession() {
        generation += 1;
        inspection?.abort();
        inspection = null;
        window.removeEventListener('beforeunload', beforeUnload);
        session = {
            tab: 'gpx', gpxFile: null, kmlFile: null, mode: null, report: null,
            inspecting: false, busy: false, uncertain: false, errors: { gpx: '', kml: '' }, layerNameEdited: false,
            result: null, refreshing: false, refreshed: false, refreshError: '', showing: false,
            collectionsReady: false, collectionsLoading: false, collectionsError: '', progress: null, progressText: '',
        };
    }

    function init(csrfToken) {
        if (interactionLocked()) return;
        destroy();
        token = csrfToken;
        modal = element('import-data-modal');
        if (!modal) return;
        resetSession();
        listen(element('import-data-button'), 'click', showModal);
        listen(modal, 'click', event => {
            const button = event.target.closest('[data-import-action]');
            if (!button || button.disabled) return;
            const action = button.dataset.importAction;
            if (action === 'hide') hideModal();
            else if (action === 'tab') switchTab(button.dataset.importTab);
            else if (action === 'browse-gpx' || action === 'browse-kml') {
                if (!session.busy && (action === 'browse-gpx' || session.mode)) element(`${action.slice(7)}-file-input`).click();
            } else if (action === 'clear-gpx') clearFile('gpx');
            else if (action === 'clear-kml') clearFile('kml');
            else if (action === 'inspect-kml') inspectKML();
            else if (action === 'submit') submit();
            else if (action === 'refresh') refreshResult();
            else if (action === 'collections') loadCollections();
            else if (action === 'show') showResult();
            else if (action === 'choose-mode' && !session.busy) {
                session.mode = button.dataset.importMode;
                render();
                query('[data-import-action="change-mode"]').focus();
            } else if (action === 'change-mode' && !session.busy) {
                const previousMode = session.mode;
                session.mode = null;
                render();
                query(`[data-import-mode="${previousMode}"]`).focus();
            }
        });
        listen(modal, 'change', event => {
            if (session.busy) return;
            if (event.target.id.endsWith('-landmark-collection')) render();
        });
        listen(element('kml-layer-name'), 'input', () => {
            session.layerNameEdited = true;
            render();
        });
        listen(query('[role="tablist"]'), 'keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || session.busy) return;
            event.preventDefault();
            const tab = event.key === 'Home' ? 'gpx' : event.key === 'End' ? 'kml' : session.tab === 'gpx' ? 'kml' : 'gpx';
            switchTab(tab);
            element(`import-tab-${tab}`).focus();
        });
        for (const type of ['gpx', 'kml']) {
            listen(element(`${type}-file-input`), 'change', event => selectFile(type, event.target.files?.[0]));
            const zone = element(`${type}-drop-zone`);
            for (const name of ['dragenter', 'dragover', 'dragleave', 'drop']) {
                listen(zone, name, event => {
                    event.preventDefault();
                    event.stopPropagation();
                    zone.classList.toggle('is-dragging', name === 'dragenter' || name === 'dragover');
                    if (name === 'drop' && !session.busy) {
                        if (event.dataTransfer.files.length !== 1) {
                            session.errors[type] = 'Choose one file at a time.';
                            render();
                        } else selectFile(type, event.dataTransfer.files[0]);
                    }
                });
            }
        }
    }

    function showModal() {
        if (!modal || interactionLocked() || !modal.classList.contains('hidden')) return;
        resetSession();
        for (const type of ['gpx', 'kml']) element(`${type}-file-input`).value = '';
        element('kml-layer-name').value = '';
        render();
        openMapDialog(modal, {
            returnFocus: element('import-data-button'), dismissOnBackdrop: false,
            canDismiss: () => !interactionLocked(),
            onClose: resetSession,
        });
        element('import-data-title').focus({ preventScroll: true });
        loadCollections();
    }

    function hideModal() { closeMapDialog(modal); }

    async function loadCollections() {
        if (session.collectionsLoading) return;
        const current = session;
        current.collectionsLoading = true;
        current.collectionsReady = false;
        current.collectionsError = '';
        render();
        try {
            await LandmarkManager.loadCollections({ throwOnError: true });
            if (current !== session) return;
            current.collectionsReady = renderImportCollections(State.landmarkCollections.values());
            if (!current.collectionsReady) current.collectionsError = 'No writable landmark collections are available.';
        } catch {
            if (current !== session) return;
            current.collectionsError = 'Unable to load landmark collections. Please try again.';
        } finally {
            if (current === session) {
                current.collectionsLoading = false;
                render();
            }
        }
    }

    function switchTab(tab) {
        if (session.busy || session.result || !['gpx', 'kml'].includes(tab)) return;
        session.tab = tab;
        render();
    }

    function clearFile(type) {
        if (session.busy) return;
        session[`${type}File`] = null;
        element(`${type}-file-input`).value = '';
        session.errors[type] = '';
        session.uncertain = false;
        if (type === 'kml') {
            generation += 1;
            inspection?.abort();
            inspection = null;
            session.report = null;
            session.inspecting = false;
        }
        render();
    }

    function selectFile(type, file) {
        if (!file || session.busy) return;
        if (type === 'kml' && !session.mode) {
            session.errors.kml = 'Choose Placemarks or Map Overlay before selecting a file.';
            render();
            return;
        }
        clearFile(type);
        if (!(type === 'gpx' ? /\.gpx$/i : /\.(kml|kmz)$/i).test(file.name)) {
            session.errors[type] = type === 'gpx' ? 'Choose a .gpx file.' : 'Choose a .kml or .kmz file.';
            render();
            return;
        }
        session[`${type}File`] = file;
        if (type === 'kml') {
            session.layerNameEdited = false;
            applySuggestedLayerName(element('kml-layer-name'), file.name.replace(/\.(kml|kmz)$/i, ''), false);
        }
        render();
        if (type === 'kml') inspectKML();
    }

    async function inspectKML() {
        if (!session.kmlFile || session.busy) return;
        generation += 1;
        const requestGeneration = generation;
        inspection?.abort();
        session.inspecting = true;
        session.report = null;
        session.errors.kml = '';
        session.progress = null;
        session.progressText = 'Uploading for review…';
        render();
        const data = new FormData();
        data.append('file', session.kmlFile, session.kmlFile.name);
        const isCurrent = () => generation === requestGeneration;
        try {
            const report = await new Promise((resolve, reject) => {
                inspection = uploadWithProgress(Urls['api:v2:kml-kmz-inspect'](), data, {
                    csrfToken: token, onSuccess: resolve, onError: reject,
                    onProgress: percent => {
                        if (!isCurrent()) return;
                        session.progress = percent;
                        session.progressText = `Uploading for review… ${percent}%`;
                        renderProgress();
                    },
                    onUploaded: () => {
                        if (!isCurrent()) return;
                        session.progress = null;
                        session.progressText = 'Reviewing file…';
                        renderProgress();
                    },
                });
            });
            if (!isCurrent()) return;
            if (!validReport(report)) throw new Error('The file review could not be read. Please try again.');
            session.report = report;
            applySuggestedLayerName(element('kml-layer-name'), report.suggested_name, session.layerNameEdited);
        } catch (error) {
            if (!isCurrent()) return;
            session.errors.kml = error.message || 'Unable to review this file.';
        } finally {
            if (isCurrent()) {
                inspection = null;
                session.inspecting = false;
                render();
            }
        }
    }

    function eligible() {
        if (session.result || session.busy || session.uncertain) return false;
        if (session.tab === 'gpx') return Boolean(session.gpxFile && session.collectionsReady);
        return canImportKML({
            file: session.kmlFile, report: session.report, mode: session.mode,
            collectionId: session.collectionsReady ? element('kml-landmark-collection').value : '',
            layerName: element('kml-layer-name').value,
        });
    }

    async function submit() {
        if (!eligible()) return;
        generation += 1;
        inspection?.abort();
        inspection = null;
        session.inspecting = false;
        const kind = session.tab === 'gpx' ? 'gpx' : session.mode;
        const file = kind === 'gpx' ? session.gpxFile : session.kmlFile;
        const data = new FormData();
        const overlay = kind === 'overlay';
        data.append(overlay ? 'source_file' : 'file', file, file.name);
        if (overlay) data.append('name', element('kml-layer-name').value.trim());
        else data.append('collection', element(`${kind === 'gpx' ? 'gpx' : 'kml'}-landmark-collection`).value);
        const endpoint = overlay ? 'api:v2:gis-layers' : kind === 'gpx' ? 'api:v2:gpx-import' : 'api:v2:kml-kmz-import';
        session.busy = true;
        session.errors[session.tab] = '';
        session.progress = null;
        session.progressText = 'Uploading file…';
        window.addEventListener('beforeunload', beforeUnload);
        render();
        try {
            const response = await new Promise((resolve, reject) => {
                uploadWithProgress(Urls[endpoint](), data, {
                    method: overlay ? 'POST' : 'PUT', csrfToken: token,
                    onSuccess: resolve, onError: reject,
                    onProgress: percent => {
                        session.progress = percent;
                        session.progressText = `Uploading file… ${percent}%`;
                        renderProgress();
                    },
                    onUploaded: () => {
                        session.progress = null;
                        session.progressText = overlay ? 'Preparing your map overlay… Keep this window open.'
                            : kind === 'gpx' ? 'Importing landmarks and tracks… Keep this window open.' : 'Importing places… Keep this window open.';
                        renderProgress();
                    },
                });
            });
            if (!response || (overlay ? !response.id : !Number.isFinite(response.landmarks_created))) {
                throw Object.assign(new Error('The server returned an unreadable import result.'), { ambiguous: true });
            }
            session.result = {
                kind, layerId: response.id, collectionId: response.collection_id,
                bounds: response.bounds, landmarksCreated: count(response.landmarks_created),
                gpsTracksCreated: count(response.gps_tracks_created),
                gpsTrackIds: Array.isArray(response.gps_track_ids) ? response.gps_track_ids.map(String) : [],
                landmarksSkipped: count(response.landmarks_skipped), duplicatesInFile: count(response.duplicates_in_file),
                name: overlay ? String(response.name || element('kml-layer-name').value) : '',
            };
        } catch (error) {
            session.uncertain = Boolean(error.ambiguous);
            session.errors[session.tab] = session.uncertain
                ? 'The connection ended before the import result could be confirmed. Check your GIS layers, landmarks, or GPS tracks before importing this file again.'
                : error.message || 'Import failed. Please try again.';
        } finally {
            session.busy = false;
            window.removeEventListener('beforeunload', beforeUnload);
            render();
        }
        if (session.result) {
            element('import-result').focus({ preventScroll: true });
            await refreshResult();
        }
    }

    async function refreshResult() {
        if (!session.result || session.refreshing) return;
        const current = session;
        current.refreshing = true;
        current.refreshError = '';
        render();
        try {
            await refreshImportedMapData(current.result);
            if (current === session) current.refreshed = true;
        } catch {
            if (current === session) current.refreshError = 'Your import is saved, but the map could not refresh.';
        } finally {
            if (current === session) {
                current.refreshing = false;
                render();
            }
        }
    }

    async function showResult() {
        if (!session.result || session.refreshing || !session.refreshed) return;
        const current = session;
        current.refreshing = true;
        current.showing = true;
        render();
        try {
            await showImportedMapData(current.result);
            if (current === session) {
                current.showing = false;
                hideModal();
            }
        } catch {
            if (current === session) current.refreshError = 'Your import is saved, but it could not be shown on the map. Please try again.';
        } finally {
            if (current === session) {
                current.showing = false;
                current.refreshing = false;
                render();
            }
        }
    }

    function renderProgress() {
        const visible = session.busy || (session.tab === 'kml' && session.mode && session.inspecting);
        element('import-progress').hidden = !visible;
        element('import-progress-text').textContent = session.progressText;
        const progress = element('import-progress-bar');
        if (session.progress === null) progress.removeAttribute('value');
        else progress.value = session.progress;
    }

    function render() {
        if (!modal || !session) return;
        const completed = Boolean(session.result);
        for (const type of ['gpx', 'kml']) {
            const selected = session.tab === type;
            const tab = element(`import-tab-${type}`);
            tab.setAttribute('aria-selected', String(selected));
            tab.tabIndex = selected ? 0 : -1;
            tab.disabled = session.busy || completed;
            element(`import-content-${type}`).hidden = !selected || completed;
            element(`${type}-import-fields`).disabled = session.busy;
            element(`${type}-landmark-collection`).disabled = session.collectionsLoading || !session.collectionsReady;
            const file = session[`${type}File`];
            element(`${type}-drop-zone`).hidden = Boolean(file);
            element(`${type}-selected-file`).hidden = !file;
            if (file) {
                element(`${type}-file-name`).textContent = file.name;
                element(`${type}-file-size`).textContent = `${file.size.toLocaleString()} bytes`;
            }
        }
        query('[role="tablist"]').hidden = completed;
        element('kml-collection-field').hidden = session.mode !== 'places';
        element('kml-name-field').hidden = session.mode !== 'overlay';
        element('kml-mode-help').hidden = Boolean(session.mode);
        element('kml-selected-mode').hidden = !session.mode;
        element('kml-selected-mode-label').textContent = session.mode === 'places' ? 'Placemarks' : 'Map Overlay';
        element('kml-import-form').hidden = !session.mode;
        element('kml-export-instructions').hidden = !session.mode;
        element('kml-export-selection').textContent = session.mode === 'places'
            ? 'In the Places panel, select a point placemark or a folder of point placemarks.'
            : 'In the Places panel, select the folder containing the points, lines, and areas for your layer.';
        query('[data-import-action="browse-kml"]').disabled = !session.mode || session.busy;
        renderImportReview(session.report, session.mode);
        element('kml-review').hidden = !session.mode || !session.report;
        element('kml-inspect-retry').hidden = !session.mode || !session.kmlFile || session.inspecting || Boolean(session.report) || session.busy;
        renderImportError(session.errors, session.tab);
        if (session.tab === 'kml' && !session.mode) element('import-error').hidden = true;
        element('import-collections-error').textContent = session.collectionsError;
        element('import-collections-error').hidden = !session.collectionsError || completed || (session.tab === 'kml' && session.mode !== 'places');
        element('import-collections-retry').hidden = element('import-collections-error').hidden;
        element('import-collections-retry').disabled = session.collectionsLoading || session.busy;
        modal.querySelectorAll('[data-import-action="hide"]').forEach(button => { button.disabled = interactionLocked(); });
        element('import-dismiss-button').textContent = completed ? 'Close' : 'Cancel';
        const submitButton = element('import-submit-button');
        submitButton.hidden = completed || (session.tab === 'kml' && !session.mode);
        submitButton.disabled = !eligible();
        submitButton.textContent = session.busy ? 'Importing…' : session.tab === 'gpx' ? 'Import GPX'
            : session.mode === 'overlay' ? 'Import map overlay'
                : session.mode === 'places' && session.report ? `Import ${plural(session.report.places.unique_coordinate_count, 'place')}` : 'Import';
        element('import-result').hidden = !completed;
        const show = element('import-show-button');
        show.hidden = !completed || (session.result.kind !== 'overlay'
            && !session.result.landmarksCreated && !session.result.gpsTracksCreated);
        show.disabled = session.refreshing || !session.refreshed;
        show.textContent = session.showing ? 'Showing on map…' : 'Show on map';
        if (completed) {
            const result = session.result;
            const created = result.kind === 'overlay' || result.landmarksCreated || result.gpsTracksCreated;
            element('import-result-title').textContent = created ? 'Import complete' : 'Nothing new to import';
            element('import-result-message').textContent = result.kind === 'overlay' ? `“${result.name}” is ready as one GIS layer.`
                : result.kind === 'gpx' ? `Imported ${plural(result.landmarksCreated, 'landmark')} and ${plural(result.gpsTracksCreated, 'GPS track')}.`
                    : `Imported ${plural(result.landmarksCreated, 'landmark')}.`;
            element('import-result-detail').textContent = result.kind === 'overlay' ? 'Your original file is preserved. Show the overlay when you are ready.'
                : result.kind === 'places' ? `${plural(result.landmarksSkipped, 'place')} already in this collection. ${plural(result.duplicatesInFile, 'repeated coordinate')} in the file.`
                    : 'Show your imported tracks and landmarks when you are ready.';
            element('import-refresh-status').textContent = session.refreshing ? 'Updating map…' : session.refreshError || (session.refreshed ? 'Map data updated.' : '');
            element('import-refresh-retry').hidden = !session.refreshError || session.refreshing;
        }
        renderProgress();
    }

    function destroy() {
        if (interactionLocked()) return;
        if (modal) closeMapDialog(modal);
        listeners.forEach(remove => remove());
        listeners = [];
        if (session) resetSession();
        modal = null;
    }

    return {
        init, destroy, showModal, hideModal, switchTab, inspectKML,
        clearGPXFile: () => clearFile('gpx'), clearKMLFile: () => clearFile('kml'),
        uploadGPX: submit, uploadKML: submit,
    };
})();
