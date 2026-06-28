import { DataImport } from '../../frontend_private/static/private/js/data_import.js';
import { configureRuntimeContext } from '../../frontend_private/static/private/js/map_viewer/runtime_context.js';

export async function init(context) {
    configureRuntimeContext(context);
    const { initPrivateMapViewer } = await import(
        '../../frontend_private/static/private/js/map_viewer/main.js'
    );

    const cylinderIcon = document.getElementById('cylinder-modal-icon');
    if (cylinderIcon && context.icons?.cylinderOrange) {
        cylinderIcon.src = context.icons.cylinderOrange;
    }

    await initPrivateMapViewer();

    DataImport.init(context.csrfToken);
    $('#import-data-button').on('click', () => DataImport.showModal());
    $(document).on('click', '[data-import-action]', function () {
        const actions = {
            'browse-gpx': () => document.getElementById('gpx-file-input').click(),
            'browse-kml': () => document.getElementById('kml-file-input').click(),
            'clear-gpx': () => DataImport.clearGPXFile(),
            'clear-kml': () => DataImport.clearKMLFile(),
            hide: () => DataImport.hideModal(),
            'hide-warning': () => DataImport.hideWarningModal(),
            tab: () => DataImport.switchTab($(this).data('import-tab')),
            'upload-gpx': () => DataImport.uploadGPX(),
            'upload-kml': () => DataImport.uploadKML(),
        };
        actions[$(this).data('import-action')]?.();
    });
}
