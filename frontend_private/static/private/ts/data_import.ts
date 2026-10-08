import { count, canImportKML, validReport } from './import_model.ts';
import { renderImportCollections, applySuggestedLayerName, renderImportProgress, renderImportDialog } from './import_presentation.ts';
export { canImportKML } from './import_model.ts';
export { renderImportReview, renderImportCollections, renderImportError, applySuggestedLayerName } from './import_presentation.ts';
import type { ImportTab, ImportMode, ImportResponse, ImportSession } from '../../../../ts-types/domain/data-import.ts';
import type { UploadError } from '../../../../ts-types/domain/upload.ts';
import { openMapDialog, closeMapDialog } from './map_viewer/components/dialog_lifecycle.ts';
import { uploadWithProgress } from './map_viewer/components/upload.ts';
import { refreshImportedMapData, showImportedMapData } from './map_viewer/components/map_import_navigation.ts';
import { LandmarkManager } from './map_viewer/landmarks/manager.ts';
import { State } from './map_viewer/state.ts';

/** One transient dialog session; inspection never creates an import or background job. */
export const DataImport = (() => {
    let token = '';
    let modal: HTMLElement | null = null;
    let listeners: (() => void)[] = [];
    let session: ImportSession | null = null;
    let inspection: XMLHttpRequest | null = null;
    let generation = 0;
    const element = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
    const query = <T extends HTMLElement = HTMLElement>(selector: string) => modal!.querySelector<T>(selector)!;
    const listen = <K extends keyof HTMLElementEventMap>(target: HTMLElement | null, name: K, handler: (event: HTMLElementEventMap[K]) => void) => {
        target?.addEventListener(name, handler);
        listeners.push(() => target?.removeEventListener(name, handler));
    };
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
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

    function init(csrfToken: string) {
        if (interactionLocked()) return;
        destroy();
        token = csrfToken;
        modal = element('import-data-modal');
        if (!modal) return;
        resetSession();
        listen(element('import-data-button'), 'click', showModal);
        listen(modal, 'click', event => {
            const button = (event.target as Element).closest<HTMLButtonElement>('[data-import-action]');
            if (!button || button.disabled) return;
            const action = button.dataset.importAction;
            if (action === 'hide') hideModal();
            else if (action === 'tab') switchTab(button.dataset.importTab as ImportTab);
            else if (action === 'browse-gpx' || action === 'browse-kml') {
                if (!session!.busy && (action === 'browse-gpx' || session!.mode)) element<HTMLInputElement>(`${action.slice(7)}-file-input`).click();
            } else if (action === 'clear-gpx') clearFile('gpx');
            else if (action === 'clear-kml') clearFile('kml');
            else if (action === 'inspect-kml') void inspectKML();
            else if (action === 'submit') void submit();
            else if (action === 'refresh') void refreshResult();
            else if (action === 'collections') void loadCollections();
            else if (action === 'show') void showResult();
            else if (action === 'choose-mode' && !session!.busy) {
                session!.mode = button.dataset.importMode as ImportMode;
                render();
                query('[data-import-action="change-mode"]').focus();
            } else if (action === 'change-mode' && !session!.busy) {
                const previousMode = session!.mode;
                session!.mode = null;
                render();
                query(`[data-import-mode="${previousMode}"]`).focus();
            }
        });
        listen(modal, 'change', event => {
            if (session!.busy) return;
            if ((event.target as HTMLElement).id.endsWith('-landmark-collection')) render();
        });
        listen(element<HTMLInputElement>('kml-layer-name'), 'input', () => {
            session!.layerNameEdited = true;
            render();
        });
        listen(query('[role="tablist"]'), 'keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || session!.busy) return;
            event.preventDefault();
            const tab = event.key === 'Home' ? 'gpx' : event.key === 'End' ? 'kml' : session!.tab === 'gpx' ? 'kml' : 'gpx';
            switchTab(tab);
            element<HTMLButtonElement>(`import-tab-${tab}`).focus();
        });
        for (const type of ['gpx', 'kml'] as const) {
            listen(element<HTMLInputElement>(`${type}-file-input`), 'change', event => selectFile(type, (event.target as HTMLInputElement).files?.[0]));
            const zone = element(`${type}-drop-zone`);
            for (const name of ['dragenter', 'dragover', 'dragleave', 'drop'] as const) {
                listen(zone, name, event => {
                    event.preventDefault();
                    event.stopPropagation();
                    zone.classList.toggle('is-dragging', name === 'dragenter' || name === 'dragover');
                    if (name === 'drop' && !session!.busy) {
                        if (event.dataTransfer!.files.length !== 1) {
                            session!.errors[type] = 'Choose one file at a time.';
                            render();
                        } else selectFile(type, event.dataTransfer!.files[0]);
                    }
                });
            }
        }
    }

    function showModal() {
        if (!modal || interactionLocked() || !modal.classList.contains('hidden')) return;
        resetSession();
        for (const type of ['gpx', 'kml'] as const) element<HTMLInputElement>(`${type}-file-input`).value = '';
        element<HTMLInputElement>('kml-layer-name').value = '';
        render();
        openMapDialog(modal, {
            returnFocus: element('import-data-button'), dismissOnBackdrop: false,
            canDismiss: () => !interactionLocked(),
            onClose: resetSession,
        });
        element('import-data-title').focus({ preventScroll: true });
        void loadCollections();
    }

    function hideModal() { closeMapDialog(modal); }

    async function loadCollections() {
        if (session!.collectionsLoading) return;
        const current = session!;
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

    function switchTab(tab: ImportTab) {
        if (session!.busy || session!.result || !['gpx', 'kml'].includes(tab)) return;
        session!.tab = tab;
        render();
    }

    function clearFile(type: ImportTab) {
        if (session!.busy) return;
        session![`${type}File`] = null;
        element<HTMLInputElement>(`${type}-file-input`).value = '';
        session!.errors[type] = '';
        session!.uncertain = false;
        if (type === 'kml') {
            generation += 1;
            inspection?.abort();
            inspection = null;
            session!.report = null;
            session!.inspecting = false;
        }
        render();
    }

    function selectFile(type: ImportTab, file: File | undefined) {
        if (!file || session!.busy) return;
        if (type === 'kml' && !session!.mode) {
            session!.errors.kml = 'Choose Placemarks or Map Overlay before selecting a file.';
            render();
            return;
        }
        clearFile(type);
        if (!(type === 'gpx' ? /\.gpx$/i : /\.(kml|kmz)$/i).test(file.name)) {
            session!.errors[type] = type === 'gpx' ? 'Choose a .gpx file.' : 'Choose a .kml or .kmz file.';
            render();
            return;
        }
        session![`${type}File`] = file;
        if (type === 'kml') {
            session!.layerNameEdited = false;
            applySuggestedLayerName(element<HTMLInputElement>('kml-layer-name'), file.name.replace(/\.(kml|kmz)$/i, ''), false);
        }
        render();
        if (type === 'kml') void inspectKML();
    }

    async function inspectKML() {
        if (!session!.kmlFile || session!.busy) return;
        generation += 1;
        const requestGeneration = generation;
        inspection?.abort();
        session!.inspecting = true;
        session!.report = null;
        session!.errors.kml = '';
        session!.progress = null;
        session!.progressText = 'Uploading for review…';
        render();
        const data = new FormData();
        data.append('file', session!.kmlFile, session!.kmlFile.name);
        const isCurrent = () => generation === requestGeneration;
        try {
            const report = await new Promise<unknown>((resolve, reject) => {
                inspection = uploadWithProgress(Urls['api:v2:kml-kmz-inspect'](), data, {
                    csrfToken: token, onSuccess: resolve, onError: reject,
                    onProgress: percent => {
                        if (!isCurrent()) return;
                        session!.progress = percent;
                        session!.progressText = `Uploading for review… ${percent}%`;
                        renderProgress();
                    },
                    onUploaded: () => {
                        if (!isCurrent()) return;
                        session!.progress = null;
                        session!.progressText = 'Reviewing file…';
                        renderProgress();
                    },
                });
            });
            if (!isCurrent()) return;
            if (!validReport(report)) throw new Error('The file review could not be read. Please try again.');
            session!.report = report;
            applySuggestedLayerName(element<HTMLInputElement>('kml-layer-name'), report.suggested_name, session!.layerNameEdited);
        } catch (error) {
            if (!isCurrent()) return;
            session!.errors.kml = (error as UploadError).message || 'Unable to review this file.';
        } finally {
            if (isCurrent()) {
                inspection = null;
                session!.inspecting = false;
                render();
            }
        }
    }

    function eligible() {
        if (session!.result || session!.busy || session!.uncertain) return false;
        if (session!.tab === 'gpx') return Boolean(session!.gpxFile && session!.collectionsReady);
        return canImportKML({
            file: session!.kmlFile, report: session!.report, mode: session!.mode,
            collectionId: session!.collectionsReady ? element<HTMLSelectElement>('kml-landmark-collection').value : '',
            layerName: element<HTMLInputElement>('kml-layer-name').value,
        });
    }

    async function submit() {
        if (!eligible()) return;
        generation += 1;
        inspection?.abort();
        inspection = null;
        session!.inspecting = false;
        const kind = session!.tab === 'gpx' ? 'gpx' : session!.mode;
        const file = kind === 'gpx' ? session!.gpxFile : session!.kmlFile;
        const data = new FormData();
        const overlay = kind === 'overlay';
        data.append(overlay ? 'source_file' : 'file', file!, file!.name);
        if (overlay) data.append('name', element<HTMLInputElement>('kml-layer-name').value.trim());
        else data.append('collection', element<HTMLSelectElement>(`${kind === 'gpx' ? 'gpx' : 'kml'}-landmark-collection`).value);
        const endpoint = overlay ? 'api:v2:gis-layers' : kind === 'gpx' ? 'api:v2:gpx-import' : 'api:v2:kml-kmz-import';
        session!.busy = true;
        session!.errors[session!.tab] = '';
        session!.progress = null;
        session!.progressText = 'Uploading file…';
        window.addEventListener('beforeunload', beforeUnload);
        render();
        try {
            const response = await new Promise<ImportResponse | null>((resolve, reject) => {
                uploadWithProgress<ImportResponse>(Urls[endpoint](), data, {
                    method: overlay ? 'POST' : 'PUT', csrfToken: token,
                    onSuccess: resolve, onError: reject,
                    onProgress: percent => {
                        session!.progress = percent;
                        session!.progressText = `Uploading file… ${percent}%`;
                        renderProgress();
                    },
                    onUploaded: () => {
                        session!.progress = null;
                        session!.progressText = overlay ? 'Preparing your map overlay… Keep this window open.'
                            : kind === 'gpx' ? 'Importing landmarks and tracks… Keep this window open.' : 'Importing places… Keep this window open.';
                        renderProgress();
                    },
                });
            });
            if (!response || (overlay ? !response.id : !Number.isFinite(response.landmarks_created))) {
                throw Object.assign(new Error('The server returned an unreadable import result.'), { ambiguous: true });
            }
            session!.result = {
                kind: kind!, layerId: response.id, collectionId: response.collection_id,
                bounds: response.bounds, landmarksCreated: count(response.landmarks_created),
                gpsTracksCreated: count(response.gps_tracks_created),
                gpsTrackIds: Array.isArray(response.gps_track_ids) ? response.gps_track_ids.map(String) : [],
                landmarksSkipped: count(response.landmarks_skipped), duplicatesInFile: count(response.duplicates_in_file),
                name: overlay ? String(response.name || element<HTMLInputElement>('kml-layer-name').value) : '',
            };
        } catch (error) {
            session!.uncertain = Boolean((error as UploadError).ambiguous);
            session!.errors[session!.tab] = session!.uncertain
                ? 'The connection ended before the import result could be confirmed. Check your GIS layers, landmarks, or GPS tracks before importing this file again.'
                : (error as UploadError).message || 'Import failed. Please try again.';
        } finally {
            session!.busy = false;
            window.removeEventListener('beforeunload', beforeUnload);
            render();
        }
        if (session!.result) {
            element('import-result').focus({ preventScroll: true });
            await refreshResult();
        }
    }

    async function refreshResult() {
        if (!session!.result || session!.refreshing) return;
        const current = session!;
        current.refreshing = true;
        current.refreshError = '';
        render();
        try {
            await refreshImportedMapData(current.result!);
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
        if (!session!.result || session!.refreshing || !session!.refreshed) return;
        const current = session!;
        current.refreshing = true;
        current.showing = true;
        render();
        try {
            await showImportedMapData(current.result!);
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
        renderImportProgress(session!, element);
    }

    function render() {
        if (!modal || !session) return;
        renderImportDialog(session, modal, { element, query, eligible, interactionLocked, renderProgress });
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
