type HtmlPrimitive = string | number | boolean | null | undefined;
import { StationResources } from './resources.ts';

it('keeps note copy info styling throughout clipboard feedback', async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    try {
        StationResources.openNoteViewer({ title: 'Note', content: 'Survey note', author: 'Surveyor', date: '2026-09-17' });
        const button = document.querySelector<HTMLButtonElement>('[data-copy-note]')!;
        const originalMarkup = button.innerHTML;
        button.click();
        await vi.advanceTimersByTimeAsync(0);
        expect(writeText).toHaveBeenCalledWith('Survey note');
        expect(button.textContent.trim()).toBe('Copied!');
        expect(button.className).toBe('copy-button');
        await vi.advanceTimersByTimeAsync(2000);
        expect(button.innerHTML).toBe(originalMarkup);
        expect(button.className).toBe('copy-button');
    } finally {
        StationResources.closeNoteViewer();
        vi.useRealTimers();
        vi.unstubAllGlobals();
    }
});

const API = vi.hoisted(() => ({
        getStationResources: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        createStationResource: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        updateStationResource: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        deleteStationResource: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
    }));
vi.mock('../api.ts', () => ({ API }));

vi.mock('../config.ts', () => ({
    Config: {
        getStationAccess: vi.fn(() => ({ write: true, delete: true })),
    },
    DEFAULTS: {
        UPLOAD: { MAX_FILE_SIZE: 500 * 1024 * 1024 },
        UI: {
            NOTE_PREVIEW_LENGTH: 200,
        },
    },
}));

vi.mock('../state.ts', () => ({
    State: {
        allStations: new Map(),
        allSurfaceStations: new Map(),
    },
}));

const Utils = vi.hoisted(() => {
    const escapeHtml = (text: HtmlPrimitive) => {
        if (text === null || text === undefined) return '';
        const str = String(text);
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    const RAW = Symbol('RAW_HTML');
    type RawHTML = { [RAW]: true; value: string };
    return {
            showNotification: vi.fn(),
            showLoadingOverlay: vi.fn(() => document.createElement('div')),
            hideLoadingOverlay: vi.fn(),
            escapeHtml: vi.fn(escapeHtml),
            sanitizeUrl: vi.fn((url: string | null | undefined) => {
                if (!url || typeof url !== 'string') return '';
                const trimmed = url.trim();
                if (/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(trimmed)) {
                    try {
                        const parsed = new URL(trimmed);
                        return (parsed.protocol === 'http:' || parsed.protocol === 'https:') ? trimmed : '';
                    } catch (_) { return ''; }
                }
                return trimmed;
            }),
            safeCssColor: vi.fn((color: string | null | undefined, fb?: string) => {
                if (!color || typeof color !== 'string') return fb || '#94a3b8';
                return /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(color) ? color : (fb || '#94a3b8');
            }),
            raw: (html: string): RawHTML => ({ [RAW]: true, value: String(html) }),
            safeHtml: (strings: TemplateStringsArray, ...values: (HtmlPrimitive | RawHTML)[]) => strings.reduce((r, s, i) => {
                if (i < values.length) {
                    const v = values[i];
                    if (v && typeof v === 'object' && v[RAW]) return r + s + v.value;
                    return r + s + escapeHtml(v as HtmlPrimitive);
                }
                return r + s;
            }, ''),
    };
});
vi.mock('../utils.ts', () => ({ Utils }));

describe('StationResources XSS', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renderResourceCard escapes resource.title in text content', () => {
        const payload = '<img onerror=alert(1)>';
        const html = StationResources.renderResourceCard({
            id: 1,
            title: payload,
            resource_type: 'photo',
            creation_date: '2024-01-15',
            file: 'https://example.com/p.jpg',
            miniature: 'https://example.com/m.jpg',
        }, false, false);
        expect(html).toContain('&lt;img');
        expect(html).not.toContain('<img onerror');
    });

    it('renderResourceCard escapes resource.description', () => {
        const payload = '<img onerror=alert(1)>';
        const html = StationResources.renderResourceCard({
            id: 2,
            title: 'T',
            description: payload,
            resource_type: 'photo',
            creation_date: '2024-01-15',
            file: 'https://example.com/p.jpg',
            miniature: 'https://example.com/m.jpg',
        }, false, false);
        expect(html).toContain('&lt;img');
        expect(html).not.toContain('<img onerror');
    });

    it('renderResourceCard escapes resource.created_by', () => {
        const payload = '<img onerror=alert(1)>';
        const html = StationResources.renderResourceCard({
            id: 3,
            title: 'T',
            resource_type: 'photo',
            creation_date: '2024-01-15',
            created_by: payload,
            file: 'https://example.com/p.jpg',
            miniature: 'https://example.com/m.jpg',
        }, false, false);
        expect(html).toContain('&lt;img');
        expect(html).not.toContain('<img onerror');
    });

    it('getResourcePreview video escapes resource.title in data-video-title and alt', () => {
        const title = 'test" onclick="alert(1)';
        const html = StationResources.getResourcePreview({
            resource_type: 'video',
            file: 'https://example.com/v.mp4',
            miniature: 'https://example.com/thumb.jpg',
            title,
        });
        expect(html).toContain('&quot;');
        expect(html).not.toContain('test" onclick');
    });

    it('getResourcePreview document escapes resource.title in alt', () => {
        const title = 'test" onclick="alert(1)';
        const html = StationResources.getResourcePreview({
            resource_type: 'document',
            file: 'https://example.com/doc.pdf',
            miniature: 'https://example.com/doc-thumb.png',
            title,
        });
        expect(html).toContain('&quot;');
        expect(html).not.toContain('test" onclick');
    });

    it('getResourcePreview note escapes data-note-title, data-note-content, data-note-description, data-note-author', () => {
        const html = StationResources.getResourcePreview({
            resource_type: 'note',
            title: 't"x',
            text_content: 'c"y',
            description: 'd"z',
            created_by: 'a"w',
            creation_date: '2024-06-01',
        });
        expect(html).toContain('data-note-title="t&quot;x"');
        expect(html).toContain('data-note-content="c&quot;y"');
        expect(html).toContain('data-note-description="d&quot;z"');
        expect(html).toContain('data-note-author="a&quot;w"');
    });

    it('getResourcePreview sanitizes javascript: URLs to empty href and src', () => {
        const docHtml = StationResources.getResourcePreview({
            resource_type: 'document',
            file: 'javascript:alert(1)',
        });
        expect(docHtml).toContain('href=""');
        const photoHtml = StationResources.getResourcePreview({
            resource_type: 'photo',
            file: 'javascript:alert(1)',
        });
        expect(photoHtml).toContain('src=""');
        expect(photoHtml).toContain('data-photo-url=""');
    });

    it('getResourcePreview passes through normal https URLs', () => {
        const url = 'https://example.com/safe.pdf';
        const html = StationResources.getResourcePreview({
            resource_type: 'document',
            file: url,
        });
        expect(html).toContain(url);
    });
});

describe('StationResources lifecycle and transport', () => {
    beforeEach(() => { vi.clearAllMocks(); document.body.innerHTML = '<div id="station-modal-content"></div>'; });
    afterEach(() => { StationResources.closePhotoLightbox(); StationResources.closeNoteViewer(); document.body.innerHTML = ''; });

    it('sorts the response array in place and uses cached record identity in editing', async () => {
        const old = { id: 'old', resource_type: 'note', title: 'Old', text_content: '', creation_date: '2024-01-01' };
        const newest = { id: 'new', resource_type: 'note', title: 'New', text_content: '', creation_date: '2025-01-01' };
        const response = [old, newest];
        API.getStationResources.mockResolvedValue(response);
        await StationResources.render('station', (document.getElementById('station-modal-content') as HTMLElement));
        expect(response).toEqual([newest, old]);
        old.title = 'Changed cached title';
        StationResources.openEditForm('station', 'old');
        expect((document.getElementById('station-modal-content') as HTMLElement).innerHTML).toContain('Changed cached title');
        expect(API.getStationResources).toHaveBeenCalledOnce();
    });

    it('keeps selected file input identity while replacing preview markup', () => {
        const container = document.createElement('div');
        container.innerHTML = '<div class="text-center"><input type="file"></div>';
        const input = container.querySelector('input')!;
        const selected = new File(['abc'], 'selected.txt');
        Object.defineProperty(input, 'files', { value: [selected] });
        StationResources.updateFileDisplay(container, selected);
        expect(container.querySelector('input')).toBe(input);
        expect(input.files![0]).toBe(selected);
        expect(container.textContent).toContain('selected.txt');
    });

    it('retains ordinary viewer functions, receiver callbacks and current overflow reset', () => {
        const receiver = { ...StationResources, closePhotoLightbox: vi.fn() };
        document.body.style.overflow = 'scroll';
        expect(receiver.openPhotoLightbox('/photo.jpg', 'Title')).toBeUndefined();
        document.querySelector<HTMLButtonElement>('[data-close-lightbox]')!.click();
        expect(receiver.closePhotoLightbox).toHaveBeenCalledOnce();
        StationResources.closePhotoLightbox();
        expect(document.body.style.overflow).toBe('');
    });

    it('submits text FormData and starts a refresh without awaiting its promise', async () => {
        const receiver = { ...StationResources, render: vi.fn(() => new Promise<void>(() => {})) };
        receiver.openAddForm('station', 'note');
        const form = (document.getElementById('resource-form') as HTMLFormElement);
        API.createStationResource.mockResolvedValue({});
        await expect(receiver.saveResource('station', form)).resolves.toBeUndefined();
        expect(API.createStationResource).toHaveBeenCalledWith('station', expect.any(FormData));
        expect(receiver.render).toHaveBeenCalledOnce();
    });

    it('restores form controls on save errors', async () => {
        StationResources.openAddForm('station', 'note');
        const button = (document.getElementById('resource-submit-btn') as HTMLButtonElement);
        const original = button.innerHTML;
        API.createStationResource.mockRejectedValue(new Error('Denied'));
        await StationResources.saveResource('station', (document.getElementById('resource-form') as HTMLFormElement));
        expect(button.disabled).toBe(false);
        expect(button.innerHTML).toBe(original);
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Denied');
    });

    it('retains missing note-content errors and ordinary clipboard return', () => {
        expect(() => StationResources.formatNoteContent(null as unknown as string)).toThrow(TypeError);
        expect(StationResources.copyNoteToClipboard()).toBeUndefined();
    });
});
