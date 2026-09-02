const mocks = vi.hoisted(() => ({
    reload: vi.fn(),
    showSuccess: vi.fn(),
}));

vi.mock('../../frontend_private/static/private/js/color-picker.js', () => ({
    initColorPicker: vi.fn(() => vi.fn()),
}));
vi.mock('../../frontend_private/static/private/js/forms/tagged_entity_list.js', () => ({
    attachTaggedEntityList: vi.fn(() => ({
        reload: mocks.reload,
        openEditModal: vi.fn(),
        openDeleteModal: vi.fn(),
    })),
}));
vi.mock('../../frontend_private/static/private/js/forms/modals.js', () => ({
    FormModals: { showError: vi.fn(), showSuccess: mocks.showSuccess },
}));

import { init } from './gis-layers.js';

class XMLHttpRequestMock {
    static DONE = 4;

    constructor() {
        this.listeners = {};
        this.uploadListeners = {};
        this.upload = { addEventListener: (type, handler) => { this.uploadListeners[type] = handler; } };
        this.readyState = 1;
        XMLHttpRequestMock.instance = this;
    }

    open() {}
    setRequestHeader() {}
    addEventListener(type, handler) { this.listeners[type] = handler; }
    send(body) { this.sentBody = body; }
}

function uploadDOM() {
    document.body.innerHTML = `
        <button id="upload-layer-open"></button>
        <div id="upload-layer-modal" class="hidden">
            <button type="button" data-layer-upload-action="hide">Close</button>
            <form id="upload-layer-form">
                <input id="upload-layer-file-input" type="file">
                <div id="upload-layer-drop-zone"></div>
                <div id="upload-layer-selected-file" class="hidden"></div>
                <span id="upload-layer-file-name"></span><span id="upload-layer-file-size"></span>
                <input id="upload-layer-name"><textarea id="upload-layer-description"></textarea>
                <input id="upload-layer-color-value" value="#377eb8">
                <div id="upload-layer-progress-wrap" class="hidden"></div>
                <div id="upload-layer-progress"></div><span id="upload-layer-progress-value"></span><span id="upload-layer-progress-label"></span>
                <div id="upload-layer-error-message" class="hidden"><span id="upload-layer-error-text"></span></div>
                <span id="upload-layer-spinner" class="hidden"></span><span id="upload-layer-button-text"></span>
                <button type="button" data-layer-upload-action="hide">Cancel</button>
                <button id="upload-layer-button" type="submit"></button>
            </form>
        </div>`;
}

describe('GIS Layer synchronous upload', () => {
    beforeEach(() => {
        mocks.reload.mockClear();
        mocks.showSuccess.mockClear();
        uploadDOM();
        globalThis.XMLHttpRequest = XMLHttpRequestMock;
        init({ csrfToken: 'token', listEndpoint: '/api/v2/gis-layers/' });
    });

    afterEach(() => {
        delete globalThis.XMLHttpRequest;
        document.body.innerHTML = '';
    });

    it('reloads the management list exactly once after a successful upload', () => {
        document.getElementById('upload-layer-open').click();
        const dropEvent = new Event('drop', { bubbles: true, cancelable: true });
        Object.defineProperty(dropEvent, 'dataTransfer', {
            value: { files: [new File(['{}'], 'layer.geojson', { type: 'application/geo+json' })] },
        });
        document.getElementById('upload-layer-drop-zone').dispatchEvent(dropEvent);
        document.getElementById('upload-layer-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        XMLHttpRequestMock.instance.status = 201;
        XMLHttpRequestMock.instance.readyState = XMLHttpRequestMock.DONE;
        XMLHttpRequestMock.instance.listeners.load();

        expect(mocks.reload).toHaveBeenCalledTimes(1);
        expect(mocks.showSuccess).toHaveBeenCalledWith('GIS Layer uploaded successfully!');
    });

    it('shows that GeoJSON is being saved without claiming it is prepared', () => {
        document.getElementById('upload-layer-open').click();
        const dropEvent = new Event('drop', { bubbles: true, cancelable: true });
        Object.defineProperty(dropEvent, 'dataTransfer', {
            value: { files: [new File(['{}'], 'layer.geojson', { type: 'application/geo+json' })] },
        });
        document.getElementById('upload-layer-drop-zone').dispatchEvent(dropEvent);
        document.getElementById('upload-layer-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        XMLHttpRequestMock.instance.uploadListeners.load();

        expect(document.getElementById('upload-layer-progress-label').textContent).toBe('Saving layer…');
        expect(document.getElementById('upload-layer-button-text').textContent).toBe('Saving…');
    });

    it('sends GeoJSON immediately without reading or transforming it in JavaScript', () => {
        document.getElementById('upload-layer-open').click();
        const file = new File(['{"type":"FeatureCollection","features":[]}'], 'layer.geojson', {
            type: 'application/geo+json',
        });
        const dropEvent = new Event('drop', { bubbles: true, cancelable: true });
        Object.defineProperty(dropEvent, 'dataTransfer', { value: { files: [file] } });
        document.getElementById('upload-layer-drop-zone').dispatchEvent(dropEvent);

        document.getElementById('upload-layer-form').dispatchEvent(new Event('submit', {
            bubbles: true,
            cancelable: true,
        }));

        expect(XMLHttpRequestMock.instance.sentBody).toBeInstanceOf(FormData);
        const sentFile = XMLHttpRequestMock.instance.sentBody.get('source_file');
        expect(sentFile.name).toBe(file.name);
        expect(sentFile.size).toBe(file.size);
        expect(document.getElementById('upload-layer-progress-label').textContent).toBe('Uploading…');
    });

    it('does not dismiss the upload modal when its backdrop is clicked', () => {
        document.getElementById('upload-layer-open').click();
        const modal = document.getElementById('upload-layer-modal');

        modal.click();

        expect(modal.classList.contains('hidden')).toBe(false);
    });

    it('cannot be dismissed after the upload request starts', () => {
        document.getElementById('upload-layer-open').click();
        const modal = document.getElementById('upload-layer-modal');
        const dismissButtons = document.querySelectorAll('[data-layer-upload-action="hide"]');
        const dropEvent = new Event('drop', { bubbles: true, cancelable: true });
        Object.defineProperty(dropEvent, 'dataTransfer', {
            value: { files: [new File(['{}'], 'layer.geojson', { type: 'application/geo+json' })] },
        });
        document.getElementById('upload-layer-drop-zone').dispatchEvent(dropEvent);
        document.getElementById('upload-layer-form').dispatchEvent(new Event('submit', {
            bubbles: true,
            cancelable: true,
        }));

        expect([...dismissButtons].every(button => button.disabled)).toBe(true);
        dismissButtons[0].click();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

        expect(modal.classList.contains('hidden')).toBe(false);
        expect(XMLHttpRequestMock.instance.readyState).toBe(1);
    });

    it('shows the server processor error for a supported but invalid file', () => {
        document.getElementById('upload-layer-open').click();
        const dropEvent = new Event('drop', { bubbles: true, cancelable: true });
        Object.defineProperty(dropEvent, 'dataTransfer', {
            value: {
                files: [new File(['{}'], 'broken.topojson', { type: 'application/topo+json' })],
            },
        });
        document.getElementById('upload-layer-drop-zone').dispatchEvent(dropEvent);
        document.getElementById('upload-layer-form').dispatchEvent(new Event('submit', {
            bubbles: true,
            cancelable: true,
        }));
        XMLHttpRequestMock.instance.status = 422;
        XMLHttpRequestMock.instance.responseText = JSON.stringify({
            error: 'The uploaded file is not a TopoJSON topology.',
            code: 'TOPOJSON_INVALID',
        });

        XMLHttpRequestMock.instance.listeners.load();

        expect(document.getElementById('upload-layer-error-text').textContent)
            .toBe('The uploaded file is not a TopoJSON topology.');
    });
});
