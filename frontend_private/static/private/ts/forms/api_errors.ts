/**
 * Shared generated-API error presentation for Django/DRF-backed forms.
 * Reads the adapter's untrusted data/status/message fields, escapes serializer
 * validation output, and shows the shared error modal. Requires jQuery.
 */

import { escapeHtml } from '../xss-helpers.ts';

export function showApiErrorModal(error: unknown): void {
    const xhr = error && typeof error === 'object' ? error as { data?: unknown; status?: number; message?: string; statusText?: string } : {};
    const errorKeys = ['error', 'errors', 'detail'];
    let found = false;

    try {
        // Assertions retain the existing unchecked DRF/body and thrown-error contracts.
        const body = xhr.data as Record<string, unknown> | null | undefined;
        if (body) {
            for (const key of errorKeys) {
                if (key in body) {
                    const value = body[key];
                    if (key === 'errors' && value && typeof value === 'object') {
                        let html = '';
                        for (const fieldName in value) {
                            const fieldErrors = (value as Record<string, unknown>)[fieldName];
                            if (Array.isArray(fieldErrors)) {
                                html += '<b>' + escapeHtml(fieldName) + ':</b><br>';
                                fieldErrors.forEach(function (err) {
                                    html += '- ' + escapeHtml(err) + '<br>';
                                });
                            } else {
                                html += '- <b>Error:</b> `' + escapeHtml(fieldName) + '`: ';
                                html += escapeHtml(fieldErrors) + '<br>';
                            }
                        }
                        $('#modal_error_txt').html(html);
                    } else {
                        $('#modal_error_txt').text(typeof value === 'string' ? value : JSON.stringify(value));
                    }
                    found = true;
                    break;
                }
            }

            if (!found) {
                // Fallback: render the body key-by-key
                let html = '';
                for (const fieldName in body) {
                    const fieldErrors = body[fieldName];
                    if (Array.isArray(fieldErrors)) {
                        html += '<b>' + escapeHtml(fieldName) + ':</b><br>';
                        fieldErrors.forEach(function (err) {
                            html += '- ' + escapeHtml(err) + '<br>';
                        });
                    } else if (typeof fieldErrors === 'string') {
                        html += '<b>' + escapeHtml(fieldName) + ':</b> ' + escapeHtml(fieldErrors) + '<br>';
                    } else if (typeof fieldErrors === 'object' && fieldErrors !== null) {
                        html += '<b>' + escapeHtml(fieldName) + ':</b><br>';
                        for (const sub in fieldErrors) {
                            html += '- ' + escapeHtml(sub) + ': ' + escapeHtml((fieldErrors as Record<string, unknown>)[sub]) + '<br>';
                        }
                    }
                }
                if (html) {
                    $('#modal_error_txt').html(html);
                    found = true;
                }
            }
        }

        if (!found) {
            throw new Error('No Error Key Found');
        }
    } catch (exception) {
        const fallback = '<b>[Status ' + escapeHtml(String(xhr.status)) + '] An error occurred:</b> `'
            + escapeHtml(String(xhr.message || xhr.statusText || '')) + '`<br>'
            + 'Please email: <a class="underline" href="mailto:contact@speleodb.org">contact@speleodb.org</a>';
        if (typeof console !== 'undefined' && console.error) {
            console.error(fallback, (exception as Error).message);
        }
        $('#modal_error_txt').html(fallback);
    } finally {
        $('#modal_error').css('display', 'flex');
    }
}
