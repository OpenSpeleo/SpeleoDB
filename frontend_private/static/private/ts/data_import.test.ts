import type { ImportReview } from '../../../../ts-types/domain/data-import.ts';
import { startApiServer, setBrowserUrl } from '../../../../frontend_common/test/api-server.ts';
import { State } from './map_viewer/state.ts';
import { readFileSync } from 'node:fs';
import { DataImport, applySuggestedLayerName, canImportKML, renderImportCollections, renderImportError, renderImportReview } from './data_import.ts';
import * as importModel from './import_model.ts';
import * as importPresentation from './import_presentation.ts';

const template = readFileSync('frontend_private/templates/snippets/modal_data_import.html', 'utf8');
const report: ImportReview = {
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

it('retains direct model and presentation export aliases', () => {
    expect(canImportKML).toBe(importModel.canImportKML);
    expect(renderImportReview).toBe(importPresentation.renderImportReview);
    expect(renderImportCollections).toBe(importPresentation.renderImportCollections);
    expect(renderImportError).toBe(importPresentation.renderImportError);
    expect(applySuggestedLayerName).toBe(importPresentation.applySuggestedLayerName);
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
    expect((document.getElementById('kml-review-summary') as HTMLElement).textContent).toContain('2 places');
    expect((document.getElementById('kml-review-detail') as HTMLElement).textContent).toContain('1 repeated coordinate');
    expect((document.getElementById('kml-review-warnings') as HTMLElement).textContent).toContain('2 items');
    expect((document.getElementById('kml-review-warnings') as HTMLElement).textContent).not.toContain('appears flat');
    renderImportReview(report, 'overlay');
    expect((document.getElementById('kml-review-summary') as HTMLElement).textContent).toBe('One GIS layer with 3 points, 1 line, and 1 area.');
    expect((document.getElementById('kml-review-detail') as HTMLElement).textContent).toContain('All folders stay together');
    expect((document.getElementById('kml-review-warnings') as HTMLElement).textContent).toContain('<img src=x onerror=alert(1)>');
    expect((document.getElementById('kml-review-warnings') as HTMLElement).querySelector('img')).toBeNull();
    expect((document.getElementById('kml-review-warnings') as HTMLElement).textContent).not.toContain('Line placemarks');
});

it('clears stale review visibility when its file is removed', () => {
    renderImportReview(report, 'places');
    expect((document.getElementById('kml-review') as HTMLElement).hidden).toBe(false);
    renderImportReview(null, 'places');
    expect((document.getElementById('kml-review') as HTMLElement).hidden).toBe(true);
});

it('explains empty output without implying a layer will be created or switching intent', () => {
    const empty = { ...report, overlay: { feature_count: 0 }, places: { unique_coordinate_count: 0 }, warnings: [] };
    renderImportReview(empty, 'overlay');
    expect((document.getElementById('kml-review-summary') as HTMLElement).textContent).toBe('No supported map geometry found.');
    renderImportReview({ ...report, places: { unique_coordinate_count: 0 } }, 'places');
    expect((document.getElementById('kml-review-summary') as HTMLElement).textContent).toBe('No editable places found.');
    expect((document.getElementById('kml-review-detail') as HTMLElement).textContent).toContain('Choose Map Overlay');
});

it('reports skipped items once when the server includes the same compatibility warning', () => {
    renderImportReview({ ...report, warnings: [{ code: 'PLACEMARKS_NOT_IMPORTED', message: 'Repeated skipped warning', count: 2, modes: ['places'] }] }, 'places');
    expect((document.getElementById('kml-review-warnings') as HTMLElement).children).toHaveLength(1);
    expect((document.getElementById('kml-review-warnings') as HTMLElement).textContent).not.toContain('Repeated skipped warning');
});

it('retains native format tabs and starts KML with no intent or enabled file picker', () => {
    DataImport.init();
    DataImport.switchTab('kml');
    expect((document.getElementById('import-tab-kml') as HTMLElement).getAttribute('aria-selected')).toBe('true');
    expect((document.getElementById('import-content-gpx') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('kml-import-form') as HTMLElement).hidden).toBe(true);
    expect(document.querySelector<HTMLButtonElement>('[data-import-action="browse-kml"]')!.disabled).toBe(true);
    expect((document.getElementById('import-submit-button') as HTMLButtonElement).disabled).toBe(true);
    expect((document.getElementById('kml-mode-help') as HTMLElement).textContent).toContain('Placemarks');
    expect((document.getElementById('kml-mode-help') as HTMLElement).textContent).toContain('Map Overlay');
    const card = document.querySelector<HTMLButtonElement>('[data-import-mode="overlay"]')!;
    card.click();
    expect(document.querySelector<HTMLButtonElement>('[data-import-action="browse-kml"]')!.disabled).toBe(false);
    expect((document.getElementById('kml-name-field') as HTMLElement).hidden).toBe(false);
    expect((document.getElementById('kml-collection-field') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('kml-mode-help') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('kml-import-form') as HTMLElement).hidden).toBe(false);
    const change = document.querySelector<HTMLButtonElement>('[data-import-action="change-mode"]')!;
    expect(document.activeElement).toBe(change);
    change.click();
    expect((document.getElementById('kml-mode-help') as HTMLElement).hidden).toBe(false);
    expect((document.getElementById('kml-import-form') as HTMLElement).hidden).toBe(true);
    expect(document.activeElement).toBe(card);
});

it('supports keyboard format navigation and keeps the GPX collection/file form intact', () => {
    DataImport.init();
    DataImport.switchTab('kml');
    (document.getElementById('import-tab-kml') as HTMLElement).dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
    expect(document.activeElement!.id).toBe('import-tab-gpx');
    expect((document.getElementById('import-tab-gpx') as HTMLElement).getAttribute('aria-selected')).toBe('true');
    expect((document.getElementById('import-content-gpx') as HTMLElement).hidden).toBe(false);
    expect((document.getElementById('gpx-file-input') as HTMLInputElement).accept).toBe('.gpx');
    expect((document.getElementById('gpx-landmark-collection') as HTMLSelectElement)).not.toBeNull();
    expect((document.getElementById('import-submit-button') as HTMLButtonElement).textContent).toBe('Import GPX');
});

it('keeps file feedback out of the intent chooser and restores it when a mode is selected', () => {
    DataImport.init();
    DataImport.switchTab('kml');
    document.querySelector<HTMLButtonElement>('[data-import-mode="places"]')!.click();
    const drop = new Event('drop', { bubbles: true, cancelable: true });
    Object.defineProperty(drop, 'dataTransfer', {
        value: { files: [new File(['invalid'], 'not-a-kml.txt')] },
    });
    (document.getElementById('kml-drop-zone') as HTMLElement).dispatchEvent(drop);
    const error = (document.getElementById('import-error') as HTMLElement);
    expect(error.hidden).toBe(false);
    expect(error.textContent).toBe('Choose a .kml or .kmz file.');

    document.querySelector<HTMLButtonElement>('[data-import-action="change-mode"]')!.click();

    expect(error.hidden).toBe(true);
    expect((document.getElementById('import-progress') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('kml-review') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('import-submit-button') as HTMLButtonElement).hidden).toBe(true);

    document.querySelector<HTMLButtonElement>('[data-import-mode="overlay"]')!.click();

    expect(error.hidden).toBe(false);
    expect(error.textContent).toBe('Choose a .kml or .kmz file.');
});

it('exposes each intent explanation to screen-reader button navigation', () => {
    for (const mode of ['places', 'overlay']) {
        const card = document.querySelector<HTMLButtonElement>(`[data-import-mode="${mode}"]`)!;
        const description = document.getElementById(card.getAttribute('aria-describedby')!)!;
        expect(description).not.toBeNull();
        expect(description.textContent).toBe(card.querySelector('.map-import-guide-description')!.textContent);
    }
});

it('does not accumulate handlers after controller reinitialization', () => {
    DataImport.init();
    DataImport.init();
    DataImport.switchTab('gpx');
    (document.getElementById('import-tab-gpx') as HTMLElement).dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(document.activeElement!.id).toBe('import-tab-kml');
});

it('preserves a writable destination across a retry and removes revoked choices', () => {
    const collections = [
        { id: 'shared', name: '<img src=x>', can_write: true, is_personal: false },
        { id: 'personal', name: 'Personal', can_write: true, is_personal: true },
        { id: 'readonly', name: 'Read only', can_write: false, is_personal: false },
    ];
    expect(renderImportCollections(collections)).toBe(true);
    const select = (document.getElementById('kml-landmark-collection') as HTMLSelectElement);
    expect(select.value).toBe('personal');
    select.value = 'shared';
    renderImportCollections(collections);
    expect(select.value).toBe('shared');
    expect([...select.options].map(option => option.textContent)).toEqual(['Personal (Private)', '<img src=x>']);
    expect(select.querySelector('img')).toBeNull();
    renderImportCollections([collections[1]!]);
    expect(select.value).toBe('personal');
    expect(renderImportCollections([])).toBe(false);
});

it('keeps a late KML inspection error out of the GPX panel and restores it on return', () => {
    const errors = { gpx: '', kml: '' };
    renderImportError(errors, 'gpx');
    errors.kml = '<img src=x> could not be inspected.';
    renderImportError(errors, 'gpx');
    expect((document.getElementById('import-error') as HTMLElement).hidden).toBe(true);
    renderImportError(errors, 'kml');
    expect((document.getElementById('import-error') as HTMLElement).textContent).toBe(errors.kml);
    expect((document.getElementById('import-error') as HTMLElement).querySelector('img')).toBeNull();
});

it('uses a bounded server suggestion without replacing a name the user edited', () => {
    const input = (document.getElementById('kml-layer-name') as HTMLInputElement);
    applySuggestedLayerName(input, 'x'.repeat(input.maxLength + 1), false);
    expect(input.value.length).toBe(input.maxLength);
    input.value = 'My chosen name';
    applySuggestedLayerName(input, 'Server suggestion', true);
    expect(input.value).toBe('My chosen name');
    applySuggestedLayerName(input, 'Server suggestion', false);
    expect(input.value).toBe('Server suggestion');
});

function fileChange(id: string, name: string) {
    const input = document.getElementById(id) as HTMLInputElement;
    const file = new File(['file'], name);
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return file;
}

describe('DataImport HTTP and session contracts', () => {
    let server: Awaited<ReturnType<typeof startApiServer>>;
    beforeAll(async () => { server = await startApiServer(); });
    afterAll(async () => { await server.close(); });
    const collections = [{ id: 'c1', name: 'Collection', color: '#123456', collection_type: 'SHARED', user_permission_level: 3 }];
    beforeEach(() => {
        setBrowserUrl(server.origin);
        server.reset();
        server.handle(request => request.path === '/api/v2/landmark-collections/' ? { json: collections } : { json: report });
        State.landmarkCollections.clear();
    });
    afterEach(() => { State.landmarkCollections.clear(); });
    async function open(mode?: 'places' | 'overlay') {
        DataImport.init();
        DataImport.showModal();
        await vi.waitFor(() => { expect(document.querySelector<HTMLSelectElement>('#gpx-landmark-collection')!.value).toBe('c1'); });
        if (mode) { DataImport.switchTab('kml'); document.querySelector<HTMLButtonElement>(`[data-import-mode="${mode}"]`)!.click(); }
    }
    it('aborts an obsolete inspection when the file changes and ignores its late response', async () => {
        let release: (() => void) | undefined;
        server.handle(async request => {
            if (request.path === '/api/v2/landmark-collections/') return { json: collections };
            if (request.body.includes('one.kml')) {
                await new Promise<void>(resolve => { release = resolve; });
                return { json: { ...report, suggested_name: 'STALE' } };
            }
            return { json: { ...report, suggested_name: 'Current' } };
        });
        await open('places');
        fileChange('kml-file-input', 'one.kml');
        await vi.waitFor(() => { expect(server.requests).toHaveLength(2); });
        fileChange('kml-file-input', 'two.kmz');
        await vi.waitFor(() => { expect(document.querySelector<HTMLInputElement>('#kml-layer-name')!.value).toBe('Current'); });
        release?.();
        expect(document.getElementById('kml-review')!.hidden).toBe(false);
        expect(server.requests[2]!.body).toContain('filename="two.kmz"');
    });
    it('rejects malformed inspection data, scopes its error to KML, and permits retry', async () => {
        await open('places');
        server.reply({ json: {} });
        fileChange('kml-file-input', 'one.kml');
        await vi.waitFor(() => { expect(document.getElementById('import-error')!.textContent).toContain('file review could not be read'); });
        DataImport.switchTab('gpx');
        expect(document.getElementById('import-error')!.hidden).toBe(true);
        DataImport.switchTab('kml');
        server.reply({ json: report });
        await DataImport.inspectKML();
        expect(document.querySelector<HTMLButtonElement>('#import-submit-button')!.disabled).toBe(false);
    });
    it('sends GPX through PUT and blocks dismissal until server publication settles', async () => {
        await open();
        let release: (() => void) | undefined;
        server.handle(async () => {
            await new Promise<void>(resolve => { release = resolve; });
            return { json: { landmarks_created: 0, gps_tracks_created: 0, gps_track_ids: [], collection_id: 'c1', bounds: null } };
        });
        fileChange('gpx-file-input', 'route.gpx');
        const pending = DataImport.uploadGPX();
        await vi.waitFor(() => { expect(server.requests).toHaveLength(2); });
        expect(server.requests[1]).toMatchObject({ method: 'PUT', path: '/api/v2/import/gpx/' });
        expect(server.requests[1]!.body).toContain('filename="route.gpx"');
        expect(server.requests[1]!.body).toContain('name="collection"');
        DataImport.hideModal();
        DataImport.destroy();
        expect(document.getElementById('import-data-modal')!.classList.contains('hidden')).toBe(false);
        release?.();
        await pending;
        expect(document.getElementById('import-result-title')!.textContent).toBe('Nothing new to import');
    });
    it('separates successful overlay publication from a subsequent map refresh failure', async () => {
        await open('overlay');
        fileChange('kml-file-input', 'areas.kml');
        await vi.waitFor(() => { expect(document.querySelector<HTMLButtonElement>('#import-submit-button')!.disabled).toBe(false); });
        document.querySelector<HTMLInputElement>('#kml-layer-name')!.value = ' Custom ';
        server.handle(request => request.method === 'POST'
            ? { status: 201, json: { id: 'layer', name: 'Custom' } }
            : { status: 503, json: { error: 'Unavailable' } });
        await DataImport.uploadKML();
        const request = server.requests.find(item => item.method === 'POST' && item.path === '/api/v2/gis-layers/');
        expect(request!.body).toContain('filename="areas.kml"');
        expect(request!.body).toContain('Custom');
        expect(request!.body).not.toContain('name="collection"');
        expect(document.getElementById('import-result-title')!.textContent).toBe('Import complete');
        expect(document.getElementById('import-refresh-status')!.textContent).toBe('Your import is saved, but the map could not refresh.');
        expect(document.querySelector<HTMLButtonElement>('#import-show-button')!.disabled).toBe(true);
    });
    it('requires explicit file reset before retrying an ambiguous server result', async () => {
        await open();
        server.reply({ status: 503, json: { error: 'Unavailable' } });
        fileChange('gpx-file-input', 'route.gpx');
        await DataImport.uploadGPX();
        expect(document.getElementById('import-error')!.textContent).toContain('could be confirmed');
        expect(document.querySelector<HTMLButtonElement>('#import-submit-button')!.disabled).toBe(true);
        const before = server.requests.length;
        await DataImport.uploadGPX();
        expect(server.requests).toHaveLength(before);
        DataImport.clearGPXFile();
        fileChange('gpx-file-input', 'route.gpx');
        expect(document.querySelector<HTMLButtonElement>('#import-submit-button')!.disabled).toBe(false);
    });
    it('does nothing when the modal is absent', () => {
        document.body.replaceChildren();
        expect(DataImport.init()).toBeUndefined();
        expect(DataImport.showModal()).toBeUndefined();
    });
});
