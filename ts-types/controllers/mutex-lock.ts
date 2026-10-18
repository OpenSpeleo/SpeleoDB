import type { MutexLockOptions } from '../domain/forms/crud.ts';
export interface MutexLockContext extends Omit<MutexLockOptions, 'acquire' | 'release'> { projectId: string; canAcquire?: boolean; canRelease?: boolean }
