import { Notification } from './notification.ts';

describe('Notification', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    function getContainer() {
        return document.getElementById('notification-container')!;
    }

    // ------------------------------------------------------------------ //
    // Container creation
    // ------------------------------------------------------------------ //

    describe('container creation', () => {
        it('creates a notification-container when none exists', () => {
            Notification.show('success', 'Hello');

            const container = getContainer();
            expect(container).not.toBeNull();
            expect(container.parentElement).toBe(document.body);
        });

        it('reuses existing container on subsequent calls', () => {
            Notification.show('success', 'First');
            Notification.show('success', 'Second');

            const containers = document.querySelectorAll('#notification-container');
            expect(containers).toHaveLength(1);
        });
    });

    // ------------------------------------------------------------------ //
    // Element rendering
    // ------------------------------------------------------------------ //

    describe('element rendering', () => {
        it('creates a notification element with the message', () => {
            Notification.show('success', 'Saved!');

            const container = getContainer();
            expect(container.children).toHaveLength(1);
            expect(container.children[0]!.textContent).toContain('Saved!');
        });

        it('applies success background class', () => {
            Notification.show('success', 'ok');

            const el = getContainer().children[0]!;
            expect(el.className).toContain('bg-emerald-500');
        });

        it('applies error background class', () => {
            Notification.show('error', 'fail');

            const el = getContainer().children[0]!;
            expect(el.className).toContain('bg-red-500');
        });

        it('applies default (info/warning) background class', () => {
            Notification.show('warning', 'heads up');

            const el = getContainer().children[0]!;
            expect(el.className).toContain('bg-slate-700');
        });

        it('applies info background for unknown type', () => {
            Notification.show('info', 'note');

            const el = getContainer().children[0]!;
            expect(el.className).toContain('bg-slate-700');
        });

        it('includes success emoji for success type', () => {
            Notification.show('success', 'done');

            expect(getContainer().children[0]!.innerHTML).toContain('✅');
        });

        it('includes warning emoji for error type', () => {
            Notification.show('error', 'oops');

            expect(getContainer().children[0]!.innerHTML).toContain('⚠️');
        });

        it('includes info emoji for other types', () => {
            Notification.show('info', 'fyi');

            expect(getContainer().children[0]!.innerHTML).toContain('ℹ️');
        });
    });

    // ------------------------------------------------------------------ //
    // Auto-removal timing
    // ------------------------------------------------------------------ //

    describe('auto-removal', () => {
        it('removes notification element after duration + fade-out', async () => {
            Notification.show('success', 'bye', 40);

            const container = getContainer();
            expect(container.children).toHaveLength(1);

            await vi.waitFor(() => expect(container.children[0]!.classList.contains('translate-y-2')).toBe(true));
            expect(container.children).toHaveLength(1);
            await vi.waitFor(() => expect(container.children).toHaveLength(0));
        });

        it('uses default 3000ms duration', async () => {
            Notification.show('success', 'default');

            const container = getContainer();
            const element = container.children[0]!;
            expect(element.classList.contains('translate-y-2')).toBe(false);
            await vi.waitFor(() => expect(element.classList.contains('translate-y-2')).toBe(true), { timeout: 4000 });
            expect(container.children).toHaveLength(1);
            await vi.waitFor(() => expect(container.children).toHaveLength(0));
        });

        it('adds fade-out classes before removal', async () => {
            Notification.show('success', 'fading', 40);

            const el = getContainer().children[0]!;

            await vi.waitFor(() => expect(el.classList.contains('translate-y-2')).toBe(true));
            expect(el.classList.contains('opacity-0')).toBe(true);
            expect(el.classList.contains('translate-y-2')).toBe(true);
        });
    });

    // ------------------------------------------------------------------ //
    // Multiple notifications
    // ------------------------------------------------------------------ //

    describe('multiple notifications', () => {
        it('can show multiple notifications simultaneously', () => {
            Notification.show('success', 'first');
            Notification.show('error', 'second');
            Notification.show('warning', 'third');

            expect(getContainer().children).toHaveLength(3);
        });

        it('removes each independently based on their duration', async () => {
            Notification.show('success', 'short', 40);
            Notification.show('error', 'long', 500);

            await vi.waitFor(() => expect(getContainer().children).toHaveLength(1));
            expect(getContainer().children).toHaveLength(1);

            await vi.waitFor(() => expect(getContainer().children).toHaveLength(0));
            expect(getContainer().children).toHaveLength(0);
        });
    });
});
