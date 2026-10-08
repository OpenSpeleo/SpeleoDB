/**
 * Regression tests for the shared user autocomplete helper.
 *
 * Loads real jQuery via readFileSync + eval and imports user_autocomplete.ts
 * with its xss-helpers.ts dependency to exercise production code (and catch any
 * drift between it and the tests). Covers the Phase 1 unwrap regression:
 * the autocomplete must read a raw array off the API response, not the
 * legacy `{data: [...]}` envelope.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { attachUserAutocomplete } from './user_autocomplete.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));

const JQUERY_PATH = resolve(__dirname, '..', '..', '..', '..', 'frontend_public', 'static', 'ts', 'vendors', 'jquery-3.7.1.js');
const JQUERY_SRC = readFileSync(JQUERY_PATH, 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
});

// The vendor eval installs this runtime property; jQuery's ambient declaration
// describes its callable binding rather than the globalThis property.
const jqueryHost = globalThis as typeof globalThis & { jQuery: JQueryStatic };
interface AutocompleteAjaxOptions {
    success(response: unknown): void;
    error(): void;
    complete?(): void;
}
function mockAjax(implementation: (options: AutocompleteAjaxOptions) => { abort(): void }) {
    const mock = vi.fn(implementation);
    // Only the consumed transport callbacks/abort capability are replaced.
    Object.assign(jqueryHost.jQuery, { ajax: mock });
    return mock;
}

const URL = '/api/v2/user/autocomplete/';

function installInput() {
    document.body.innerHTML = `
        <input id="user" />
        <div id="user_suggestions" class="hidden"></div>
    `;
    const $ = jqueryHost.jQuery;
    return { $input: $('#user'), $suggestions: $('#user_suggestions'), $ };
}

describe('user_autocomplete', () => {
    let originalAjax: JQueryStatic['ajax'];
    let ajaxHost: { ajax: JQueryStatic['ajax'] };

    beforeEach(() => {
        vi.useFakeTimers();
        ajaxHost = jqueryHost.jQuery;
        originalAjax = ajaxHost.ajax;
    });

    afterEach(() => {
        jqueryHost.jQuery.ajax = originalAjax;
        document.body.innerHTML = '';
        vi.useRealTimers();
    });

    it('renders suggestions when the API returns a bare array', () => {
        const { $input, $suggestions, $ } = installInput();
        mockAjax((opts) => {
            opts.success([
                { email: 'alice@example.com', name: 'Alice' },
                { email: 'bob@example.com', name: 'Bob' },
            ]);
            opts.complete?.();
            return { abort: vi.fn() };
        });
        attachUserAutocomplete($input, $suggestions, URL);

        $input.val('ali').trigger('input');
        vi.advanceTimersByTime(260);

        expect(ajaxHost.ajax).toHaveBeenCalledTimes(1);
        expect($suggestions.hasClass('hidden')).toBe(false);
        expect($suggestions.children('div[data-index]').length).toBe(2);
        expect($suggestions.text()).toContain('Alice');
        expect($suggestions.text()).toContain('alice@example.com');
    });

    it('keeps dropdown hidden when the API returns a legacy wrapper {data: [...]}', () => {
        const { $input, $suggestions, $ } = installInput();
        mockAjax((opts) => {
            // Simulate a rogue v1-style wrapped response.
            opts.success({ data: [{ email: 'wrapped@example.com', name: 'W' }] });
            opts.complete?.();
            return { abort: vi.fn() };
        });
        attachUserAutocomplete($input, $suggestions, URL);

        $input.val('wra').trigger('input');
        vi.advanceTimersByTime(260);

        expect(ajaxHost.ajax).toHaveBeenCalledTimes(1);
        expect($suggestions.hasClass('hidden')).toBe(true);
        expect($suggestions.children('div[data-index]').length).toBe(0);
    });

    it('hides dropdown and does not throw when the API errors', () => {
        const { $input, $suggestions, $ } = installInput();
        mockAjax((opts) => {
            opts.error();
            opts.complete?.();
            return { abort: vi.fn() };
        });
        attachUserAutocomplete($input, $suggestions, URL);

        expect(() => {
            $input.val('err').trigger('input');
            vi.advanceTimersByTime(260);
        }).not.toThrow();
        expect($suggestions.hasClass('hidden')).toBe(true);
    });

    it('debounces rapid typing into a single request', () => {
        const { $input, $suggestions, $ } = installInput();
        mockAjax((opts) => {
            opts.success([]);
            opts.complete?.();
            return { abort: vi.fn() };
        });
        attachUserAutocomplete($input, $suggestions, URL);

        // Rapid three-keystroke burst under 250ms - one ajax only.
        $input.val('ali').trigger('input');
        vi.advanceTimersByTime(100);
        $input.val('alic').trigger('input');
        vi.advanceTimersByTime(100);
        $input.val('alice').trigger('input');
        vi.advanceTimersByTime(260);

        expect(ajaxHost.ajax).toHaveBeenCalledTimes(1);
        expect(ajaxHost.ajax).toHaveBeenCalledWith(expect.objectContaining({ data: { query: 'alice' } }));
    });

    it('does not fire for queries shorter than 3 characters', () => {
        const { $input, $suggestions, $ } = installInput();
        $.ajax = vi.fn();
        attachUserAutocomplete($input, $suggestions, URL);

        $input.val('a').trigger('input');
        vi.advanceTimersByTime(260);
        $input.val('al').trigger('input');
        vi.advanceTimersByTime(260);

        expect(ajaxHost.ajax).not.toHaveBeenCalled();
        expect($suggestions.hasClass('hidden')).toBe(true);
    });

    it('commits selection to the input on Enter, hiding suggestions', () => {
        const { $input, $suggestions, $ } = installInput();
        mockAjax((opts) => {
            opts.success([
                { email: 'carol@example.com', name: 'Carol' },
                { email: 'dave@example.com', name: 'Dave' },
            ]);
            opts.complete?.();
            return { abort: vi.fn() };
        });
        attachUserAutocomplete($input, $suggestions, URL);

        $input.val('car').trigger('input');
        vi.advanceTimersByTime(260);

        const enter = $.Event('keydown', { key: 'Enter' });
        $input.trigger(enter);

        expect($input.val()).toBe('carol@example.com');
        expect($suggestions.hasClass('hidden')).toBe(true);
    });
});
