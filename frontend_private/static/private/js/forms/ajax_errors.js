/**
 * Shared AJAX error handling for Django/DRF-backed forms.
 *
 * Replaces the inline `{% include 'snippets/ajax_error_modal_management.js' %}`
 * snippet that was duplicated across ~40 templates.  Call `showAjaxErrorModal(xhr)`
 * from the error callback of any `$.ajax` request.  The function walks the JSON
 * body looking for `error` / `errors` / `detail` keys (DRF conventions) and
 * falls back to a generic "status X" message if none are present.
 *
 * Requires: jQuery, globally-available `escapeHtml` (from xss-helpers.js).
 */

/* global escapeHtml */
/* exported showAjaxErrorModal */

function showAjaxErrorModal(xhr) {
    const errorKeys = ['error', 'errors', 'detail'];
    let found = false;

    try {
        const body = xhr.responseJSON;
        if (body) {
            for (const key of errorKeys) {
                if (key in body) {
                    const value = body[key];
                    if (key === 'errors' && value && typeof value === 'object') {
                        let html = '';
                        for (const fieldName in value) {
                            const fieldErrors = value[fieldName];
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
                            html += '- ' + escapeHtml(sub) + ': ' + escapeHtml(fieldErrors[sub]) + '<br>';
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
            + escapeHtml(String(xhr.statusText || '')) + '`<br>'
            + 'Please email: <a class="underline" href="mailto:contact@speleodb.org">contact@speleodb.org</a>';
        if (typeof console !== 'undefined' && console.error) {
            console.error(fallback, exception.message);
        }
        $('#modal_error_txt').html(fallback);
    } finally {
        $('#modal_error').css('display', 'flex');
    }
}
