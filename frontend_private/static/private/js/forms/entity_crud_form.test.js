/**
 * Tests for forms/entity_crud_form.js - shared new/edit JSON-CRUD form wiring.
 */

/* global attachEntityCrudForm, FormModals */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const JQUERY_SRC = readFileSync(resolve(__dirname, '..', '..', '..', '..', '..', 'frontend_public', 'static', 'js', 'vendors', 'jquery-3.7.1.js'), 'utf-8');
const XSS_SRC = readFileSync(resolve(__dirname, '..', 'xss-helpers.js'), 'utf-8');
const MODALS_SRC = readFileSync(resolve(__dirname, 'modals.js'), 'utf-8');
const AJAX_ERRORS_SRC = readFileSync(resolve(__dirname, 'ajax_errors.js'), 'utf-8');
const ENTITY_SRC = readFileSync(resolve(__dirname, 'entity_crud_form.js'), 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(XSS_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(MODALS_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(AJAX_ERRORS_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(ENTITY_SRC);
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
    let originalAjax;
    let originalLocation;
    let locationHrefSpy;
    let reloadSpy;

    beforeEach(() => {
        vi.useFakeTimers();
        setupPage();
        originalAjax = globalThis.jQuery.ajax;
        originalLocation = window.location;
        locationHrefSpy = vi.fn();
        reloadSpy = vi.fn();
        Object.defineProperty(window, 'location', {
            writable: true,
            value: new Proxy({ href: '', reload: reloadSpy }, {
                set(target, prop, value) {
                    target[prop] = value;
                    if (prop === 'href') { locationHrefSpy(value); }
                    return true;
                },
                get(target, prop) { return target[prop]; },
            }),
        });
    });

    afterEach(() => {
        globalThis.jQuery.ajax = originalAjax;
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
        const $ = globalThis.jQuery;
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

        document.getElementById('btn_submit').click();

        expect($.ajax).toHaveBeenCalledTimes(1);
        const call = $.ajax.mock.calls[0][0];
        expect(call.url).toBe('/api/v2/teams/');
        expect(call.method).toBe('POST');
        const parsed = JSON.parse(call.data);
        expect(parsed).toEqual({
            csrfmiddlewaretoken: 'csrf-xyz',
            name: 'Alice',
            description: 'Hi there',
        });

        expect(document.getElementById('modal_success').style.display).toBe('flex');
        vi.advanceTimersByTime(500);
        expect(locationHrefSpy).toHaveBeenCalledWith('/teams');
    });

    it('fires redirectFromResponse instead of static redirect when provided', () => {
        const $ = globalThis.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            opts.success({ id: 'xxx' });
            return {};
        });

        attachEntityCrudForm({
            formId: 'my_form',
            endpoint: '/api/v2/teams/',
            successMessage: 'Created!',
            redirectFromResponse: (resp) => `/teams/${resp.id}`,
            redirectDelayMs: 0,
        });

        document.getElementById('btn_submit').click();
        vi.advanceTimersByTime(0);
        expect(locationHrefSpy).toHaveBeenCalledWith('/teams/xxx');
    });

    it('reloadOnSuccess triggers window.location.reload', () => {
        const $ = globalThis.jQuery;
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

        document.getElementById('btn_submit').click();
        vi.advanceTimersByTime(0);
        expect(reloadSpy).toHaveBeenCalledTimes(1);
    });

    it('beforeSubmit returning false cancels the request', () => {
        const $ = globalThis.jQuery;
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

        document.getElementById('btn_submit').click();
        expect($.ajax).not.toHaveBeenCalled();
        expect(document.getElementById('modal_error').style.display).toBe('flex');
    });

    it('renders AJAX error via showAjaxErrorModal on failure', () => {
        const $ = globalThis.jQuery;
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

        document.getElementById('btn_submit').click();
        expect(document.getElementById('modal_error').style.display).toBe('flex');
        expect(document.getElementById('modal_error_txt').textContent).toBe('bad');
        vi.advanceTimersByTime(100);
        expect(locationHrefSpy).not.toHaveBeenCalled();
    });

    it('invokes custom serialize callback when provided', () => {
        const $ = globalThis.jQuery;
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

        document.getElementById('btn_submit').click();
        const call = $.ajax.mock.calls[0][0];
        expect(JSON.parse(call.data)).toEqual({
            csrfmiddlewaretoken: 'csrf-xyz',
            name: 'Alice',
            description: 'Hi there',
            extra: true,
        });
    });
});
