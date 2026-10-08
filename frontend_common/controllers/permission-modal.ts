import type { PermissionModalContext } from '../../ts-types/controllers/permission-modal.ts';
import { afterWindowLoad } from '../readiness.ts';
import { attachPermissionModal } from '../../frontend_private/static/private/ts/forms/permission_modal.ts';

export async function init(context: PermissionModalContext) {
    await afterWindowLoad();
    attachPermissionModal(context);
}
