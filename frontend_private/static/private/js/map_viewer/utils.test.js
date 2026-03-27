import { describe, it, expect } from 'vitest';
import { Utils } from './utils.js';

describe('Utils.escapeHtml', () => {
    it('escapes HTML special characters', () => {
        expect(Utils.escapeHtml('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
        );
    });

    it('escapes ampersands', () => {
        expect(Utils.escapeHtml('A & B')).toBe('A &amp; B');
    });

    it('escapes angle brackets', () => {
        expect(Utils.escapeHtml('<img onerror=alert(1)>')).toBe(
            '&lt;img onerror=alert(1)&gt;'
        );
    });

    it('returns empty string for null', () => {
        expect(Utils.escapeHtml(null)).toBe('');
    });

    it('returns empty string for undefined', () => {
        expect(Utils.escapeHtml(undefined)).toBe('');
    });

    it('returns empty string for empty string', () => {
        expect(Utils.escapeHtml('')).toBe('');
    });

    it('converts numbers to string and returns as-is', () => {
        expect(Utils.escapeHtml(42)).toBe('42');
        expect(Utils.escapeHtml(0)).toBe('0');
    });

    it('handles strings with no special characters', () => {
        expect(Utils.escapeHtml('Hello World')).toBe('Hello World');
    });

    it('escapes double quotes for attribute safety', () => {
        expect(Utils.escapeHtml('test" onclick="alert(1)')).toBe(
            'test&quot; onclick=&quot;alert(1)'
        );
    });

    it('escapes single quotes for attribute safety', () => {
        expect(Utils.escapeHtml("O'Malley")).toBe('O&#39;Malley');
    });

    it('escapes all five HTML-sensitive characters together', () => {
        expect(Utils.escapeHtml(`<a href="x" title='y'>&`)).toBe(
            '&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;'
        );
    });
});

describe('Utils.raw', () => {
    it('wraps a string as trusted HTML', () => {
        const result = Utils.raw('<b>bold</b>');
        expect(result.value).toBe('<b>bold</b>');
    });

    it('converts non-string values to string', () => {
        const result = Utils.raw(42);
        expect(result.value).toBe('42');
    });
});

describe('Utils.safeHtml', () => {
    it('escapes interpolated values', () => {
        const userInput = '<img onerror=alert(1)>';
        const result = Utils.safeHtml`<div>${userInput}</div>`;
        expect(result).toBe('<div>&lt;img onerror=alert(1)&gt;</div>');
    });

    it('passes through raw() values without escaping', () => {
        const icon = Utils.raw('<svg>icon</svg>');
        const result = Utils.safeHtml`<div>${icon}</div>`;
        expect(result).toBe('<div><svg>icon</svg></div>');
    });

    it('escapes some values and passes through raw() in the same template', () => {
        const name = 'O\'Malley & Sons <LLC>';
        const icon = Utils.raw('<svg></svg>');
        const result = Utils.safeHtml`<div>${icon} ${name}</div>`;
        expect(result).toBe(
            '<div><svg></svg> O&#39;Malley &amp; Sons &lt;LLC&gt;</div>'
        );
    });

    it('handles null and undefined interpolations', () => {
        const result = Utils.safeHtml`<span>${null} ${undefined}</span>`;
        expect(result).toBe('<span> </span>');
    });

    it('handles numeric interpolations', () => {
        const count = 42;
        const result = Utils.safeHtml`<span>${count} items</span>`;
        expect(result).toBe('<span>42 items</span>');
    });

    it('handles template with no interpolations', () => {
        const result = Utils.safeHtml`<div>static content</div>`;
        expect(result).toBe('<div>static content</div>');
    });

    it('does not double-escape already-escaped content via raw()', () => {
        const preEscaped = Utils.raw('A &amp; B');
        const result = Utils.safeHtml`<span>${preEscaped}</span>`;
        expect(result).toBe('<span>A &amp; B</span>');
    });

    it('does not double-escape when used with plain text containing &', () => {
        const name = 'A & B';
        const result = Utils.safeHtml`<span>${name}</span>`;
        expect(result).toBe('<span>A &amp; B</span>');
    });

    it('escapes interpolated values in attribute positions', () => {
        const title = 'test" onclick="alert(1)';
        const result = Utils.safeHtml`<input value="${title}">`;
        expect(result).toBe('<input value="test&quot; onclick=&quot;alert(1)">');
        expect(result).not.toContain('onclick="alert');
    });

    it('escapes single quotes in attribute positions', () => {
        const name = "O'Malley";
        const result = Utils.safeHtml`<div data-name="${name}">text</div>`;
        expect(result).toContain('O&#39;Malley');
    });
});

describe('Utils.isValidCssColor', () => {
    it('accepts valid 6-digit hex colors', () => {
        expect(Utils.isValidCssColor('#ff0000')).toBe(true);
        expect(Utils.isValidCssColor('#AABBCC')).toBe(true);
    });

    it('accepts valid 3-digit hex colors', () => {
        expect(Utils.isValidCssColor('#abc')).toBe(true);
    });

    it('rejects non-hex strings', () => {
        expect(Utils.isValidCssColor('red')).toBe(false);
        expect(Utils.isValidCssColor('rgb(1,2,3)')).toBe(false);
        expect(Utils.isValidCssColor('#gg0000')).toBe(false);
    });

    it('rejects null/undefined/empty', () => {
        expect(Utils.isValidCssColor(null)).toBe(false);
        expect(Utils.isValidCssColor(undefined)).toBe(false);
        expect(Utils.isValidCssColor('')).toBe(false);
    });

    it('rejects CSS injection attempts', () => {
        expect(Utils.isValidCssColor('#ff0000; background-image: url(evil)')).toBe(false);
        expect(Utils.isValidCssColor('red" onclick="alert(1)')).toBe(false);
    });
});

describe('Utils.safeCssColor', () => {
    it('returns color when valid', () => {
        expect(Utils.safeCssColor('#ff0000')).toBe('#ff0000');
    });

    it('returns fallback when invalid', () => {
        expect(Utils.safeCssColor('not-a-color')).toBe('#94a3b8');
    });

    it('accepts custom fallback', () => {
        expect(Utils.safeCssColor('bad', '#000')).toBe('#000');
    });
});

describe('Utils.sanitizeUrl', () => {
    it('allows https URLs', () => {
        expect(Utils.sanitizeUrl('https://example.com/file.jpg')).toBe('https://example.com/file.jpg');
    });

    it('allows http URLs', () => {
        expect(Utils.sanitizeUrl('http://example.com/file.jpg')).toBe('http://example.com/file.jpg');
    });

    it('allows relative URLs', () => {
        expect(Utils.sanitizeUrl('/media/uploads/photo.jpg')).toBe('/media/uploads/photo.jpg');
    });

    it('rejects javascript: protocol', () => {
        expect(Utils.sanitizeUrl('javascript:alert(1)')).toBe('');
    });

    it('rejects data: protocol', () => {
        expect(Utils.sanitizeUrl('data:text/html,<script>alert(1)</script>')).toBe('');
    });

    it('rejects vbscript: protocol', () => {
        expect(Utils.sanitizeUrl('vbscript:msgbox("xss")')).toBe('');
    });

    it('returns empty string for null/undefined/empty', () => {
        expect(Utils.sanitizeUrl(null)).toBe('');
        expect(Utils.sanitizeUrl(undefined)).toBe('');
        expect(Utils.sanitizeUrl('')).toBe('');
    });

    it('returns empty string for non-string input', () => {
        expect(Utils.sanitizeUrl(123)).toBe('');
        expect(Utils.sanitizeUrl({})).toBe('');
    });
});

describe('Utils.raw edge cases', () => {
    it('converts null to string "null"', () => {
        const result = Utils.raw(null);
        expect(result.value).toBe('null');
    });

    it('converts undefined to string "undefined"', () => {
        const result = Utils.raw(undefined);
        expect(result.value).toBe('undefined');
    });
});
