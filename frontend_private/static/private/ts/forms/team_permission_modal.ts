import { sendPermissionRequest } from './permission_request.ts';
import { readFormCSRFToken, hideFormStatus, scheduleFormReload } from './lifecycle.ts';
import type { TeamPermissionOptions } from '../../../../../ts-types/domain/forms/permissions.ts';

/**
 * Shared team-permission Add / Edit / Delete modal.
 *
 * Sibling of `permission_modal.ts`, but the primary entity is a team
 * (picked from a static `<select>`) instead of a user (autocomplete).
 * Currently used by `project/team_permissions.html`.
 *
 * Wires:
 *   #btn_open_add_team     -> opens modal in create mode (unlocks #team select)
 *   .btn_open_edit_perm    -> opens modal in edit mode (locks #team select,
 *                             appends option built from `data-team-name`)
 *   #btn_submit_add        -> POST/PUT with client-side validation
 *   .btn_delete_perm       -> DELETE for `data-team`
 *   .btn_close             -> dismiss modal
 *   body click             -> auto-dismiss success / error modals
 *
 * Usage:
 *   attachTeamPermissionModal({
 *       endpoint: "{% url 'api:v2:project-team-permissions-detail' id=project.id %}",
 *       addModalTitle: "Add a Team to the project",
 *       addModalHeader: "What team would you like to add?",
 *       editModalTitle: "How shall we modify this team's access?",
 *       fieldLabel: 'Access Level',
 *   });
 *
 * Requires: jQuery, FormModals, showAjaxErrorModal.
 */

import { showAjaxErrorModal } from './ajax_errors.ts';
import { FormModals } from './modals.ts';

export function attachTeamPermissionModal(options: TeamPermissionOptions) {
    var endpoint = options.endpoint;
    var addModalTitle = options.addModalTitle || 'Add a team';
    var addModalHeader = options.addModalHeader || 'What team would you like to add?';
    var editModalTitle = options.editModalTitle || 'Edit team access';
    var fieldLabel = options.fieldLabel || 'Access Level';
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;

    if (!endpoint) {
        throw new Error('attachTeamPermissionModal: endpoint is required');
    }

    FormModals.bindAutoDismiss();

    function preventInteraction(e: JQuery.TriggeredEvent) { e.preventDefault(); }
    function lockSelect(sel: string) {
        $(sel).addClass('readonly').on('mousedown keydown', preventInteraction);
    }
    function unlockSelect(sel: string) {
        $(sel).removeClass('readonly').off('mousedown keydown', preventInteraction);
    }

    $('.btn_close').click(function () {
        $('#permission_modal').hide();
        return false;
    });

    $(document).on('click', '#btn_open_add_team', function () {
        var form = $<HTMLFormElement>('#permission_form');
        form[0]!.reset();
        form.data('method', 'POST');
        $('#permission_modal_title').text(addModalTitle);
        $('#permission_modal_header').text(addModalHeader);
        $('#permission_modal').css('display', 'flex');
        unlockSelect('#team');
        return false;
    });

    $(document).on('click', '.btn_open_edit_perm', function () {
        var form = $<HTMLFormElement>('#permission_form');
        form[0]!.reset();
        form.data('method', 'PUT');
        $('#permission_modal_title').text(editModalTitle);
        $('#permission_modal_header').text('');
        $('#permission_modal').css('display', 'flex');

        var team_id = $(this).data('team') as string;
        var team_name = $(this).data('team-name') as string;
        var access_level = $(this).data('level') as string;

        // The `#team` <select> normally lists only non-already-assigned teams.
        // For the edit flow we append an option for the currently-assigned team
        // so the user sees what they are editing.
        $('#team').append(new Option(team_name, team_id));
        $('#team').val(team_id);
        $('#level').val(access_level);

        lockSelect('#team');
        return false;
    });

    $('#btn_submit_add').click(function () {
        var csrftoken = readFormCSRFToken();
        var form = $<HTMLFormElement>('#permission_form');
        var formData = new FormData(form[0]);

        hideFormStatus();

        sendPermissionRequest({
            endpoint: endpoint,
            method: form.data('method') as string,
            data: JSON.stringify(Object.fromEntries(formData)),
            csrfToken: csrftoken,
            validate: function () {
                if ($('#team').val() === '') {
                    FormModals.showError('The team is empty!');
                    return false;
                }
                if ($('#level').val() === '') {
                    FormModals.showError('The ' + fieldLabel + ' field is empty!');
                    return false;
                }
                return true;
            },
            success: function () {
                FormModals.showSuccess('Action executed with success!');
                scheduleFormReload(reloadDelayMs);
            },
            error: function (xhr) {
                showAjaxErrorModal(xhr);
            },
        });
        return false;
    });

    $(document).on('click', '.btn_delete_perm', function () {
        var $this = $(this);
        if ($this.hasClass('disabled')) { return false; }
        $this.addClass('disabled');

        var csrftoken = readFormCSRFToken();
        var formData = new FormData();
        formData.append('team', $this.data('team') as string);

        hideFormStatus();

        sendPermissionRequest({
            endpoint: endpoint,
            method: 'DELETE',
            data: JSON.stringify(Object.fromEntries(formData)),
            csrfToken: csrftoken,
            success: function () {
                FormModals.showSuccess('The permission has been deleted successfully.');
                scheduleFormReload(reloadDelayMs);
            },
            error: function (xhr) {
                showAjaxErrorModal(xhr);
                $this.removeClass('disabled');
            },
        });
        return false;
    });
}
