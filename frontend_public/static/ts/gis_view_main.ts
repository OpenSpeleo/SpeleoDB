import { v2GisOgcViewGeojsonRetrieve } from '@speleodb/api';
import { apiData, webApiOptions } from '../../../frontend_common/api/client.ts';
import { getRuntimeContext } from '../../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';
import { initReadOnlyViewer } from '../../../frontend_private/static/private/ts/map_viewer/read_only_viewer.ts';
import { Utils } from '../../../frontend_private/static/private/ts/map_viewer/utils.ts';

// Global entry point for Public GIS View Map Viewer
export async function initPublicGISViewer() {
    const context = getRuntimeContext();

    // Validate context for public view mode
    if (context.viewMode !== 'public' || !context.gisToken) {
        console.error('❌ Invalid GIS View context - viewMode or gisToken missing');
        Utils.showNotification('error', 'Invalid GIS View configuration');
        return;
    }

    await initReadOnlyViewer(context, async () =>
        apiData(v2GisOgcViewGeojsonRetrieve(context.gisToken!, undefined, webApiOptions())));
}
