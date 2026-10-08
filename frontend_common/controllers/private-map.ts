import type { PrivateMapContext } from '../../ts-types/controllers/private-map.ts';
import { DataImport } from '../../frontend_private/static/private/ts/data_import.ts';
import { configureRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';

export async function init(context: PrivateMapContext) {
    const runtimeContext = configureRuntimeContext(context);
    const { initPrivateMapViewer } = await import(
        '../../frontend_private/static/private/ts/map_viewer/main.ts'
    );

    const cylinderIcon = document.getElementById('cylinder-modal-icon') as HTMLImageElement | null;
    if (cylinderIcon) {
        cylinderIcon.src = runtimeContext.icons.cylinderOrange;
    }

    await initPrivateMapViewer();

    DataImport.init(context.csrfToken);
}
