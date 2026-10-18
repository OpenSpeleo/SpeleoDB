import { deleteEntity } from '../api/entity-forms.ts';
import type { DangerZoneContext } from '../../ts-types/controllers/danger-zone.ts';
import { attachDangerZone } from '../../frontend_private/static/private/ts/forms/danger_zone.ts';
import { afterWindowLoad } from '../readiness.ts';

export async function init(context: DangerZoneContext) {
    await afterWindowLoad();
    attachDangerZone({ ...context, remove: () => deleteEntity(context.resource, context.entityId) });
}
