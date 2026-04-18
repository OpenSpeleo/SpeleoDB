/**
 * Tests for forms/modals.js (FormModals namespace).
 */

/* global FormModals */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const JQUERY_SRC = readFileSync(resolve(__dirname, '..', '..', '..', '..', '..', 'frontend_public', 'static', 'js', 'vendors', 'jquery-3.7.1.js'), 'utf-8');
const MODALS_SRC = readFileSync(resolve(__dirname, 'modals.js'), 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(MODALS_SRC);
});

function setupThreeModals() {
    document.body.innerHTML = `
        <div id="modal_success" style="display: none;"><span id="modal_success_txt"></span></div>
        <div id="modal_error" style="display: none;"><span id="modal_error_txt"></span></div>
        <div id="modal_confirmation" style="display: none;"></div>
    `;
}

describe('FormModals', () => {
    beforeEach(setupThreeModals);
    afterEach(() => { document.body.innerHTML = ''; });

    it('showSuccess renders text and flex-displays modal_success', () => {
        FormModals.showSuccess('<b>Done!</b>');
        expect(document.getElementById('modal_success').style.display).toBe('flex');
        expect(document.getElementById('modal_success_txt').innerHTML).toBe('<b>Done!</b>');
    });

    it('showError renders text and flex-displays modal_error', () => {
        FormModals.showError('Oops');
        expect(document.getElementById('modal_error').style.display).toBe('flex');
        expect(document.getElementById('modal_error_txt').innerHTML).toBe('Oops');
    });

    it('showConfirmation flex-displays modal_confirmation', () => {
        FormModals.showConfirmation();
        expect(document.getElementById('modal_confirmation').style.display).toBe('flex');
    });

    it('hideConfirmation hides modal_confirmation', () => {
        FormModals.showConfirmation();
        FormModals.hideConfirmation();
        expect(document.getElementById('modal_confirmation').style.display).toBe('none');
    });

    it('hideAll hides every managed modal', () => {
        FormModals.showSuccess('x');
        FormModals.showError('y');
        FormModals.showConfirmation();
        FormModals.hideAll();
        expect(document.getElementById('modal_success').style.display).toBe('none');
        expect(document.getElementById('modal_error').style.display).toBe('none');
        expect(document.getElementById('modal_confirmation').style.display).toBe('none');
    });

    it('bindAutoDismiss hides visible modals on body click', () => {
        FormModals.bindAutoDismiss();
        FormModals.showSuccess('x');
        FormModals.showError('y');
        FormModals.showConfirmation();

        // Trigger a body click
        document.body.dispatchEvent(new Event('click', { bubbles: true }));

        expect(document.getElementById('modal_success').style.display).toBe('none');
        expect(document.getElementById('modal_error').style.display).toBe('none');
        expect(document.getElementById('modal_confirmation').style.display).toBe('none');
    });
});
