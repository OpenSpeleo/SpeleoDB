import { escapeHtml, isValidCssColor, safeCssColor, sanitizeUrl } from './xss-helpers.ts';

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('shared HTML boundary translation contract', () => {
    it.each([
        [null, ''], [undefined, ''], ['', ''], [0, '0'], [false, 'false'],
        ['<a title="x">&\'</a>', '&lt;a title=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;'],
    ])('preserves coercion and quote escaping for %s', (value, expected) => {
        expect(escapeHtml(value)).toBe(expected);
    });

    it('uses the original object string conversion and propagates its failures', () => {
        const toString = vi.fn(() => '<example>');
        expect(escapeHtml({ toString })).toBe('&lt;example&gt;');
        expect(toString).toHaveBeenCalledOnce();
        const failure = new Error('Cannot stringify');
        expect(() => escapeHtml({ toString() { throw failure; } })).toThrow(failure);
    });

    it.each([
        ['#ABC', true], ['#aabbcc', true], ['red', false], ['#abcd', false],
        ['', false], [null, false], [123, false], [' #abc', false],
    ])('retains strict hexadecimal color acceptance for %s', (value, expected) => {
        expect(isValidCssColor(value)).toBe(expected);
    });

    it('preserves valid color spelling and the existing falsey fallback policy', () => {
        expect(safeCssColor('#ABC', '#ffffff')).toBe('#ABC');
        expect(safeCssColor('red')).toBe('#94a3b8');
        expect(safeCssColor(null, '')).toBe('#94a3b8');
        expect(safeCssColor('red', 'trusted fallback')).toBe('trusted fallback');
    });

    it.each([
        [null, ''], [false, ''], [1, ''], ['', ''], ['  ', ''],
        ['  /relative?q=1  ', '/relative?q=1'],
        [' https://example.org/a%20b ', 'https://example.org/a%20b'],
        ['HTTP://EXAMPLE.ORG', 'HTTP://EXAMPLE.ORG'],
        ['javascript:alert(1)', ''], ['data:text/plain,hello', ''], ['http://%', ''],
    ])('returns the trimmed original URL or an empty string for %s', (value, expected) => {
        expect(sanitizeUrl(value)).toBe(expected);
    });

    it('retains the relative-path fallback when URL construction throws', () => {
        vi.stubGlobal('URL', class {
            constructor() { throw new TypeError('Unavailable URL parser'); }
        });
        expect(sanitizeUrl(' /relative ')).toBe('/relative');
        expect(sanitizeUrl('custom:payload')).toBe('');
    });
});
