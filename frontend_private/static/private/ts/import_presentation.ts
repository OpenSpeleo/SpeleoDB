import type { ImportTab, ImportMode, ImportReview, ImportCollection, ImportSession, ImportPresentationHost } from '../../../../ts-types/domain/data-import.ts';
import { count, plural } from './import_model.ts';

/** Stable review IDs and intent values are shared by the template and controller. */
export function renderImportReview(report: ImportReview | null, mode: ImportMode | null, root: ParentNode = document) {
    const review = root.querySelector<HTMLElement>('#kml-review')!;
    review.hidden = !report;
    if (!report) return;
    const places = report.places;
    const overlay = report.overlay;
    const summary = root.querySelector<HTMLElement>('#kml-review-summary')!;
    const detail = root.querySelector<HTMLElement>('#kml-review-detail')!;
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
    const warnings = root.querySelector<HTMLElement>('#kml-review-warnings')!;
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

export function renderImportCollections(collections: Iterable<ImportCollection>, root: ParentNode = document) {
    const writable = [...collections].filter(collection => collection.can_write)
        .sort((a, b) => Number(b.is_personal) - Number(a.is_personal) || a.name.localeCompare(b.name));
    for (const type of ['gpx', 'kml'] as const) {
        const select = root.querySelector<HTMLSelectElement>(`#${type}-landmark-collection`)!;
        const selected = select.value;
        select.replaceChildren();
        for (const collection of writable) {
            const option = document.createElement('option');
            option.value = collection.id as string;
            option.textContent = collection.is_personal ? `${collection.name} (Private)` : collection.name;
            select.append(option);
        }
        if (writable.some(collection => String(collection.id) === selected)) select.value = selected;
    }
    return writable.length > 0;
}

export function renderImportError(errors: Record<ImportTab, string>, tab: ImportTab, root: ParentNode = document) {
    const error = root.querySelector<HTMLElement>('#import-error')!;
    error.textContent = errors[tab] || '';
    error.hidden = !errors[tab];
}

export function applySuggestedLayerName(input: HTMLInputElement, name: unknown, edited: boolean) {
    if (edited || typeof name !== 'string') return;
    input.value = input.maxLength > 0 ? name.slice(0, input.maxLength) : name;
}

export function renderImportProgress(session: ImportSession, element: ImportPresentationHost['element']) {
    const visible = session.busy || (session.tab === 'kml' && session.mode && session.inspecting);
    element('import-progress').hidden = !visible;
    element('import-progress-text').textContent = session.progressText;
    const progress = element<HTMLProgressElement>('import-progress-bar');
    if (session.progress === null) progress.removeAttribute('value');
    else progress.value = session.progress;
}

export function renderImportDialog(session: ImportSession, modal: HTMLElement, { element, query, eligible, interactionLocked, renderProgress }: ImportPresentationHost) {
    const completed = Boolean(session.result);
    for (const type of ['gpx', 'kml'] as const) {
        const selected = session.tab === type;
        const tab = element<HTMLButtonElement>(`import-tab-${type}`);
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        tab.disabled = session.busy || completed;
        element(`import-content-${type}`).hidden = !selected || completed;
        element<HTMLFieldSetElement>(`${type}-import-fields`).disabled = session.busy;
        element<HTMLSelectElement>(`${type}-landmark-collection`).disabled = session.collectionsLoading || !session.collectionsReady;
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
    query<HTMLButtonElement>('[data-import-action="browse-kml"]').disabled = !session.mode || session.busy;
    renderImportReview(session.report, session.mode);
    element('kml-review').hidden = !session.mode || !session.report;
    element('kml-inspect-retry').hidden = !session.mode || !session.kmlFile || session.inspecting || Boolean(session.report) || session.busy;
    renderImportError(session.errors, session.tab);
    if (session.tab === 'kml' && !session.mode) element('import-error').hidden = true;
    element('import-collections-error').textContent = session.collectionsError;
    element('import-collections-error').hidden = !session.collectionsError || completed || (session.tab === 'kml' && session.mode !== 'places');
    element<HTMLButtonElement>('import-collections-retry').hidden = element('import-collections-error').hidden;
    element<HTMLButtonElement>('import-collections-retry').disabled = session.collectionsLoading || session.busy;
    modal.querySelectorAll<HTMLButtonElement>('[data-import-action="hide"]').forEach(button => { button.disabled = interactionLocked(); });
    element('import-dismiss-button').textContent = completed ? 'Close' : 'Cancel';
    const submitButton = element<HTMLButtonElement>('import-submit-button');
    submitButton.hidden = completed || (session.tab === 'kml' && !session.mode);
    submitButton.disabled = !eligible();
    submitButton.textContent = session.busy ? 'Importing…' : session.tab === 'gpx' ? 'Import GPX'
        : session.mode === 'overlay' ? 'Import map overlay'
            : session.mode === 'places' && session.report ? `Import ${plural(session.report.places.unique_coordinate_count, 'place')}` : 'Import';
    element('import-result').hidden = !completed;
    const show = element<HTMLButtonElement>('import-show-button');
    show.hidden = !completed || (session.result!.kind !== 'overlay'
        && !session.result!.landmarksCreated && !session.result!.gpsTracksCreated);
    show.disabled = session.refreshing || !session.refreshed;
    show.textContent = session.showing ? 'Showing on map…' : 'Show on map';
    if (completed) {
        const result = session.result!;
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
