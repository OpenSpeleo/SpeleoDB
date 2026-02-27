import { ContextMenu } from './context_menu.js';

describe('ContextMenu', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="context-menu" style="display:none;"></div><div id="map"></div>';
        ContextMenu.menuEl = null;
        ContextMenu.iconDataUrlCache = new Map();
        ContextMenu.iconFetchPromises = new Map();
        window.MAPVIEWER_CONTEXT = { icons: {} };
    });

    afterEach(() => {
        vi.restoreAllMocks();
        delete window.MAPVIEWER_CONTEXT;
    });

    function makeItems(count = 2) {
        return Array.from({ length: count }, (_, i) => ({
            label: `Item ${i + 1}`,
            icon: '',
            onClick: vi.fn(),
        }));
    }

    // ------------------------------------------------------------------ //
    // init
    // ------------------------------------------------------------------ //

    describe('init', () => {
        it('sets menuEl from DOM', () => {
            ContextMenu.init();

            expect(ContextMenu.menuEl).toBe(document.getElementById('context-menu'));
        });

        it('hides menu on document click', () => {
            ContextMenu.init();
            ContextMenu.menuEl.style.display = 'block';

            document.dispatchEvent(new Event('click'));

            expect(ContextMenu.menuEl.style.display).toBe('none');
        });

        it('hides menu on Escape key', () => {
            ContextMenu.init();
            ContextMenu.menuEl.style.display = 'block';

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

            expect(ContextMenu.menuEl.style.display).toBe('none');
        });
    });

    // ------------------------------------------------------------------ //
    // show
    // ------------------------------------------------------------------ //

    describe('show', () => {
        it('renders menu items', () => {
            const items = makeItems(3);

            ContextMenu.show(100, 200, items);

            const menuItems = ContextMenu.menuEl.querySelectorAll('.context-menu-item');
            expect(menuItems).toHaveLength(3);
        });

        it('renders item labels', () => {
            const items = [{ label: 'Edit', icon: '', onClick: vi.fn() }];

            ContextMenu.show(0, 0, items);

            expect(ContextMenu.menuEl.textContent).toContain('Edit');
        });

        it('renders separators', () => {
            const items = [
                { label: 'A', icon: '', onClick: vi.fn() },
                '-',
                { label: 'B', icon: '', onClick: vi.fn() },
            ];

            ContextMenu.show(0, 0, items);

            const separators = ContextMenu.menuEl.querySelectorAll('.context-menu-separator');
            expect(separators).toHaveLength(1);
        });

        it('renders subtitle when provided', () => {
            const items = [{ label: 'Move', subtitle: 'Drag to reposition', icon: '', onClick: vi.fn() }];

            ContextMenu.show(0, 0, items);

            expect(ContextMenu.menuEl.innerHTML).toContain('Drag to reposition');
            expect(ContextMenu.menuEl.querySelector('.context-menu-subtitle')).not.toBeNull();
        });

        it('adds disabled class for disabled items', () => {
            const items = [{ label: 'Locked', icon: '', disabled: true }];

            ContextMenu.show(0, 0, items);

            const item = ContextMenu.menuEl.querySelector('.context-menu-item');
            expect(item.classList.contains('disabled')).toBe(true);
        });

        it('makes the menu visible', () => {
            ContextMenu.show(100, 200, makeItems());

            expect(ContextMenu.menuEl.style.display).toBe('block');
        });

        it('positions menu at given coordinates', () => {
            ContextMenu.show(150, 250, makeItems());

            expect(ContextMenu.menuEl.style.left).toContain('150');
            expect(ContextMenu.menuEl.style.top).toContain('250');
        });

        it('auto-initializes if menuEl is null', () => {
            ContextMenu.menuEl = null;

            ContextMenu.show(0, 0, makeItems());

            expect(ContextMenu.menuEl).not.toBeNull();
        });
    });

    // ------------------------------------------------------------------ //
    // hide
    // ------------------------------------------------------------------ //

    describe('hide', () => {
        it('sets display to none', () => {
            ContextMenu.init();
            ContextMenu.menuEl.style.display = 'block';

            ContextMenu.hide();

            expect(ContextMenu.menuEl.style.display).toBe('none');
        });

        it('does nothing when menuEl is null', () => {
            ContextMenu.menuEl = null;

            expect(() => ContextMenu.hide()).not.toThrow();
        });
    });

    // ------------------------------------------------------------------ //
    // click handlers
    // ------------------------------------------------------------------ //

    describe('item click handlers', () => {
        it('calls onClick and hides menu when item is clicked', () => {
            const onClick = vi.fn();
            const items = [{ label: 'Delete', icon: '', onClick }];

            ContextMenu.show(0, 0, items);

            const menuItem = ContextMenu.menuEl.querySelector('.context-menu-item');
            menuItem.click();

            expect(onClick).toHaveBeenCalledTimes(1);
            expect(ContextMenu.menuEl.style.display).toBe('none');
        });

        it('does not attach onClick to disabled items', () => {
            const onClick = vi.fn();
            const items = [{ label: 'Disabled', icon: '', disabled: true, onClick }];

            ContextMenu.show(0, 0, items);

            const menuItem = ContextMenu.menuEl.querySelector('.context-menu-item');
            expect(menuItem.onclick).toBeNull();
        });

        it('does not attach onClick to items without onClick handler', () => {
            const items = [{ label: 'Info', icon: '' }];

            ContextMenu.show(0, 0, items);

            const menuItem = ContextMenu.menuEl.querySelector('.context-menu-item');
            expect(menuItem.onclick).toBeNull();
        });
    });

    // ------------------------------------------------------------------ //
    // getImageSourcesFromMarkup
    // ------------------------------------------------------------------ //

    describe('getImageSourcesFromMarkup', () => {
        it('extracts src URLs from img tags', () => {
            const markup = '<img src="/icons/pin.svg" />';

            const urls = ContextMenu.getImageSourcesFromMarkup(markup);

            expect(urls).toEqual(['/icons/pin.svg']);
        });

        it('extracts multiple src URLs', () => {
            const markup = '<img src="/a.png" /><img src="/b.png" />';

            const urls = ContextMenu.getImageSourcesFromMarkup(markup);

            expect(urls).toEqual(['/a.png', '/b.png']);
        });

        it('returns empty array for non-string input', () => {
            expect(ContextMenu.getImageSourcesFromMarkup(null)).toEqual([]);
            expect(ContextMenu.getImageSourcesFromMarkup(undefined)).toEqual([]);
        });

        it('returns empty array when no src attributes exist', () => {
            expect(ContextMenu.getImageSourcesFromMarkup('<span>text</span>')).toEqual([]);
        });
    });

    // ------------------------------------------------------------------ //
    // getCachedIconMarkup
    // ------------------------------------------------------------------ //

    describe('getCachedIconMarkup', () => {
        it('replaces src URLs with cached data URLs', () => {
            ContextMenu.iconDataUrlCache.set('/icon.svg', 'data:image/svg+xml;base64,abc');
            const markup = '<img src="/icon.svg" />';

            const result = ContextMenu.getCachedIconMarkup(markup);

            expect(result).toContain('data:image/svg+xml;base64,abc');
            expect(result).not.toContain('/icon.svg');
        });

        it('returns original markup when URL is not cached', () => {
            const markup = '<img src="/uncached.svg" />';

            const result = ContextMenu.getCachedIconMarkup(markup);

            expect(result).toContain('/uncached.svg');
        });

        it('returns empty string for falsy input', () => {
            expect(ContextMenu.getCachedIconMarkup(null)).toBe('');
            expect(ContextMenu.getCachedIconMarkup(undefined)).toBe('');
        });

        it('returns string unchanged when no src present', () => {
            expect(ContextMenu.getCachedIconMarkup('plain text')).toBe('plain text');
        });
    });

    // ------------------------------------------------------------------ //
    // getClampedPosition
    // ------------------------------------------------------------------ //

    describe('getClampedPosition', () => {
        it('returns click position when menu fits within viewport', () => {
            const menuRect = { width: 100, height: 50 };
            Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
            Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });

            const { left, top } = ContextMenu.getClampedPosition(100, 200, menuRect);

            expect(left).toBe(100);
            expect(top).toBe(200);
        });

        it('flips left when menu exceeds right edge', () => {
            const menuRect = { width: 200, height: 50 };
            Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
            Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });

            const { left } = ContextMenu.getClampedPosition(900, 100, menuRect);

            expect(left).toBe(700);
        });

        it('flips up when menu exceeds bottom edge', () => {
            const menuRect = { width: 100, height: 200 };
            Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
            Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });

            const { top } = ContextMenu.getClampedPosition(100, 700, menuRect);

            expect(top).toBe(500);
        });

        it('clamps to padding bounds', () => {
            const menuRect = { width: 100, height: 50 };
            Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
            Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });

            const { left, top } = ContextMenu.getClampedPosition(0, 0, menuRect);

            expect(left).toBe(8);
            expect(top).toBe(8);
        });
    });
});
