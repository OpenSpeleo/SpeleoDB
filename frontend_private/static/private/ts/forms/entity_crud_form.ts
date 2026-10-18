import { hideFormStatus, scheduleFormReload, scheduleFormRedirect } from './lifecycle.ts';
import type { EntityCrudOptions } from '../../../../../ts-types/domain/forms/crud.ts';

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
 *       -> invokes the caller's typed generated-operation callback
 *       -> on success: showSuccess(successMessage) then optional redirect
 *       -> on error:   showApiErrorModal(xhr)
 *
 * Usage:
 *   attachEntityCrudForm({
 *       formId: 'new_team_form',
 *       submit: createTeam,
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
 * Requires: jQuery, FormModals, showApiErrorModal.
 */

import { showApiErrorModal } from './api_errors.ts';
import { FormModals } from './modals.ts';

export function attachEntityCrudForm<Response = unknown>(options: EntityCrudOptions<Response>) {
    var formId = options.formId;
    var submit = options.submit;
    var submitBtnId = options.submitBtnId || 'btn_submit';
    var successMessage = options.successMessage || 'Saved successfully.';
    var successRedirect = options.successRedirect;
    var redirectFromResponse = options.redirectFromResponse;
    var reloadOnSuccess = Boolean(options.reloadOnSuccess);
    var redirectDelayMs = typeof options.redirectDelayMs === 'number' ? options.redirectDelayMs : 2000;
    var beforeSubmit = options.beforeSubmit;
    var onSuccess = options.onSuccess;
    var prepare = options.prepare;  // optional form-value transformation

    if (!formId) {
        throw new Error('attachEntityCrudForm: formId is required');
    }
    if (typeof submit !== 'function') {
        throw new Error('attachEntityCrudForm: submit is required');
    }

    FormModals.bindAutoDismiss();

    var pending = false;
    var submitTarget = options.submitOnForm ? $('#' + formId) : $('#' + submitBtnId);
    submitTarget.on(options.submitOnForm ? 'submit' : 'click', function (e) {
        e.preventDefault();
        if (options.onPendingChange && pending) { return false; }

        hideFormStatus();

        var form = document.getElementById(formId!) as HTMLFormElement | null;
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

        var body = typeof prepare === 'function' ? prepare(payload) : payload;

        pending = true;
        options.onPendingChange?.(true);
        void Promise.resolve().then(() => submit(body)).then(
            function (response) {
                if (options.showSuccessModal !== false) {
                    FormModals.showSuccess(successMessage);
                }
                if (typeof onSuccess === 'function') { onSuccess(response); }
                var target = typeof redirectFromResponse === 'function'
                    ? redirectFromResponse(response)
                    : successRedirect;
                if (target) {
                    scheduleFormRedirect(target, redirectDelayMs);
                } else if (reloadOnSuccess) {
                    scheduleFormReload(redirectDelayMs);
                }
            },
            function (xhr: unknown) {
                if (typeof options.onError === 'function') {
                    options.onError(xhr);
                } else {
                    showApiErrorModal(xhr);
                }
            },
        ).finally(function () {
                pending = false;
                options.onPendingChange?.(false);
        });
        return false;
    });
}
