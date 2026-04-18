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
 *   });
 *
 * Requires: jQuery, FormModals, showAjaxErrorModal.
 */

/* global FormModals, showAjaxErrorModal */
/* exported attachEntityCrudForm */

function attachEntityCrudForm(options) {
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

    $('#' + submitBtnId).click(function (e) {
        e.preventDefault();

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
                FormModals.showSuccess(successMessage);
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
                showAjaxErrorModal(xhr);
            },
        });
        return false;
    });
}
