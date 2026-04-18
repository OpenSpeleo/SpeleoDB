/**
 * Shared CRUD scaffold for "named + colored + owned" list pages:
 *   - `pages/station_tags.html`
 *   - `pages/gps_tracks.html`
 *
 * Both pages have the same skeleton: fetch a list of entities, render
 * them into a desktop table + mobile cards, open an edit modal from a
 * row button, submit the modal back to a detail endpoint, and handle a
 * separate delete-confirm modal.
 *
 * The *rendering* (which columns, how colors are shown, etc.) and the
 * *modal fields* differ, so those are supplied as callbacks. Everything
 * else is shared.
 *
 * Usage:
 *   var list = attachTaggedEntityList({
 *       listEndpoint: "{% url 'api:v2:station-tags' %}",
 *       detailEndpointBuilder: function (id) {
 *           return Urls['api:v2:station-tag-detail'](id);
 *       },
 *       editMethod: 'PUT',
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
 * Returns an object with a `reload()` method that reruns the fetch.
 * Useful for external events (e.g. GPX import refreshes the tracks list).
 *
 * Requires: jQuery, FormModals, showAjaxErrorModal.
 */

/* global FormModals, showAjaxErrorModal */
/* exported attachTaggedEntityList */

function _tteGetCSRFToken() {
    return $('input[name^=csrfmiddlewaretoken]').val() || '';
}

function attachTaggedEntityList(options) {
    var listEndpoint = options.listEndpoint;
    var detailEndpointBuilder = options.detailEndpointBuilder;
    var editMethod = options.editMethod || 'PUT';
    var createMethod = options.createMethod || 'POST';

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

    if (!listEndpoint) { throw new Error('attachTaggedEntityList: listEndpoint is required'); }
    if (typeof detailEndpointBuilder !== 'function') {
        throw new Error('attachTaggedEntityList: detailEndpointBuilder must be function(id)');
    }
    if (typeof renderList !== 'function') {
        throw new Error('attachTaggedEntityList: renderList is required');
    }
    if (typeof collectEditPayload !== 'function') {
        throw new Error('attachTaggedEntityList: collectEditPayload is required');
    }

    var allEntities = [];

    FormModals.bindAutoDismiss();

    function load() {
        $.ajax({
            url: listEndpoint,
            method: 'GET',
            dataType: 'json',
            success: function (response) {
                if (Array.isArray(response)) {
                    allEntities = response;
                    renderList(allEntities, api);
                } else {
                    FormModals.showError(loadFailedMessage);
                }
            },
            error: function () {
                FormModals.showError(loadFailedMessage);
            },
        });
    }

    function openEditModal(entityId) {
        var entity = allEntities.find(function (e) { return e.id === entityId; });
        if (!entity) { return; }
        if (typeof openEditModalForEntity === 'function') {
            openEditModalForEntity(entity);
        }
        if (editModalTitleSelector) { $(editModalTitleSelector).text(editModalTitle); }
        if (createSubmitLabelSelector) { $(createSubmitLabelSelector).text(editSubmitLabel); }
        $(editModalSelector).css('display', 'flex').removeClass('hidden');
    }

    function openDeleteModal(entityId) {
        var entity = allEntities.find(function (e) { return e.id === entityId; });
        if (!entity) { return; }
        if (typeof openDeleteModalForEntity === 'function') {
            openDeleteModalForEntity(entity);
        }
        $(deleteIdInputSelector).val(entity.id);
        $(deleteModalSelector).css('display', 'flex').removeClass('hidden');
    }

    function closeEditModal() {
        $(editModalSelector).css('display', 'none').addClass('hidden');
    }
    function closeDeleteModal() {
        $(deleteModalSelector).css('display', 'none').addClass('hidden');
    }

    if (createBtnSelector && typeof resetEditModal === 'function') {
        $(createBtnSelector).click(function () {
            if (editFormSelector && $(editFormSelector)[0]) { $(editFormSelector)[0].reset(); }
            if (editIdInputSelector) { $(editIdInputSelector).val(''); }
            if (editModalTitleSelector) { $(editModalTitleSelector).text(createModalTitle); }
            if (createSubmitLabelSelector) { $(createSubmitLabelSelector).text(createSubmitLabel); }
            resetEditModal();
            $(editModalSelector).css('display', 'flex').removeClass('hidden');
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
            var entityId = editIdInputSelector ? $(editIdInputSelector).val() : null;
            var payload = collectEditPayload();
            if (!payload) { return false; }

            var url = entityId ? detailEndpointBuilder(entityId) : listEndpoint;
            var method = entityId ? editMethod : createMethod;

            $.ajax({
                url: url,
                method: method,
                data: JSON.stringify(payload),
                contentType: 'application/json; charset=utf-8',
                beforeSend: function (xhr) { xhr.setRequestHeader('X-CSRFToken', _tteGetCSRFToken()); },
                success: function () {
                    FormModals.showSuccess(
                        _tteCapitalize(entityLabel) + (entityId ? ' updated' : ' created') + ' successfully!'
                    );
                    closeEditModal();
                    window.setTimeout(load, 500);
                },
                error: function (xhr) {
                    showAjaxErrorModal(xhr);
                },
            });
            return false;
        });
    }

    if (confirmDeleteSelector) {
        $(confirmDeleteSelector).click(function () {
            var entityId = deleteIdInputSelector ? $(deleteIdInputSelector).val() : null;
            if (!entityId) { return; }
            $.ajax({
                url: detailEndpointBuilder(entityId),
                method: 'DELETE',
                beforeSend: function (xhr) { xhr.setRequestHeader('X-CSRFToken', _tteGetCSRFToken()); },
                success: function () {
                    FormModals.showSuccess(_tteCapitalize(entityLabel) + ' deleted successfully!');
                    closeDeleteModal();
                    window.setTimeout(load, 500);
                },
                error: function (xhr) {
                    showAjaxErrorModal(xhr);
                },
            });
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

function _tteCapitalize(s) {
    if (!s) { return ''; }
    return s.charAt(0).toUpperCase() + s.slice(1);
}
