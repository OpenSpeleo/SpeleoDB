/**
 * Tests for forms/permission_modal.js - user permission Add / Edit / Delete modal.
 */

/* global attachPermissionModal */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const JQUERY_SRC = readFileSync(resolve(__dirname, '..', '..', '..', '..', '..', 'frontend_public', 'static', 'js', 'vendors', 'jquery-3.7.1.js'), 'utf-8');
const XSS_SRC = readFileSync(resolve(__dirname, '..', 'xss-helpers.js'), 'utf-8');
const AUTOCOMPLETE_SRC = readFileSync(resolve(__dirname, '..', 'user_autocomplete.js'), 'utf-8');
const MODALS_SRC = readFileSync(resolve(__dirname, 'modals.js'), 'utf-8');
const AJAX_ERRORS_SRC = readFileSync(resolve(__dirname, 'ajax_errors.js'), 'utf-8');
const PERM_SRC = readFileSync(resolve(__dirname, 'permission_modal.js'), 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(XSS_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(AUTOCOMPLETE_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(MODALS_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(AJAX_ERRORS_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(PERM_SRC);
});

function setupPage() {
    document.body.innerHTML = `
        <input type="hidden" name="csrfmiddlewaretoken" value="csrf-perm" />
        <button id="btn_open_add_user">Add</button>
        <button class="btn_open_edit_perm" data-user="alice@example.com" data-level="READ_ONLY">Edit</button>
        <button class="btn_delete_perm" data-user="alice@example.com">Delete</button>
        <button class="btn_close">Close</button>
        <div id="permission_modal" style="display: none;">
            <h2 id="permission_modal_title"></h2>
            <h3 id="permission_modal_header"></h3>
            <form id="permission_form">
                <input id="user" name="user" />
                <input id="user_suggestions" />
                <select id="level" name="level">
                    <option value=""></option>
                    <option value="READ_ONLY">RO</option>
                    <option value="READ_AND_WRITE">RW</option>
                </select>
                <button id="btn_submit_add">Submit</button>
            </form>
        </div>
        <div id="error_div" style="display: none;"></div>
        <div id="success_div" style="display: none;"></div>
        <div id="modal_success" style="display: none;"><span id="modal_success_txt"></span></div>
        <div id="modal_error" style="display: none;"><span id="modal_error_txt"></span></div>
    `;
}

describe('attachPermissionModal', () => {
    let originalAjax;
    let originalLocation;
    let reloadSpy;

    beforeEach(() => {
        vi.useFakeTimers();
        setupPage();
        originalAjax = globalThis.jQuery.ajax;
        originalLocation = window.location;
        reloadSpy = vi.fn();
        Object.defineProperty(window, 'location', {
            writable: true,
            value: { href: '', reload: reloadSpy },
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

    it('requires endpoint and autocompleteUrl', () => {
        expect(() => attachPermissionModal({ autocompleteUrl: '/a' })).toThrow(/endpoint/);
        expect(() => attachPermissionModal({ endpoint: '/p' })).toThrow(/autocompleteUrl/);
    });

    it('Add button opens modal in POST mode', () => {
        attachPermissionModal({
            endpoint: '/api/v2/projects/x/permission/user/detail/',
            autocompleteUrl: '/api/v2/user/autocomplete/',
            addModalTitle: 'Add X',
        });
        document.getElementById('btn_open_add_user').click();

        const modal = document.getElementById('permission_modal');
        expect(modal.style.display).toBe('flex');
        expect(document.getElementById('permission_modal_title').textContent).toBe('Add X');
        const form = globalThis.jQuery('#permission_form');
        expect(form.data('method')).toBe('POST');
        expect(document.getElementById('user').readOnly).toBe(false);
    });

    it('Edit button opens modal in PUT mode and prefills user+level', () => {
        attachPermissionModal({
            endpoint: '/api/v2/projects/x/permission/user/detail/',
            autocompleteUrl: '/api/v2/user/autocomplete/',
            editModalTitle: 'Edit X',
        });
        document.querySelector('.btn_open_edit_perm').click();

        expect(document.getElementById('permission_modal').style.display).toBe('flex');
        expect(document.getElementById('permission_modal_title').textContent).toBe('Edit X');
        const form = globalThis.jQuery('#permission_form');
        expect(form.data('method')).toBe('PUT');
        expect(document.getElementById('user').value).toBe('alice@example.com');
        expect(document.getElementById('user').readOnly).toBe(true);
        expect(document.getElementById('level').value).toBe('READ_ONLY');
    });

    it('btn_submit_add rejects invalid email', () => {
        const $ = globalThis.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            // beforeSend returns false -> success/error not called
            return { abort: vi.fn() };
        });

        attachPermissionModal({
            endpoint: '/api/v2/projects/x/permission/user/detail/',
            autocompleteUrl: '/api/v2/user/autocomplete/',
        });
        document.getElementById('btn_open_add_user').click();
        document.getElementById('user').value = 'not-an-email';
        document.getElementById('level').value = 'READ_ONLY';
        document.getElementById('btn_submit_add').click();

        expect(document.getElementById('modal_error').style.display).toBe('flex');
        expect(document.getElementById('modal_error_txt').innerHTML).toContain('Email');
    });

    it('btn_submit_add rejects empty level', () => {
        attachPermissionModal({
            endpoint: '/api/v2/projects/x/permission/user/detail/',
            autocompleteUrl: '/api/v2/user/autocomplete/',
            fieldLabel: 'Access Level',
        });
        document.getElementById('btn_open_add_user').click();
        document.getElementById('user').value = 'ok@example.com';
        document.getElementById('level').value = '';
        document.getElementById('btn_submit_add').click();

        expect(document.getElementById('modal_error').style.display).toBe('flex');
        expect(document.getElementById('modal_error_txt').innerHTML).toContain('Access Level');
    });

    it('btn_submit_add POSTs and reloads on success', () => {
        const $ = globalThis.jQuery;
        $.ajax = vi.fn((opts) => {
            // beforeSend validates
            const allow = opts.beforeSend({ setRequestHeader: () => true });
            if (allow !== false) { opts.success({}); }
            return {};
        });

        attachPermissionModal({
            endpoint: '/api/v2/projects/x/permission/user/detail/',
            autocompleteUrl: '/api/v2/user/autocomplete/',
            reloadDelayMs: 100,
        });
        document.getElementById('btn_open_add_user').click();
        document.getElementById('user').value = 'new@example.com';
        document.getElementById('level').value = 'READ_AND_WRITE';
        document.getElementById('btn_submit_add').click();

        expect($.ajax).toHaveBeenCalledTimes(1);
        const call = $.ajax.mock.calls[0][0];
        expect(call.method).toBe('POST');
        expect(document.getElementById('modal_success').style.display).toBe('flex');
        vi.advanceTimersByTime(100);
        expect(reloadSpy).toHaveBeenCalledTimes(1);
    });

    it('btn_delete_perm DELETEs for the target user', () => {
        const $ = globalThis.jQuery;
        $.ajax = vi.fn((opts) => {
            opts.beforeSend({ setRequestHeader: () => true });
            opts.success({});
            return {};
        });

        attachPermissionModal({
            endpoint: '/api/v2/projects/x/permission/user/detail/',
            autocompleteUrl: '/api/v2/user/autocomplete/',
            reloadDelayMs: 0,
        });
        document.querySelector('.btn_delete_perm').click();

        expect($.ajax).toHaveBeenCalledTimes(1);
        const call = $.ajax.mock.calls[0][0];
        expect(call.method).toBe('DELETE');
        const parsed = JSON.parse(call.data);
        expect(parsed.user).toBe('alice@example.com');
    });

    it('btn_close hides the permission modal', () => {
        attachPermissionModal({
            endpoint: '/api/v2/projects/x/permission/user/detail/',
            autocompleteUrl: '/api/v2/user/autocomplete/',
        });
        document.getElementById('btn_open_add_user').click();
        expect(document.getElementById('permission_modal').style.display).toBe('flex');

        document.querySelector('.btn_close').click();
        expect(document.getElementById('permission_modal').style.display).toBe('none');
    });
});
