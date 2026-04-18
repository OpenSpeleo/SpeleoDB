/**
 * Shared handler for the public allauth auth forms (login, signup,
 * password_reset, password_reset_from_key).
 *
 * Unlike the private forms, these pages do NOT use the `modal_success`
 * / `modal_error` partials - they render messages in `#error_div` /
 * `#success_div` inline text blocks. The messaging format that allauth
 * headless returns under error is either `{error: "..."}` or
 * `{errors: [{message: "..."}]}`.
 *
 * Usage:
 *   attachAuthForm({
 *       formId: 'login_form',
 *       endpoint: "{% url 'headless:browser:account:login' %}",
 *       // optional custom validators that return an error string or null.
 *       validators: [
 *           (payload) => payload.email ? null : "Email is required.",
 *       ],
 *       // optional on-success handler (default: show a generic message)
 *       onSuccess: () => { window.location.href = "{% url 'private:user_dashboard' %}"; },
 *       // optional: treat a particular status code as success (e.g. 401
 *       // for signup, which redirects to email verification)
 *       treat401AsSuccess: false,
 *       successMessage: 'Success!',
 *       // allauth 401 sometimes carries flow info - login.html special-cases
 *       // it to differentiate "inactive account" from "verify email". If you
 *       // need that behaviour, pass a custom errorHandler that returns the
 *       // string to render in `#error_div`.
 *       errorHandler: (xhr) => string | null,
 *   });
 *
 * Requires: jQuery.
 */

/* exported attachAuthForm, validateEmail */

var EMAIL_REGEX_AUTH = /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;

function validateEmail(email) {
    return EMAIL_REGEX_AUTH.test(email);
}

function _defaultErrorMessage(xhr) {
    var body = xhr.responseJSON;
    if (!body) { return 'An error occurred. Please try again.'; }
    if ('error' in body) { return body.error; }
    if ('errors' in body && Array.isArray(body.errors) && body.errors.length > 0) {
        return body.errors[0].message || 'An error occurred.';
    }
    return 'An error occurred. Please try again.';
}

function attachAuthForm(options) {
    var formId = options.formId;
    var endpoint = options.endpoint;
    var validators = options.validators || [];
    var onSuccess = options.onSuccess;
    var successMessage = options.successMessage || 'Success!';
    var treat401AsSuccess = Boolean(options.treat401AsSuccess);
    var errorHandler = options.errorHandler;
    var submitBtnId = options.submitBtnId || 'btn_submit';
    var beforeAjax = options.beforeAjax;  // optional payload mutator; receives (payload, formData)

    if (!formId) { throw new Error('attachAuthForm: formId is required'); }
    if (!endpoint) { throw new Error('attachAuthForm: endpoint is required'); }

    function showError(msg) {
        $('#error_div').text(msg).show();
    }

    function showSuccess(msg) {
        $('#success_div').text(msg).show();
    }

    $('#' + submitBtnId).click(function () {
        var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();
        var form = document.getElementById(formId);
        var formData = new FormData(form);

        $('#error_div').hide();
        $('#success_div').hide();

        var payload = Object.fromEntries(formData);

        // beforeAjax runs first so it can short-circuit (e.g. anti-robot
        // modals) or strip fields from the outgoing payload before the
        // regular validators run.
        if (typeof beforeAjax === 'function') {
            var cancelled = beforeAjax(payload, formData);
            if (cancelled === false) { return false; }
        }

        // Run synchronous validators before sending.
        for (var i = 0; i < validators.length; i++) {
            var err = validators[i](payload, formData);
            if (err) { showError(err); return false; }
        }

        $.ajax({
            url: endpoint,
            method: 'POST',
            data: JSON.stringify(Object.fromEntries(formData)),
            contentType: 'application/json; charset=utf-8',
            cache: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrftoken);
                return true;
            },
            success: function () {
                if (typeof onSuccess === 'function') {
                    onSuccess();
                } else {
                    showSuccess(successMessage);
                }
            },
            error: function (xhr) {
                if (treat401AsSuccess && xhr.status === 401) {
                    showSuccess(successMessage);
                    return;
                }
                var msg = null;
                if (typeof errorHandler === 'function') {
                    msg = errorHandler(xhr);
                }
                if (msg === null || typeof msg === 'undefined') {
                    try { msg = _defaultErrorMessage(xhr); }
                    catch (e) { msg = 'There has been an error ...'; }
                }
                showError(msg);
            },
        });
        return false;
    });
}
