import type { Mock } from 'vitest';
import type { ModuleMock } from '../../../../ts-types/testing/vitest/mocks.ts';
import type { ApplicationUrls } from '../../../../ts-types/browser/urls.d.ts';
import type { UploadOptions } from '../../../../ts-types/domain/upload.ts';
import { readFileSync } from 'node:fs';
import { DataImport, applySuggestedLayerName, canImportKML, renderImportCollections, renderImportError, renderImportReview } from './data_import.ts';
import * as importModel from './import_model.ts';
import * as importPresentation from './import_presentation.ts';

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
    renderImportReview({ ...report, warnings: [{ code: 'PLACEMARKS_NOT_IMPORTED', message: 'Repeated skipped warning', modes: ['places'] }] }, 'places');
    expect((document.getElementById('kml-review-warnings') as HTMLElement).children).toHaveLength(1);
    expect((document.getElementById('kml-review-warnings') as HTMLElement).textContent).not.toContain('Repeated skipped warning');
});

it('retains native format tabs and starts KML with no intent or enabled file picker', () => {
    DataImport.init('token');
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
    DataImport.init('token');
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
    DataImport.init('token');
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
    DataImport.init('first');
    DataImport.init('second');
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

import { uploadWithProgress as uploaded } from './map_viewer/components/upload.ts';
import { LandmarkManager as manager } from './map_viewer/landmarks/manager.ts';
import { State } from './map_viewer/state.ts';
import { refreshImportedMapData, showImportedMapData } from './map_viewer/components/map_import_navigation.ts';
vi.mock('./map_viewer/components/upload.ts', () => ({ uploadWithProgress: vi.fn() }));
vi.mock('./map_viewer/landmarks/manager.ts', () => ({ LandmarkManager: { loadCollections: vi.fn() } }));
vi.mock('./map_viewer/components/map_import_navigation.ts', () => ({ refreshImportedMapData: vi.fn(), showImportedMapData: vi.fn() }));

const settle = async () => { for (let turn = 0; turn < 6; turn++) await Promise.resolve(); };
function fileChange(id: string, name: string) {
    const input = document.getElementById(id) as HTMLInputElement;
    const file = new File(['file'], name);
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return file;
}
describe('DataImport session, inspection and submission contracts', () => {
    let abort: Mock<() => void>;
    beforeEach(() => {
        vi.clearAllMocks();
        abort = vi.fn();
        vi.mocked(uploadWithProgress).mockReturnValue({ abort });
        globalThis.Urls = {
            'api:v2:kml-kmz-inspect': () => '/inspect/', 'api:v2:kml-kmz-import': () => '/places/',
            'api:v2:gpx-import': () => '/gpx/', 'api:v2:gis-layers': () => '/layers/',
        } as ApplicationUrls;
        State.landmarkCollections.clear();
        State.landmarkCollections.set('c1', { id: 'c1', name: 'Collection', can_write: true, description: '', color: '#123456', collection_type: 'shared' });
        vi.mocked(LandmarkManager.loadCollections).mockResolvedValue([]);
    });
    afterEach(() => { Reflect.deleteProperty(globalThis, 'Urls'); State.landmarkCollections.clear(); });
    async function open(mode?: 'places' | 'overlay') {
        DataImport.init('csrf'); DataImport.showModal(); await settle();
        if (mode) { DataImport.switchTab('kml'); document.querySelector<HTMLButtonElement>(`[data-import-mode="${mode}"]`)!.click(); }
    }
    it('retains upload aliases and ignores stale inspection success after file replacement', async () => {
        expect(DataImport.uploadGPX).toBe(DataImport.uploadKML);
        await open('places');
        const first = fileChange('kml-file-input', 'one.kml');
        const firstCall = vi.mocked(uploadWithProgress).mock.calls[0]!;
        expect(firstCall[0]).toBe('/inspect/'); expect(firstCall[2].csrfToken).toBe('csrf');
        expect((firstCall[1].get('file') as File).name).toBe(first.name);
        fileChange('kml-file-input', 'two.kmz');
        expect(abort).toHaveBeenCalledTimes(1);
        firstCall[2].onSuccess!({ ...report, suggested_name: 'STALE' }); await settle();
        expect((document.getElementById('kml-review') as HTMLElement).hidden).toBe(true);
        vi.mocked(uploadWithProgress).mock.calls[1]![2].onSuccess!({ ...report, suggested_name: 'Current' }); await settle();
        expect((document.getElementById('kml-layer-name') as HTMLInputElement).value).toBe('Current');
        expect((document.getElementById('kml-review') as HTMLElement).hidden).toBe(false);
    });
    it('rejects malformed inspection results locally, keeps errors tab-scoped and permits retry', async () => {
        await open('places'); fileChange('kml-file-input', 'one.kml');
        vi.mocked(uploadWithProgress).mock.calls[0]![2].onSuccess!({}); await settle();
        expect((document.getElementById('import-error') as HTMLElement).textContent).toContain('file review could not be read');
        DataImport.switchTab('gpx'); expect((document.getElementById('import-error') as HTMLElement).hidden).toBe(true);
        DataImport.switchTab('kml');
        const retry = DataImport.inspectKML();
        vi.mocked(uploadWithProgress).mock.calls[1]![2].onSuccess!(report); await retry;
        expect((document.getElementById('import-submit-button') as HTMLButtonElement).disabled).toBe(false);
    });
    it('sends GPX through PUT, blocks dismissal while pending, then refreshes without moving until requested', async () => {
        await open(); fileChange('gpx-file-input', 'route.gpx');
        const pending = DataImport.uploadGPX();
        const [url, data, options] = vi.mocked(uploadWithProgress).mock.calls[0]!;
        expect(url).toBe('/gpx/'); expect(options).toMatchObject({ method: 'PUT', csrfToken: 'csrf' });
        expect(data.get('collection')).toBe('c1'); expect((data.get('file') as File).name).toBe('route.gpx');
        DataImport.hideModal(); DataImport.destroy();
        expect((document.getElementById('import-data-modal') as HTMLElement).classList.contains('hidden')).toBe(false);
        options.onProgress(30); expect((document.getElementById('import-progress-bar') as HTMLProgressElement).value).toBe(30);
        options.onUploaded(); expect((document.getElementById('import-progress-text') as HTMLElement).textContent).toContain('Keep this window open.');
        options.onSuccess!({ landmarks_created: 1, gps_tracks_created: 1, gps_track_ids: [12], collection_id: 'c1', bounds: [0, 0, 1, 1] });
        await pending;
        expect(refreshImportedMapData).toHaveBeenCalledWith(expect.objectContaining({ kind: 'gpx', gpsTrackIds: ['12'] }));
        expect(showImportedMapData).not.toHaveBeenCalled();
        (document.getElementById('import-show-button') as HTMLButtonElement).click(); await settle();
        expect(showImportedMapData).toHaveBeenCalledTimes(1);
        expect((document.getElementById('import-data-modal') as HTMLElement).classList.contains('hidden')).toBe(true);
    });
    it('sends overlays through POST with source_file and selected name, separating publication from refresh failure', async () => {
        await open('overlay'); fileChange('kml-file-input', 'areas.kml');
        vi.mocked(uploadWithProgress).mock.calls[0]![2].onSuccess!(report); await settle();
        (document.getElementById('kml-layer-name') as HTMLInputElement).value = ' Custom ';
        vi.mocked(refreshImportedMapData).mockRejectedValueOnce(new Error('offline'));
        const pending = DataImport.uploadKML();
        const [url, data, options] = vi.mocked(uploadWithProgress).mock.calls[1]!;
        expect(url).toBe('/layers/'); expect(options.method).toBe('POST');
        expect((data.get('source_file') as File).name).toBe('areas.kml'); expect(data.get('name')).toBe('Custom'); expect(data.has('collection')).toBe(false);
        options.onSuccess!({ id: 'layer', name: 'Custom' }); await pending;
        expect((document.getElementById('import-result-title') as HTMLElement).textContent).toBe('Import complete');
        expect((document.getElementById('import-refresh-status') as HTMLElement).textContent).toBe('Your import is saved, but the map could not refresh.');
        expect((document.getElementById('import-show-button') as HTMLButtonElement).disabled).toBe(true);
    });
    it('prevents retry after an ambiguous result until file selection is explicitly reset', async () => {
        await open(); fileChange('gpx-file-input', 'route.gpx');
        const pending = DataImport.uploadGPX();
        vi.mocked(uploadWithProgress).mock.calls[0]![2].onError!(Object.assign(new Error('lost'), { ambiguous: true, status: 0 })); await pending;
        expect((document.getElementById('import-error') as HTMLElement).textContent).toContain('could be confirmed');
        expect((document.getElementById('import-submit-button') as HTMLButtonElement).disabled).toBe(true);
        await DataImport.uploadGPX(); expect(uploadWithProgress).toHaveBeenCalledTimes(1);
        DataImport.clearGPXFile(); fileChange('gpx-file-input', 'route.gpx');
        expect((document.getElementById('import-submit-button') as HTMLButtonElement).disabled).toBe(false);
    });
    it('does nothing when modal is absent and does not retain handlers after destroy', () => {
        document.body.replaceChildren(); expect(DataImport.init('token')).toBeUndefined();
        expect(DataImport.showModal()).toBeUndefined();
    });
});

const LandmarkManager = manager as unknown as ModuleMock<typeof manager>;
type UploadFixtureOptions = Omit<UploadOptions, 'onProgress' | 'onUploaded'> & { onProgress: (percent: number) => void; onUploaded: () => void };
const uploadWithProgress = uploaded as unknown as Mock<(url: string, data: FormData, options: UploadFixtureOptions) => { abort: () => void }>;
