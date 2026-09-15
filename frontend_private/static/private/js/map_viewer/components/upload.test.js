import { createProgressBarHTML, UploadProgressController } from './upload.js';

// Real transport, cancellation and promise results run against Django in
// speleodb/api/v2/tests/test_frontend_upload_integration.py.

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
    let controller;

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

    it('handles cancellation without an active request', () => {
        controller.show();
        controller.cancel();

        expect(controller.xhr).toBeNull();
        expect(document.getElementById('test-container').classList.contains('hidden')).toBe(true);
    });

    it('renders error text without interpreting uploaded data as HTML', () => {
        controller.error('<img src=x onerror=alert(1)>');

        expect(document.getElementById('test-status').querySelector('img')).toBeNull();
        expect(document.getElementById('test-status').textContent).toContain('<img src=x onerror=alert(1)>');
    });
});
