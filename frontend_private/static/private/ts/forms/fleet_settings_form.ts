import { readFormCSRFToken, scheduleFormReload } from './lifecycle.ts';
import type { FleetSettingsOptions } from '../../../../../ts-types/domain/forms/fleet.ts';

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

import { showAjaxErrorModal } from './ajax_errors.ts';
import { FormModals } from './modals.ts';

export function attachFleetSettingsForm(options: FleetSettingsOptions) {
    var endpoint = options.endpoint;
    var successMessage = options.successMessage || 'Fleet updated.';
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;
    var submitBtnSelector = options.submitBtnSelector || '#btn_submit';
    var nameSelector = options.nameSelector || '#name';
    var descSelector = options.descSelector || '#description';

    if (!endpoint) { throw new Error('attachFleetSettingsForm: endpoint is required'); }

    $(submitBtnSelector).click(function (e) {
        e.preventDefault();

        var name = ($(nameSelector).val() as string).trim();
        var description = ($(descSelector).val() as string).trim();

        if (!name) {
            FormModals.showError('Fleet name is required.');
            return false;
        }

        var csrftoken = readFormCSRFToken('[name=csrfmiddlewaretoken]');

        $.ajax({
            url: endpoint,
            method: 'PUT',
            data: JSON.stringify({ name: name, description: description }),
            contentType: 'application/json; charset=utf-8',
            headers: { 'X-CSRFToken': csrftoken },
            success: function () {
                FormModals.showSuccess(successMessage);
                scheduleFormReload(reloadDelayMs);
            },
            error: function (xhr) {
                showAjaxErrorModal(xhr);
            },
        });
        return false;
    });
}
