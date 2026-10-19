import { v2ProjectsAcquireCreate, v2ProjectsReleaseCreateWithJson } from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';
import type { MutexLockContext } from '../../ts-types/controllers/mutex-lock.ts';
import { afterWindowLoad } from '../readiness.ts';
import { attachMutexLock } from '../../frontend_private/static/private/ts/forms/mutex_lock.ts';

export async function init(context: MutexLockContext) {
    await afterWindowLoad();
    attachMutexLock({ ...context,
        acquire: context.canAcquire ? () => apiData(v2ProjectsAcquireCreate(context.projectId, undefined, webApiOptions())) : undefined,
        release: context.canRelease ? () => apiData(v2ProjectsReleaseCreateWithJson(context.projectId, {}, undefined, webApiOptions())) : undefined,
    });
}
