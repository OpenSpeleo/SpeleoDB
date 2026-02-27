import { createProgressBarHTML, UploadProgressController, uploadWithProgress } from './upload.js';
import { Utils } from '../utils.js';

vi.mock('../utils.js', () => ({
    Utils: {
        getCSRFToken: vi.fn(() => 'test-csrf-token'),
    },
}));

// ------------------------------------------------------------------ //
// createProgressBarHTML
// ------------------------------------------------------------------ //

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

// ------------------------------------------------------------------ //
// uploadWithProgress
// ------------------------------------------------------------------ //

describe('uploadWithProgress', () => {
    let mockXHR;
    let OriginalXHR;

    beforeEach(() => {
        OriginalXHR = globalThis.XMLHttpRequest;
        mockXHR = {
            upload: { addEventListener: vi.fn() },
            addEventListener: vi.fn(),
            open: vi.fn(),
            setRequestHeader: vi.fn(),
            send: vi.fn(),
            abort: vi.fn(),
            status: 200,
            responseText: '{"success": true}',
        };
        // Must use a regular function so `new XMLHttpRequest()` works
        globalThis.XMLHttpRequest = function () { return mockXHR; };
    });

    afterEach(() => {
        globalThis.XMLHttpRequest = OriginalXHR;
        vi.clearAllMocks();
    });

    it('opens XHR with POST by default', () => {
        uploadWithProgress('/api/upload', new FormData());

        expect(mockXHR.open).toHaveBeenCalledWith('POST', '/api/upload');
    });

    it('uses custom method', () => {
        uploadWithProgress('/api/upload', new FormData(), { method: 'PUT' });

        expect(mockXHR.open).toHaveBeenCalledWith('PUT', '/api/upload');
    });

    it('sets CSRF token header', () => {
        uploadWithProgress('/api/upload', new FormData());

        expect(mockXHR.setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'test-csrf-token');
    });

    it('sends the provided FormData', () => {
        const formData = new FormData();
        formData.append('file', 'content');

        uploadWithProgress('/api/upload', formData);

        expect(mockXHR.send).toHaveBeenCalledWith(formData);
    });

    it('returns the XHR object for external cancellation', () => {
        const result = uploadWithProgress('/api/upload', new FormData());

        expect(result).toBe(mockXHR);
    });

    it('calls onProgress with computed percentage', () => {
        const onProgress = vi.fn();
        uploadWithProgress('/api/upload', new FormData(), { onProgress });

        const progressCb = mockXHR.upload.addEventListener.mock.calls.find(c => c[0] === 'progress')[1];
        progressCb({ lengthComputable: true, loaded: 50, total: 100 });

        expect(onProgress).toHaveBeenCalledWith(50, 50, 100);
    });

    it('does not call onProgress when length is not computable', () => {
        const onProgress = vi.fn();
        uploadWithProgress('/api/upload', new FormData(), { onProgress });

        const progressCb = mockXHR.upload.addEventListener.mock.calls.find(c => c[0] === 'progress')[1];
        progressCb({ lengthComputable: false, loaded: 0, total: 0 });

        expect(onProgress).not.toHaveBeenCalled();
    });

    it('calls onSuccess with parsed JSON on 2xx response', () => {
        const onSuccess = vi.fn();
        uploadWithProgress('/api/upload', new FormData(), { onSuccess });

        mockXHR.status = 200;
        mockXHR.responseText = '{"data": "test"}';
        const loadCb = mockXHR.addEventListener.mock.calls.find(c => c[0] === 'load')[1];
        loadCb();

        expect(onSuccess).toHaveBeenCalledWith({ data: 'test' });
    });

    it('falls back to { success: true } when response is not valid JSON', () => {
        const onSuccess = vi.fn();
        uploadWithProgress('/api/upload', new FormData(), { onSuccess });

        mockXHR.status = 201;
        mockXHR.responseText = 'not-json';
        const loadCb = mockXHR.addEventListener.mock.calls.find(c => c[0] === 'load')[1];
        loadCb();

        expect(onSuccess).toHaveBeenCalledWith({ success: true });
    });

    it('calls onError with parsed message on non-2xx response', () => {
        const onError = vi.fn();
        uploadWithProgress('/api/upload', new FormData(), { onError });

        mockXHR.status = 500;
        mockXHR.responseText = '{"message": "Server error"}';
        const loadCb = mockXHR.addEventListener.mock.calls.find(c => c[0] === 'load')[1];
        loadCb();

        expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'Server error' }));
    });

    it('uses default error message when response body is not parsable', () => {
        const onError = vi.fn();
        uploadWithProgress('/api/upload', new FormData(), { onError });

        mockXHR.status = 500;
        mockXHR.responseText = 'invalid';
        const loadCb = mockXHR.addEventListener.mock.calls.find(c => c[0] === 'load')[1];
        loadCb();

        expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'Upload failed' }));
    });

    it('calls onError on network error', () => {
        const onError = vi.fn();
        uploadWithProgress('/api/upload', new FormData(), { onError });

        const errorCb = mockXHR.addEventListener.mock.calls.find(c => c[0] === 'error')[1];
        errorCb();

        expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'Network error during upload' }));
    });

    it('calls onError on abort', () => {
        const onError = vi.fn();
        uploadWithProgress('/api/upload', new FormData(), { onError });

        const abortCb = mockXHR.addEventListener.mock.calls.find(c => c[0] === 'abort')[1];
        abortCb();

        expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'Upload cancelled' }));
    });
});

// ------------------------------------------------------------------ //
// UploadProgressController
// ------------------------------------------------------------------ //

describe('UploadProgressController', () => {
    let controller;

    beforeEach(() => {
        document.body.innerHTML = createProgressBarHTML('test');
        controller = new UploadProgressController('test');
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    describe('show', () => {
        it('removes hidden class from container', () => {
            controller.show();

            expect(document.getElementById('test-container').classList.contains('hidden')).toBe(false);
        });

        it('resets progress to 0%', () => {
            controller.show();

            expect(document.getElementById('test-percent').textContent).toBe('0%');
        });

        it('wires cancel button', () => {
            controller.show();
            const cancelBtn = document.getElementById('test-cancel');

            expect(cancelBtn.onclick).toBeTypeOf('function');
        });
    });

    describe('hide', () => {
        it('adds hidden class to container', () => {
            controller.show();
            controller.hide();

            expect(document.getElementById('test-container').classList.contains('hidden')).toBe(true);
        });
    });

    describe('update', () => {
        beforeEach(() => controller.show());

        it('updates progress bar width', () => {
            controller.update(50, 512, 1024);

            expect(document.getElementById('test-bar').style.width).toBe('50%');
        });

        it('updates percent text', () => {
            controller.update(75, 768, 1024);

            expect(document.getElementById('test-percent').textContent).toBe('75%');
        });

        it('updates size display with human-readable values', () => {
            controller.update(50, 512, 1024);

            expect(document.getElementById('test-size').textContent).toBe('512 B / 1 KB');
        });

        it('shows "Processing..." at 100%', () => {
            controller.update(100, 1024, 1024);

            expect(document.getElementById('test-status').textContent).toBe('Processing...');
        });

        it('shows "Uploading..." below 100%', () => {
            controller.update(50, 512, 1024);

            expect(document.getElementById('test-status').textContent).toBe('Uploading...');
        });
    });

    describe('complete', () => {
        beforeEach(() => controller.show());

        it('shows completion message', () => {
            controller.complete();

            expect(document.getElementById('test-status').innerHTML).toContain('Upload complete!');
        });

        it('hides cancel button', () => {
            controller.complete();

            expect(document.getElementById('test-cancel').classList.contains('hidden')).toBe(true);
        });
    });

    describe('error', () => {
        beforeEach(() => controller.show());

        it('shows custom error message', () => {
            controller.error('Something went wrong');

            expect(document.getElementById('test-status').innerHTML).toContain('Something went wrong');
        });

        it('uses default message when none provided', () => {
            controller.error();

            expect(document.getElementById('test-status').innerHTML).toContain('Upload failed');
        });

        it('changes bar color to red', () => {
            controller.error('Error');

            const bar = document.getElementById('test-bar');
            expect(bar.classList.contains('bg-red-500')).toBe(true);
            expect(bar.classList.contains('from-blue-500')).toBe(false);
        });

        it('hides cancel button', () => {
            controller.error('Error');

            expect(document.getElementById('test-cancel').classList.contains('hidden')).toBe(true);
        });
    });

    describe('cancel', () => {
        it('aborts XHR and hides progress', () => {
            const mockXhr = { abort: vi.fn() };
            controller.setXHR(mockXhr);
            controller.show();

            controller.cancel();

            expect(mockXhr.abort).toHaveBeenCalled();
            expect(document.getElementById('test-container').classList.contains('hidden')).toBe(true);
        });

        it('handles cancel when no XHR is set', () => {
            controller.show();

            expect(() => controller.cancel()).not.toThrow();
        });

        it('clears XHR reference after abort', () => {
            const mockXhr = { abort: vi.fn() };
            controller.setXHR(mockXhr);
            controller.cancel();

            // Calling cancel again should not abort twice
            controller.cancel();
            expect(mockXhr.abort).toHaveBeenCalledTimes(1);
        });
    });

    describe('setXHR', () => {
        it('stores XHR reference for later cancellation', () => {
            const mockXhr = { abort: vi.fn() };

            controller.setXHR(mockXhr);
            controller.cancel();

            expect(mockXhr.abort).toHaveBeenCalled();
        });
    });

    describe('upload', () => {
        let OriginalXHR;

        beforeEach(() => {
            OriginalXHR = globalThis.XMLHttpRequest;
        });

        afterEach(() => {
            globalThis.XMLHttpRequest = OriginalXHR;
        });

        it('resolves with response data on successful upload', async () => {
            const xhrMock = {
                upload: { addEventListener: vi.fn() },
                addEventListener: vi.fn(),
                open: vi.fn(),
                setRequestHeader: vi.fn(),
                send: vi.fn(),
                abort: vi.fn(),
                status: 200,
                responseText: '{"data": "ok"}',
            };
            globalThis.XMLHttpRequest = function () { return xhrMock; };

            const promise = controller.upload('/api/upload', new FormData());

            // Container should be visible
            expect(document.getElementById('test-container').classList.contains('hidden')).toBe(false);

            // Trigger successful load
            const loadCb = xhrMock.addEventListener.mock.calls.find(c => c[0] === 'load')[1];
            loadCb();

            const result = await promise;
            expect(result).toEqual({ data: 'ok' });
        });

        it('rejects on failed upload', async () => {
            const xhrMock = {
                upload: { addEventListener: vi.fn() },
                addEventListener: vi.fn(),
                open: vi.fn(),
                setRequestHeader: vi.fn(),
                send: vi.fn(),
                abort: vi.fn(),
                status: 500,
                responseText: '{"message": "Fail"}',
            };
            globalThis.XMLHttpRequest = function () { return xhrMock; };

            const promise = controller.upload('/api/upload', new FormData());

            const loadCb = xhrMock.addEventListener.mock.calls.find(c => c[0] === 'load')[1];
            loadCb();

            await expect(promise).rejects.toThrow('Fail');
        });
    });
});
