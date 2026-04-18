/**
 * Shared "Fleet name + description" save flow for cylinder and sensor
 * fleet detail pages.
 *
 * The fleet detail pages render a form with `#name` + `#description`
 * inputs and a `#btn_submit` button. Both PUT to their respective
 * `*-fleet-detail` endpoint.
 *
 * Usage:
 *   attachFleetSettingsForm({
 *       endpoint: Urls['api:v2:cylinder-fleet-detail']('{{ cylinder_fleet.id }}'),
 *       successMessage: 'The cylinder fleet has been updated.',
 *   });
 *
 * Requires: jQuery, FormModals, showAjaxErrorModal.
 */

/* global FormModals, showAjaxErrorModal */
/* exported attachFleetSettingsForm */

function attachFleetSettingsForm(options) {
    var endpoint = options.endpoint;
    var successMessage = options.successMessage || 'Fleet updated.';
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;
    var submitBtnSelector = options.submitBtnSelector || '#btn_submit';
    var nameSelector = options.nameSelector || '#name';
    var descSelector = options.descSelector || '#description';

    if (!endpoint) { throw new Error('attachFleetSettingsForm: endpoint is required'); }

    $(submitBtnSelector).click(function (e) {
        e.preventDefault();

        var name = $(nameSelector).val().trim();
        var description = $(descSelector).val().trim();

        if (!name) {
            FormModals.showError('Fleet name is required.');
            return false;
        }

        var csrftoken = $('[name=csrfmiddlewaretoken]').val();

        $.ajax({
            url: endpoint,
            method: 'PUT',
            data: JSON.stringify({ name: name, description: description }),
            contentType: 'application/json; charset=utf-8',
            headers: { 'X-CSRFToken': csrftoken },
            success: function () {
                FormModals.showSuccess(successMessage);
                window.setTimeout(function () { window.location.reload(); }, reloadDelayMs);
            },
            error: function (xhr) {
                showAjaxErrorModal(xhr);
            },
        });
        return false;
    });
}
