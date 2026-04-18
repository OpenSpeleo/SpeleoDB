/**
 * Shared helpers for the project lock / unlock buttons on
 * `project/mutex_history.html`.
 *
 * Usage:
 *   attachMutexLock({
 *       lockUrl:   "{% url 'api:v2:project-acquire' id=project.id %}",
 *       unlockUrl: "{% url 'api:v2:project-release' id=project.id %}",
 *   });
 *
 * - `.btn_unlock` click -> POST unlockUrl, reload on success
 * - `#btn_lock_project` click -> POST lockUrl, reload on success
 *
 * Either URL can be omitted if the template does not render the
 * corresponding button.
 *
 * Requires: jQuery, FormModals, showAjaxErrorModal.
 */

/* global FormModals, showAjaxErrorModal */
/* exported attachMutexLock */

function _postMutexAction(url, successMessage, reloadDelayMs) {
    var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();
    $('#error_div').hide();
    $('#success_div').hide();

    $.ajax({
        url: url,
        method: 'POST',
        contentType: 'application/json; charset=utf-8',
        cache: false,
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-CSRFToken', csrftoken);
            return true;
        },
        success: function () {
            FormModals.showSuccess(successMessage);
            window.setTimeout(function () { window.location.reload(); }, reloadDelayMs);
        },
        error: function (xhr) {
            showAjaxErrorModal(xhr);
        },
    });
}

function attachMutexLock(options) {
    var lockUrl = options.lockUrl;
    var unlockUrl = options.unlockUrl;
    var lockMessage = options.lockMessage || 'The project has been locked for edition.';
    var unlockMessage = options.unlockMessage || 'The project has been unlocked for edition.';
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;

    FormModals.bindAutoDismiss();

    if (unlockUrl) {
        $('.btn_unlock').click(function () {
            _postMutexAction(unlockUrl, unlockMessage, reloadDelayMs);
            return false;
        });
    }

    if (lockUrl) {
        $('#btn_lock_project').click(function () {
            _postMutexAction(lockUrl, lockMessage, reloadDelayMs);
            return false;
        });
    }
}
