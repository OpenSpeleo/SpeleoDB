import { attachDangerZone } from '../../frontend_private/static/private/js/forms/danger_zone.js';
import { afterWindowLoad } from '../readiness.js';

export async function init(context) {
    await afterWindowLoad();
    attachDangerZone(context);
}
