import type { TeamPermissionContext } from '../../ts-types/controllers/team-permission.ts';
import { afterWindowLoad } from '../readiness.ts';
import { attachTeamPermissionModal } from '../../frontend_private/static/private/ts/forms/team_permission_modal.ts';

export async function init(context: TeamPermissionContext) {
    await afterWindowLoad();
    attachTeamPermissionModal(context);
}
