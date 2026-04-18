/**
 * Shared danger-zone delete flow.
 *
 * Replaces the identical inline `<script>` block previously duplicated
 * across 7 danger_zone.html templates (project, experiment, team, gis_view,
 * cylinder_fleet, sensor_fleet, surface_network).
 *
 * Wires:
 *   #btn_delete             -> opens #modal_confirmation
 *   #btn_confirmed_delete   -> DELETE deleteUrl, show success, redirect
 *   body click              -> auto-dismiss all modals
 *
 * Usage:
 *   attachDangerZone({
 *       deleteUrl: "{% url 'api:v2:project-detail' id=project.id %}",
 *       successMessage: "The project has been deleted successfully.",
 *       successRedirect: "{% url 'private:projects' %}",
 *       redirectDelayMs: 2000,  // optional
 *   });
 *
 * Requires: jQuery, FormModals (forms/modals.js), showAjaxErrorModal
 * (forms/ajax_errors.js), and the `{% csrf_token %}` hidden input.
 */

/* global FormModals, showAjaxErrorModal */
/* exported attachDangerZone */

function attachDangerZone(options) {
    var deleteUrl = options.deleteUrl;
    var successMessage = options.successMessage || 'Deleted successfully.';
    var successRedirect = options.successRedirect;
    var redirectDelayMs = typeof options.redirectDelayMs === 'number' ? options.redirectDelayMs : 2000;

    if (!deleteUrl) {
        throw new Error('attachDangerZone: deleteUrl is required');
    }

    FormModals.bindAutoDismiss();

    $('#btn_delete').click(function () {
        FormModals.showConfirmation();
        return false; // prevent default
    });

    $('#btn_confirmed_delete').click(function () {
        var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();

        $('#error_div').hide();
        $('#success_div').hide();
        FormModals.hideConfirmation();

        $.ajax({
            url: deleteUrl,
            method: 'DELETE',
            contentType: 'application/json; charset=utf-8',
            cache: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrftoken);
                return true;
            },
            success: function () {
                FormModals.showSuccess(successMessage);
                if (successRedirect) {
                    window.setTimeout(function () {
                        window.location.href = successRedirect;
                    }, redirectDelayMs);
                }
            },
            error: function (xhr) {
                showAjaxErrorModal(xhr);
            },
        });
        return false; // prevent default
    });
}
