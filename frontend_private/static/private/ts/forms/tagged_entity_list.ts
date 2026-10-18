import type { TaggedEntity, TaggedListApi, TaggedListOptions } from '../../../../../ts-types/domain/forms/tagged-list.ts';

/**
 * Shared CRUD scaffold for "named + colored + owned" list pages:
 *   - `pages/station_tags.html`
 *   - `pages/gps_tracks.html`
 *   - `pages/gis_layers.html`
 *
 * These pages share the same list skeleton: fetch entities and render them
 * into a desktop table + mobile cards. Mutation modals are optional so a
 * listing can send users to the standard settings workflow instead.
 *
 * The *rendering* (which columns, how colors are shown, etc.) and the
 * *modal fields* differ, so those are supplied as callbacks. Everything
 * else is shared.
 *
 * Usage:
 *   var list = attachTaggedEntityList({
 *       list: listTags,
 *       create: createTag,
 *       update: updateTag,
 *       remove: deleteTag,
 *
 *       renderList: function (entities) { ... populate table + cards ... },
 *       openEditModalForEntity: function (entity) { ... set fields ... },
 *       resetEditModal: function () { ... for the Create flow ... },
 *       collectEditPayload: function () {
 *           return { name: ..., color: ... } or null if invalid
 *       },
 *
 *       editFormSelector: '#edit-tag-form',
 *       editIdInputSelector: '#edit-tag-id',
 *       editModalSelector: '#edit-tag-modal',
 *       editModalTitleSelector: '#edit-modal-title',
 *       createModalTitle: 'Create New Tag',
 *       editModalTitle: 'Edit Tag',
 *       createBtnSelector: '#btn-create-tag',    // optional (omit for edit-only lists)
 *       closeEditModalSelectors: '.btn-close-edit-modal',
 *       createSubmitLabelSelector: '#edit-submit-text',
 *       createSubmitLabel: 'Create Tag',
 *       editSubmitLabel: 'Save Changes',
 *
 *       deleteModalSelector: '#delete-tag-modal',
 *       deleteIdInputSelector: '#delete-tag-id',
 *       confirmDeleteSelector: '#btn-confirm-delete',
 *       closeDeleteModalSelectors: '.btn-close-delete-modal',
 *       openDeleteModalForEntity: function (entity) { ... fill info ... },
 *
 *       entityLabel: 'tag',
 *       entityLabelPlural: 'tags',
 *       loadFailedMessage: 'Error loading tags',
 *   });
 *
 * Edit and delete options are optional. List-only pages can use the same loader
 * and returned `reload()` method without providing modal configuration.
 *
 * Requires: jQuery, FormModals, showApiErrorModal.
 */

import { showApiErrorModal } from './api_errors.ts';
import { FormModals } from './modals.ts';

export function attachTaggedEntityList<Entity extends TaggedEntity = TaggedEntity, Payload = unknown>(options: TaggedListOptions<Entity, Payload>): TaggedListApi {
    var list = options.list;
    var create = options.create;
    var update = options.update;
    var remove = options.remove;

    var renderList = options.renderList;
    var openEditModalForEntity = options.openEditModalForEntity;
    var resetEditModal = options.resetEditModal;
    var collectEditPayload = options.collectEditPayload;
    var openDeleteModalForEntity = options.openDeleteModalForEntity;

    var editFormSelector = options.editFormSelector;
    var editIdInputSelector = options.editIdInputSelector;
    var editModalSelector = options.editModalSelector;
    var editModalTitleSelector = options.editModalTitleSelector;
    var createModalTitle = options.createModalTitle || 'Create';
    var editModalTitle = options.editModalTitle || 'Edit';
    var createBtnSelector = options.createBtnSelector;
    var closeEditModalSelectors = options.closeEditModalSelectors;
    var createSubmitLabelSelector = options.createSubmitLabelSelector;
    var createSubmitLabel = options.createSubmitLabel || 'Create';
    var editSubmitLabel = options.editSubmitLabel || 'Save Changes';

    var deleteModalSelector = options.deleteModalSelector;
    var deleteIdInputSelector = options.deleteIdInputSelector;
    var confirmDeleteSelector = options.confirmDeleteSelector;
    var closeDeleteModalSelectors = options.closeDeleteModalSelectors;

    var entityLabel = options.entityLabel || 'item';
    var loadFailedMessage = options.loadFailedMessage || ('Failed to load ' + entityLabel + 's');

    if (typeof list !== 'function') { throw new Error('attachTaggedEntityList: list is required'); }
    if (editFormSelector && typeof update !== 'function') {
        throw new Error('attachTaggedEntityList: update is required for editing');
    }
    if (confirmDeleteSelector && typeof remove !== 'function') {
        throw new Error('attachTaggedEntityList: remove is required for deletion');
    }
    if (typeof renderList !== 'function') {
        throw new Error('attachTaggedEntityList: renderList is required');
    }
    if (editFormSelector && typeof collectEditPayload !== 'function') {
        throw new Error('attachTaggedEntityList: collectEditPayload is required');
    }

    var allEntities: Entity[] = [];

    FormModals.bindAutoDismiss();

    function load() {
        void list().then(entities => {
            allEntities = entities;
            renderList!(allEntities, api);
        }).catch(() => FormModals.showError(loadFailedMessage));
    }

    function openEditModal(entityId: string | number) {
        var entity = allEntities.find(function (e) { return e.id === entityId; });
        if (!entity) { return; }
        if (typeof openEditModalForEntity === 'function') {
            openEditModalForEntity(entity);
        }
        if (editModalTitleSelector) { $(editModalTitleSelector).text(editModalTitle); }
        if (createSubmitLabelSelector) { $(createSubmitLabelSelector).text(editSubmitLabel); }
        $(editModalSelector!).css('display', 'flex').removeClass('hidden');
    }

    function openDeleteModal(entityId: string | number) {
        var entity = allEntities.find(function (e) { return e.id === entityId; });
        if (!entity) { return; }
        if (typeof openDeleteModalForEntity === 'function') {
            openDeleteModalForEntity(entity);
        }
        $(deleteIdInputSelector!).val(entity.id);
        $(deleteModalSelector!).css('display', 'flex').removeClass('hidden');
    }

    function closeEditModal() {
        $(editModalSelector!).css('display', 'none').addClass('hidden');
    }
    function closeDeleteModal() {
        $(deleteModalSelector!).css('display', 'none').addClass('hidden');
    }

    if (createBtnSelector && typeof resetEditModal === 'function') {
        $(createBtnSelector).click(function () {
            if (editFormSelector && $(editFormSelector)[0]) { ($<HTMLFormElement>(editFormSelector)[0]!).reset(); }
            if (editIdInputSelector) { $(editIdInputSelector).val(''); }
            if (editModalTitleSelector) { $(editModalTitleSelector).text(createModalTitle); }
            if (createSubmitLabelSelector) { $(createSubmitLabelSelector).text(createSubmitLabel); }
            resetEditModal!();
            $(editModalSelector!).css('display', 'flex').removeClass('hidden');
            return false;
        });
    }

    if (closeEditModalSelectors) {
        $(document).on('click', closeEditModalSelectors, function () { closeEditModal(); });
    }
    if (closeDeleteModalSelectors) {
        $(document).on('click', closeDeleteModalSelectors, function () { closeDeleteModal(); });
    }

    if (editFormSelector) {
        $(editFormSelector).submit(function (e) {
            e.preventDefault();
            var entityId = editIdInputSelector ? $(editIdInputSelector).val() as string : null;
            var payload = collectEditPayload!();
            if (!payload) { return false; }

            if (!entityId && !create) return false;
            const request = entityId ? update!(entityId, payload) : create!(payload);
            void request.then(function () {
                    FormModals.showSuccess(
                        _tteCapitalize(entityLabel) + (entityId ? ' updated' : ' created') + ' successfully!'
                    );
                    closeEditModal();
                    window.setTimeout(load, 500);
            }).catch(showApiErrorModal);
            return false;
        });
    }

    if (confirmDeleteSelector) {
        $(confirmDeleteSelector).click(function () {
            var entityId = deleteIdInputSelector ? $(deleteIdInputSelector).val() as string : null;
            if (!entityId) { return; }
            void remove!(entityId).then(function () {
                    FormModals.showSuccess(_tteCapitalize(entityLabel) + ' deleted successfully!');
                    closeDeleteModal();
                    window.setTimeout(load, 500);
            }).catch(showApiErrorModal);
        });
    }

    var api = {
        reload: load,
        openEditModal: openEditModal,
        openDeleteModal: openDeleteModal,
    };

    load();

    return api;
}

function _tteCapitalize(s: string) {
    if (!s) { return ''; }
    return s.charAt(0).toUpperCase() + s.slice(1);
}
