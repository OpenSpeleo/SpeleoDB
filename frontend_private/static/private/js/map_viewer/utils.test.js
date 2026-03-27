import { describe, it, expect } from 'vitest';
import { Utils } from './utils.js';

describe('Utils.escapeHtml', () => {
    it('escapes HTML special characters', () => {
        expect(Utils.escapeHtml('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert("xss")&lt;/script&gt;'
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
            '<div><svg></svg> O\'Malley &amp; Sons &lt;LLC&gt;</div>'
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
});
