import { readFileSync } from 'node:fs';
import { DataImport, applySuggestedLayerName, canImportKML, renderImportCollections, renderImportError, renderImportReview } from './data_import.js';

const template = readFileSync('frontend_private/templates/snippets/modal_data_import.html', 'utf8');
const report = {
    source_placemarks: 4,
    places: { eligible_placemarks: 2, point_count: 3, unique_coordinate_count: 2, duplicate_coordinate_count: 1, skipped_placemarks: 2 },
    overlay: { source_placemarks: 4, feature_count: 4, point_parts: 3, line_parts: 1, polygon_parts: 1 },
    warnings: [
        { code: 'OVERLAY_TEST', message: '<img src=x onerror=alert(1)> appears flat.', count: 1, modes: ['overlay'] },
        { code: 'PLACES_TEST', message: 'Line placemarks are not imported as editable places.', count: 1, modes: ['places'] },
    ],
};

beforeEach(() => {
    document.body.innerHTML = `<div id="map-viewer-shell"><button id="import-data-button">Import</button>${template}</div>`;
});
afterEach(() => {
    DataImport.destroy();
    document.body.innerHTML = '';
});

it('requires an explicit intent and a valid destination before confirmation', () => {
    const values = { file: new File(['kml'], 'places.kml'), report, collectionId: 'collection', layerName: 'Overlay' };
    expect(canImportKML(values)).toBe(false);
    expect(canImportKML({ ...values, mode: 'places' })).toBe(true);
    expect(canImportKML({ ...values, mode: 'overlay' })).toBe(true);
    expect(canImportKML({ ...values, mode: 'places', collectionId: '' })).toBe(false);
    expect(canImportKML({ ...values, mode: 'overlay', layerName: '  ' })).toBe(false);
    for (const condition of [{ file: null }, { report: null }, { busy: true }, { uncertain: true }]) {
        expect(canImportKML({ ...values, mode: 'places', ...condition })).toBe(false);
    }
});

it('blocks modes that have no eligible output', () => {
    const empty = { places: { unique_coordinate_count: 0 }, overlay: { feature_count: 0 } };
    const values = { file: new File(['kml'], 'empty.kml'), report: empty, collectionId: 'c1', layerName: 'Overlay' };
    expect(canImportKML({ ...values, mode: 'places' })).toBe(false);
    expect(canImportKML({ ...values, mode: 'overlay' })).toBe(false);
});

it('uses the same inspection for both intents and limits warnings to the chosen outcome', () => {
    renderImportReview(report, 'places');
    expect(document.getElementById('kml-review-summary').textContent).toContain('2 places');
    expect(document.getElementById('kml-review-detail').textContent).toContain('1 repeated coordinate');
    expect(document.getElementById('kml-review-warnings').textContent).toContain('2 items');
    expect(document.getElementById('kml-review-warnings').textContent).not.toContain('appears flat');
    renderImportReview(report, 'overlay');
    expect(document.getElementById('kml-review-summary').textContent).toBe('One GIS layer with 3 points, 1 line, and 1 area.');
    expect(document.getElementById('kml-review-detail').textContent).toContain('All folders stay together');
    expect(document.getElementById('kml-review-warnings').textContent).toContain('<img src=x onerror=alert(1)>');
    expect(document.getElementById('kml-review-warnings').querySelector('img')).toBeNull();
    expect(document.getElementById('kml-review-warnings').textContent).not.toContain('Line placemarks');
});

it('clears stale review visibility when its file is removed', () => {
    renderImportReview(report, 'places');
    expect(document.getElementById('kml-review').hidden).toBe(false);
    renderImportReview(null, 'places');
    expect(document.getElementById('kml-review').hidden).toBe(true);
});

it('explains empty output without implying a layer will be created or switching intent', () => {
    const empty = { ...report, overlay: { feature_count: 0 }, places: { unique_coordinate_count: 0 }, warnings: [] };
    renderImportReview(empty, 'overlay');
    expect(document.getElementById('kml-review-summary').textContent).toBe('No supported map geometry found.');
    renderImportReview({ ...report, places: { unique_coordinate_count: 0 } }, 'places');
    expect(document.getElementById('kml-review-summary').textContent).toBe('No editable places found.');
    expect(document.getElementById('kml-review-detail').textContent).toContain('Choose Map Overlay');
});

it('reports skipped items once when the server includes the same compatibility warning', () => {
    renderImportReview({ ...report, warnings: [{ code: 'PLACEMARKS_NOT_IMPORTED', message: 'Repeated skipped warning', modes: ['places'] }] }, 'places');
    expect(document.getElementById('kml-review-warnings').children).toHaveLength(1);
    expect(document.getElementById('kml-review-warnings').textContent).not.toContain('Repeated skipped warning');
});

it('retains native format tabs and starts KML with no intent or enabled file picker', () => {
    DataImport.init('token');
    DataImport.switchTab('kml');
    expect(document.getElementById('import-tab-kml').getAttribute('aria-selected')).toBe('true');
    expect(document.getElementById('import-content-gpx').hidden).toBe(true);
    expect(document.getElementById('kml-import-form').hidden).toBe(true);
    expect(document.querySelector('[data-import-action="browse-kml"]').disabled).toBe(true);
    expect(document.getElementById('import-submit-button').disabled).toBe(true);
    expect(document.getElementById('kml-mode-help').textContent).toContain('Placemarks');
    expect(document.getElementById('kml-mode-help').textContent).toContain('Map Overlay');
    const card = document.querySelector('[data-import-mode="overlay"]');
    card.click();
    expect(document.querySelector('[data-import-action="browse-kml"]').disabled).toBe(false);
    expect(document.getElementById('kml-name-field').hidden).toBe(false);
    expect(document.getElementById('kml-collection-field').hidden).toBe(true);
    expect(document.getElementById('kml-mode-help').hidden).toBe(true);
    expect(document.getElementById('kml-import-form').hidden).toBe(false);
    const change = document.querySelector('[data-import-action="change-mode"]');
    expect(document.activeElement).toBe(change);
    change.click();
    expect(document.getElementById('kml-mode-help').hidden).toBe(false);
    expect(document.getElementById('kml-import-form').hidden).toBe(true);
    expect(document.activeElement).toBe(card);
});

it('supports keyboard format navigation and keeps the GPX collection/file form intact', () => {
    DataImport.init('token');
    DataImport.switchTab('kml');
    document.getElementById('import-tab-kml').dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
    expect(document.activeElement.id).toBe('import-tab-gpx');
    expect(document.getElementById('import-tab-gpx').getAttribute('aria-selected')).toBe('true');
    expect(document.getElementById('import-content-gpx').hidden).toBe(false);
    expect(document.getElementById('gpx-file-input').accept).toBe('.gpx');
    expect(document.getElementById('gpx-landmark-collection')).not.toBeNull();
    expect(document.getElementById('import-submit-button').textContent).toBe('Import GPX');
});

it('keeps file feedback out of the intent chooser and restores it when a mode is selected', () => {
    DataImport.init('token');
    DataImport.switchTab('kml');
    document.querySelector('[data-import-mode="places"]').click();
    const drop = new Event('drop', { bubbles: true, cancelable: true });
    Object.defineProperty(drop, 'dataTransfer', {
        value: { files: [new File(['invalid'], 'not-a-kml.txt')] },
    });
    document.getElementById('kml-drop-zone').dispatchEvent(drop);
    const error = document.getElementById('import-error');
    expect(error.hidden).toBe(false);
    expect(error.textContent).toBe('Choose a .kml or .kmz file.');

    document.querySelector('[data-import-action="change-mode"]').click();

    expect(error.hidden).toBe(true);
    expect(document.getElementById('import-progress').hidden).toBe(true);
    expect(document.getElementById('kml-review').hidden).toBe(true);
    expect(document.getElementById('import-submit-button').hidden).toBe(true);

    document.querySelector('[data-import-mode="overlay"]').click();

    expect(error.hidden).toBe(false);
    expect(error.textContent).toBe('Choose a .kml or .kmz file.');
});

it('exposes each intent explanation to screen-reader button navigation', () => {
    for (const mode of ['places', 'overlay']) {
        const card = document.querySelector(`[data-import-mode="${mode}"]`);
        const description = document.getElementById(card.getAttribute('aria-describedby'));
        expect(description).not.toBeNull();
        expect(description.textContent).toBe(card.querySelector('.map-import-guide-description').textContent);
    }
});

it('does not accumulate handlers after controller reinitialization', () => {
    DataImport.init('first');
    DataImport.init('second');
    DataImport.switchTab('gpx');
    document.getElementById('import-tab-gpx').dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(document.activeElement.id).toBe('import-tab-kml');
});

it('preserves a writable destination across a retry and removes revoked choices', () => {
    const collections = [
        { id: 'shared', name: '<img src=x>', can_write: true, is_personal: false },
        { id: 'personal', name: 'Personal', can_write: true, is_personal: true },
        { id: 'readonly', name: 'Read only', can_write: false, is_personal: false },
    ];
    expect(renderImportCollections(collections)).toBe(true);
    const select = document.getElementById('kml-landmark-collection');
    expect(select.value).toBe('personal');
    select.value = 'shared';
    renderImportCollections(collections);
    expect(select.value).toBe('shared');
    expect([...select.options].map(option => option.textContent)).toEqual(['Personal (Private)', '<img src=x>']);
    expect(select.querySelector('img')).toBeNull();
    renderImportCollections([collections[1]]);
    expect(select.value).toBe('personal');
    expect(renderImportCollections([])).toBe(false);
});

it('keeps a late KML inspection error out of the GPX panel and restores it on return', () => {
    const errors = { gpx: '', kml: '' };
    renderImportError(errors, 'gpx');
    errors.kml = '<img src=x> could not be inspected.';
    renderImportError(errors, 'gpx');
    expect(document.getElementById('import-error').hidden).toBe(true);
    renderImportError(errors, 'kml');
    expect(document.getElementById('import-error').textContent).toBe(errors.kml);
    expect(document.getElementById('import-error').querySelector('img')).toBeNull();
});

it('uses a bounded server suggestion without replacing a name the user edited', () => {
    const input = document.getElementById('kml-layer-name');
    applySuggestedLayerName(input, 'x'.repeat(input.maxLength + 1), false);
    expect(input.value.length).toBe(input.maxLength);
    input.value = 'My chosen name';
    applySuggestedLayerName(input, 'Server suggestion', true);
    expect(input.value).toBe('My chosen name');
    applySuggestedLayerName(input, 'Server suggestion', false);
    expect(input.value).toBe('Server suggestion');
});
