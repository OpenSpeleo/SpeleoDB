import type { GisViewFormContext, GisViewSaved } from '../../ts-types/controllers/gis-view-form.ts';
import type { EntityId } from '../../ts-types/domain/identifiers.ts';
import { afterWindowLoad } from '../readiness.ts';
import { attachGisViewForm } from '../../frontend_private/static/private/ts/forms/gis_view_form.ts';

function route(name: 'private:gis_view_details' | 'api:v2:project-geojson-commits', value: EntityId) {
    const builder = window.Urls?.[name];
    if (typeof builder !== 'function') throw new Error(`Missing Django URL route: ${name}`);
    return builder(value);
}

export async function init(context: GisViewFormContext) {
    await afterWindowLoad();
    attachGisViewForm<GisViewSaved>({
        ...context,
        commitsEndpointBuilder: projectId => route('api:v2:project-geojson-commits', projectId),
        onSuccess: context.redirectRoute
            ? data => { window.location.href = route(context.redirectRoute!, data.id); }
            : undefined,
    });
}
