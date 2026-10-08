import type { Mock } from 'vitest';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

/**
 * Tests for forms/entity_crud_form.ts - shared new/edit JSON-CRUD form wiring.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { attachEntityCrudForm } from './entity_crud_form.ts';
import { FormModals } from './modals.ts';

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
        <form id="my_form">
            <input type="hidden" name="csrfmiddlewaretoken" value="csrf-xyz" />
            <input name="name" value="Alice" />
            <input name="description" value="Hi there" />
            <button id="btn_submit">Save</button>
        </form>
        <div id="error_div" style="display: none;"></div>
        <div id="success_div" style="display: none;"></div>
        <div id="modal_success" style="display: none;"><span id="modal_success_txt"></span></div>
        <div id="modal_error" style="display: none;"><span id="modal_error_txt"></span></div>
    `;
}

describe('attachEntityCrudForm', () => {
    let originalAjax: FormTestJQuery['ajax'];
    let originalLocation: Location;
    let locationHrefSpy: Mock<(value: unknown) => void>;
    let reloadSpy: Mock<() => void>;

    beforeEach(() => {
        vi.useFakeTimers();
        setupPage();
        originalAjax = jqueryHost.jQuery.ajax;
        originalLocation = window.location;
        locationHrefSpy = vi.fn();
        reloadSpy = vi.fn();
        Object.defineProperty(window, 'location', {
            writable: true,
            value: new Proxy({ href: '', reload: reloadSpy }, {
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

    it('requires formId and endpoint', () => {
        expect(() => attachEntityCrudForm({ endpoint: '/x' })).toThrow(/formId/);
        expect(() => attachEntityCrudForm({ formId: 'my_form' })).toThrow(/endpoint/);
    });

    it('POSTs JSON-stringified form data and fires redirect', () => {
        const $ = jqueryHost.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            opts.success({ id: 'new-1' });
            return {};
        });

        attachEntityCrudForm({
            formId: 'my_form',
            endpoint: '/api/v2/teams/',
            method: 'POST',
            successMessage: 'Created!',
            successRedirect: '/teams',
            redirectDelayMs: 500,
        });

        (document.getElementById('btn_submit') as HTMLElement).click();

        expect($.ajax).toHaveBeenCalledTimes(1);
        const call = $.ajax.mock.calls[0]![0];
        expect(call.url).toBe('/api/v2/teams/');
        expect(call.method).toBe('POST');
        const parsed = JSON.parse(call.data!) as { user?: string };
        expect(parsed).toEqual({
            csrfmiddlewaretoken: 'csrf-xyz',
            name: 'Alice',
            description: 'Hi there',
        });

        expect((document.getElementById('modal_success') as HTMLElement).style.display).toBe('flex');
        vi.advanceTimersByTime(500);
        expect(locationHrefSpy).toHaveBeenCalledWith('/teams');
    });

    it('fires redirectFromResponse instead of static redirect when provided', () => {
        const $ = jqueryHost.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            opts.success({ id: 'xxx' });
            return {};
        });

        attachEntityCrudForm({
            formId: 'my_form',
            endpoint: '/api/v2/teams/',
            successMessage: 'Created!',
            redirectFromResponse: (resp: { id: string }) => `/teams/${resp.id}`,
            redirectDelayMs: 0,
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        vi.advanceTimersByTime(0);
        expect(locationHrefSpy).toHaveBeenCalledWith('/teams/xxx');
    });

    it('reloadOnSuccess triggers window.location.reload', () => {
        const $ = jqueryHost.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            opts.success({});
            return {};
        });

        attachEntityCrudForm({
            formId: 'my_form',
            endpoint: '/api/v2/whatever/',
            method: 'PATCH',
            successMessage: 'Saved.',
            reloadOnSuccess: true,
            redirectDelayMs: 0,
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        vi.advanceTimersByTime(0);
        expect(reloadSpy).toHaveBeenCalledTimes(1);
    });

    it('beforeSubmit returning false cancels the request', () => {
        const $ = jqueryHost.jQuery;
        $.ajax = vi.fn();

        attachEntityCrudForm({
            formId: 'my_form',
            endpoint: '/api/v2/teams/',
            successMessage: 'Created!',
            beforeSubmit: () => {
                FormModals.showError('Validation failed');
                return false;
            },
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        expect($.ajax).not.toHaveBeenCalled();
        expect((document.getElementById('modal_error') as HTMLElement).style.display).toBe('flex');
    });

    it('renders AJAX error via showAjaxErrorModal on failure', () => {
        const $ = jqueryHost.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            opts.error({ responseJSON: { error: 'bad' }, status: 400, statusText: 'Bad' });
            return {};
        });

        attachEntityCrudForm({
            formId: 'my_form',
            endpoint: '/api/v2/teams/',
            successMessage: 'Created!',
            successRedirect: '/list',
            redirectDelayMs: 10,
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        expect((document.getElementById('modal_error') as HTMLElement).style.display).toBe('flex');
        expect((document.getElementById('modal_error_txt') as HTMLElement).textContent).toBe('bad');
        vi.advanceTimersByTime(100);
        expect(locationHrefSpy).not.toHaveBeenCalled();
    });

    it('invokes custom serialize callback when provided', () => {
        const $ = jqueryHost.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            opts.success({});
            return {};
        });

        attachEntityCrudForm({
            formId: 'my_form',
            endpoint: '/api/v2/whatever/',
            successMessage: 'OK',
            serialize: (payload) => JSON.stringify({ ...payload, extra: true }),
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        const call = $.ajax.mock.calls[0]![0];
        expect(JSON.parse(call.data!) as unknown).toEqual({
            csrfmiddlewaretoken: 'csrf-xyz',
            name: 'Alice',
            description: 'Hi there',
            extra: true,
        });
    });
});
