import { afterWindowLoad } from '../readiness.js';
import { attachTeamPermissionModal } from '../../frontend_private/static/private/js/forms/team_permission_modal.js';

export async function init(context) {
    await afterWindowLoad();
    attachTeamPermissionModal(context);
}
