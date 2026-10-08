import type { MutexLockContext } from '../../ts-types/controllers/mutex-lock.ts';
import { afterWindowLoad } from '../readiness.ts';
import { attachMutexLock } from '../../frontend_private/static/private/ts/forms/mutex_lock.ts';

export async function init(context: MutexLockContext) {
    await afterWindowLoad();
    attachMutexLock(context);
}
