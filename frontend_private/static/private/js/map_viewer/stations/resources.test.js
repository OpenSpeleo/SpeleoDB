import { StationResources } from './resources.js';

vi.mock('../api.js', () => ({
    API: {
        getStationResources: vi.fn(),
    },
}));

vi.mock('../config.js', () => ({
    Config: {
        getStationAccess: vi.fn(() => ({ write: true, delete: true })),
    },
    DEFAULTS: {
        UI: {
            NOTE_PREVIEW_LENGTH: 200,
        },
    },
}));

vi.mock('../state.js', () => ({
    State: {
        allStations: new Map(),
        allSurfaceStations: new Map(),
    },
}));

vi.mock('../components/upload.js', () => ({
    createProgressBarHTML: vi.fn(() => ''),
    UploadProgressController: vi.fn(),
}));

vi.mock('../utils.js', () => {
    const escapeHtml = (text) => {
        if (text === null || text === undefined) return '';
        const str = String(text);
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    const RAW = Symbol('RAW_HTML');
    return {
        Utils: {
            showNotification: vi.fn(),
            showLoadingOverlay: vi.fn(() => document.createElement('div')),
            hideLoadingOverlay: vi.fn(),
            escapeHtml: vi.fn(escapeHtml),
            sanitizeUrl: vi.fn((url) => {
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
            safeCssColor: vi.fn((color, fb) => {
                if (!color || typeof color !== 'string') return fb || '#94a3b8';
                return /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(color) ? color : (fb || '#94a3b8');
            }),
            raw: (html) => ({ [RAW]: true, value: String(html) }),
            safeHtml: (strings, ...values) => strings.reduce((r, s, i) => {
                if (i < values.length) {
                    const v = values[i];
                    if (v && typeof v === 'object' && v[RAW]) return r + s + v.value;
                    return r + s + escapeHtml(v);
                }
                return r + s;
            }, ''),
        },
    };
});

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
