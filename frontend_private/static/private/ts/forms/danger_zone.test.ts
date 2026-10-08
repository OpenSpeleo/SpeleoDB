import type { Mock } from 'vitest';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

/**
 * Tests for forms/danger_zone.ts - the shared delete-with-confirm flow.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { attachDangerZone } from './danger_zone.ts';

// The real vendor is callable; these tests replace only its AJAX transport.
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };

const __dirname = dirname(fileURLToPath(import.meta.url));

const JQUERY_SRC = readFileSync(resolve(__dirname, '..', '..', '..', '..', '..', 'frontend_public', 'static', 'ts', 'vendors', 'jquery-3.7.1.js'), 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
});

function setupPage() {
    document.body.innerHTML = `
        <input type="hidden" name="csrfmiddlewaretoken" value="csrf-test-token" />
        <div id="error_div" style="display: none;"></div>
        <div id="success_div" style="display: none;"></div>
        <button id="btn_delete">Delete</button>
        <div id="modal_confirmation" style="display: none;">
            <button id="btn_confirmed_delete">Yes</button>
        </div>
        <div id="modal_success" style="display: none;"><span id="modal_success_txt"></span></div>
        <div id="modal_error" style="display: none;"><span id="modal_error_txt"></span></div>
    `;
}

describe('attachDangerZone', () => {
    let originalAjax: FormTestJQuery['ajax'];
    let originalLocation: Location;
    let locationHrefSpy: Mock<(value: unknown) => void>;

    beforeEach(() => {
        vi.useFakeTimers();
        setupPage();
        originalAjax = jqueryHost.jQuery.ajax;
        // Track assignments to window.location.href.
        originalLocation = window.location;
        locationHrefSpy = vi.fn();
        Object.defineProperty(window, 'location', {
            writable: true,
            value: new Proxy({ href: '' }, {
                set(target, prop, value: unknown) {
                    Reflect.set(target, prop, value);
                    if (prop === 'href') { locationHrefSpy(value); }
                    return true;
                },
                get(target, prop) { return Reflect.get(target, prop) as unknown; },
            }),
        });
    });

    afterEach(() => {
        jqueryHost.jQuery.ajax = originalAjax;
        Object.defineProperty(window, 'location', {
            configurable: true,
            writable: true,
            value: originalLocation,
        });
        vi.useRealTimers();
        document.body.innerHTML = '';
    });

    it('throws when deleteUrl is missing', () => {
        expect(() => attachDangerZone({})).toThrow(/deleteUrl/);
    });

    it('opens the confirmation modal on btn_delete click', () => {
        attachDangerZone({
            deleteUrl: '/api/v2/projects/x/',
            successRedirect: '/list',
        });
        (document.getElementById('btn_delete') as HTMLElement).click();
        expect((document.getElementById('modal_confirmation') as HTMLElement).style.display).toBe('flex');
    });

    it('sends DELETE with CSRF and fires successRedirect on 2xx', () => {
        const $ = jqueryHost.jQuery;
        $.ajax = vi.fn((opts) => {
            // capture csrf for assertion
            const fakeXhr = { setRequestHeader: vi.fn(() => true) };
            opts.beforeSend(fakeXhr);
            opts.success();
            return fakeXhr;
        });

        attachDangerZone({
            deleteUrl: '/api/v2/projects/x/',
            successMessage: 'Gone.',
            successRedirect: '/list',
            redirectDelayMs: 1000,
        });

        // Open confirmation, then confirm.
        (document.getElementById('btn_delete') as HTMLElement).click();
        (document.getElementById('btn_confirmed_delete') as HTMLElement).click();

        expect($.ajax).toHaveBeenCalledTimes(1);
        const call = $.ajax.mock.calls[0]![0];
        expect(call.url).toBe('/api/v2/projects/x/');
        expect(call.method).toBe('DELETE');

        // Success modal flashed & redirect scheduled
        expect((document.getElementById('modal_success') as HTMLElement).style.display).toBe('flex');
        expect((document.getElementById('modal_success_txt') as HTMLElement).innerHTML).toBe('Gone.');

        vi.advanceTimersByTime(1000);
        expect(locationHrefSpy).toHaveBeenCalledWith('/list');
    });

    it('surfaces the error modal on non-2xx', () => {
        const $ = jqueryHost.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            opts.error({ responseJSON: { error: 'nope' }, status: 400, statusText: 'Bad' });
            return {};
        });

        attachDangerZone({ deleteUrl: '/api/v2/x/', successRedirect: '/list' });
        (document.getElementById('btn_delete') as HTMLElement).click();
        (document.getElementById('btn_confirmed_delete') as HTMLElement).click();

        expect((document.getElementById('modal_error') as HTMLElement).style.display).toBe('flex');
        expect((document.getElementById('modal_error_txt') as HTMLElement).textContent).toBe('nope');
        // No redirect on failure.
        vi.advanceTimersByTime(10_000);
        expect(locationHrefSpy).not.toHaveBeenCalled();
    });
});
