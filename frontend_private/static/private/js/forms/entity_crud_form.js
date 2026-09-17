/**
 * Shared "new entity" / "edit details" JSON-CRUD form handler.
 *
 * Replaces the near-identical inline `$('#btn_submit').click(...)` blocks
 * duplicated across many simple templates (project/new, team/new, team/details,
 * surface_network/new, surface_network/details, user/preferences, user/password, ...).
 *
 * Wires:
 *   body click              -> auto-dismiss modal_success / modal_error
 *   #btn_submit (or options.submitBtnId)
 *       -> serializes the form as JSON (FormData -> Object.fromEntries)
 *       -> optional `beforeSubmit(payload)` hook; return false to cancel
 *       -> fires options.method (default POST) to options.endpoint
 *       -> on success: showSuccess(successMessage) then optional redirect
 *       -> on error:   showAjaxErrorModal(xhr)
 *
 * Usage:
 *   attachEntityCrudForm({
 *       formId: 'new_team_form',
 *       endpoint: "{% url 'api:v2:teams' %}",
 *       method: 'POST',
 *       successMessage: 'The team has been created.',
 *       successRedirect: "{% url 'private:teams' %}",
 *       // optional:
 *       submitBtnId: 'btn_submit',
 *       beforeSubmit: function(payload) { return true; },
 *       onSuccess: function(response) {},
 *       redirectDelayMs: 2000,
 *       redirectFromResponse: function(response) { return url; }, // dynamic
 *       submitOnForm: true, // handle form submission, including the Enter key
 *       onPendingChange: function(pending) {}, // optional busy state + duplicate guard
 *       onError: function(xhr) {}, // optional inline error presentation
 *       showSuccessModal: false, // caller presents success through onSuccess
 *   });
 *
 * Requires: jQuery, FormModals, showAjaxErrorModal.
 */

import { showAjaxErrorModal } from './ajax_errors.js';
import { FormModals } from './modals.js';

export function attachEntityCrudForm(options) {
    var formId = options.formId;
    var endpoint = options.endpoint;
    var method = (options.method || 'POST').toUpperCase();
    var submitBtnId = options.submitBtnId || 'btn_submit';
    var successMessage = options.successMessage || 'Saved successfully.';
    var successRedirect = options.successRedirect;
    var redirectFromResponse = options.redirectFromResponse;
    var reloadOnSuccess = Boolean(options.reloadOnSuccess);
    var redirectDelayMs = typeof options.redirectDelayMs === 'number' ? options.redirectDelayMs : 2000;
    var beforeSubmit = options.beforeSubmit;
    var onSuccess = options.onSuccess;
    var serialize = options.serialize;  // optional (payload) => stringified body

    if (!formId) {
        throw new Error('attachEntityCrudForm: formId is required');
    }
    if (!endpoint) {
        throw new Error('attachEntityCrudForm: endpoint is required');
    }

    FormModals.bindAutoDismiss();

    var pending = false;
    var submitTarget = options.submitOnForm ? $('#' + formId) : $('#' + submitBtnId);
    submitTarget.on(options.submitOnForm ? 'submit' : 'click', function (e) {
        e.preventDefault();
        if (options.onPendingChange && pending) { return false; }

        $('#error_div').hide();
        $('#success_div').hide();

        var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();
        var form = document.getElementById(formId);
        if (!form) {
            if (typeof console !== 'undefined' && console.error) {
                console.error('attachEntityCrudForm: form not found: #' + formId);
            }
            return false;
        }
        var formData = new FormData(form);
        var payload = Object.fromEntries(formData);

        if (typeof beforeSubmit === 'function') {
            if (beforeSubmit(payload) === false) { return false; }
        }

        var body = typeof serialize === 'function'
            ? serialize(payload)
            : JSON.stringify(payload);

        pending = true;
        options.onPendingChange?.(true);
        $.ajax({
            url: endpoint,
            method: method,
            data: body,
            contentType: 'application/json; charset=utf-8',
            cache: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrftoken);
                return true;
            },
            success: function (response) {
                if (options.showSuccessModal !== false) {
                    FormModals.showSuccess(successMessage);
                }
                if (typeof onSuccess === 'function') { onSuccess(response); }
                var target = typeof redirectFromResponse === 'function'
                    ? redirectFromResponse(response)
                    : successRedirect;
                if (target) {
                    window.setTimeout(function () {
                        window.location.href = target;
                    }, redirectDelayMs);
                } else if (reloadOnSuccess) {
                    window.setTimeout(function () {
                        window.location.reload();
                    }, redirectDelayMs);
                }
            },
            error: function (xhr) {
                if (typeof options.onError === 'function') {
                    options.onError(xhr);
                } else {
                    showAjaxErrorModal(xhr);
                }
            },
            complete: function () {
                pending = false;
                options.onPendingChange?.(false);
            },
        });
        return false;
    });
}
