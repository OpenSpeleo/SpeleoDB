/**
 * Shared permission / membership modal flow.
 *
 * Powers the identical Add / Edit / Delete modal on:
 *   - project/user_permissions.html
 *   - experiment/user_permissions.html
 *   - cylinder_fleet/user_permissions.html
 *   - sensor_fleet/user_permissions.html
 *   - surface_network/user_permissions.html
 *   - team/memberships.html  (field name is "role" instead of "level"; CSS
 *     selectors differ - pass `selectors: {...}` to override)
 *
 * All of those duplicated ~150 lines of wiring. With this helper each
 * template reduces to a single `attachPermissionModal({...})` call.
 *
 * Wires (default selector set; override via `selectors` option):
 *   #btn_open_add_user         -> opens modal in create mode (fresh form, POST)
 *   .btn_open_edit_perm        -> opens modal in edit mode (locks user, PUT)
 *   #btn_submit_add            -> fires the request with client-side validation
 *   .btn_delete_perm           -> DELETE for the given `data-user`
 *   .btn_close                 -> dismiss modal
 *   body click                 -> auto-dismiss success / error modals
 *
 * Usage:
 *   attachPermissionModal({
 *       endpoint: "{% url 'api:v2:project-user-permissions-detail' id=project.id %}",
 *       autocompleteUrl: "{% url 'api:v2:user-autocomplete' %}",
 *       addModalTitle: "Add a collaborator to the project",
 *       addModalHeader: "Who would you like to add?",
 *       editModalTitle: "How shall we modify this user's access?",
 *       fieldName: 'level',        // optional, defaults to 'level' ('role' for team memberships)
 *       fieldLabel: 'Access Level',// used in the "field is empty" validation message
 *       selectors: {               // optional overrides for templates that
 *                                  // renamed the DOM hooks
 *           openAddBtn: '#btn_open_add_user',
 *           openEditBtn: '.btn_open_edit_perm',
 *           deleteBtn: '.btn_delete_perm',
 *           modal: '#permission_modal',
 *           modalTitle: '#permission_modal_title',
 *           modalHeader: '#permission_modal_header',
 *           form: '#permission_form',
 *           submitBtn: '#btn_submit_add',
 *           closeBtn: '.btn_close',
 *       },
 *   });
 *
 * Requires: jQuery, FormModals, showAjaxErrorModal, attachUserAutocomplete.
 */

/* global FormModals, showAjaxErrorModal, attachUserAutocomplete */
/* exported attachPermissionModal */

var EMAIL_REGEX = /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;

var DEFAULT_PERMISSION_SELECTORS = {
    openAddBtn: '#btn_open_add_user',
    openEditBtn: '.btn_open_edit_perm',
    deleteBtn: '.btn_delete_perm',
    modal: '#permission_modal',
    modalTitle: '#permission_modal_title',
    modalHeader: '#permission_modal_header',
    form: '#permission_form',
    submitBtn: '#btn_submit_add',
    closeBtn: '.btn_close',
};

function attachPermissionModal(options) {
    var endpoint = options.endpoint;
    var autocompleteUrl = options.autocompleteUrl;
    var addModalTitle = options.addModalTitle || 'Add a collaborator';
    var addModalHeader = options.addModalHeader || 'Who would you like to add?';
    var editModalTitle = options.editModalTitle || 'Edit access';
    var fieldName = options.fieldName || 'level';
    var fieldLabel = options.fieldLabel || 'Access Level';
    var successMessage = options.successMessage || 'Action executed with success!';
    var deleteMessage = options.deleteMessage || 'The permission has been deleted successfully.';
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;

    var sel = Object.assign({}, DEFAULT_PERMISSION_SELECTORS, options.selectors || {});

    if (!endpoint) {
        throw new Error('attachPermissionModal: endpoint is required');
    }
    if (!autocompleteUrl) {
        throw new Error('attachPermissionModal: autocompleteUrl is required');
    }

    FormModals.bindAutoDismiss();

    $(sel.closeBtn).click(function () {
        $(sel.modal).hide();
        return false;
    });

    $(sel.openAddBtn).click(function () {
        var form = $(sel.form);
        if (form.length) { form[0].reset(); }
        form.data('method', 'POST');
        $(sel.modalTitle).text(addModalTitle);
        $(sel.modalHeader).text(addModalHeader);
        $(sel.modal).css('display', 'flex');
        $('#user').prop('readonly', false);
        attachUserAutocomplete($('#user'), $('#user_suggestions'), autocompleteUrl);
        return false;
    });

    $(sel.openEditBtn).click(function () {
        var form = $(sel.form);
        if (form.length) { form[0].reset(); }
        form.data('method', 'PUT');
        $(sel.modalTitle).text(editModalTitle);
        $(sel.modalHeader).text('');
        $(sel.modal).css('display', 'flex');
        $('#user').val($(this).data('user')).prop('readonly', true);
        $('#' + fieldName).val($(this).data(fieldName));
        return false;
    });

    $(sel.submitBtn).click(function () {
        var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();
        var form = $(sel.form);
        var formData = new FormData(form[0]);

        $('#error_div').hide();
        $('#success_div').hide();

        $.ajax({
            url: endpoint,
            method: form.data('method'),
            data: JSON.stringify(Object.fromEntries(formData)),
            contentType: 'application/json; charset=utf-8',
            cache: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrftoken);

                if (!EMAIL_REGEX.test($('#user').val()) || $('#user').val() === '') {
                    FormModals.showError('The Email Address is not valid!');
                    return false;
                }
                if ($('#' + fieldName).val() === '') {
                    FormModals.showError('The ' + fieldLabel + ' field is empty!');
                    return false;
                }
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
        return false;
    });

    $(sel.deleteBtn).click(function () {
        var $this = $(this);
        if ($this.hasClass('disabled')) { return false; }
        $this.addClass('disabled');

        var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();
        var formData = new FormData();
        formData.append('user', $this.data('user'));

        $('#error_div').hide();
        $('#success_div').hide();

        $.ajax({
            url: endpoint,
            method: 'DELETE',
            data: JSON.stringify(Object.fromEntries(formData)),
            contentType: 'application/json; charset=utf-8',
            cache: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrftoken);
                return true;
            },
            success: function () {
                FormModals.showSuccess(deleteMessage);
                window.setTimeout(function () { window.location.reload(); }, reloadDelayMs);
            },
            error: function (xhr) {
                showAjaxErrorModal(xhr);
                $this.removeClass('disabled');
            },
        });
        return false;
    });
}
