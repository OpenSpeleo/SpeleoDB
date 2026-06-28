import { afterWindowLoad } from '../readiness.js';
import { showAjaxErrorModal } from '../../frontend_private/static/private/js/forms/ajax_errors.js';
import { attachFleetEntityCrud } from '../../frontend_private/static/private/js/forms/fleet_entity_crud.js';
import {
    cylinderCollectPayload,
    cylinderPopulateForEdit,
    cylinderResetForCreate,
    sensorCollectPayload,
    sensorPopulateForEdit,
    sensorResetForCreate,
} from '../../frontend_private/static/private/js/forms/fleet_modal_helpers.js';
import { attachFleetSettingsForm } from '../../frontend_private/static/private/js/forms/fleet_settings_form.js';
import { attachFleetWatchlist } from '../../frontend_private/static/private/js/forms/fleet_watchlist.js';

function route(name, ...args) {
    const builder = window.Urls?.[name];
    if (typeof builder !== 'function') throw new Error(`Missing Django URL route: ${name}`);
    return builder(...args);
}

function entityOptions(context) {
    const cylinder = context.kind === 'cylinder';
    const noun = cylinder ? 'cylinder' : 'sensor';
    return {
        entityLabel: noun,
        modalSelector: `#${noun}_modal`,
        deleteModalSelector: context.mode === 'details' ? `#delete_${noun}_modal` : undefined,
        editButtonSelector: `.edit-${noun}-btn`,
        deleteButtonSelector: context.mode === 'details' ? `.delete-${noun}-btn` : undefined,
        deleteIdInputSelector: context.mode === 'details' ? `#delete_${noun}_id` : undefined,
        addButtonSelector: context.mode === 'details' ? `#add_${noun}_btn, #add_first_${noun}_btn` : undefined,
        saveButtonSelector: `#${noun}_modal_save`,
        cancelSelectors: `#${noun}_modal_cancel, #${noun}_modal_close_x`,
        deleteCancelSelectors: context.mode === 'details' ? '#delete_modal_cancel, #delete_modal_close_x' : undefined,
        confirmDeleteSelector: context.mode === 'details' ? '#delete_modal_confirm' : undefined,
        modalTitleSelector: `#${noun}_modal_title`,
        addTitle: cylinder ? 'Add Cylinder' : 'Add Sensor',
        editTitle: cylinder ? 'Edit Cylinder' : 'Edit Sensor',
        listEndpoint: context.listEndpoint,
        detailEndpoint: id => route(context.detailRoute, id),
        resetForCreate: cylinder ? cylinderResetForCreate : sensorResetForCreate,
        populateForEdit: cylinder ? cylinderPopulateForEdit : sensorPopulateForEdit,
        collectPayload: cylinder ? cylinderCollectPayload : sensorCollectPayload,
    };
}

export async function init(context) {
    await afterWindowLoad();

    if (context.tableSelector && context.hasRows !== false) {
        const dataTableOptions = context.orderAscending
            ? { order: [[0, 'asc']] }
            : {};
        if (context.hasWrite) dataTableOptions.columnDefs = [{ targets: -1, orderable: false }];
        attachFleetWatchlist({
            tableSelector: context.tableSelector,
            dataTableOptions,
            formSelector: context.showDaysFilter ? '#watchlist_form' : undefined,
            exportBtnSelector: context.showDaysFilter ? '#btn_export_excel' : undefined,
            exportUrlBuilder: context.exportRoute
                ? days => `${route(context.exportRoute, context.fleetId)}?days=${days}`
                : undefined,
        });
    }

    if (context.settingsEndpoint) {
        attachFleetSettingsForm({
            endpoint: context.settingsEndpoint,
            successMessage: context.settingsMessage,
        });
    }

    if (context.entityCrud) attachFleetEntityCrud(entityOptions(context));

    if (context.kind === 'sensor' && context.mode === 'details') {
        $(document).on('click', '.toggle-sensor-btn', function () {
            const sensorId = $(this).data('sensor-id');
            $.ajax({
                url: route('api:v2:sensor-toggle-functional', sensorId),
                method: 'PATCH',
                headers: { 'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val() },
                success() { window.location.reload(); },
                error: showAjaxErrorModal,
            });
        });
    }
}
