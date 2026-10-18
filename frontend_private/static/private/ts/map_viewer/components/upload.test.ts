import { v2GisLayersCreateWithFormData } from '@speleodb/api';
import { apiData, webApiOptions } from '../../../../../../frontend_common/api/client.ts';
import { startApiServer, setBrowserUrl } from '../../../../../../frontend_common/test/api-server.ts';
import type { UploadOperation } from '../../../../../../ts-types/domain/upload.ts';
import { uploadWithProgress, createProgressBarHTML, getUploadErrorMessage, UploadProgressController } from './upload.ts';

// Real transport, cancellation and promise results run against Django in
// speleodb/api/v2/tests/test_frontend_upload_integration.py.

describe('getUploadErrorMessage', () => {
    it('preserves existing messages and exposes serializer field errors', () => {
        expect(getUploadErrorMessage({ error: 'Invalid file' })).toBe('Invalid file');
        expect(getUploadErrorMessage({ errors: { name: ['Keep the name shorter.'], source_file: ['Choose a KML file.'] } }))
            .toBe('name: Keep the name shorter. source file: Choose a KML file.');
    });

    it('uses a safe fallback for malformed payloads', () => {
        expect(getUploadErrorMessage(null)).toBe('Upload failed');
        expect(getUploadErrorMessage({ detail: {}, errors: { field: { nested: true } } })).toBe('Upload failed');
    });
});

describe('createProgressBarHTML', () => {
    it('returns HTML with default ID prefix', () => {
        const html = createProgressBarHTML();

        expect(html).toContain('id="upload-progress-container"');
        expect(html).toContain('id="upload-progress-bar"');
        expect(html).toContain('id="upload-progress-percent"');
        expect(html).toContain('id="upload-progress-status"');
        expect(html).toContain('id="upload-progress-size"');
        expect(html).toContain('id="upload-progress-cancel"');
    });

    it('uses custom ID prefix', () => {
        const html = createProgressBarHTML('my-upload');

        expect(html).toContain('id="my-upload-container"');
        expect(html).toContain('id="my-upload-bar"');
        expect(html).toContain('id="my-upload-percent"');
        expect(html).toContain('id="my-upload-size"');
    });

    it('starts hidden', () => {
        const html = createProgressBarHTML();

        expect(html).toContain('class="hidden');
    });

    it('includes cancel button', () => {
        const html = createProgressBarHTML('test');

        expect(html).toContain('Cancel Upload');
        expect(html).toContain('id="test-cancel"');
    });
});

describe('UploadProgressController', () => {
    let controller: UploadProgressController;

    beforeEach(() => {
        document.body.innerHTML = createProgressBarHTML('test');
        controller = new UploadProgressController('test');
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    describe('show', () => {
        it('removes hidden class from container', () => {
            controller.show();

            expect(document.getElementById('test-container')!.classList.contains('hidden')).toBe(false);
        });

        it('resets progress to 0%', () => {
            controller.show();

            expect(document.getElementById('test-percent')!.textContent).toBe('0%');
        });

        it('wires cancel button', () => {
            controller.show();
            const cancelBtn = document.getElementById('test-cancel')!;

            expect(cancelBtn.onclick).toBeTypeOf('function');
        });
    });

    describe('hide', () => {
        it('adds hidden class to container', () => {
            controller.show();
            controller.hide();

            expect(document.getElementById('test-container')!.classList.contains('hidden')).toBe(true);
        });
    });

    describe('update', () => {
        beforeEach(() => controller.show());

        it('updates progress bar width', () => {
            controller.update(50, 512, 1024);

            expect(document.getElementById('test-bar')!.style.width).toBe('50%');
        });

        it('updates percent text', () => {
            controller.update(75, 768, 1024);

            expect(document.getElementById('test-percent')!.textContent).toBe('75%');
        });

        it('updates size display with human-readable values', () => {
            controller.update(50, 512, 1024);

            expect(document.getElementById('test-size')!.textContent).toBe('512 B / 1 KB');
        });

        it('shows "Processing..." at 100%', () => {
            controller.update(100, 1024, 1024);

            expect(document.getElementById('test-status')!.textContent).toBe('Processing...');
        });

        it('shows "Uploading..." below 100%', () => {
            controller.update(50, 512, 1024);

            expect(document.getElementById('test-status')!.textContent).toBe('Uploading...');
        });
    });

    describe('complete', () => {
        beforeEach(() => controller.show());

        it('shows completion message', () => {
            controller.complete();

            expect(document.getElementById('test-status')!.innerHTML).toContain('Upload complete!');
        });

        it('hides cancel button', () => {
            controller.complete();

            expect(document.getElementById('test-cancel')!.classList.contains('hidden')).toBe(true);
        });
    });

    describe('error', () => {
        beforeEach(() => controller.show());

        it('shows custom error message', () => {
            controller.error('Something went wrong');

            expect(document.getElementById('test-status')!.innerHTML).toContain('Something went wrong');
        });

        it('uses default message when none provided', () => {
            controller.error();

            expect(document.getElementById('test-status')!.innerHTML).toContain('Upload failed');
        });

        it('changes bar color to red', () => {
            controller.error('Error');

            const bar = document.getElementById('test-bar')!;
            expect(bar.classList.contains('bg-red-500')).toBe(true);
            expect(bar.classList.contains('from-blue-500')).toBe(false);
        });

        it('hides cancel button', () => {
            controller.error('Error');

            expect(document.getElementById('test-cancel')!.classList.contains('hidden')).toBe(true);
        });
    });

    it('handles cancellation without an active request', () => {
        controller.show();
        controller.cancel();

        expect(controller.request).toBeNull();
        expect(document.getElementById('test-container')!.classList.contains('hidden')).toBe(true);
    });

    it('renders error text without interpreting uploaded data as HTML', () => {
        controller.error('<img src=x onerror=alert(1)>');

        expect(document.getElementById('test-status')!.querySelector<HTMLElement>('img')!).toBeNull();
        expect(document.getElementById('test-status')!.textContent).toContain('<img src=x onerror=alert(1)>');
    });
});

describe('upload generated operation boundary', () => {
    let server: Awaited<ReturnType<typeof startApiServer>>;
    beforeAll(async () => { server = await startApiServer(); });
    beforeEach(() => {
        server.reset();
        setBrowserUrl(server.origin);
        document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="upload-token">';
    });
    afterEach(() => { document.body.replaceChildren(); });
    afterAll(async () => { await server.close(); });

    const operation: UploadOperation<unknown> = options => apiData(v2GisLayersCreateWithFormData({
        name: 'Layer', source_file: new File(['<kml/>'], 'cave.kml'),
    }, webApiOptions(options)));

    it('sends generated multipart headers and forwards progress and completion', async () => {
        server.reply({ status: 201, json: { id: 'layer', name: 'Layer' } });
        const progress: number[] = [];
        let uploaded = false;
        const result = await new Promise<unknown>((resolve, reject) => {
            uploadWithProgress(operation, {
                onProgress: percent => progress.push(percent),
                onUploaded: () => { uploaded = true; },
                onSuccess: resolve, onError: reject,
            });
        });
        expect(result).toMatchObject({ id: 'layer' });
        expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/gis-layers/' });
        expect(server.requests[0]!.headers['x-csrftoken']).toBe('upload-token');
        expect(server.requests[0]!.headers['content-type']).toMatch(/^multipart\/form-data; boundary=/);
        expect(server.requests[0]!.body).toContain('filename="cave.kml"');
        expect(progress.at(-1)).toBe(100);
        expect(uploaded).toBe(true);
    });

    it.each([
        [400, { errors: { source_file: ['Choose a KML file.'] } }, false, 'source file: Choose a KML file.'],
        [503, { error: 'Unavailable' }, true, 'Unavailable'],
    ] as const)('preserves status %s validation and ambiguous failure policy', async (status, json, ambiguous, message) => {
        server.reply({ status, json });
        const failure = await new Promise<unknown>(resolve => {
            uploadWithProgress(operation, { onError: resolve });
        });
        expect(failure).toMatchObject({ status, ambiguous, message, payload: json });
    });

    it('cancels the real request and reports AbortError once', async () => {
        let complete: (() => void) | undefined;
        server.handle(async () => {
            await new Promise<void>(resolve => { complete = resolve; });
            return { status: 201, json: { id: 'late' } };
        });
        const failures: unknown[] = [];
        const request = uploadWithProgress(operation, { onError: error => failures.push(error) });
        await vi.waitFor(() => { expect(server.requests).toHaveLength(1); });
        request.abort();
        await vi.waitFor(() => { expect(failures).toHaveLength(1); });
        expect(failures[0]).toMatchObject({ name: 'AbortError', message: 'Upload cancelled', ambiguous: false });
        complete?.();
    });

    it('settles the controller promise and hides the successful UI after its delay', async () => {
        server.reply({ status: 201, json: { id: 'layer' } });
        document.body.innerHTML += createProgressBarHTML('transport');
        const controller = new UploadProgressController('transport');
        const promise = controller.upload(operation);
        expect(controller.request).toBeInstanceOf(AbortController);
        await expect(promise).resolves.toMatchObject({ id: 'layer' });
        expect(controller.request).toBeNull();
        expect(document.getElementById('transport-container')!.classList.contains('hidden')).toBe(false);
        await vi.waitFor(() => { expect(document.getElementById('transport-container')!.classList.contains('hidden')).toBe(true); }, { timeout: 2000 });
    });
});
