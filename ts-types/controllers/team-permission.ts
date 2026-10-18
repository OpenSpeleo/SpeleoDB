import type { TeamPermissionOptions } from '../domain/forms/permissions.ts';
export interface TeamPermissionContext extends Omit<TeamPermissionOptions, 'operations'> { projectId: string }
