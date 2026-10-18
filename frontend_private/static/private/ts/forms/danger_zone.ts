import { hideFormStatus, scheduleFormRedirect } from './lifecycle.ts';
import type { DangerZoneOptions } from '../../../../../ts-types/domain/forms/crud.ts';

/**
 * Shared danger-zone delete flow.
 *
 * Replaces the identical inline `<script>` block previously duplicated
 * across 7 danger_zone.html templates (project, experiment, team, gis_view,
 * cylinder_fleet, sensor_fleet, surface_network).
 *
 * Wires:
 *   #btn_delete             -> opens #modal_confirmation
 *   #btn_confirmed_delete   -> the generated delete operation, show success, redirect
 *   body click              -> auto-dismiss all modals
 *
 * Usage:
 *   attachDangerZone({
 *       remove: deleteProject,
 *       successMessage: "The project has been deleted successfully.",
 *       successRedirect: "{% url 'private:projects' %}",
 *       redirectDelayMs: 2000,  // optional
 *   });
 *
 * Requires: jQuery, FormModals (forms/modals.ts), showApiErrorModal
 * (forms/api_errors.ts), and the `{% csrf_token %}` hidden input.
 */

import { showApiErrorModal } from './api_errors.ts';
import { FormModals } from './modals.ts';

export function attachDangerZone(options: DangerZoneOptions) {
    var remove = options.remove;
    var successMessage = options.successMessage || 'Deleted successfully.';
    var successRedirect = options.successRedirect;
    var redirectDelayMs = typeof options.redirectDelayMs === 'number' ? options.redirectDelayMs : 2000;

    if (typeof remove !== 'function') {
        throw new Error('attachDangerZone: remove is required');
    }

    FormModals.bindAutoDismiss();

    $('#btn_delete').click(function () {
        FormModals.showConfirmation();
        return false; // prevent default
    });

    $('#btn_confirmed_delete').click(function () {
        hideFormStatus();
        FormModals.hideConfirmation();

        void remove().then(function () {
                FormModals.showSuccess(successMessage);
                if (successRedirect) {
                    scheduleFormRedirect(successRedirect, redirectDelayMs);
                }
        }).catch(showApiErrorModal);
        return false; // prevent default
    });
}
