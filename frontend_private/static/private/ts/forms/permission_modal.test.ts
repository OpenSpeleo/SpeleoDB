import type { Mock } from 'vitest';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

/**
 * Tests for forms/permission_modal.ts - user permission Add / Edit / Delete modal.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { attachPermissionModal } from './permission_modal.ts';

// Use the real vendor and the public operation callbacks.
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };

const operations = {
    create: vi.fn(async (_payload: Record<string, unknown>) => ({})),
    update: vi.fn(async (_payload: Record<string, unknown>) => ({})),
    remove: vi.fn(async (_payload: Record<string, unknown>) => ({})),
};

const __dirname = dirname(fileURLToPath(import.meta.url));

const JQUERY_SRC = readFileSync(resolve(__dirname, '..', '..', '..', '..', '..', 'frontend_public', 'static', 'ts', 'vendors', 'jquery-3.7.1.js'), 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
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
        let originalLocation: Location;
    let reloadSpy: Mock<() => void>;

    beforeEach(() => {
        vi.useFakeTimers();
        setupPage();
        vi.clearAllMocks();
            originalLocation = window.location;
        reloadSpy = vi.fn();
        // JSDOM cannot navigate; observe the unavailable reload boundary only.
        Object.defineProperty(window, 'location', {
            writable: true,
            value: { href: '', reload: reloadSpy },
        });
    });

    afterEach(() => {
            Object.defineProperty(window, 'location', {
            configurable: true,
            writable: true,
            value: originalLocation,
        });
        vi.useRealTimers();
        document.body.innerHTML = '';
    });

    it('requires operation callbacks', () => {
        expect(() => attachPermissionModal({} as never)).toThrow(/operations/);
    });

    it('Add button opens modal in POST mode', () => {
        attachPermissionModal({
            operations,
            addModalTitle: 'Add X',
        });
        (document.getElementById('btn_open_add_user') as HTMLElement).click();

        const modal = (document.getElementById('permission_modal') as HTMLElement);
        expect(modal.style.display).toBe('flex');
        expect((document.getElementById('permission_modal_title') as HTMLElement).textContent).toBe('Add X');
        const form = jqueryHost.jQuery('#permission_form');
        expect(form.data('method')).toBe('POST');
        expect((document.getElementById('user') as HTMLInputElement).readOnly).toBe(false);
    });

    it('Edit button opens modal in PUT mode and prefills user+level', () => {
        attachPermissionModal({
            operations,
            editModalTitle: 'Edit X',
        });
        document.querySelector<HTMLElement>('.btn_open_edit_perm')!.click();

        expect((document.getElementById('permission_modal') as HTMLElement).style.display).toBe('flex');
        expect((document.getElementById('permission_modal_title') as HTMLElement).textContent).toBe('Edit X');
        const form = jqueryHost.jQuery('#permission_form');
        expect(form.data('method')).toBe('PUT');
        expect((document.getElementById('user') as HTMLInputElement).value).toBe('alice@example.com');
        expect((document.getElementById('user') as HTMLInputElement).readOnly).toBe(true);
        expect((document.getElementById('level') as HTMLSelectElement).value).toBe('READ_ONLY');
    });

    it('btn_submit_add rejects invalid email', () => {

        attachPermissionModal({
            operations,
        });
        (document.getElementById('btn_open_add_user') as HTMLElement).click();
        (document.getElementById('user') as HTMLInputElement).value = 'not-an-email';
        (document.getElementById('level') as HTMLSelectElement).value = 'READ_ONLY';
        (document.getElementById('btn_submit_add') as HTMLElement).click();

        expect((document.getElementById('modal_error') as HTMLElement).style.display).toBe('flex');
        expect((document.getElementById('modal_error_txt') as HTMLElement).innerHTML).toContain('Email');
    });

    it('btn_submit_add rejects empty level', () => {
        attachPermissionModal({
            operations,
            fieldLabel: 'Access Level',
        });
        (document.getElementById('btn_open_add_user') as HTMLElement).click();
        (document.getElementById('user') as HTMLInputElement).value = 'ok@example.com';
        (document.getElementById('level') as HTMLSelectElement).value = '';
        (document.getElementById('btn_submit_add') as HTMLElement).click();

        expect((document.getElementById('modal_error') as HTMLElement).style.display).toBe('flex');
        expect((document.getElementById('modal_error_txt') as HTMLElement).innerHTML).toContain('Access Level');
    });

    it('btn_submit_add creates permission and reloads on success', async () => {

        attachPermissionModal({
            operations,
            reloadDelayMs: 100,
        });
        (document.getElementById('btn_open_add_user') as HTMLElement).click();
        (document.getElementById('user') as HTMLInputElement).value = 'new@example.com';
        (document.getElementById('level') as HTMLSelectElement).value = 'READ_AND_WRITE';
        (document.getElementById('btn_submit_add') as HTMLElement).click();

        expect(operations.create).toHaveBeenCalledWith({ user: 'new@example.com', level: 'READ_AND_WRITE' });
        await vi.advanceTimersByTimeAsync(0);
        expect((document.getElementById('modal_success') as HTMLElement).style.display).toBe('flex');
        vi.advanceTimersByTime(100);
        expect(reloadSpy).toHaveBeenCalledTimes(1);
    });

    it('btn_delete_perm removes permission for the target user', () => {

        attachPermissionModal({
            operations,
            reloadDelayMs: 0,
        });
        document.querySelector<HTMLElement>('.btn_delete_perm')!.click();

        expect(operations.remove).toHaveBeenCalledWith({ user: 'alice@example.com' });
    });

    it('btn_close hides the permission modal', () => {
        attachPermissionModal({
            operations,
        });
        (document.getElementById('btn_open_add_user') as HTMLElement).click();
        expect((document.getElementById('permission_modal') as HTMLElement).style.display).toBe('flex');

        document.querySelector<HTMLElement>('.btn_close')!.click();
        expect((document.getElementById('permission_modal') as HTMLElement).style.display).toBe('none');
    });
});
