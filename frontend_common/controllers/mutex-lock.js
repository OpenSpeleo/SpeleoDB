import { afterWindowLoad } from '../readiness.js';
import { attachMutexLock } from '../../frontend_private/static/private/js/forms/mutex_lock.js';

export async function init(context) {
    await afterWindowLoad();
    attachMutexLock(context);
}
