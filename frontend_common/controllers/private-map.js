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
}
