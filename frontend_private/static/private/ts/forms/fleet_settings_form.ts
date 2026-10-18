import { scheduleFormReload } from './lifecycle.ts';
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
 *       save: updateCylinderFleet,
 *       successMessage: 'The cylinder fleet has been updated.',
 *   });
 *
 * Requires: jQuery, FormModals, showApiErrorModal.
 */

import { showApiErrorModal } from './api_errors.ts';
import { FormModals } from './modals.ts';

export function attachFleetSettingsForm(options: FleetSettingsOptions) {
    var save = options.save;
    var successMessage = options.successMessage || 'Fleet updated.';
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;
    var submitBtnSelector = options.submitBtnSelector || '#btn_submit';
    var nameSelector = options.nameSelector || '#name';
    var descSelector = options.descSelector || '#description';

    if (typeof save !== 'function') { throw new Error('attachFleetSettingsForm: save is required'); }

    $(submitBtnSelector).click(function (e) {
        e.preventDefault();

        var name = ($(nameSelector).val() as string).trim();
        var description = ($(descSelector).val() as string).trim();

        if (!name) {
            FormModals.showError('Fleet name is required.');
            return false;
        }

        void save({ name, description }).then(function () {
                FormModals.showSuccess(successMessage);
                scheduleFormReload(reloadDelayMs);
        }).catch(showApiErrorModal);
        return false;
    });
}
