/**
 * Tests for forms/ajax_errors.js - shared DRF error-modal rendering.
 *
 * Loads real jQuery, xss-helpers.js, and ajax_errors.js via readFileSync so
 * we exercise the production module.
 */

/* global showAjaxErrorModal */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const JQUERY_SRC = readFileSync(resolve(__dirname, '..', '..', '..', '..', '..', 'frontend_public', 'static', 'js', 'vendors', 'jquery-3.7.1.js'), 'utf-8');
const XSS_SRC = readFileSync(resolve(__dirname, '..', 'xss-helpers.js'), 'utf-8');
const AJAX_ERRORS_SRC = readFileSync(resolve(__dirname, 'ajax_errors.js'), 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(XSS_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(AJAX_ERRORS_SRC);
});

function setupModal() {
    document.body.innerHTML = `
        <div id="modal_error" style="display: none;">
            <span id="modal_error_txt"></span>
        </div>
    `;
}

describe('showAjaxErrorModal', () => {
    beforeEach(setupModal);
    afterEach(() => { document.body.innerHTML = ''; });

    it('shows the error modal with a single-key error', () => {
        showAjaxErrorModal({ responseJSON: { error: 'Boom' }, status: 500, statusText: 'Server Error' });
        expect(document.getElementById('modal_error').style.display).toBe('flex');
        expect(document.getElementById('modal_error_txt').textContent).toBe('Boom');
    });

    it('shows a detail message', () => {
        showAjaxErrorModal({ responseJSON: { detail: 'Auth required' }, status: 403, statusText: 'Forbidden' });
        expect(document.getElementById('modal_error_txt').textContent).toBe('Auth required');
    });

    it('handles DRF errors:{field:[msgs]} shape', () => {
        showAjaxErrorModal({
            responseJSON: { errors: { name: ['too short', 'required'] } },
            status: 400,
            statusText: 'Bad Request',
        });
        const html = document.getElementById('modal_error_txt').innerHTML;
        // Array-shaped field errors render as "<b>field:</b><br>- msg<br>..."
        expect(html).toContain('<b>name:</b>');
        expect(html).toContain('too short');
        expect(html).toContain('required');
    });

    it('handles DRF errors:{field:"msg"} shape (non-array value)', () => {
        showAjaxErrorModal({
            responseJSON: { errors: { name: 'duplicate' } },
            status: 400,
            statusText: 'Bad Request',
        });
        const html = document.getElementById('modal_error_txt').innerHTML;
        // Non-array field error falls through to the "- <b>Error:</b> `field`: msg" branch.
        expect(html).toContain('<b>Error:</b>');
        expect(html).toContain('name');
        expect(html).toContain('duplicate');
    });

    it('escapes XSS payloads in errors', () => {
        showAjaxErrorModal({
            responseJSON: { error: '<img src=x onerror=alert(1)>' },
            status: 400,
            statusText: 'Bad Request',
        });
        const el = document.getElementById('modal_error_txt');
        // Using `.text()` path -> textContent reflects escaped rendering
        expect(el.textContent).toContain('<img');
        // No actual <img> child node
        expect(el.querySelectorAll('img').length).toBe(0);
    });

    it('falls back to field-by-field rendering when no known key is present', () => {
        showAjaxErrorModal({
            responseJSON: { price: ['must be positive'] },
            status: 400,
            statusText: 'Bad Request',
        });
        const html = document.getElementById('modal_error_txt').innerHTML;
        expect(html).toContain('<b>price');
        expect(html).toContain('must be positive');
    });

    it('shows a generic fallback when responseJSON is empty', () => {
        showAjaxErrorModal({ responseJSON: null, status: 500, statusText: 'Server Error' });
        const html = document.getElementById('modal_error_txt').innerHTML;
        expect(html).toContain('Status 500');
        expect(html).toContain('Server Error');
    });
});
