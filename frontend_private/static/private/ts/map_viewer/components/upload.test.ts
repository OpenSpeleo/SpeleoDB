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

        expect(controller.xhr).toBeNull();
        expect(document.getElementById('test-container')!.classList.contains('hidden')).toBe(true);
    });

    it('renders error text without interpreting uploaded data as HTML', () => {
        controller.error('<img src=x onerror=alert(1)>');

        expect(document.getElementById('test-status')!.querySelector<HTMLElement>('img')!).toBeNull();
        expect(document.getElementById('test-status')!.textContent).toContain('<img src=x onerror=alert(1)>');
    });
});

describe('upload transport boundary', () => {
    const fixture = {} as { xhr: FixtureXHR };
    class FixtureXHR extends EventTarget {
        upload = new EventTarget();
        status = 0;
        responseText = '';
        open = vi.fn();
        setRequestHeader = vi.fn();
        send = vi.fn();
        abort = vi.fn(() => this.dispatchEvent(new Event('abort')));
        constructor() { super(); fixture.xhr = this; }
    }
    beforeEach(() => { vi.stubGlobal('XMLHttpRequest', FixtureXHR); });
    afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

    it('forwards the method, token and FormData identity and upload receiver', () => {
        const data = new FormData();
        const onProgress = vi.fn();
        const onUploaded = vi.fn(function (this: EventTarget) { expect(this).toBe(fixture.xhr.upload); });
        expect(uploadWithProgress('/upload', data, { method: 'PUT', csrfToken: 'token', onProgress, onUploaded })).toBe(fixture.xhr);
        expect(fixture.xhr.open).toHaveBeenCalledWith('PUT', '/upload');
        expect(fixture.xhr.setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'token');
        expect(fixture.xhr.send).toHaveBeenCalledWith(data);
        fixture.xhr.upload.dispatchEvent(new ProgressEvent('progress', { lengthComputable: false, loaded: 10, total: 20 }));
        expect(onProgress).not.toHaveBeenCalled();
        fixture.xhr.upload.dispatchEvent(new ProgressEvent('progress', { lengthComputable: true, loaded: 1, total: 3 }));
        expect(onProgress).toHaveBeenCalledWith(33, 1, 3);
        fixture.xhr.upload.dispatchEvent(new Event('load'));
        expect(onUploaded).toHaveBeenCalledOnce();
    });

    it.each([[204, 'ignored', null], [201, '', null], [200, '{"id":3}', { id: 3 }]] as const)('settles successful status %s with the existing payload policy', (status, responseText, expected) => {
        const onSuccess = vi.fn();
        uploadWithProgress('/upload', new FormData(), { csrfToken: '', onSuccess });
        Object.assign(fixture.xhr, { status, responseText });
        fixture.xhr.dispatchEvent(new Event('load'));
        expect(onSuccess).toHaveBeenCalledWith(expected);
    });

    it('preserves ambiguous parse and server errors and the abort error name', () => {
        const onError = vi.fn();
        uploadWithProgress('/upload', new FormData(), { csrfToken: '', onError });
        Object.assign(fixture.xhr, { status: 200, responseText: 'not JSON' });
        fixture.xhr.dispatchEvent(new Event('load'));
        expect(onError.mock.calls[0]![0]).toMatchObject({ status: 200, ambiguous: true });
        Object.assign(fixture.xhr, { status: 503, responseText: '{"error":"Unavailable"}' });
        fixture.xhr.dispatchEvent(new Event('load'));
        expect(onError.mock.calls[1]![0]).toMatchObject({ status: 503, ambiguous: true, message: 'Unavailable', payload: { error: 'Unavailable' } });
        fixture.xhr.abort();
        expect(onError.mock.calls[2]![0]).toMatchObject({ status: 0, name: 'AbortError', message: 'Upload cancelled' });
    });

    it('preserves controller promise settlement and delayed hide after completion', async () => {
        vi.useFakeTimers();
        document.body.innerHTML = createProgressBarHTML('transport');
        const controller = new UploadProgressController('transport');
        const promise = controller.upload('/upload', new FormData());
        expect(controller.xhr).toBe(fixture.xhr);
        Object.assign(fixture.xhr, { status: 204 });
        fixture.xhr.dispatchEvent(new Event('load'));
        await expect(promise).resolves.toBeNull();
        expect(document.getElementById('transport-container')!.classList.contains('hidden')).toBe(false);
        vi.advanceTimersByTime(1499);
        expect(document.getElementById('transport-container')!.classList.contains('hidden')).toBe(false);
        vi.advanceTimersByTime(1);
        expect(document.getElementById('transport-container')!.classList.contains('hidden')).toBe(true);
        document.body.innerHTML = '';
    });
});
