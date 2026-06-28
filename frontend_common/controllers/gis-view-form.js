import { afterWindowLoad } from '../readiness.js';
import { attachGisViewForm } from '../../frontend_private/static/private/js/forms/gis_view_form.js';

function route(name, value) {
    const builder = window.Urls?.[name];
    if (typeof builder !== 'function') throw new Error(`Missing Django URL route: ${name}`);
    return builder(value);
}

export async function init(context) {
    await afterWindowLoad();
    attachGisViewForm({
        ...context,
        commitsEndpointBuilder: projectId => route('api:v2:project-geojson-commits', projectId),
        onSuccess: context.redirectRoute
            ? data => { window.location.href = route(context.redirectRoute, data.id); }
            : undefined,
    });
}
