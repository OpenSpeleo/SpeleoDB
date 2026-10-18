import { scheduleFormReload } from './lifecycle.ts';
import type { FleetEntityOptions } from '../../../../../ts-types/domain/forms/fleet.ts';

/**
 * Shared Add / Edit / Delete modal flow for entities that live under a
 * fleet (cylinders under a cylinder fleet, sensors under a sensor fleet).
 *
 * Also covers the "edit-only" case used by the cylinder watchlist page
 * (which reuses the same modal but never adds).
 *
 * The domain-specific parts (which fields, default values, payload
 * shape and generated operations) are injected as callbacks; modal open/close,
 * and delete-confirm flow are owned by this helper.
 *
 * Usage:
 *   attachFleetEntityCrud({
 *       entityLabel: 'cylinder',
 *       modalSelector: '#cylinder_modal',
 *       deleteModalSelector: '#delete_cylinder_modal',
 *       editButtonSelector: '.edit-cylinder-btn',
 *       deleteButtonSelector: '.delete-cylinder-btn',
 *       deleteIdInputSelector: '#delete_cylinder_id',
 *       addButtonSelector: '#add_cylinder_btn, #add_first_cylinder_btn',
 *       saveButtonSelector: '#cylinder_modal_save',
 *       cancelSelectors: '#cylinder_modal_cancel, #cylinder_modal_close_x',
 *       deleteCancelSelectors: '#delete_modal_cancel, #delete_modal_close_x',
 *       confirmDeleteSelector: '#delete_modal_confirm',
 *       modalTitleSelector: '#cylinder_modal_title',
 *       addTitle: 'Add Cylinder',
 *       editTitle: 'Edit Cylinder',
 *       create: payload => createCylinder(payload),
 *       update: (id, payload) => updateCylinder(id, payload),
 *       remove: id => deleteCylinder(id),
 *       resetForCreate: function () { ... populate defaults ... },
 *       populateForEdit: function ($button) { ... fill modal from data-* ... },
 *       collectPayload: function (isEdit) {
 *           // return the JSON payload, or return null to abort (the
 *           // caller is responsible for having shown a validation modal).
 *           // `isEdit` is true when currentId is set (PUT); false for POST.
 *       },
 *       // Optional - if omitted, Add is disabled (useful for watchlist page).
 *       // When Add is enabled, the add button must exist and `resetForCreate`
 *       // must be provided.
 *   });
 *
 * Requires: jQuery, FormModals, showApiErrorModal.
 */

import { showApiErrorModal } from './api_errors.ts';
import { FormModals } from './modals.ts';

export function attachFleetEntityCrud<Payload>(options: FleetEntityOptions<Payload>) {
    var entityLabel = options.entityLabel || 'entity';
    var modalSelector = options.modalSelector;
    var deleteModalSelector = options.deleteModalSelector;
    var editButtonSelector = options.editButtonSelector;
    var deleteButtonSelector = options.deleteButtonSelector;
    var deleteIdInputSelector = options.deleteIdInputSelector;
    var addButtonSelector = options.addButtonSelector;
    var saveButtonSelector = options.saveButtonSelector;
    var cancelSelectors = options.cancelSelectors;
    var deleteCancelSelectors = options.deleteCancelSelectors;
    var confirmDeleteSelector = options.confirmDeleteSelector;
    var modalTitleSelector = options.modalTitleSelector;
    var addTitle = options.addTitle || 'Add';
    var editTitle = options.editTitle || 'Edit';
    var create = options.create;
    var update = options.update;
    var remove = options.remove;
    var resetForCreate = options.resetForCreate;
    var populateForEdit = options.populateForEdit;
    var collectPayload = options.collectPayload;
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;

    if (!modalSelector) { throw new Error('attachFleetEntityCrud: modalSelector required'); }
    if (!saveButtonSelector) { throw new Error('attachFleetEntityCrud: saveButtonSelector required'); }
    if (typeof update !== 'function') {
        throw new Error('attachFleetEntityCrud: update must be function(id, payload)');
    }
    if (typeof collectPayload !== 'function') {
        throw new Error('attachFleetEntityCrud: collectPayload must be function()');
    }

    var currentId: string | number | null | undefined = null;

    FormModals.bindAutoDismiss();

    function openEntityModal() {
        $(modalSelector!).css('display', 'flex').removeClass('hidden');
    }
    function closeEntityModal() {
        $(modalSelector!).css('display', 'none').addClass('hidden');
    }
    function closeDeleteModal() {
        $(deleteModalSelector!).css('display', 'none').addClass('hidden');
    }

    if (addButtonSelector && typeof resetForCreate === 'function' && create) {
        $(addButtonSelector).click(function () {
            currentId = null;
            if (modalTitleSelector) { $(modalTitleSelector).text(addTitle); }
            resetForCreate!();
            openEntityModal();
        });
    }

    if (editButtonSelector && typeof populateForEdit === 'function') {
        $(document).on('click', editButtonSelector, function () {
            var $btn = $(this as HTMLElement);
            currentId = $btn.data(entityLabel + '-id') as string | number | undefined;
            if (modalTitleSelector) { $(modalTitleSelector).text(editTitle); }
            populateForEdit!($btn);
            openEntityModal();
        });
    }

    if (cancelSelectors) {
        $(cancelSelectors).click(function () { closeEntityModal(); });
    }

    if (deleteCancelSelectors) {
        $(deleteCancelSelectors).click(function () { closeDeleteModal(); });
    }

    $(saveButtonSelector).click(function () {
        var isEdit = Boolean(currentId);
        var payload;
        try {
            payload = collectPayload!(isEdit);
        } catch (err) {
            FormModals.showError(((err as Error | null | undefined) && (err as Error).message) || 'Validation failed.');
            return;
        }
        if (!payload) { return; }  // collectPayload signalled validation failure internally

        if (!isEdit && !create) {
            FormModals.showError('No create operation configured for this action.');
            return;
        }
        const request = isEdit ? update(currentId!, payload) : create!(payload);
        void request.then(function () {
                var verb = isEdit ? 'updated' : 'added';
                FormModals.showSuccess(_capitalize(entityLabel) + ' ' + verb + ' successfully.');
                closeEntityModal();
                scheduleFormReload(reloadDelayMs);
        }).catch(showApiErrorModal);
    });

    if (deleteButtonSelector && deleteIdInputSelector && deleteModalSelector) {
        $(document).on('click', deleteButtonSelector, function () {
            var id = $(this).data(entityLabel + '-id') as string | number;
            $(deleteIdInputSelector!).val(id);
            $(deleteModalSelector!).css('display', 'flex').removeClass('hidden');
        });

        if (confirmDeleteSelector) {
            $(confirmDeleteSelector).click(function () {
                var id = $(deleteIdInputSelector!).val() as string;
                if (!id) { return; }

                if (!remove) return;
                void remove(id).then(function () {
                        FormModals.showSuccess(_capitalize(entityLabel) + ' deleted successfully.');
                        closeDeleteModal();
                        scheduleFormReload(reloadDelayMs);
                }, function (xhr: unknown) {
                        closeDeleteModal();
                        showApiErrorModal(xhr);
                });
            });
        }
    }

    $('#modal_error button, #modal_success button').click(function () {
        $(this).closest('.fixed').fadeOut(200);
    });
}

function _capitalize(s: string) {
    if (!s) { return ''; }
    return s.charAt(0).toUpperCase() + s.slice(1);
}
