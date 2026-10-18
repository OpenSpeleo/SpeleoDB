import { v2ProjectsList, v2ProjectsGeojsonRetrieve, v2UserGisViewsCreate, v2UserGisViewsPartialUpdateWithJson } from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';
import type { GisViewFormContext, GisViewSaved } from '../../ts-types/controllers/gis-view-form.ts';
import type { EntityId } from '../../ts-types/domain/identifiers.ts';
import { afterWindowLoad } from '../readiness.ts';
import { attachGisViewForm } from '../../frontend_private/static/private/ts/forms/gis_view_form.ts';

function route(name: 'private:gis_view_details', value: EntityId) {
    const builder = window.Urls?.[name];
    if (typeof builder !== 'function') throw new Error(`Missing Django URL route: ${name}`);
    return builder(value);
}

export async function init(context: GisViewFormContext) {
    await afterWindowLoad();
    attachGisViewForm<GisViewSaved>({
        ...context,
        loadProjects: () => apiData(v2ProjectsList(webApiOptions())),
        loadCommits: projectId => apiData(v2ProjectsGeojsonRetrieve(projectId, webApiOptions())),
        save: payload => context.viewId
            ? apiData(v2UserGisViewsPartialUpdateWithJson(context.viewId, payload, webApiOptions()))
            : apiData(v2UserGisViewsCreate(payload, webApiOptions())),
        onSuccess: context.redirectRoute
            ? data => { window.location.href = route(context.redirectRoute!, data.id); }
            : undefined,
    });
}
