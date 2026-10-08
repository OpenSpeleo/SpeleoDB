import { GPXImport } from './gpx_import.ts';

describe('GPX import modal dismissal', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div id="import-gpx-modal">
                <input id="gpx-file-input" type="file">
                <div id="gpx-drop-zone"></div>
                <div id="gpx-selected-file" class="hidden"></div>
                <div id="gpx-error-message" class="hidden"></div>
                <button id="gpx-upload-btn"></button>
                <span id="gpx-upload-text"></span>
                <span id="gpx-upload-spinner"></span>
            </div>
            <div id="gpx-warning-modal" class="hidden"></div>`;
        GPXImport.init('csrf-token');
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('does not dismiss when the backdrop is clicked', () => {
        const modal = document.getElementById('import-gpx-modal')!;

        modal.click();

        expect(modal.classList.contains('hidden')).toBe(false);
    });
});

describe('GPX import transport and lifecycle', () => {
    function choose(file: File) {
        const input = document.getElementById('gpx-file-input')!;
        Object.defineProperty(input, 'files', { configurable: true, value: [file] });
        input.dispatchEvent(new Event('change'));
    }
    beforeEach(() => {
        vi.useFakeTimers();
        document.body.innerHTML = `
            <div id="import-gpx-modal"><input id="gpx-file-input" type="file">
              <div id="gpx-drop-zone"></div><div id="gpx-selected-file" class="hidden"></div>
              <div id="gpx-error-message" class="hidden"><span id="gpx-error-text"></span></div>
              <button id="gpx-upload-btn"></button><span id="gpx-upload-text"></span><span id="gpx-upload-spinner" class="hidden"></span>
              <span id="gpx-file-name"></span><span id="gpx-file-size"></span>
            </div><div id="gpx-warning-modal" class="hidden"></div>
            <div id="gpx-success-modal" class="hidden"><span id="gpx-success-message"></span></div>`;
        GPXImport.init('csrf');
        GPXImport.clearFile();
        vi.stubGlobal('Urls', { 'api:v2:gpx-import': () => '/gpx/' });
    });
    afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = ''; });

    it('settles without transport when no file is selected and preserves validation text', async () => {
        const fetcher = vi.fn();
        vi.stubGlobal('fetch', fetcher);
        await expect(GPXImport.upload()).resolves.toBeUndefined();
        expect(fetcher).not.toHaveBeenCalled();
        choose(new File(['data'], 'wrong.txt'));
        expect(document.getElementById('gpx-error-text')!.textContent).toBe('Invalid file type. Please select a .gpx file.');
        expect((document.getElementById('gpx-upload-btn') as HTMLButtonElement).disabled).toBe(true);
    });

    it('uses multipart PUT and refreshes landmarks before tracks with exact detail', async () => {
        const fetcher = vi.fn<(url: string, options: RequestInit) => Promise<{ ok: boolean; json(): Promise<unknown> }>>().mockResolvedValue({ ok: true, json: async () => ({ landmarks_created: 2, gps_tracks_created: 1 }) });
        vi.stubGlobal('fetch', fetcher);
        const dispatch = vi.spyOn(window, 'dispatchEvent');
        const file = new File(['<gpx/>'], 'route.GPX');
        choose(file);
        expect(document.getElementById('gpx-file-name')!.textContent).toBe(file.name);
        expect(document.getElementById('gpx-file-size')!.textContent).toBe('6 B');
        await expect(GPXImport.upload()).resolves.toBeUndefined();
        const [url, options] = fetcher.mock.calls[0]!;
        expect(url).toBe('/gpx/');
        expect(options).toMatchObject({ method: 'PUT', credentials: 'same-origin', redirect: 'follow' });
        expect((options.headers as Headers).get('X-CSRFToken')).toBe('csrf');
        expect((options.headers as Headers).has('Content-Type')).toBe(false);
        expect(((options.body as FormData).get('file') as File).name).toBe(file.name);
        expect(dispatch.mock.calls.map(([event]) => [event.type, (event as CustomEvent<unknown>).detail])).toEqual([
            ['speleo:refresh-landmarks', null], ['speleo:refresh-gps-tracks', { deactivateAll: true }],
        ]);
        expect(document.getElementById('gpx-success-message')!.textContent).toBe('Successfully imported 1 GPS track and 2 landmarks!');
        vi.advanceTimersByTime(2500);
        expect(document.getElementById('gpx-success-modal')!.classList.contains('hidden')).toBe(true);
        await GPXImport.upload();
        expect(fetcher).toHaveBeenCalledTimes(1);
    });

    it('warns on empty success and renders errors as text while resolving the upload promise', async () => {
        const fetcher = vi.fn<(url: string, options: RequestInit) => Promise<{ ok: boolean; json(): Promise<unknown> }>>().mockResolvedValue({ ok: true, json: async () => ({}) });
        vi.stubGlobal('fetch', fetcher);
        choose(new File([''], 'empty.gpx'));
        await GPXImport.upload();
        expect(document.getElementById('gpx-warning-modal')!.classList.contains('hidden')).toBe(false);
        fetcher.mockResolvedValue({ ok: false, json: async () => ({ message: '<img src=x>', error: 'secondary' }) });
        vi.spyOn(console, 'error').mockImplementation(() => {});
        choose(new File([''], 'retry.gpx'));
        await expect(GPXImport.upload()).resolves.toBeUndefined();
        expect(document.getElementById('gpx-error-text')!.textContent).toBe('<img src=x>');
        expect(document.querySelector('#gpx-error-text img')).toBeNull();
        expect((document.getElementById('gpx-upload-btn') as HTMLButtonElement).disabled).toBe(false);
        expect(document.getElementById('gpx-upload-text')!.textContent).toBe('Import GPX');
    });

    it('retains duplicate listener registration and closes both dialogs on Escape', () => {
        const listener = vi.spyOn(document, 'addEventListener');
        GPXImport.init('next');
        GPXImport.init('last');
        expect(listener.mock.calls.filter(([event]) => event === 'keydown')).toHaveLength(2);
        document.getElementById('gpx-warning-modal')!.classList.remove('hidden');
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(document.getElementById('import-gpx-modal')!.classList.contains('hidden')).toBe(true);
        expect(document.getElementById('gpx-warning-modal')!.classList.contains('hidden')).toBe(true);
    });
});
