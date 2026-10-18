import * as sdk from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';
import type { FleetContext } from '../../ts-types/controllers/fleet.ts';
import type { FleetEntityOptions } from '../../ts-types/domain/forms/fleet.ts';
import type { EntityId } from '../../ts-types/domain/identifiers.ts';
import { afterWindowLoad } from '../readiness.ts';
import { showApiErrorModal } from '../../frontend_private/static/private/ts/forms/api_errors.ts';
import { attachFleetEntityCrud } from '../../frontend_private/static/private/ts/forms/fleet_entity_crud.ts';
import {
    cylinderCollectPayload,
    cylinderPopulateForEdit,
    cylinderResetForCreate,
    sensorCollectPayload,
    sensorPopulateForEdit,
    sensorResetForCreate,
} from '../../frontend_private/static/private/ts/forms/fleet_modal_helpers.ts';
import { attachFleetSettingsForm } from '../../frontend_private/static/private/ts/forms/fleet_settings_form.ts';
import { attachFleetWatchlist } from '../../frontend_private/static/private/ts/forms/fleet_watchlist.ts';

function entityOptions(context: FleetContext) {
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


    };
}

export async function init(context: FleetContext) {
    await afterWindowLoad();

    if (context.tableSelector && context.hasRows !== false) {
        const dataTableOptions: DataTableOptions = context.orderAscending
            ? { order: [[0, 'asc']] }
            : {};
        if (context.hasWrite) dataTableOptions.columnDefs = [{ targets: -1, orderable: false }];
        attachFleetWatchlist({
            tableSelector: context.tableSelector,
            dataTableOptions,
            formSelector: context.showDaysFilter ? '#watchlist_form' : undefined,
            exportBtnSelector: context.showDaysFilter ? '#btn_export_excel' : undefined,
            exportUrlBuilder: context.showDaysFilter ? days => context.kind === 'cylinder'
                ? sdk.getV2CylinderFleetsCylindersWatchlistExportRetrieveUrl(String(context.fleetId), { days: Number(days) })
                : sdk.getV2SensorFleetsSensorsWatchlistExportRetrieveUrl(String(context.fleetId), { days: Number(days) })
                : undefined,
        });
    }

    if (context.settings) {
        attachFleetSettingsForm({
            save: payload => context.kind === 'cylinder'
                ? apiData(sdk.v2CylinderFleetsUpdateWithJson(String(context.fleetId), payload, webApiOptions()))
                : apiData(sdk.v2SensorFleetsUpdateWithJson(String(context.fleetId), payload, webApiOptions())),
            successMessage: context.settingsMessage,
        });
    }

    if (context.entityCrud) {
        const shared = entityOptions(context);
        if (context.kind === 'cylinder') {
            attachFleetEntityCrud({ ...shared,
                resetForCreate: cylinderResetForCreate, populateForEdit: cylinderPopulateForEdit, collectPayload: cylinderCollectPayload,
                create: payload => apiData(sdk.v2CylinderFleetsCylindersCreateWithJson(String(context.fleetId), payload, webApiOptions())),
                update: (id, payload) => apiData(sdk.v2CylindersUpdateWithJson(String(id), payload, webApiOptions())),
                remove: id => apiData(sdk.v2CylindersDestroy(String(id), webApiOptions())),
            });
        } else {
            attachFleetEntityCrud({ ...shared,
                resetForCreate: sensorResetForCreate, populateForEdit: sensorPopulateForEdit, collectPayload: sensorCollectPayload,
                create: payload => apiData(sdk.v2SensorFleetsSensorsCreateWithJson(String(context.fleetId), payload, webApiOptions())),
                update: (id, payload) => apiData(sdk.v2SensorsUpdateWithJson(String(id), payload, webApiOptions())),
                remove: id => apiData(sdk.v2SensorsDestroy(String(id), webApiOptions())),
            });
        }
    }

    if (context.kind === 'sensor' && context.mode === 'details') {
        $(document).on('click', '.toggle-sensor-btn', function () {
            const sensorId = $(this as HTMLElement).data('sensor-id') as EntityId;
            apiData(sdk.v2SensorsToggleFunctionalPartialUpdate(String(sensorId), webApiOptions()))
                .then(() => window.location.reload()).catch(showApiErrorModal);
        });
    }
}
