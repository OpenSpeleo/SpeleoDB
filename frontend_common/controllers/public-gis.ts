import type { PublicGISContext } from '../../ts-types/controllers/public-gis.ts';
import { configureRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';

export async function init(context: PublicGISContext) {
    configureRuntimeContext(context);
    const { initPublicGISViewer } = await import(
        '../../frontend_public/static/ts/gis_view_main.ts'
    );
    await initPublicGISViewer();
}
