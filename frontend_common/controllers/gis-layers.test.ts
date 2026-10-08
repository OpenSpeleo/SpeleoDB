import type { Mock } from 'vitest';
import type { ApplicationUrls } from '../../ts-types/browser/urls.d.ts';
import type { GISListRecord, GISListContext, GISUploadListContext, GISUploadErrorDetails } from '../../ts-types/controllers/gis-lists.ts';
import type { TaggedListApi, TaggedListOptions } from '../../ts-types/domain/forms/tagged-list.ts';
import { buildGISLayerListMarkup, renderGISLayerUploadError } from './gis-layers.ts';

function layer(overrides: Partial<GISListRecord> = {}) {
    return {
        id: '11111111-1111-4111-8111-111111111111', name: 'Protected Areas',
        description: 'Boundaries', color: '#377eb8', created_by: 'creator@example.com',
        user_permission_level_label: 'READ_ONLY', can_write: false, can_delete: false,
        source_format: 'KMZ', modified_date: '2026-08-29T12:00:00Z', ...overrides,
    };
}

beforeEach(() => {
    globalThis.Urls = {
        'api:v2:gis-layer-source': id => `/api/v2/gis-layers/${id}/source/`,
        'private:gis_layer_details': id => `/private/gis-layer/${id}/`,
    } as ApplicationUrls;
});

describe('GIS Layer upload error display', () => {
    let errorElement: HTMLParagraphElement;

    beforeEach(() => {
        errorElement = document.createElement('p');
    });

    it('shows the KML source line and parser location', () => {
        renderGISLayerUploadError(errorElement, 'The KML document is not well-formed XML.', {
            line: 12, column: 8, source_line: '    </Placemark',
        });

        expect(errorElement.textContent).toContain('The KML document is not well-formed XML.');
        expect(errorElement.querySelector('span')!.textContent).toBe('Line 12, column 8');
        expect(errorElement.querySelector('code')!.textContent).toBe('    </Placemark');
        expect(errorElement.querySelector('code')!.classList.contains('whitespace-pre-wrap')).toBe(true);
    });

    it('renders malicious KML and error messages as text', () => {
        const sourceLine = '<img src=x onerror="alert(1)"><script>alert(1)</script>';
        const message = '<svg onload="alert(1)">Invalid XML</svg>';
        renderGISLayerUploadError(errorElement, message, {
            line: 2, column: 1, source_line: sourceLine,
        });

        expect(errorElement.textContent).toContain(message);
        expect(errorElement.querySelector('code')!.textContent).toBe(sourceLine);
        expect(errorElement.querySelector('img,script,svg,[onerror],[onload]')!).toBeNull();
    });

    it('shows a line when a column or source snippet is unavailable', () => {
        renderGISLayerUploadError(errorElement, 'Invalid XML.', { line: 4 });
        expect(errorElement.querySelector('span')!.textContent).toBe('Line 4');
        expect(errorElement.querySelector('code')!).toBeNull();
    });

    it.each([undefined, null, {}, { line: 0 }, { line: '<img src=x>' }])(
        'keeps generic errors readable when source details are unavailable: %j', details => {
            renderGISLayerUploadError(errorElement, 'Upload failed.', details as GISUploadErrorDetails | null | undefined);
            expect(errorElement.textContent).toBe('Upload failed.');
            expect(errorElement.childElementCount).toBe(0);
        },
    );

    it('clears previous source details when another upload fails', () => {
        renderGISLayerUploadError(errorElement, 'Invalid XML.', {
            line: 2, column: 9, source_line: '<kml>',
        });
        renderGISLayerUploadError(errorElement, 'The upload was interrupted. Try again.');
        expect(errorElement.textContent).toBe('The upload was interrupted. Try again.');
        expect(errorElement.childElementCount).toBe(0);
    });
});
afterEach(() => { Reflect.deleteProperty(globalThis, 'Urls'); });

describe('GIS Layer management markup', () => {
    it('shows source download and the standard Open control', () => {
        const { tableHtml, cardsHtml } = buildGISLayerListMarkup(
            [layer()],
            '/static/private/media/right_arrow.svg',
        );
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>${cardsHtml}`;
        expect(document.body.textContent).toContain('Protected Areas');
        expect(document.body.textContent).toContain('KMZ');
        expect(document.querySelectorAll('a[href$="/source/"]')).toHaveLength(2);
        expect(document.querySelectorAll('a[href$="111111111111/"]')).toHaveLength(2);
        expect(document.querySelectorAll('img[src$="right_arrow.svg"]')).toHaveLength(2);
        expect(document.querySelectorAll('.btn-edit-gis-layer')).toHaveLength(0);
        expect(document.querySelectorAll('.btn-delete-gis-layer')).toHaveLength(0);
        expect(document.querySelector<HTMLElement>('.bg-pastel-beige')!).not.toBeNull();
    });

    it('does not expose inline mutations for writers or administrators', () => {
        const { tableHtml } = buildGISLayerListMarkup([layer({
            can_write: true,
            can_delete: true,
        })], '/static/private/media/right_arrow.svg');
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>`;
        expect(document.querySelector<HTMLElement>('.btn-edit-gis-layer')!).toBeNull();
        expect(document.querySelector<HTMLElement>('.btn-delete-gis-layer')!).toBeNull();
    });

    it('escapes names, descriptions, creators, IDs, and validates colors', () => {
        const { tableHtml } = buildGISLayerListMarkup([layer({
            id: 'bad\" onmouseover=\"alert(1)', name: '<img src=x onerror=alert(1)>',
            description: '<script>alert(1)</script>',
            created_by: '<svg/onload=alert(1)>', color: 'red;background:url(evil)', can_write: true,
        })]);
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>`;
        expect(document.querySelector<HTMLElement>('script,[onmouseover],[onload]')!).toBeNull();
        expect(document.querySelectorAll('img')).toHaveLength(1);
        expect(document.querySelector<HTMLElement>('svg')!).not.toBeNull();
        expect(document.body.textContent).toContain('<img src=x onerror=alert(1)>');
        expect(document.querySelector<HTMLElement>('.w-3.h-3')!.style.backgroundColor).toBe('rgb(148, 163, 184)');
    });

    it('sanitizes action URLs while retaining trusted static icons', () => {
        globalThis.Urls['api:v2:gis-layer-source'] = () => 'javascript:alert(1)';
        globalThis.Urls['private:gis_layer_details'] = () => 'data:text/html,<script>alert(1)</script>';
        const { tableHtml } = buildGISLayerListMarkup([layer()]);
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>`;
        expect([...document.querySelectorAll('a')].every(anchor => !/^(javascript|data):/i.test(anchor.getAttribute('href')!))).toBe(true);
        expect(document.querySelectorAll('svg')).not.toHaveLength(0);
    });

    it('renders source format and an empty state', () => {
        const emptyMarkup = buildGISLayerListMarkup([]);
        expect(emptyMarkup.tableHtml).toContain('No GIS Layers yet');
        expect(emptyMarkup.cardsHtml).toContain('No GIS Layers yet');
        const { tableHtml, cardsHtml } = buildGISLayerListMarkup([
            layer({ source_format: 'GEOJSON' }),
        ]);
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>${cardsHtml}`;
        expect(document.body.textContent).toContain('GEOJSON');
        expect(document.body.textContent).not.toContain('features');
    });
});

import { readFileSync } from 'node:fs';
import { init as initialize } from './gis-layers.ts';
import { attachTaggedEntityList } from '../../frontend_private/static/private/ts/forms/tagged_entity_list.ts';
import { initColorPicker } from '../../frontend_private/static/private/ts/color-picker.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';
vi.mock('../../frontend_private/static/private/ts/forms/tagged_entity_list.ts', () => ({ attachTaggedEntityList: vi.fn() }));
vi.mock('../../frontend_private/static/private/ts/color-picker.ts', () => ({ initColorPicker: vi.fn() }));
vi.mock('../../frontend_private/static/private/ts/forms/modals.ts', () => ({ FormModals: { showSuccess: vi.fn() } }));
const jquery = readFileSync('frontend_public/static/ts/vendors/jquery-3.7.1.js', 'utf8');
beforeAll(() => { (0, eval)(jquery); });
class UploadRequest extends EventTarget {
    static DONE = 4;
    static requests: UploadRequest[] = [];
    upload = new EventTarget();
    readyState = 1;
    status = 0;
    responseText = '';
    open = vi.fn<(method: string, url: string) => void>();
    setRequestHeader = vi.fn<(name: string, value: string) => void>();
    send = vi.fn<(data: FormData) => void>();
    constructor() { super(); UploadRequest.requests.push(this); }
}

describe('GIS Layer initialization and upload lifecycle', () => {
    let listeners: [EventTarget, string, EventListenerOrEventListenerObject | null][];
    let reload: Mock<() => void>;
    let color: Mock<(color: string) => void>;
    const context = { listEndpoint: '/layers/', csrfToken: 'csrf', openIconUrl: '/open.svg' };
    function element<T extends HTMLElement = HTMLElement>(id: string) { return document.getElementById('upload-layer-' + id) as T; }
    function select(name = 'boundary.geojson') {
        const file = new File(['{}'], name, { type: 'application/json' });
        Object.defineProperty(element('file-input'), 'files', { configurable: true, value: [file] });
        element('file-input').dispatchEvent(new Event('change'));
        return file;
    }
    function submit() { element('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); }
    beforeEach(() => {
        vi.clearAllMocks();
        reload = vi.fn(); color = vi.fn(); listeners = [];
        attachment.mockReturnValue({ reload, openEditModal: vi.fn(), openDeleteModal: vi.fn() });
        vi.mocked(initColorPicker).mockReturnValue(color);
        for (const target of [document, window] as EventTarget[]) {
            const add = target.addEventListener.bind(target);
            vi.spyOn(target, 'addEventListener').mockImplementation((name, listener, options) => { listeners.push([target, name, listener]); add(name, listener, options); });
        }
        UploadRequest.requests = [];
        vi.stubGlobal('XMLHttpRequest', UploadRequest);
        document.body.innerHTML = `
            <table><tbody id="gis-layers-table-body"></tbody></table><div id="gis-layers-cards-container"></div>
            <button id="upload-layer-open"></button><div id="upload-layer-modal" class="hidden"><form id="upload-layer-form">
            <input id="upload-layer-file-input" type="file"><input id="upload-layer-name"><input id="upload-layer-description" value=" description "><input id="upload-layer-color-value" value="#123456">
            <div id="upload-layer-drop-zone"></div><div id="upload-layer-selected-file"></div><span id="upload-layer-file-name"></span><span id="upload-layer-file-size"></span>
            <div id="upload-layer-error-message"><span id="upload-layer-error-text"></span></div><div id="upload-layer-progress-wrap"><span id="upload-layer-progress"></span><span id="upload-layer-progress-value"></span><span id="upload-layer-progress-label"></span></div>
            <button id="upload-layer-button" type="submit"><span id="upload-layer-button-text"></span><span id="upload-layer-spinner"></span></button>
            <button type="button" data-layer-upload-action="hide"></button><button type="button" data-layer-upload-action="browse"></button><button type="button" data-layer-upload-action="clear"></button></form></div>`;
    });
    afterEach(() => {
        for (const [target, name, listener] of listeners) target.removeEventListener(name, listener);
        vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = '';
    });
    it('attaches immediately, renders both lists and reloads for the window event', () => {
        expect(init(context)).toBeUndefined();
        expect(vi.mocked(initColorPicker).mock.invocationCallOrder[0]!).toBeLessThan(attachment.mock.invocationCallOrder[0]!);
        const options = attachment.mock.calls[0]![0];
        expect(options).toMatchObject({ listEndpoint: '/layers/', entityLabel: 'GIS Layer', loadFailedMessage: 'Error loading GIS Layers' });
        options.renderList!([layer()], {} as TaggedListApi);
        expect(document.querySelectorAll('img[src="/open.svg"]')).toHaveLength(2);
        window.dispatchEvent(new Event('speleo:refresh-gis-layers'));
        expect(reload).toHaveBeenCalledTimes(1);
    });
    it('keeps original multipart fields and upload/processing progress, locks dismissal then reloads on success', () => {
        init(context); element('open').click();
        expect(color).toHaveBeenCalledWith('#377eb8');
        select(); submit();
        const request = UploadRequest.requests[0]!;
        expect(request.open).toHaveBeenCalledWith('POST', '/layers/');
        expect(request.setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'csrf');
        const data = request.send.mock.calls[0]![0];
        expect((data.get('source_file') as File).name).toBe('boundary.geojson');
        expect(data.get('name')).toBe('boundary'); expect(data.get('description')).toBe('description'); expect(data.get('color')).toBe('#123456');
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(element('modal').classList.contains('hidden')).toBe(false);
        expect(document.querySelector<HTMLButtonElement>('[data-layer-upload-action="hide"]')!.disabled).toBe(true);
        request.upload.dispatchEvent(new ProgressEvent('progress', { lengthComputable: true, loaded: 1, total: 4 }));
        expect(element('progress-value').textContent).toBe('25%');
        request.upload.dispatchEvent(new Event('load'));
        expect(element('progress-label').textContent).toBe('Saving layer…');
        request.status = 201; request.readyState = 4; request.dispatchEvent(new Event('load'));
        expect(element('modal').classList.contains('hidden')).toBe(true);
        expect(FormModals.showSuccess).toHaveBeenCalledWith('GIS Layer uploaded successfully!');
        expect(reload).toHaveBeenCalledTimes(1);
    });
    it.each(['load', 'error', 'abort'])('restores controls after %s failure while retaining selected file', event => {
        init(context); element('open').click(); select('boundary.kml'); submit();
        const request = UploadRequest.requests[0]!;
        request.upload.dispatchEvent(new Event('load'));
        expect(element('progress-label').textContent).toBe('Preparing map data…');
        request.status = 400; request.readyState = 4; request.responseText = JSON.stringify({ code: 'XML_INVALID', error: 'Invalid XML', details: { line: 3, source_line: '<bad>' } });
        request.dispatchEvent(new Event(event));
        expect(element<HTMLButtonElement>('button').disabled).toBe(false);
        expect(document.querySelector<HTMLButtonElement>('[data-layer-upload-action="hide"]')!.disabled).toBe(false);
        expect(element('file-name').textContent).toBe('boundary.kml');
        if (event === 'load') expect(element('error-text').textContent).toContain('Invalid XMLLine 3<bad>');
        if (event === 'error') expect(element('error-text').textContent).toBe('The upload was interrupted. Try again.');
        expect(reload).not.toHaveBeenCalled();
    });
    it('validates selection and name, retains duplicate wiring and required DOM failures', () => {
        init(context); init(context); select('bad.exe');
        expect(element('error-text').textContent).toContain('Choose KML');
        submit(); expect(UploadRequest.requests).toHaveLength(0);
        select(); element<HTMLInputElement>('name').value = ' '; submit();
        expect(element('error-text').textContent).toBe('Please enter a layer name.');
        window.dispatchEvent(new Event('speleo:refresh-gis-layers')); expect(reload).toHaveBeenCalledTimes(2);
        expect(() => init()).toThrow(TypeError);
        document.body.innerHTML = '';
        expect(() => init(context)).toThrow(TypeError);
    });
});

function init(context?: unknown) { return initialize(context as GISUploadListContext); }
const attachment = vi.mocked(attachTaggedEntityList) as unknown as Mock<(options: TaggedListOptions<GISListRecord>) => TaggedListApi>;
