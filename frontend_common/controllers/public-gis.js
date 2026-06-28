import { configureRuntimeContext } from '../../frontend_private/static/private/js/map_viewer/runtime_context.js';

export async function init(context) {
    configureRuntimeContext(context);
    const { initPublicGISViewer } = await import(
        '../../frontend_public/static/js/gis_view_main.js'
    );
    await initPublicGISViewer();
}
