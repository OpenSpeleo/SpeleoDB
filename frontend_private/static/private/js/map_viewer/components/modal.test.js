import { Modal } from './modal.js';

describe('Modal', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    // ------------------------------------------------------------------ //
    // base()
    // ------------------------------------------------------------------ //

    describe('base', () => {
        it('returns HTML string with the given id, title, and content', () => {
            const html = Modal.base('test-modal', 'My Title', '<p>body</p>');

            expect(html).toContain('id="test-modal"');
            expect(html).toContain('My Title');
            expect(html).toContain('<p>body</p>');
        });

        it('includes close button with data-close-modal attribute', () => {
            const html = Modal.base('m1', 'Title', 'Content');

            expect(html).toContain('data-close-modal="m1"');
        });

        it('includes footer when provided', () => {
            const footer = '<button>Save</button>';
            const html = Modal.base('m1', 'Title', 'Content', footer);

            expect(html).toContain('<button>Save</button>');
        });

        it('omits footer section when footer is null', () => {
            const html = Modal.base('m1', 'Title', 'Content', null);

            expect(html).not.toContain('justify-end space-x-3');
        });

        it('uses custom maxWidth when provided', () => {
            const html = Modal.base('m1', 'Title', 'Content', null, 'max-w-lg');

            expect(html).toContain('max-w-lg');
            expect(html).not.toContain('max-w-2xl');
        });

        it('defaults to max-w-2xl', () => {
            const html = Modal.base('m1', 'Title', 'Content');

            expect(html).toContain('max-w-2xl');
        });
    });

    // ------------------------------------------------------------------ //
    // open()
    // ------------------------------------------------------------------ //

    describe('open', () => {
        it('inserts modal HTML into the DOM', () => {
            const html = Modal.base('m1', 'Title', 'Content');

            Modal.open('m1', html);

            expect(document.getElementById('m1')).not.toBeNull();
        });

        it('attaches close handler to close buttons', () => {
            const html = Modal.base('m1', 'Title', 'Content');
            Modal.open('m1', html);

            const closeBtn = document.querySelector('[data-close-modal="m1"]');
            expect(closeBtn).not.toBeNull();

            closeBtn.click();
            expect(document.getElementById('m1')).toBeNull();
        });

        it('closes on Escape key', () => {
            const html = Modal.base('m1', 'Title', 'Content');
            Modal.open('m1', html);

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

            expect(document.getElementById('m1')).toBeNull();
        });

        it('removes previous modal with same id before opening', () => {
            const html1 = Modal.base('m1', 'First', 'Content 1');
            const html2 = Modal.base('m1', 'Second', 'Content 2');

            Modal.open('m1', html1);
            Modal.open('m1', html2);

            const modals = document.querySelectorAll('#m1');
            expect(modals).toHaveLength(1);
            expect(modals[0].textContent).toContain('Second');
        });

        it('calls onOpen callback after opening', () => {
            vi.useFakeTimers();
            const onOpen = vi.fn();
            const html = Modal.base('m1', 'Title', 'Content');

            Modal.open('m1', html, onOpen);

            expect(onOpen).not.toHaveBeenCalled();
            vi.advanceTimersByTime(50);
            expect(onOpen).toHaveBeenCalledTimes(1);
            vi.useRealTimers();
        });

        it('works without onOpen callback', () => {
            const html = Modal.base('m1', 'Title', 'Content');

            expect(() => Modal.open('m1', html)).not.toThrow();
        });
    });

    // ------------------------------------------------------------------ //
    // close()
    // ------------------------------------------------------------------ //

    describe('close', () => {
        it('removes modal element from DOM', () => {
            const html = Modal.base('m1', 'Title', 'Content');
            Modal.open('m1', html);

            Modal.close('m1');

            expect(document.getElementById('m1')).toBeNull();
        });

        it('does nothing when modal id does not exist', () => {
            expect(() => Modal.close('nonexistent')).not.toThrow();
        });

        it('only removes the targeted modal', () => {
            Modal.open('m1', Modal.base('m1', 'First', 'A'));
            Modal.open('m2', Modal.base('m2', 'Second', 'B'));

            Modal.close('m1');

            expect(document.getElementById('m1')).toBeNull();
            expect(document.getElementById('m2')).not.toBeNull();
        });
    });
});
