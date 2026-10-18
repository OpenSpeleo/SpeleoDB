import { startApiServer, setBrowserUrl, useNativeFetchBodyConstructors } from '../../../../frontend_common/test/api-server.ts';
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
        GPXImport.init();
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
    let server: Awaited<ReturnType<typeof startApiServer>>;
    let restoreConstructors: () => void;
    beforeAll(async () => { server = await startApiServer(); });
    afterAll(async () => { await server.close(); });
    function choose(file: File) {
        const input = document.getElementById('gpx-file-input')!;
        Object.defineProperty(input, 'files', { configurable: true, value: [file] });
        input.dispatchEvent(new Event('change'));
    }
    beforeEach(() => {
        restoreConstructors = useNativeFetchBodyConstructors();
        server.reset();
        setBrowserUrl(server.origin);
        document.body.innerHTML = `
            <input name="csrfmiddlewaretoken" value="csrf"><div id="import-gpx-modal"><input id="gpx-file-input" type="file">
              <div id="gpx-drop-zone"></div><div id="gpx-selected-file" class="hidden"></div>
              <div id="gpx-error-message" class="hidden"><span id="gpx-error-text"></span></div>
              <button id="gpx-upload-btn"></button><span id="gpx-upload-text"></span><span id="gpx-upload-spinner" class="hidden"></span>
              <span id="gpx-file-name"></span><span id="gpx-file-size"></span>
            </div><div id="gpx-warning-modal" class="hidden"></div>
            <div id="gpx-success-modal" class="hidden"><span id="gpx-success-message"></span></div>`;
        GPXImport.init();
        GPXImport.clearFile();
    });
    afterEach(() => { restoreConstructors(); document.body.innerHTML = ''; });

    it('settles without transport when no file is selected and preserves validation text', async () => {
        await expect(GPXImport.upload()).resolves.toBeUndefined();
        expect(server.requests).toHaveLength(0);
        choose(new File(['data'], 'wrong.txt'));
        expect(document.getElementById('gpx-error-text')!.textContent).toBe('Invalid file type. Please select a .gpx file.');
        expect((document.getElementById('gpx-upload-btn') as HTMLButtonElement).disabled).toBe(true);
    });

    it('uses multipart PUT and refreshes landmarks before tracks with exact detail', async () => {
        server.reply({ json: { landmarks_created: 2, gps_tracks_created: 1 } });
        const events: [string, unknown][] = [];
        const record = (event: Event) => { events.push([event.type, (event as CustomEvent<unknown>).detail]); };
        window.addEventListener('speleo:refresh-landmarks', record);
        window.addEventListener('speleo:refresh-gps-tracks', record);
        const file = new File(['<gpx/>'], 'route.GPX');
        choose(file);
        expect(document.getElementById('gpx-file-name')!.textContent).toBe(file.name);
        expect(document.getElementById('gpx-file-size')!.textContent).toBe('6 B');
        await expect(GPXImport.upload()).resolves.toBeUndefined();
        expect(server.requests[0]).toMatchObject({ method: 'PUT', path: '/api/v2/import/gpx/' });
        expect(server.requests[0]!.headers['x-csrftoken']).toBe('csrf');
        expect(server.requests[0]!.headers['content-type']).toContain('multipart/form-data');
        expect(server.requests[0]!.body).toContain('filename="route.GPX"');
        expect(events).toEqual([
            ['speleo:refresh-landmarks', null], ['speleo:refresh-gps-tracks', { deactivateAll: true }],
        ]);
        window.removeEventListener('speleo:refresh-landmarks', record);
        window.removeEventListener('speleo:refresh-gps-tracks', record);
        expect(document.getElementById('gpx-success-message')!.textContent).toBe('Successfully imported 1 GPS track and 2 landmarks!');
        await vi.waitFor(() => { expect(document.getElementById('gpx-success-modal')!.classList.contains('hidden')).toBe(true); }, { timeout: 3000 });
        await GPXImport.upload();
        expect(server.requests).toHaveLength(1);
    });

    it('warns on empty success and renders errors as text while resolving the upload promise', async () => {
        server.reply({ json: { landmarks_created: 0, gps_tracks_created: 0 } });
        choose(new File([''], 'empty.gpx'));
        await GPXImport.upload();
        expect(document.getElementById('gpx-warning-modal')!.classList.contains('hidden')).toBe(false);
        server.reply({ status: 400, json: { message: '<img src=x>', error: 'secondary' } });
        choose(new File([''], 'retry.gpx'));
        await expect(GPXImport.upload()).resolves.toBeUndefined();
        expect(document.getElementById('gpx-error-text')!.textContent).toBe('<img src=x>');
        expect(document.querySelector('#gpx-error-text img')).toBeNull();
        expect((document.getElementById('gpx-upload-btn') as HTMLButtonElement).disabled).toBe(false);
        expect(document.getElementById('gpx-upload-text')!.textContent).toBe('Import GPX');
    });

    it('closes both dialogs after repeated initialization on Escape', () => {
        GPXImport.init();
        GPXImport.init();
        document.getElementById('gpx-warning-modal')!.classList.remove('hidden');
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(document.getElementById('import-gpx-modal')!.classList.contains('hidden')).toBe(true);
        expect(document.getElementById('gpx-warning-modal')!.classList.contains('hidden')).toBe(true);
    });
});
