import type { Mock } from 'vitest';

/**
 * Tests for forms/entity_crud_form.ts - shared new/edit JSON-CRUD form wiring.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { attachEntityCrudForm } from './entity_crud_form.ts';
import { FormModals } from './modals.ts';


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
    let originalLocation: Location;
    let locationHrefSpy: Mock<(value: unknown) => void>;
    let reloadSpy: Mock<() => void>;

    beforeEach(() => {
        vi.useFakeTimers();
        setupPage();
        originalLocation = window.location;
        locationHrefSpy = vi.fn();
        reloadSpy = vi.fn();
        // JSDOM cannot perform navigation; observe only the unavailable navigation boundary.
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
        Object.defineProperty(window, 'location', {
            configurable: true,
            writable: true,
            value: originalLocation,
        });
        vi.useRealTimers();
        document.body.innerHTML = '';
    });

    it('requires formId and a submit callback', () => {
        expect(() => attachEntityCrudForm({ submit: async () => ({}) })).toThrow(/formId/);
        expect(() => attachEntityCrudForm({ formId: 'my_form' } as never)).toThrow(/submit/);
    });

    it('passes form values to the operation callback and fires redirect', async () => {
        const submit = vi.fn(async (_payload: Record<string, unknown>) => ({ id: 'new-1' }));

        attachEntityCrudForm({
            formId: 'my_form',
            submit,
            successMessage: 'Created!',
            successRedirect: '/teams',
            redirectDelayMs: 500,
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        await vi.advanceTimersByTimeAsync(0);

        expect(submit).toHaveBeenCalledTimes(1);
        expect(submit.mock.calls[0]?.[0]).toEqual({
            csrfmiddlewaretoken: 'csrf-xyz',
            name: 'Alice',
            description: 'Hi there',
        });

        expect((document.getElementById('modal_success') as HTMLElement).style.display).toBe('flex');
        vi.advanceTimersByTime(500);
        expect(locationHrefSpy).toHaveBeenCalledWith('/teams');
    });

    it('fires redirectFromResponse instead of static redirect when provided', async () => {
        const submit = vi.fn(async (_payload: Record<string, unknown>) => ({ id: 'xxx' }));

        attachEntityCrudForm({
            formId: 'my_form',
            submit,
            successMessage: 'Created!',
            redirectFromResponse: (resp: { id: string }) => `/teams/${resp.id}`,
            redirectDelayMs: 0,
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        await vi.advanceTimersByTimeAsync(0);
        vi.advanceTimersByTime(0);
        expect(locationHrefSpy).toHaveBeenCalledWith('/teams/xxx');
    });

    it('reloadOnSuccess triggers window.location.reload', async () => {
        const submit = vi.fn(async (_payload: Record<string, unknown>) => ({}));

        attachEntityCrudForm({
            formId: 'my_form',
            submit,
            successMessage: 'Saved.',
            reloadOnSuccess: true,
            redirectDelayMs: 0,
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        await vi.advanceTimersByTimeAsync(0);
        vi.advanceTimersByTime(0);
        expect(reloadSpy).toHaveBeenCalledTimes(1);
    });

    it('beforeSubmit returning false cancels the request', async () => {
        const submit = vi.fn(async (_payload: Record<string, unknown>) => ({}));

        attachEntityCrudForm({
            formId: 'my_form',
            submit,
            successMessage: 'Created!',
            beforeSubmit: () => {
                FormModals.showError('Validation failed');
                return false;
            },
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        await vi.advanceTimersByTimeAsync(0);
        expect(submit).not.toHaveBeenCalled();
        expect((document.getElementById('modal_error') as HTMLElement).style.display).toBe('flex');
    });

    it('renders the rejected operation error without redirecting', async () => {
        const submit = vi.fn(async (_payload: Record<string, unknown>) => { throw Object.assign(new Error('bad'), { data: { error: 'bad' }, status: 400 }); });

        attachEntityCrudForm({
            formId: 'my_form',
            submit,
            successMessage: 'Created!',
            successRedirect: '/list',
            redirectDelayMs: 10,
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        await vi.advanceTimersByTimeAsync(0);
        expect((document.getElementById('modal_error') as HTMLElement).style.display).toBe('flex');
        expect((document.getElementById('modal_error_txt') as HTMLElement).textContent).toBe('bad');
        vi.advanceTimersByTime(100);
        expect(locationHrefSpy).not.toHaveBeenCalled();
    });

    it('invokes custom prepare callback before the operation', async () => {
        const submit = vi.fn(async (_payload: Record<string, unknown>) => ({}));

        attachEntityCrudForm({
            formId: 'my_form',
            submit,
            successMessage: 'OK',
            prepare: (payload) => ({ ...payload, extra: true }),
        });

        (document.getElementById('btn_submit') as HTMLElement).click();
        await vi.advanceTimersByTimeAsync(0);
        expect(submit.mock.calls[0]?.[0]).toEqual({
            csrfmiddlewaretoken: 'csrf-xyz',
            name: 'Alice',
            description: 'Hi there',
            extra: true,
        });
    });

    it('blocks duplicate submissions until the configured operation settles', async () => {
        let finish!: (value: unknown) => void;
        const submit = vi.fn(() => new Promise(resolve => { finish = resolve; }));
        const onPendingChange = vi.fn();
        attachEntityCrudForm({ formId: 'my_form', submit, onPendingChange });
        const button = document.getElementById('btn_submit') as HTMLElement;
        button.click();
        button.click();
        await vi.advanceTimersByTimeAsync(0);
        expect(submit).toHaveBeenCalledOnce();
        expect(onPendingChange.mock.calls).toEqual([[true]]);
        finish({});
        await vi.advanceTimersByTimeAsync(0);
        expect(onPendingChange.mock.calls).toEqual([[true], [false]]);
        button.click();
        await vi.advanceTimersByTimeAsync(0);
        expect(submit).toHaveBeenCalledTimes(2);
        finish({});
        await vi.advanceTimersByTimeAsync(0);
    });

    it('releases pending state when request preparation throws synchronously', async () => {
        const failure = new Error('Invalid request');
        const onError = vi.fn();
        const onPendingChange = vi.fn();
        attachEntityCrudForm({
            formId: 'my_form', submit: () => { throw failure; }, onError, onPendingChange,
        });
        (document.getElementById('btn_submit') as HTMLElement).click();
        await vi.advanceTimersByTimeAsync(0);
        expect(onError).toHaveBeenCalledWith(failure);
        expect(onPendingChange.mock.calls).toEqual([[true], [false]]);
    });
});
