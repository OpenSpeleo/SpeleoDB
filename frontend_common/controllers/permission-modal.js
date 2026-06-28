import { afterWindowLoad } from '../readiness.js';
import { attachPermissionModal } from '../../frontend_private/static/private/js/forms/permission_modal.js';

export async function init(context) {
    await afterWindowLoad();
    attachPermissionModal(context);
}
